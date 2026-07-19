// sml-daily-quest-admin — 甜甜「每日任務」後台資料 API。
// 前端(遊戲館 daily_quest_admin.html)Firebase Google 登入 → 帶 ID token 呼叫;
// 驗 token(sml2026newscore)+ gameAdmins 白名單(照 sml-earthquake-admin / sml-vote)。
// 只管任務模板池 sweetbot-quest-config 的 CRUD + 今日抽取分佈預覽。
// 玩家每日進度 / 懶抽 / 發獎 由甜甜 bot 端做,這支不碰 daily-quest / streak 表。
//
// POST body { action, ... },header Authorization: Bearer <firebaseIdToken>
//   list                       → { tasks:[...] }(含 disabled,依 key 排序)
//   saveTask {task}            → { key }(新增/更新;key 缺則自動配 q_custom_<n>)
//   deleteTask {key}           → { ok }
//   preview {vipLevel?}        → { drawCount, pool, totalWeight, difficultyMix, tasks:[{key,title,weight,appearProb}] }
//        以 enabled 池模擬「依 weight 不重複抽 N=3+vipLevel 張」的出現機率(Monte Carlo)
const https = require('https');
const crypto = require('crypto');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, ScanCommand, PutCommand, DeleteCommand } = require('@aws-sdk/lib-dynamodb');

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: process.env.AWS_REGION || 'ap-southeast-1' }));
const T_CONFIG = 'sweetbot-quest-config';

const FIREBASE_PROJECT = process.env.FIREBASE_PROJECT || 'sml2026newscore';
// 工作人員白名單同步遊戲館 config/gameAdmins(單一真相),ALLOWED_EMAILS 只作緊急備援。
const ADMIN_DOC_URL = `https://firestore.googleapis.com/v1/projects/${FIREBASE_PROJECT}/databases/(default)/documents/config/gameAdmins`;
const FALLBACK_EMAILS = (process.env.ALLOWED_EMAILS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type,Authorization',
  'Content-Type': 'application/json; charset=utf-8'
};
const reply = (code, obj) => ({ statusCode: code, headers: CORS, body: JSON.stringify(obj) });

// ── Firebase ID token 驗證(RS256,Google securetoken 公鑰,無外部套件)──────
let certCache = { at: 0, keys: {} };
function getCerts () {
  return new Promise((resolve, reject) => {
    if (Date.now() - certCache.at < 60 * 60 * 1000 && Object.keys(certCache.keys).length) return resolve(certCache.keys);
    https.get('https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com', res => {
      let d = ''; res.on('data', c => (d += c)); res.on('end', () => {
        try { certCache = { at: Date.now(), keys: JSON.parse(d) }; resolve(certCache.keys); } catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}
function b64urlJson (s) { return JSON.parse(Buffer.from(s.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8')); }

function httpGetJson (url) {
  return new Promise((resolve, reject) => {
    https.get(url, res => { let d = ''; res.on('data', c => (d += c)); res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } }); }).on('error', reject);
  });
}
let allowCache = { at: 0, emails: [] };
async function getAllowlist () {
  if (Date.now() - allowCache.at < 5 * 60 * 1000 && allowCache.emails.length) return allowCache.emails;
  try {
    const docJson = await httpGetJson(ADMIN_DOC_URL);
    const vals = docJson?.fields?.emails?.arrayValue?.values || [];
    const emails = vals.map(v => String(v.stringValue || '').toLowerCase()).filter(Boolean);
    if (emails.length) allowCache = { at: Date.now(), emails };
  } catch (e) { /* 讀取失敗保留舊快取 */ }
  return allowCache.emails.length ? allowCache.emails : FALLBACK_EMAILS;
}

async function verifyIdToken (token) {
  if (!token) throw new Error('no token');
  const [h, p, sig] = token.split('.');
  if (!h || !p || !sig) throw new Error('malformed token');
  const header = b64urlJson(h);
  const payload = b64urlJson(p);
  const now = Math.floor(Date.now() / 1000);
  if (payload.aud !== FIREBASE_PROJECT) throw new Error('bad aud');
  if (payload.iss !== `https://securetoken.google.com/${FIREBASE_PROJECT}`) throw new Error('bad iss');
  if (payload.exp < now) throw new Error('expired');
  if (!payload.email || payload.email_verified === false) throw new Error('no verified email');
  const certs = await getCerts();
  const pem = certs[header.kid];
  if (!pem) throw new Error('unknown kid');
  const v = crypto.createVerify('RSA-SHA256');
  v.update(`${h}.${p}`);
  if (!v.verify(pem, Buffer.from(sig.replace(/-/g, '+').replace(/_/g, '/'), 'base64'))) throw new Error('bad signature');
  return payload;
}

// ── DynamoDB helpers ──────────────────────────────────────────────
async function scanAll (table) {
  const items = []; let ExclusiveStartKey;
  do {
    const r = await ddb.send(new ScanCommand({ TableName: table, ExclusiveStartKey }));
    items.push(...(r.Items || [])); ExclusiveStartKey = r.LastEvaluatedKey;
  } while (ExclusiveStartKey);
  return items;
}

// 寬鬆布林正規化:前端可能送字串 "false"/"0"/"" → 這些都算 false(照 earthquake-admin)
function toBool (v, dflt = true) {
  if (v === undefined || v === null) return dflt;
  if (typeof v === 'boolean') return v;
  const s = String(v).trim().toLowerCase();
  if (['false', '0', 'no', 'off', ''].includes(s)) return false;
  if (['true', '1', 'yes', 'on'].includes(s)) return true;
  return dflt;
}

const ALLOWED_EVENT_RE = /^(checkin|post_message|mention_user|get_mentioned|add_reaction|reply_message|teeth_earned|teeth_spent|redpacket_grab|gift_send|item_use|item_buy|exp_gain|vote_join|bind_youtube|quest_complete|yt_keyword|stock_bet|game_bet|game_play:[a-z0-9_]+|game_win:[a-z0-9_]+|game_achieve:[a-z0-9_]+|button_click:[a-z0-9_]+)$/;

// 正規化前端送來的 task → 乾淨型別(避免 DDB 存到字串 "150")
function normalizeTask (raw, existingKeys) {
  const t = {};
  let key = String(raw.key || '').trim();
  if (!key) {
    let n = 1;
    while (existingKeys.has(`q_custom_${n}`)) n++;
    key = `q_custom_${n}`;
  }
  if (!/^[a-zA-Z0-9_]+$/.test(key)) throw new Error('key 只允許英數與底線: ' + key);
  t.key = key;
  t.title = String(raw.title || '').trim();
  if (!t.title) throw new Error('title 不可空');
  t.desc = String(raw.desc || '').trim();
  t.event = String(raw.event || '').trim();
  if (!ALLOWED_EVENT_RE.test(t.event)) throw new Error('event 不合法: ' + t.event);
  t.target = Math.max(1, Math.floor(Number(raw.target) || 1));
  t.difficulty = ['簡單', '普通', '挑戰'].includes(raw.difficulty) ? raw.difficulty : '普通';
  t.weight = Math.max(0, Number(raw.weight) || 0);
  t.rewardType = raw.rewardType === 'prop' ? 'prop' : 'point';
  t.rewardPoint = Math.max(0, Math.floor(Number(raw.rewardPoint) || 0));
  t.rewardExp = Math.max(0, Math.floor(Number(raw.rewardExp) || 0));
  if (t.rewardType === 'prop') {
    t.rewardPropId = String(raw.rewardPropId || '').trim();
    t.rewardPropQty = Math.max(1, Math.floor(Number(raw.rewardPropQty) || 1));
  }
  t.enabled = toBool(raw.enabled, true);
  t.isHidden = toBool(raw.isHidden, false); // 隱藏任務:不進正常抽題池,由 bot 稀有骰另抽;預設 false
  t.distinct = toBool(raw.distinct, false); // 不重複計數:progress=已出現的不同 key 數(如玩 N 種不同遊戲);預設 false
  return t;
}

// 依 weight 不重複抽 n 張(反覆按剩餘權重挑一張)
function weightedDrawWithoutReplacement (pool, n) {
  const remaining = pool.slice();
  const picked = [];
  for (let i = 0; i < n && remaining.length; i++) {
    let total = remaining.reduce((s, x) => s + x.weight, 0);
    if (total <= 0) { picked.push(remaining.splice(Math.floor(Math.random() * remaining.length), 1)[0]); continue; }
    let r = Math.random() * total, idx = 0;
    for (; idx < remaining.length; idx++) { r -= remaining[idx].weight; if (r <= 0) break; }
    if (idx >= remaining.length) idx = remaining.length - 1;
    picked.push(remaining.splice(idx, 1)[0]);
  }
  return picked;
}

exports.handler = async (event) => {
  if (event.requestContext?.http?.method === 'OPTIONS' || event.httpMethod === 'OPTIONS') return reply(200, {});

  // 驗身分
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

  try {
    if (action === 'list') {
      const tasks = (await scanAll(T_CONFIG)).sort((a, b) => String(a.key).localeCompare(String(b.key)));
      return reply(200, { ok: true, tasks });
    }

    if (action === 'saveTask') {
      const existing = await scanAll(T_CONFIG);
      const existingKeys = new Set(existing.map(t => String(t.key)));
      const t = normalizeTask(body.task || {}, existingKeys);
      await ddb.send(new PutCommand({ TableName: T_CONFIG, Item: t }));
      return reply(200, { ok: true, key: t.key });
    }

    if (action === 'deleteTask') {
      const key = String(body.key || '').trim();
      if (!key) return reply(400, { ok: false, error: 'no key' });
      await ddb.send(new DeleteCommand({ TableName: T_CONFIG, Key: { key } }));
      return reply(200, { ok: true });
    }

    if (action === 'preview') {
      const vipLevel = Math.max(0, Math.min(10, Math.floor(Number(body.vipLevel) || 0)));
      const drawCount = 3 + vipLevel;
      const allCfg = await scanAll(T_CONFIG);
      const hiddenCount = allCfg.filter(t => t.enabled !== false && t.isHidden === true).length;
      // 正常抽題池排除隱藏任務(隱藏由 bot 端稀有骰另抽,不佔正常張數)
      const pool = allCfg
        .filter(t => t.enabled !== false && !t.isHidden)
        .map(t => ({ key: String(t.key), title: t.title, difficulty: t.difficulty, weight: Math.max(0, Number(t.weight) || 0) }));
      const totalWeight = pool.reduce((s, x) => s + x.weight, 0);
      const TRIALS = 3000;
      const counts = {}; const diffCount = {};
      let totalDrawn = 0; // 實際抽到總數(drawCount>pool 時 < drawCount*TRIALS)
      for (const p of pool) counts[p.key] = 0;
      for (let i = 0; i < TRIALS; i++) {
        for (const d of weightedDrawWithoutReplacement(pool, drawCount)) {
          counts[d.key]++;
          diffCount[d.difficulty] = (diffCount[d.difficulty] || 0) + 1;
          totalDrawn++;
        }
      }
      const tasks = pool.map(p => ({ key: p.key, title: p.title, difficulty: p.difficulty, weight: p.weight, appearProb: +(counts[p.key] / TRIALS).toFixed(3) }))
        .sort((a, b) => b.appearProb - a.appearProb);
      const difficultyMix = {};
      for (const [k, v] of Object.entries(diffCount)) difficultyMix[k] = +(v / totalDrawn).toFixed(3);
      return reply(200, { ok: true, drawCount, pool: pool.length, totalWeight, difficultyMix, tasks, hiddenCount });
    }

    return reply(400, { ok: false, error: 'unknown action: ' + action });
  } catch (e) {
    return reply(500, { ok: false, error: e.message });
  }
};
