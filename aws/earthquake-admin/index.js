// sml-earthquake-admin — 甜甜「地震速報領牙齒」後台資料 API。
// 前端(遊戲館 earthquake_admin.html)Firebase Google 登入 → 帶 ID token 呼叫;
// 驗 token(sml2026newscore)+ gameAdmins 白名單(照 sml-vote)。
// 資料全在 DynamoDB。真正的輪詢 CWA / 發卡片 / 派牙由甜甜 bot 端做,這支只管:
//   - 可調設定 config(窗口/倍率/震度→牙齒/軟開關)
//   - 防災題庫 CRUD
//   - 近況(最近幾筆地震事件 + 領取統計)
//
// POST body { action, ... },header Authorization: Bearer <firebaseIdToken>
//   getConfig                       → { config }
//   saveConfig {patch}              → { config }  ← 部分或完整;intensityRewards deep-merge
//   listQuiz                        → { quiz:[...] }(含 disabled)
//   saveQuiz {item}                 → { id }(新增/更新;key 缺則自動配號)
//   deleteQuiz {key}                → { ok }
//   recent {limit?}                 → { events:[...] }(近況:meta + 領取數/發出牙齒)
const https = require('https');
const crypto = require('crypto');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, ScanCommand, PutCommand, DeleteCommand, GetCommand } = require('@aws-sdk/lib-dynamodb');

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: process.env.AWS_REGION || 'ap-southeast-1' }));
const T_CONFIG = 'sweetbot-earthquake-config';
const T_QUIZ = 'sweetbot-earthquake-quiz';
const T_LOG = 'sweetbot-earthquake-log';
const FIREBASE_PROJECT = process.env.FIREBASE_PROJECT || 'sml2026newscore';
const ADMIN_DOC_URL = `https://firestore.googleapis.com/v1/projects/${FIREBASE_PROJECT}/databases/(default)/documents/config/gameAdmins`;
const FALLBACK_EMAILS = (process.env.ALLOWED_EMAILS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);

// 預設 config = 甜甜 bot 端 EarthquakeConfigDAO.DEFAULT_CONFIG 的鏡像(現行寫死值)。
// getConfig 回傳時把 DDB 列疊在這上面,任何缺欄自動補齊 → 與 bot 端 load() 語義一致。
const DEFAULT_CONFIG = {
  key: 'main',
  intensityRewards: {
    '1級': 1, '2級': 2, '3級': 3, '4級': 4,
    '5弱': 5, '5強': 6, '6弱': 7, '6強': 8, '7級': 10
  },
  quizMultiplier: 2,
  flashWindowSec: 45,
  quizWindowSec: 90,
  disabled: false
};

const CORS = {
  'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type,Authorization', 'Content-Type': 'application/json; charset=utf-8'
};
const reply = (code, obj) => ({ statusCode: code, headers: CORS, body: JSON.stringify(obj) });
// 明確布林解析:真布林原樣;字串 'false'/'0'/'no'/'' 視為 false(擋掉 "false" 被 !! 變 true)。
const toBool = (v) => {
  if (typeof v === 'boolean') return v;
  if (typeof v === 'number') return v !== 0;
  if (typeof v === 'string') { const s = v.trim().toLowerCase(); return !(s === '' || s === 'false' || s === '0' || s === 'no'); }
  return !!v;
};
function httpGetJson (url) { return new Promise((res, rej) => { https.get(url, r => { let d = ''; r.on('data', c => (d += c)); r.on('end', () => { try { res(JSON.parse(d)); } catch (e) { rej(e); } }); }).on('error', rej); }); }

// ── Firebase ID token 驗證(RS256, Google securetoken 公鑰) ──
let certCache = { at: 0, keys: {} };
async function getCerts () {
  if (Date.now() - certCache.at < 3600e3 && Object.keys(certCache.keys).length) return certCache.keys;
  const d = await httpGetJson('https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com');
  certCache = { at: Date.now(), keys: d }; return d;
}
const b64urlJson = s => JSON.parse(Buffer.from(s.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'));
async function verifyIdToken (token) {
  if (!token) throw new Error('no token');
  const [h, p, sig] = token.split('.'); if (!h || !p || !sig) throw new Error('malformed');
  const header = b64urlJson(h), payload = b64urlJson(p), now = Math.floor(Date.now() / 1000);
  if (payload.aud !== FIREBASE_PROJECT) throw new Error('bad aud');
  if (payload.iss !== `https://securetoken.google.com/${FIREBASE_PROJECT}`) throw new Error('bad iss');
  if (payload.exp < now) throw new Error('expired');
  if (!payload.email || payload.email_verified === false) throw new Error('no verified email');
  const pem = (await getCerts())[header.kid]; if (!pem) throw new Error('unknown kid');
  const v = crypto.createVerify('RSA-SHA256'); v.update(`${h}.${p}`);
  if (!v.verify(pem, Buffer.from(sig.replace(/-/g, '+').replace(/_/g, '/'), 'base64'))) throw new Error('bad sig');
  return payload;
}
let allowCache = { at: 0, emails: [] };
async function getAllowlist () {
  if (Date.now() - allowCache.at < 3e5 && allowCache.emails.length) return allowCache.emails;
  try {
    const j = await httpGetJson(ADMIN_DOC_URL); const vals = j?.fields?.emails?.arrayValue?.values || [];
    const e = vals.map(v => String(v.stringValue || '').toLowerCase()).filter(Boolean); if (e.length) allowCache = { at: Date.now(), emails: e };
  } catch (e) {}
  return allowCache.emails.length ? allowCache.emails : FALLBACK_EMAILS;
}

async function scanAll (table, params = {}) {
  const items = []; let ExclusiveStartKey;
  do { const r = await ddb.send(new ScanCommand({ TableName: table, ExclusiveStartKey, ...params })); items.push(...(r.Items || [])); ExclusiveStartKey = r.LastEvaluatedKey; } while (ExclusiveStartKey);
  return items;
}
const nextQuizId = items => 'q' + String(items.reduce((m, x) => Math.max(m, Number(String(x.key).replace(/^q/, '')) || 0), 0) + 1);

// ── config 讀 / 寫 ──
async function loadConfig () {
  const res = await ddb.send(new GetCommand({ TableName: T_CONFIG, Key: { key: 'main' } }));
  const cur = { ...DEFAULT_CONFIG, ...(res.Item || {}) };
  // intensityRewards 也要 deep-merge 於預設之上(DDB 列可能只存部分震度)
  cur.intensityRewards = { ...DEFAULT_CONFIG.intensityRewards, ...(res.Item?.intensityRewards || {}) };
  return cur;
}
// 白名單 + 型別驗證:只接受已知欄、數值合法,擋掉會弄壞 bot 的髒資料。
function sanitizeConfigPatch (patch) {
  const p = patch || {}; const out = {};
  if (p.intensityRewards && typeof p.intensityRewards === 'object') {
    const ir = {};
    for (const [k, v] of Object.entries(p.intensityRewards)) {
      const n = Number(v);
      if (Number.isFinite(n) && n >= 0) ir[k] = Math.floor(n);
    }
    if (Object.keys(ir).length) out.intensityRewards = ir;
  }
  if (p.quizMultiplier != null) { const n = Number(p.quizMultiplier); if (Number.isFinite(n) && n >= 1 && n <= 10) out.quizMultiplier = n; }
  if (p.flashWindowSec != null) { const n = Math.floor(Number(p.flashWindowSec)); if (Number.isFinite(n) && n >= 10 && n <= 3600) out.flashWindowSec = n; }
  if (p.quizWindowSec != null) { const n = Math.floor(Number(p.quizWindowSec)); if (Number.isFinite(n) && n >= 10 && n <= 3600) out.quizWindowSec = n; }
  if (p.disabled != null) out.disabled = toBool(p.disabled);
  return out;
}
async function saveConfig (patch) {
  const cur = await loadConfig();
  const clean = sanitizeConfigPatch(patch);
  const next = { ...cur, ...clean, key: 'main', updatedAt: Date.now() };
  if (clean.intensityRewards) next.intensityRewards = { ...cur.intensityRewards, ...clean.intensityRewards };
  await ddb.send(new PutCommand({ TableName: T_CONFIG, Item: next }));
  return next;
}

// ── 題庫驗證 ──
function sanitizeQuiz (item, key) {
  const q = item || {};
  const question = String(q.question || '').trim();
  const optionA = String(q.optionA || '').trim();
  const optionB = String(q.optionB || '').trim();
  const correct = (q.correct === 'B') ? 'B' : 'A';
  if (!question || !optionA || !optionB) { const err = new Error('question/optionA/optionB required'); err.statusCode = 400; throw err; }
  const weight = Math.max(1, Math.min(100, Math.floor(Number(q.weight)) || 1));
  return {
    key,
    question, optionA, optionB, correct,
    explain: String(q.explain || '').trim(),
    weight,
    enabled: q.enabled == null ? true : toBool(q.enabled),
    updatedAt: Date.now()
  };
}

// ── 近況:掃 log 表,聚合每個地震的 meta + 領取數/發出牙齒 ──
async function recentEvents (limit) {
  const rows = await scanAll(T_LOG);
  const byEvent = {};
  for (const r of rows) {
    const id = String(r.pk);
    if (!byEvent[id]) byEvent[id] = { no: id, meta: null, claims: 0, teeth: 0 };
    if (r.sk === 'meta') byEvent[id].meta = r;
    else if (typeof r.sk === 'string' && r.sk.startsWith('claim#')) {
      byEvent[id].claims += 1;
      byEvent[id].teeth += Number(r.teeth) || 0;
    }
  }
  const events = Object.values(byEvent)
    .filter(e => e.meta) // 只保留有 meta 的(claim 孤兒忽略)
    .sort((a, b) => (Number(b.meta.time ? Date.parse(b.meta.time) : 0) || Number(b.meta.expireAt) || 0) -
                    (Number(a.meta.time ? Date.parse(a.meta.time) : 0) || Number(a.meta.expireAt) || 0));
  return events.slice(0, Math.max(1, Math.min(100, Number(limit) || 20)));
}

exports.handler = async (event) => {
  if (event.requestContext?.http?.method === 'OPTIONS' || event.httpMethod === 'OPTIONS') return reply(200, {});
  let user;
  try { const auth = event.headers?.authorization || event.headers?.Authorization || ''; user = await verifyIdToken(auth.replace(/^Bearer\s+/i, '')); }
  catch (e) { return reply(401, { ok: false, error: 'auth failed: ' + e.message }); }
  const allow = await getAllowlist();
  if (!allow.includes(String(user.email).toLowerCase())) return reply(403, { ok: false, error: 'not staff: ' + user.email });

  let body; try { body = typeof event.body === 'string' ? JSON.parse(event.body || '{}') : (event.body || {}); } catch { return reply(400, { ok: false, error: 'bad json' }); }
  const a = body.action;
  try {
    if (a === 'getConfig') return reply(200, { ok: true, config: await loadConfig() });

    if (a === 'saveConfig') return reply(200, { ok: true, config: await saveConfig(body.patch || body.config) });

    if (a === 'listQuiz') {
      const items = (await scanAll(T_QUIZ)).sort((x, y) => String(x.key).localeCompare(String(y.key), undefined, { numeric: true }));
      return reply(200, { ok: true, quiz: items });
    }

    if (a === 'saveQuiz') {
      const incoming = body.item || {};
      let key = incoming.key ? String(incoming.key) : null;
      if (!key) key = nextQuizId(await scanAll(T_QUIZ)); // 新增:自動配號
      const item = sanitizeQuiz(incoming, key);
      await ddb.send(new PutCommand({ TableName: T_QUIZ, Item: item }));
      return reply(200, { ok: true, id: key, item });
    }

    if (a === 'deleteQuiz') {
      const key = String(body.key || '');
      if (!key) return reply(400, { ok: false, error: 'no key' });
      await ddb.send(new DeleteCommand({ TableName: T_QUIZ, Key: { key } }));
      return reply(200, { ok: true });
    }

    if (a === 'recent') return reply(200, { ok: true, events: await recentEvents(body.limit) });

    return reply(400, { ok: false, error: 'unknown action: ' + a });
  } catch (e) {
    return reply(e.statusCode || 500, { ok: false, error: String(e.message || e) });
  }
};
