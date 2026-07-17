// sml-train-tycoon-admin — 火車大亨後台設定 API。
// 前端(甜甜遊戲館)Firebase Google 登入 → 帶 ID token 呼叫；驗 token(sml2026newscore)+ gameAdmins 白名單。
// 資料全在 DynamoDB train-tycoon-config，PK=section，SK=state(draft/published)。
// 改寫自 sml-mahjong-tycoon（同 section+state / draft+published 模型），僅換 SECTIONS + TABLE_NAME。
//
// POST body { action, ... }，header Authorization: Bearer <firebaseIdToken>
//   listConfig                  → { sections:{ [section]:{draft,published,version,updatedAt,updatedBy} } }
//   saveSection {section,data}   → 覆寫該 section 的 draft
//   publishConfig {section?}     → draft 複製到 published，published.version + 1
//   revertDraft {section}        → published 複製回 draft
const https = require('https');
const crypto = require('crypto');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const {
  DynamoDBDocumentClient, GetCommand, PutCommand
} = require('@aws-sdk/lib-dynamodb');

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: process.env.AWS_REGION || 'ap-southeast-1' }));
const TABLE = process.env.TABLE_NAME || 'train-tycoon-config';
const SECTIONS = ['catalogs', 'destinations', 'balance'];
const STATES = ['draft', 'published'];

const FIREBASE_PROJECT = process.env.FIREBASE_PROJECT || 'sml2026newscore';
const ADMIN_DOC_URL = `https://firestore.googleapis.com/v1/projects/${FIREBASE_PROJECT}/databases/(default)/documents/config/gameAdmins`;
const FALLBACK_EMAILS = (process.env.ALLOWED_EMAILS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type,Authorization',
  'Content-Type': 'application/json; charset=utf-8'
};
const reply = (code, obj) => ({ statusCode: code, headers: CORS, body: JSON.stringify(obj) });

function httpGetJson (url) {
  return new Promise((resolve, reject) => {
    https.get(url, res => {
      let d = '';
      res.on('data', c => (d += c));
      res.on('end', () => {
        try { resolve(JSON.parse(d)); } catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}

// ── Firebase ID token 驗證(RS256, Google securetoken 公鑰) ──
let certCache = { at: 0, keys: {} };
async function getCerts () {
  if (Date.now() - certCache.at < 3600e3 && Object.keys(certCache.keys).length) return certCache.keys;
  const keys = await httpGetJson('https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com');
  certCache = { at: Date.now(), keys };
  return keys;
}

const b64urlJson = s => JSON.parse(Buffer.from(s.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'));
async function verifyIdToken (token) {
  if (!token) throw new Error('no token');
  const [h, p, sig] = token.split('.');
  if (!h || !p || !sig) throw new Error('malformed token');
  const header = b64urlJson(h), payload = b64urlJson(p), now = Math.floor(Date.now() / 1000);
  if (payload.aud !== FIREBASE_PROJECT) throw new Error('bad aud');
  if (payload.iss !== `https://securetoken.google.com/${FIREBASE_PROJECT}`) throw new Error('bad iss');
  if (payload.exp < now) throw new Error('expired');
  if (!payload.email || payload.email_verified === false) throw new Error('no verified email');
  const pem = (await getCerts())[header.kid];
  if (!pem) throw new Error('unknown kid');
  const v = crypto.createVerify('RSA-SHA256');
  v.update(`${h}.${p}`);
  if (!v.verify(pem, Buffer.from(sig.replace(/-/g, '+').replace(/_/g, '/'), 'base64'))) throw new Error('bad signature');
  return payload;
}

// ── 工作人員白名單：同步遊戲館 config/gameAdmins(快取 5 分鐘) ──
let allowCache = { at: 0, emails: [] };
async function getAllowlist () {
  if (Date.now() - allowCache.at < 5 * 60 * 1000 && allowCache.emails.length) return allowCache.emails;
  try {
    const j = await httpGetJson(ADMIN_DOC_URL);
    const vals = j?.fields?.emails?.arrayValue?.values || [];
    const emails = vals.map(v => String(v.stringValue || '').toLowerCase()).filter(Boolean);
    if (emails.length) allowCache = { at: Date.now(), emails };
  } catch (e) {}
  return allowCache.emails.length ? allowCache.emails : FALLBACK_EMAILS;
}

function assertSection (section) {
  if (!SECTIONS.includes(section)) throw new Error('bad section: ' + section);
}

async function getItem (section, state) {
  const r = await ddb.send(new GetCommand({ TableName: TABLE, Key: { section, state } }));
  return r.Item || null;
}

async function putItem (item) {
  await ddb.send(new PutCommand({ TableName: TABLE, Item: item }));
}

function publicItem (draft, published) {
  return {
    draft: draft?.data ?? null,
    published: published?.data ?? null,
    version: Number(published?.version || 0),
    updatedAt: draft?.updatedAt || published?.updatedAt || null,
    updatedBy: draft?.updatedBy || published?.updatedBy || null
  };
}

async function listConfig () {
  const sections = {};
  await Promise.all(SECTIONS.map(async section => {
    const [draft, published] = await Promise.all(STATES.map(state => getItem(section, state)));
    sections[section] = publicItem(draft, published);
  }));
  return sections;
}

exports.handler = async (event) => {
  if (event.requestContext?.http?.method === 'OPTIONS' || event.httpMethod === 'OPTIONS') return reply(200, {});

  let user;
  try {
    const auth = event.headers?.authorization || event.headers?.Authorization || '';
    user = await verifyIdToken(auth.replace(/^Bearer\s+/i, ''));
  } catch (e) {
    return reply(401, { ok: false, error: 'auth failed: ' + e.message });
  }

  const allow = await getAllowlist();
  if (!allow.includes(String(user.email).toLowerCase())) {
    return reply(403, { ok: false, error: 'not staff: ' + user.email });
  }

  let body;
  try { body = typeof event.body === 'string' ? JSON.parse(event.body || '{}') : (event.body || {}); } catch { return reply(400, { ok: false, error: 'bad json' }); }
  const action = body.action;
  const now = new Date().toISOString();
  const updatedBy = String(user.email || '').toLowerCase();

  try {
    if (action === 'listConfig') {
      return reply(200, { ok: true, sections: await listConfig() });
    }

    if (action === 'saveSection') {
      const section = String(body.section || '');
      assertSection(section);
      if (body.data == null || typeof body.data !== 'object') return reply(400, { ok: false, error: 'bad data' });
      await putItem({ section, state: 'draft', data: body.data, updatedAt: now, updatedBy });
      return reply(200, { ok: true, updatedAt: now });
    }

    if (action === 'publishConfig') {
      const targets = body.section ? [String(body.section)] : SECTIONS;
      const versions = {};
      for (const section of targets) {
        assertSection(section);
        const draft = await getItem(section, 'draft');
        if (!draft) {
          const published = await getItem(section, 'published');
          versions[section] = Number(published?.version || 0);
          continue;
        }
        const published = await getItem(section, 'published');
        const version = Number(published?.version || 0) + 1;
        await putItem({ section, state: 'published', data: draft.data, version, updatedAt: now, updatedBy });
        versions[section] = version;
      }
      return reply(200, { ok: true, versions });
    }

    if (action === 'revertDraft') {
      const section = String(body.section || '');
      assertSection(section);
      const published = await getItem(section, 'published');
      if (!published) return reply(404, { ok: false, error: 'no published config' });
      await putItem({ section, state: 'draft', data: published.data, updatedAt: now, updatedBy });
      return reply(200, { ok: true });
    }

    return reply(400, { ok: false, error: 'unknown action: ' + action });
  } catch (e) {
    const code = String(e.message || '').startsWith('bad section') ? 400 : 500;
    return reply(code, { ok: false, error: e.message });
  }
};
