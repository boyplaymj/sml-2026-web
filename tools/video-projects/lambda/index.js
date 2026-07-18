// sml-video-projects — 影片製作專案管理 API（見 tools/video-projects/DESIGN.md v0.1）
//
// 公開讀（單一使用者私人工具，走不公開連結；讀端不做 public/draft 過濾）:
//   GET /projects            → 專案列表摘要
//   GET /projects/{id}       → 單專案完整（含 tasks）
//   GET /calendar            → 跨專案任務攤平，供首頁月曆＋時間軸
//
// 後台（POST，body={action,...}，需 Firebase ID token + gameAdmins 白名單）:
//   adminList | saveProject | deleteProject | patchTask | toggleTask
//
const https = require('https');
const crypto = require('crypto');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const {
  DynamoDBDocumentClient, QueryCommand, PutCommand, DeleteCommand, GetCommand, UpdateCommand
} = require('@aws-sdk/lib-dynamodb');

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: process.env.AWS_REGION || 'ap-southeast-1' }));
const TABLE = process.env.TABLE || 'sml-video-projects';
const GSI = 'type-updatedAt-index';
const TYPE = 'vproj';
const PUSH_TYPE = 'pushsub';
const VAPID_PUBLIC = process.env.PUSH_VAPID_PUBLIC || 'BBTJPri_4uiQVTdzFfryL6rUpI3wBVgka1-0aaCqKWJuG8OOljpbc3iPQmEJOP6EJW9E7sEjgp6GF2m5eM3s5DM';

const FIREBASE_PROJECT = process.env.FIREBASE_PROJECT || 'sml2026newscore';
const ADMIN_DOC_URL = `https://firestore.googleapis.com/v1/projects/${FIREBASE_PROJECT}/databases/(default)/documents/config/gameAdmins`;
const FALLBACK_EMAILS = (process.env.ALLOWED_EMAILS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type,Authorization',
  'Content-Type': 'application/json; charset=utf-8'
};
const reply = (code, obj, extra = {}) => ({ statusCode: code, headers: { ...CORS, ...extra }, body: JSON.stringify(obj) });

// ── 序列化 ───────────────────────────────────────────────────
function taskDates (p) {
  return (p.tasks || []).map(t => t.date).filter(d => d && /^\d{4}-\d{2}-\d{2}$/.test(d)).sort();
}
const toSummary = (p) => {
  const ds = taskDates(p);
  const tasks = p.tasks || [];
  return {
    id: p.id, slug: p.slug, title: p.title, subtitle: p.subtitle || '',
    cover: p.cover || '', status: p.status || 'active',
    taskCount: tasks.length,
    todoCount: tasks.filter(t => t.status !== 'done').length,
    dateFrom: ds[0] || null, dateTo: ds[ds.length - 1] || null,
    updatedAt: p.updatedAt
  };
};
// calendar：跨專案攤平所有帶日期的任務
function toCalendarItems (projects) {
  const out = [];
  for (const p of projects) {
    for (const t of (p.tasks || [])) {
      if (!t.date || !/^\d{4}-\d{2}-\d{2}$/.test(t.date)) continue;
      out.push({
        projectId: p.id, projectTitle: p.title,
        tid: t.tid, title: t.title, date: t.date, time: t.time || '',
        importance: t.importance || 1, status: t.status || 'todo', tag: t.tag || ''
      });
    }
  }
  out.sort((a, b) => a.date < b.date ? -1 : a.date > b.date ? 1 : 0);
  return out;
}

// ── Firebase ID token 驗證（RS256，Google securetoken 公鑰）──
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
const getProject = async (id) => (await ddb.send(new GetCommand({ TableName: TABLE, Key: { id } }))).Item;
async function listAll () {
  const r = await ddb.send(new QueryCommand({
    TableName: TABLE, IndexName: GSI,
    KeyConditionExpression: '#t = :t', ExpressionAttributeNames: { '#t': 'type' },
    ExpressionAttributeValues: { ':t': TYPE }, ScanIndexForward: false
  }));
  return r.Items || [];
}
const nowIso = () => new Date().toISOString().replace(/\.\d+Z$/, 'Z');

// 正規化單一任務（後台寫入用，把型別收斂乾淨）
function normTask (t, i) {
  const imp = Number(t.importance);
  return {
    tid: (t.tid && String(t.tid)) || ('t' + (i + 1)),
    title: String(t.title || ''),
    date: (t.date && /^\d{4}-\d{2}-\d{2}$/.test(t.date)) ? t.date : '',
    time: (t.time && /^([01]\d|2[0-3]):[0-5]\d$/.test(t.time)) ? t.time : '',
    importance: (imp === 1 || imp === 2 || imp === 3) ? imp : 1,
    status: t.status === 'done' ? 'done' : 'todo',
    tag: String(t.tag || ''),
    note: String(t.note || ''),
    doneAt: t.status === 'done' ? (t.doneAt || nowIso()) : null,
    remindedAt: t.remindedAt || null
  };
}

// ── router ───────────────────────────────────────────────────
exports.handler = async (event) => {
  const method = event.requestContext?.http?.method || event.httpMethod || 'GET';
  const rawPath = event.rawPath || event.path || '/';
  const path = rawPath.replace(/\/+$/, '') || '/';
  if (method === 'OPTIONS') return reply(200, {});

  try {
    // ---------- 公開讀 ----------
    if (method === 'GET' && path === '/projects') {
      const items = await listAll();
      return reply(200, { projects: items.map(toSummary) });
    }
    if (method === 'GET' && path === '/calendar') {
      const items = await listAll();
      return reply(200, { items: toCalendarItems(items) });
    }
    const m = path.match(/^\/projects\/([A-Za-z0-9_-]+)$/);
    if (method === 'GET' && m) {
      const p = await getProject(m[1]);
      if (!p) return reply(404, { error: 'not found' });
      return reply(200, { project: p });
    }

    // ---------- Web Push 訂閱（單一使用者私人工具，無需認證）----------
    if (method === 'GET' && path === '/push/vapid') {
      return reply(200, { publicKey: VAPID_PUBLIC });
    }
    if (method === 'POST' && path === '/push/subscribe') {
      const body = JSON.parse(event.body || '{}');
      const sub = body.subscription || body;
      if (!sub || !sub.endpoint || !sub.keys?.p256dh || !sub.keys?.auth) return reply(400, { error: 'invalid subscription' });
      const sid = 'sub#' + crypto.createHash('sha256').update(sub.endpoint).digest('hex').slice(0, 40);
      await ddb.send(new PutCommand({ TableName: TABLE, Item: {
        id: sid, type: PUSH_TYPE, endpoint: sub.endpoint,
        p256dh: sub.keys.p256dh, auth: sub.keys.auth,
        ua: String(body.ua || '').slice(0, 200),
        createdAt: nowIso(), updatedAt: nowIso()
      } }));
      return reply(200, { ok: true, id: sid });
    }
    if (method === 'POST' && path === '/push/unsubscribe') {
      const body = JSON.parse(event.body || '{}');
      const ep = body.endpoint || body.subscription?.endpoint;
      if (!ep) return reply(400, { error: 'missing endpoint' });
      const sid = 'sub#' + crypto.createHash('sha256').update(ep).digest('hex').slice(0, 40);
      await ddb.send(new DeleteCommand({ TableName: TABLE, Key: { id: sid } }));
      return reply(200, { ok: true });
    }

    // ---------- 後台（需認證）----------
    if (method === 'POST' && (path === '/admin' || path === '/admin/projects')) {
      let admin;
      try { admin = await requireAdmin(event); }
      catch (e) { return reply(401, { error: 'unauthorized', detail: e.message }); }
      const body = JSON.parse(event.body || '{}');
      const action = body.action;

      if (action === 'adminList') {
        return reply(200, { projects: (await listAll()) });
      }
      if (action === 'saveProject') {
        const p = body.project || {};
        if (!p.id) return reply(400, { error: 'missing id' });
        if (!/^[A-Za-z0-9_-]+$/.test(p.id)) return reply(400, { error: 'invalid id：需符合 [A-Za-z0-9_-]' });
        if (p.slug && !/^[A-Za-z0-9_-]+$/.test(p.slug)) return reply(400, { error: 'invalid slug' });
        const prev = await getProject(p.id);
        const item = {
          id: p.id, type: TYPE, slug: p.slug || p.id,
          title: String(p.title || ''), subtitle: String(p.subtitle || ''),
          cover: String(p.cover || ''),
          status: ['active', 'done', 'archived'].includes(p.status) ? p.status : 'active',
          tasks: Array.isArray(p.tasks) ? p.tasks.map(normTask) : [],
          createdAt: prev?.createdAt || nowIso(), updatedAt: nowIso()
        };
        await ddb.send(new PutCommand({ TableName: TABLE, Item: item }));
        return reply(200, { ok: true, id: item.id });
      }
      if (action === 'deleteProject') {
        if (!body.id) return reply(400, { error: 'missing id' });
        try {
          await ddb.send(new DeleteCommand({
            TableName: TABLE, Key: { id: body.id }, ConditionExpression: 'attribute_exists(id)'
          }));
        } catch (e) {
          if (e.name === 'ConditionalCheckFailedException') return reply(404, { error: 'not found' });
          throw e;
        }
        return reply(200, { ok: true });
      }
      // 局部改單一任務欄位（title/date/importance/tag/note）
      if (action === 'patchTask') {
        const { id, tid, patch } = body;
        if (!id || !tid || !patch) return reply(400, { error: 'missing id/tid/patch' });
        const p = await getProject(id);
        if (!p) return reply(404, { error: 'not found' });
        const tasks = p.tasks || [];
        const idx = tasks.findIndex(t => t.tid === tid);
        if (idx < 0) return reply(404, { error: 'task not found' });
        const cur = tasks[idx];
        if (patch.title !== undefined) cur.title = String(patch.title);
        if (patch.date !== undefined) { cur.date = (/^\d{4}-\d{2}-\d{2}$/.test(patch.date)) ? patch.date : ''; cur.remindedAt = null; }
        if (patch.time !== undefined) { cur.time = (/^([01]\d|2[0-3]):[0-5]\d$/.test(patch.time)) ? patch.time : ''; cur.remindedAt = null; }
        if (patch.importance !== undefined) { const im = Number(patch.importance); cur.importance = (im === 1 || im === 2 || im === 3) ? im : cur.importance; }
        if (patch.tag !== undefined) cur.tag = String(patch.tag);
        if (patch.note !== undefined) cur.note = String(patch.note);
        await ddb.send(new UpdateCommand({
          TableName: TABLE, Key: { id },
          UpdateExpression: 'SET #tasks = :t, updatedAt = :u',
          ExpressionAttributeNames: { '#tasks': 'tasks' },
          ExpressionAttributeValues: { ':t': tasks, ':u': nowIso() }
        }));
        return reply(200, { ok: true });
      }
      // 打勾/取消：切 todo↔done，done 時寫 doneAt。done=true/false 指定，未給則反轉
      if (action === 'toggleTask') {
        const { id, tid } = body;
        if (!id || !tid) return reply(400, { error: 'missing id/tid' });
        const p = await getProject(id);
        if (!p) return reply(404, { error: 'not found' });
        const tasks = p.tasks || [];
        const idx = tasks.findIndex(t => t.tid === tid);
        if (idx < 0) return reply(404, { error: 'task not found' });
        const cur = tasks[idx];
        const next = (body.done === true || body.done === false) ? body.done : (cur.status !== 'done');
        cur.status = next ? 'done' : 'todo';
        cur.doneAt = next ? nowIso() : null;
        await ddb.send(new UpdateCommand({
          TableName: TABLE, Key: { id },
          UpdateExpression: 'SET #tasks = :t, updatedAt = :u',
          ExpressionAttributeNames: { '#tasks': 'tasks' },
          ExpressionAttributeValues: { ':t': tasks, ':u': nowIso() }
        }));
        return reply(200, { ok: true, status: cur.status });
      }
      return reply(400, { error: 'unknown action' });
    }

    return reply(404, { error: 'route not found', path, method });
  } catch (e) {
    console.error(e);
    return reply(500, { error: 'internal', detail: e.message });
  }
};
