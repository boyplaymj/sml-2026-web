// sml-laoshiji-admin — 老司機每日四連號後台資料 API.
// Frontend signs in with Firebase Google auth, sends Firebase ID token.
// Lambda verifies token(project sml2026newscore) + config/gameAdmins allowlist,
// then exposes CRUD for DynamoDB table sml-plate-codes.
const https = require('https');
const crypto = require('crypto');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const {
  DynamoDBDocumentClient,
  ScanCommand,
  PutCommand,
  DeleteCommand
} = require('@aws-sdk/lib-dynamodb');

const REGION = process.env.AWS_REGION || 'ap-southeast-1';
const TABLE = process.env.TABLE_NAME || 'sml-plate-codes';
const FIREBASE_PROJECT = process.env.FIREBASE_PROJECT || 'sml2026newscore';
const ADMIN_DOC_URL = `https://firestore.googleapis.com/v1/projects/${FIREBASE_PROJECT}/databases/(default)/documents/config/gameAdmins`;
// 白名單:env ALLOWED_EMAILS 為權威來源(設了就以它為準)。
// 為什麼不直接信 Firestore config/gameAdmins:那份文件目前世界可寫(firestore.rules catch-all),
// 若當唯一授權來源會被下毒繞過認證。env 拿掉這個可被竄改的信任錨點。
const ENV_EMAILS = (process.env.ALLOWED_EMAILS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || 'https://sweetbot-games.web.app')
  .split(',').map(s => s.trim()).filter(Boolean);

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }));

function corsHeaders (event) {
  const origin = event.headers?.origin || event.headers?.Origin || '';
  const allowOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    'Access-Control-Allow-Origin': allowOrigin,
    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Max-Age': '300',
    'Content-Type': 'application/json; charset=utf-8',
    'Vary': 'Origin'
  };
}

const reply = (event, code, obj) => ({
  statusCode: code,
  headers: corsHeaders(event),
  body: JSON.stringify(obj)
});

function httpGetJson (url) {
  return new Promise((resolve, reject) => {
    https.get(url, res => {
      let data = '';
      res.on('data', c => { data += c; });
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}

let certCache = { at: 0, keys: {} };
async function getCerts () {
  if (Date.now() - certCache.at < 60 * 60 * 1000 && Object.keys(certCache.keys).length) return certCache.keys;
  const keys = await httpGetJson('https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com');
  certCache = { at: Date.now(), keys };
  return keys;
}

function b64urlJson (s) {
  return JSON.parse(Buffer.from(s.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'));
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
  if (!payload.email || payload.email_verified !== true) throw new Error('no verified email');
  const pem = (await getCerts())[header.kid];
  if (!pem) throw new Error('unknown kid');
  const verifier = crypto.createVerify('RSA-SHA256');
  verifier.update(`${h}.${p}`);
  if (!verifier.verify(pem, Buffer.from(sig.replace(/-/g, '+').replace(/_/g, '/'), 'base64'))) {
    throw new Error('bad signature');
  }
  return payload;
}

let allowCache = { at: 0, emails: [] };
async function getAllowlist () {
  // env 權威:設了 ALLOWED_EMAILS 就是唯一真相,完全不碰(世界可寫的)Firestore。
  if (ENV_EMAILS.length) return ENV_EMAILS;
  // 只有沒設 env 時才退回 Firestore config/gameAdmins(方便來源;⚠️目前公開可寫,務必設 env)。
  if (Date.now() - allowCache.at < 5 * 60 * 1000 && allowCache.emails.length) return allowCache.emails;
  try {
    const docJson = await httpGetJson(ADMIN_DOC_URL);
    const vals = docJson?.fields?.emails?.arrayValue?.values || [];
    const emails = vals.map(v => String(v.stringValue || '').toLowerCase()).filter(Boolean);
    if (emails.length) allowCache = { at: Date.now(), emails };
  } catch (e) {
    // 讀不到就保留舊 cache;沒 cache 也沒 env → 回空陣列 → fail-closed(deny all)。
  }
  return allowCache.emails;
}

const VALID = /^[A-Z]{2,6}-\d{2,5}$/;
const SPLIT = /^([A-Z]{2,6})[-\s_]*?(\d{2,5})$/;

function normalizeCode (raw) {
  if (!raw) return null;
  let s = String(raw).trim().toUpperCase().replace(/\u3000/g, '');
  s = s.replace(/\s+/g, '');
  const m = SPLIT.exec(s);
  if (!m) return null;
  const code = `${m[1]}-${m[2]}`;
  return VALID.test(code) ? code : null;
}

async function requireAdmin (event) {
  const auth = event.headers?.authorization || event.headers?.Authorization || '';
  const user = await verifyIdToken(auth.replace(/^Bearer\s+/i, ''));
  const allow = await getAllowlist();
  const email = String(user.email || '').toLowerCase();
  if (!allow.includes(email)) {
    const err = new Error('not staff: ' + email);
    err.statusCode = 403;
    throw err;
  }
  return user;
}

async function scanCodes () {
  const items = [];
  let ExclusiveStartKey;
  do {
    const r = await ddb.send(new ScanCommand({
      TableName: TABLE,
      ExclusiveStartKey,
      ProjectionExpression: '#c, #s, postedCount, lastPostedAt, imageUrl',
      ExpressionAttributeNames: { '#c': 'code', '#s': 'status' }
    }));
    items.push(...(r.Items || []));
    ExclusiveStartKey = r.LastEvaluatedKey;
  } while (ExclusiveStartKey);
  items.sort((a, b) => String(a.code).localeCompare(String(b.code)));
  return items;
}

async function addCodes (rawCodes) {
  if (!Array.isArray(rawCodes)) {
    const err = new Error('codes must be an array');
    err.statusCode = 400;
    throw err;
  }
  const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  const added = [];
  const skipped = [];
  const invalid = [];
  const seen = new Set();

  for (const raw of rawCodes) {
    const code = normalizeCode(raw);
    if (!code) {
      invalid.push(raw);
      continue;
    }
    if (seen.has(code)) {
      skipped.push(code);
      continue;
    }
    seen.add(code);
    try {
      await ddb.send(new PutCommand({
        TableName: TABLE,
        Item: { code, status: 'active', createdAt: now, postedCount: 0, source: 'admin' },
        ConditionExpression: 'attribute_not_exists(code)'
      }));
      added.push(code);
    } catch (e) {
      if (e.name === 'ConditionalCheckFailedException') skipped.push(code);
      else throw e;
    }
  }
  return { added, skipped, invalid };
}

function routeOf (event) {
  const method = event.requestContext?.http?.method || event.httpMethod || '';
  const path = event.rawPath || event.path || '/';
  return { method: method.toUpperCase(), path };
}

exports.handler = async (event) => {
  const { method, path } = routeOf(event);
  if (method === 'OPTIONS') return reply(event, 200, {});

  try {
    await requireAdmin(event);
  } catch (e) {
    return reply(event, 403, { ok: false, error: 'forbidden: ' + e.message });
  }

  try {
    if (method === 'GET' && path === '/codes') {
      return reply(event, 200, { items: await scanCodes() });
    }

    if (method === 'POST' && path === '/codes') {
      let body;
      try { body = typeof event.body === 'string' ? JSON.parse(event.body || '{}') : (event.body || {}); } catch {
        return reply(event, 400, { ok: false, error: 'bad json' });
      }
      return reply(event, 200, await addCodes(body.codes));
    }

    if (method === 'DELETE' && path.startsWith('/codes/')) {
      const raw = decodeURIComponent(path.slice('/codes/'.length));
      const code = normalizeCode(raw);
      if (!code) return reply(event, 400, { ok: false, error: 'invalid code' });
      await ddb.send(new DeleteCommand({ TableName: TABLE, Key: { code } }));
      return reply(event, 200, { ok: true });
    }

    return reply(event, 404, { ok: false, error: 'not found' });
  } catch (e) {
    const status = e.statusCode || 500;
    return reply(event, status, { ok: false, error: e.message });
  }
};
