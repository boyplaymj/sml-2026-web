// sml-trip-itinerary — 行程部落格系統 API（見 tools/trip-itinerary/DESIGN.md v0.2）
//
// 公開端點（無認證，GET）:
//   GET /trips              → 公開行程列表（僅 visibility=public，摘要欄位）
//   GET /trips/{id}         → 單篇公開版（白名單重組、遞迴略過 private item、不吐 note/hash）
//   GET /trips/{id} + header 'X-Trip-Key: <明文>'
//                           → key 雜湊比對 privateKeyHash，符合回私密完整版（含 note/private item）
//                             draft 無有效 key 一律 404（與不存在不可區分）
//
// 後台端點（POST，body={action,...}，需 Firebase ID token；實測於 P4）:
//   adminList | saveTrip | deleteTrip | patchTrip
//
const https = require('https');
const crypto = require('crypto');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const {
  DynamoDBDocumentClient, QueryCommand, PutCommand, DeleteCommand, GetCommand, UpdateCommand
} = require('@aws-sdk/lib-dynamodb');

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: process.env.AWS_REGION || 'ap-southeast-1' }));
const TABLE = process.env.TABLE || 'sml-trip-itineraries';
const GSI = 'type-updatedAt-index';

const FIREBASE_PROJECT = process.env.FIREBASE_PROJECT || 'sml2026newscore';
const ADMIN_DOC_URL = `https://firestore.googleapis.com/v1/projects/${FIREBASE_PROJECT}/databases/(default)/documents/config/gameAdmins`;
const FALLBACK_EMAILS = (process.env.ALLOWED_EMAILS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Trip-Key',
  'Content-Type': 'application/json; charset=utf-8'
};
const reply = (code, obj, extra = {}) => ({ statusCode: code, headers: { ...CORS, ...extra }, body: JSON.stringify(obj) });
const NOSTORE = { 'Cache-Control': 'no-store' };

// ── key 雜湊 & 常數時間比對 ──────────────────────────────────
const hashKey = (plain) => 'sha256:' + crypto.createHash('sha256').update(String(plain)).digest('hex');
function keyMatches (plain, storedHash) {
  if (!plain || !storedHash) return false;
  const a = Buffer.from(hashKey(plain));
  const b = Buffer.from(String(storedHash));
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

// ── 公開序列化：白名單重組（非刪欄位）。遞迴略過 private item，永不吐 note/hash ──
function toPublic (t) {
  return {
    id: t.id, slug: t.slug, title: t.title, subtitle: t.subtitle,
    region: t.region, tags: t.tags || [], cover: t.cover,
    updatedAt: t.updatedAt,
    days: (t.days || []).map(d => ({
      no: d.no, date: d.date, wd: d.wd, theme: d.theme,
      items: (d.items || []).filter(it => !it.private).map(it => ({
        time: it.time || '', ttl: it.ttl, desc: it.desc || '', tag: it.tag || ''
      }))
    }))
  };
}
// 摘要（列表用）
const toSummary = (t) => ({
  id: t.id, slug: t.slug, title: t.title, subtitle: t.subtitle,
  region: t.region, tags: t.tags || [], cover: t.cover,
  days: (t.days || []).length, updatedAt: t.updatedAt
});
// 私密完整版：全含（note/private item）但去掉內部 hash
function toPrivate (t) {
  const { privateKeyHash, ...rest } = t;
  return rest;
}

// ── Firebase ID token 驗證（RS256，Google securetoken 公鑰；沿用 sml-random-events）──
let certCache = { at: 0, keys: {} };
function getCerts () {
  return new Promise((resolve, reject) => {
    if (Date.now() - certCache.at < 3600e3 && Object.keys(certCache.keys).length) return resolve(certCache.keys);
    https.get('https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com', res => {
      let d = ''; res.on('data', c => (d += c)); res.on('end', () => {
        try { certCache = { at: Date.now(), keys: JSON.parse(d) }; resolve(certCache.keys); } catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}
const b64urlJson = (s) => JSON.parse(Buffer.from(s.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'));
function httpGetJson (url) {
  return new Promise((resolve, reject) => {
    https.get(url, res => { let d = ''; res.on('data', c => (d += c)); res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } }); }).on('error', reject);
  });
}
let allowCache = { at: 0, emails: [] };
async function getAllowlist () {
  if (Date.now() - allowCache.at < 300e3 && allowCache.emails.length) return allowCache.emails;
  try {
    const doc = await httpGetJson(ADMIN_DOC_URL);
    const vals = doc?.fields?.emails?.arrayValue?.values || [];
    const emails = vals.map(v => String(v.stringValue || '').toLowerCase()).filter(Boolean);
    if (emails.length) allowCache = { at: Date.now(), emails };
  } catch (e) { /* 保留舊快取 */ }
  return allowCache.emails.length ? allowCache.emails : FALLBACK_EMAILS;
}
async function verifyIdToken (token) {
  if (!token) throw new Error('no token');
  const [h, p, sig] = token.split('.');
  if (!h || !p || !sig) throw new Error('malformed token');
  const header = b64urlJson(h), payload = b64urlJson(p);
  const now = Math.floor(Date.now() / 1000);
  if (payload.aud !== FIREBASE_PROJECT) throw new Error('bad aud');
  if (payload.iss !== `https://securetoken.google.com/${FIREBASE_PROJECT}`) throw new Error('bad iss');
  if (payload.exp < now) throw new Error('expired');
  if (!payload.email || payload.email_verified !== true) throw new Error('no verified email');
  const certs = await getCerts();
  const pem = certs[header.kid];
  if (!pem) throw new Error('unknown kid');
  const v = crypto.createVerify('RSA-SHA256'); v.update(`${h}.${p}`);
  if (!v.verify(pem, Buffer.from(sig.replace(/-/g, '+').replace(/_/g, '/'), 'base64'))) throw new Error('bad signature');
  return payload;
}
async function requireAdmin (event) {
  const auth = event.headers?.authorization || event.headers?.Authorization || '';
  const token = auth.replace(/^Bearer\s+/i, '');
  const payload = await verifyIdToken(token);
  const allow = await getAllowlist();
  if (!allow.includes(String(payload.email).toLowerCase())) throw new Error('not in allowlist');
  return payload;
}

// ── DDB ──────────────────────────────────────────────────────
const getTrip = async (id) => (await ddb.send(new GetCommand({ TableName: TABLE, Key: { id } }))).Item;
async function listAll () {
  const r = await ddb.send(new QueryCommand({
    TableName: TABLE, IndexName: GSI,
    KeyConditionExpression: '#t = :t', ExpressionAttributeNames: { '#t': 'type' },
    ExpressionAttributeValues: { ':t': 'trip' }, ScanIndexForward: false
  }));
  return r.Items || [];
}
const nowIso = () => new Date().toISOString().replace(/\.\d+Z$/, 'Z');

// ── router ───────────────────────────────────────────────────
exports.handler = async (event) => {
  const method = event.requestContext?.http?.method || event.httpMethod || 'GET';
  const rawPath = event.rawPath || event.path || '/';
  const path = rawPath.replace(/\/+$/, '') || '/';
  if (method === 'OPTIONS') return reply(200, {});

  try {
    // ---------- 公開讀 ----------
    if (method === 'GET' && path === '/trips') {
      const items = (await listAll()).filter(t => t.visibility === 'public');
      return reply(200, { trips: items.map(toSummary) });
    }
    const m = path.match(/^\/trips\/([A-Za-z0-9_-]+)$/);
    if (method === 'GET' && m) {
      const id = m[1];
      const t = await getTrip(id);
      const tripKey = event.headers?.['x-trip-key'] || event.headers?.['X-Trip-Key'];
      const validKey = t && keyMatches(tripKey, t.privateKeyHash);
      if (!t) return reply(404, { error: 'not found' });
      if (validKey) return reply(200, { trip: toPrivate(t) }, NOSTORE);        // 私密完整版
      if (t.visibility === 'draft') return reply(404, { error: 'not found' });  // 草稿無有效 key = 不存在
      return reply(200, { trip: toPublic(t) });                                 // 公開版
    }

    // ---------- 後台（需認證；P4 配管理頁實測）----------
    if (method === 'POST' && (path === '/admin' || path === '/admin/trips')) {
      let admin;
      try { admin = await requireAdmin(event); }
      catch (e) { return reply(401, { error: 'unauthorized', detail: e.message }); }
      const body = JSON.parse(event.body || '{}');
      const action = body.action;

      if (action === 'adminList') {
        return reply(200, { trips: (await listAll()) });  // 後台看全部含草稿與 hash
      }
      if (action === 'saveTrip') {
        const t = body.trip || {};
        if (!t.id) return reply(400, { error: 'missing id' });
        if (!/^[A-Za-z0-9_-]+$/.test(t.id)) return reply(400, { error: 'invalid id：需符合 [A-Za-z0-9_-]（與公開路由一致）' });
        if (t.slug && !/^[A-Za-z0-9_-]+$/.test(t.slug)) return reply(400, { error: 'invalid slug' });
        const prev = await getTrip(t.id);
        let plainKeyOnce = null;
        // 沿用既有 hash；若全新且無 hash，產一把明文 key（僅回傳一次）
        let privateKeyHash = prev?.privateKeyHash || t.privateKeyHash;
        if (!privateKeyHash) { plainKeyOnce = crypto.randomBytes(16).toString('hex'); privateKeyHash = hashKey(plainKeyOnce); }
        const item = {
          id: t.id, type: 'trip', slug: t.slug || t.id,
          title: t.title || '', subtitle: t.subtitle || '',
          region: t.region || '', tags: Array.isArray(t.tags) ? t.tags : [],
          cover: t.cover || '', visibility: t.visibility === 'public' ? 'public' : 'draft',
          privateKeyHash, days: Array.isArray(t.days) ? t.days : [],
          createdAt: prev?.createdAt || nowIso(), updatedAt: nowIso()
        };
        await ddb.send(new PutCommand({ TableName: TABLE, Item: item }));
        // 明文 key 是 secret，回應與私密讀一致加 no-store
        return reply(200, { ok: true, id: item.id, ...(plainKeyOnce ? { privateKey: plainKeyOnce } : {}) }, plainKeyOnce ? NOSTORE : {});
      }
      if (action === 'patchTrip') {
        const { id, visibility } = body;
        if (!id) return reply(400, { error: 'missing id' });
        const exprs = ['updatedAt = :u']; const names = {}; const vals = { ':u': nowIso() };
        if (visibility === 'public' || visibility === 'draft') { exprs.push('#v = :v'); names['#v'] = 'visibility'; vals[':v'] = visibility; }
        try {
          await ddb.send(new UpdateCommand({
            TableName: TABLE, Key: { id },
            UpdateExpression: 'SET ' + exprs.join(', '),
            ConditionExpression: 'attribute_exists(id)',   // 不存在 → 不建殘缺 item
            ...(Object.keys(names).length ? { ExpressionAttributeNames: names } : {}),
            ExpressionAttributeValues: vals
          }));
        } catch (e) {
          if (e.name === 'ConditionalCheckFailedException') return reply(404, { error: 'not found' });
          throw e;
        }
        return reply(200, { ok: true });
      }
      if (action === 'deleteTrip') {
        if (!body.id) return reply(400, { error: 'missing id' });
        try {
          await ddb.send(new DeleteCommand({
            TableName: TABLE, Key: { id: body.id },
            ConditionExpression: 'attribute_exists(id)'
          }));
        } catch (e) {
          if (e.name === 'ConditionalCheckFailedException') return reply(404, { error: 'not found' });
          throw e;
        }
        return reply(200, { ok: true });
      }
      return reply(400, { error: 'unknown action' });
    }

    return reply(404, { error: 'route not found', path, method });
  } catch (e) {
    console.error(e);
    return reply(500, { error: 'internal', detail: e.message });
  }
};
