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
  DeleteCommand,
  GetCommand
} = require('@aws-sdk/lib-dynamodb');
const { S3Client, GetObjectCommand, PutObjectCommand, DeleteObjectCommand } = require('@aws-sdk/client-s3');
const { CloudFrontClient, CreateInvalidationCommand } = require('@aws-sdk/client-cloudfront');

const REGION = process.env.AWS_REGION || 'ap-southeast-1';
const TABLE = process.env.TABLE_NAME || 'sml-plate-codes';
const REF_TABLE = process.env.REF_TABLE_NAME || 'sml-plate-refs';
const TRIALGATE_LAYERS_TABLE = process.env.TRIALGATE_LAYERS_TABLE || 'sweetbot-trialgate-layers';
const ATLAS_BUCKET = process.env.ATLAS_BUCKET || 'boyplaymj-image';
const ATLAS_KEY = process.env.ATLAS_KEY || 'plate-meta/atlas.json';
const IMG_BASE = process.env.IMG_BASE || 'https://image.boyplaymj.link';
const DAILY_CHANNEL = process.env.DAILY_CHANNEL || '1525321679922921522';
const FIREBASE_PROJECT = process.env.FIREBASE_PROJECT || 'sml2026newscore';
// 試煉之門 BOSS 圖上傳:image.boyplaymj.link 的 CloudFront distro,換圖後要清快取否則吐舊圖。
const IMG_CF_DISTRIBUTION = process.env.IMG_CF_DISTRIBUTION || 'E2IJWN6FWT2XYG';
const TRIALGATE_MAX_LAYER = Number(process.env.TRIALGATE_MAX_LAYER || 20);
const TRIALGATE_LAYER_MAX = Number(process.env.TRIALGATE_LAYER_MAX || 10);
// 白名單:env ALLOWED_EMAILS 為權威來源(設了就以它為準)。
// 為什麼不直接信 Firestore config/gameAdmins:那份文件目前世界可寫(firestore.rules catch-all),
// 若當唯一授權來源會被下毒繞過認證。env 拿掉這個可被竄改的信任錨點。
const ENV_EMAILS = (process.env.ALLOWED_EMAILS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || 'https://sweetbot-games.web.app')
  .split(',').map(s => s.trim()).filter(Boolean);

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }));
const s3 = new S3Client({ region: REGION });
const cf = new CloudFrontClient({ region: 'us-east-1' }); // CloudFront 是全域服務,SDK 慣用 us-east-1

function corsHeaders (event) {
  const origin = event.headers?.origin || event.headers?.Origin || '';
  const allowOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    'Access-Control-Allow-Origin': allowOrigin,
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Max-Age': '300',
    'Content-Type': 'application/json; charset=utf-8',
    Vary: 'Origin'
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

function getAllowlist () {
  // env ALLOWED_EMAILS 是唯一授權來源;沒設就 fail-closed(回空 → deny all)。
  // 刻意不 fallback Firestore config/gameAdmins:那份文件世界可寫(firestore.rules catch-all),
  // 當授權來源會被下毒繞過認證。管理員名單一律走 Lambda env。
  return ENV_EMAILS;
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

// \u53c3\u8003\u5eab\u7684 code \u53ea\u662f\u300c\u9019\u5f35\u5716\u6709\u54ea\u4e9b\u5b57\u300d,\u4f9b EC2 \u88c1\u5b57\u5efa\u5b57\u5eab\u7528,
// \u4e0d\u5957\u756a\u865f\u7684\u82f1\u524d\u6578\u5f8c\u7d50\u69cb(\u53f0\u7063\u8eca\u724c\u5982 1051-K7 \u6578\u5b57\u958b\u982d\u4e5f\u8981\u6536)\u3002
// \u53bb\u5206\u9694\u7b26\u3001\u5927\u5beb,\u53ea\u7559 A-Z0-9,\u9577\u5ea6 1-10(\u5141\u8a31\u55ae\u5b57\u5143:\u4f7f\u7528\u8005 PS \u53bb\u80cc\u597d\u7684\u55ae\u4e00\u5b57)\u3002
function normalizeRefCode (raw) {
  const s = String(raw || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  return /^[A-Z0-9]{1,10}$/.test(s) ? s : null;
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
  if (rawCodes.length > 500) {
    const err = new Error('too many codes (max 500)');
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

// 字庫覆蓋:讀 EC2 發佈到 S3 的 atlas.json(EC2 publish_atlas.py 產出)
async function getAtlas () {
  const r = await s3.send(new GetObjectCommand({ Bucket: ATLAS_BUCKET, Key: ATLAS_KEY }));
  const body = await r.Body.transformToString();
  return JSON.parse(body);
}

// 每日推播·預覽(唯讀):複刻 db.py pick_for_today 的排序,回今日會選的 4 個。
// 註:實際 daily.py 對同級用隨機 tie-break,預覽用穩定排序,故僅為指示性。
async function dailyPreview () {
  const items = (await scanCodes()).filter(it => (it.status || 'active') === 'active');
  items.sort((a, b) =>
    (Number(a.postedCount || 0) - Number(b.postedCount || 0)) ||
    String(a.lastPostedAt || '').localeCompare(String(b.lastPostedAt || '')));
  return { channel: DAILY_CHANNEL, picks: items.slice(0, 4), pool: items.length };
}

function refId () {
  return `${Date.now().toString(36)}-${crypto.randomBytes(4).toString('hex')}`;
}

function extForContentType (contentType) {
  const ct = String(contentType || '').toLowerCase().split(';')[0].trim();
  if (ct === 'image/jpeg' || ct === 'image/jpg') return { contentType: 'image/jpeg', ext: 'jpg' };
  if (ct === 'image/png') return { contentType: 'image/png', ext: 'png' };
  if (ct === 'image/webp') return { contentType: 'image/webp', ext: 'webp' };
  return null;
}

function decodeImage (imageBase64, contentType) {
  let raw = String(imageBase64 || '').trim();
  let ct = contentType;
  const m = raw.match(/^data:([^;,]+);base64,(.*)$/is);
  if (m) {
    ct = ct || m[1];
    raw = m[2];
  }
  raw = raw.replace(/\s+/g, '');
  if (!raw) {
    const err = new Error('imageBase64 required');
    err.statusCode = 400;
    throw err;
  }
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(raw)) {
    const err = new Error('bad image base64');
    err.statusCode = 400;
    throw err;
  }
  const meta = extForContentType(ct);
  if (!meta) {
    const err = new Error('unsupported contentType');
    err.statusCode = 400;
    throw err;
  }
  const buf = Buffer.from(raw, 'base64');
  if (!buf.length) {
    const err = new Error('empty image');
    err.statusCode = 400;
    throw err;
  }
  if (buf.length > 6 * 1024 * 1024) {
    const err = new Error('image too large (max 6MB)');
    err.statusCode = 400;
    throw err;
  }
  return { buf, ...meta };
}

async function scanRefs () {
  const items = [];
  let ExclusiveStartKey;
  do {
    const r = await ddb.send(new ScanCommand({
      TableName: REF_TABLE,
      ExclusiveStartKey,
      ProjectionExpression: 'refId, code, imageUrl, #s, createdAt',
      ExpressionAttributeNames: { '#s': 'status' }
    }));
    items.push(...(r.Items || []));
    ExclusiveStartKey = r.LastEvaluatedKey;
  } while (ExclusiveStartKey);
  items.sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || '')));
  return items;
}

async function addRef (body) {
  const code = normalizeRefCode(body?.code);
  if (!code) {
    const err = new Error('invalid code');
    err.statusCode = 400;
    throw err;
  }
  const image = decodeImage(body?.imageBase64, body?.contentType);
  const id = refId();
  const imageKey = `plate-refs/${id}.${image.ext}`;
  const imageUrl = `${IMG_BASE}/${imageKey}`;
  const createdAt = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');

  await s3.send(new PutObjectCommand({
    Bucket: ATLAS_BUCKET,
    Key: imageKey,
    Body: image.buf,
    ContentType: image.contentType,
    CacheControl: 'public,max-age=31536000,immutable'
  }));
  await ddb.send(new PutCommand({
    TableName: REF_TABLE,
    Item: { refId: id, code, imageKey, imageUrl, status: 'pending', createdAt },
    ConditionExpression: 'attribute_not_exists(refId)'
  }));
  return { refId: id, imageUrl, code };
}

async function deleteRef (rawRefId) {
  const id = String(rawRefId || '').trim();
  if (!/^[a-z0-9]+-[a-f0-9]{8}$/i.test(id)) {
    const err = new Error('invalid refId');
    err.statusCode = 400;
    throw err;
  }
  const cur = await ddb.send(new GetCommand({ TableName: REF_TABLE, Key: { refId: id } }));
  const key = cur.Item?.imageKey;
  if (key) {
    await s3.send(new DeleteObjectCommand({ Bucket: ATLAS_BUCKET, Key: key }));
  }
  await ddb.send(new DeleteCommand({ TableName: REF_TABLE, Key: { refId: id } }));
}

// 試煉之門 BOSS 圖上傳 ---------------------------------------------------------
// 換的是穩定檔名(1.png..N.png / died/N.png),故上傳完必須清 CloudFront 快取,
// 否則 image.boyplaymj.link 會繼續吐舊圖(典型「我傳了圖卻沒變」)。
async function invalidateCf (paths) {
  if (!IMG_CF_DISTRIBUTION || !paths.length) return;
  await cf.send(new CreateInvalidationCommand({
    DistributionId: IMG_CF_DISTRIBUTION,
    InvalidationBatch: {
      CallerReference: `trialgate-${Date.now()}-${crypto.randomBytes(3).toString('hex')}`,
      Paths: { Quantity: paths.length, Items: paths }
    }
  }));
}

async function putBossImage (body) {
  const layer = Number(body?.layer);
  if (!Number.isInteger(layer) || layer < 1 || layer > TRIALGATE_MAX_LAYER) {
    const err = new Error('invalid layer'); err.statusCode = 400; throw err;
  }
  const state = String(body?.state || 'normal').toLowerCase();
  if (state !== 'normal' && state !== 'died') {
    const err = new Error('invalid state (normal|died)'); err.statusCode = 400; throw err;
  }
  const image = decodeImage(body?.imageBase64, body?.contentType);
  if (image.ext !== 'png') {
    // 遊戲設定固定引用 N.png,故 BOSS 圖只收 png,避免副檔名對不上。
    const err = new Error('boss image must be png'); err.statusCode = 400; throw err;
  }
  // key 一律由伺服器組,絕不接受前端傳原始 key(避免寫到桶內任意位置)。
  const key = state === 'died'
    ? `rpg/trialgate/boss/died/${layer}.png`
    : `rpg/trialgate/boss/${layer}.png`;
  await s3.send(new PutObjectCommand({
    Bucket: ATLAS_BUCKET,
    Key: key,
    Body: image.buf,
    ContentType: 'image/png',
    // 穩定檔名會被覆蓋,不能用 immutable;短快取 + 上傳即清 CloudFront。
    CacheControl: 'public,max-age=300'
  }));
  let invalidated = true;
  try {
    await invalidateCf([`/${key}`]);
  } catch (e) {
    // 清快取失敗不擋上傳(圖已進 S3),只回報讓前端提示可能要等 CDN 過期。
    console.log('cf invalidation failed:', e.message);
    invalidated = false;
  }
  return { ok: true, layer, state, key, url: `${IMG_BASE}/${key}`, invalidated };
}

// 試煉之門關卡資料 -----------------------------------------------------------
function badRequest (message) {
  const err = new Error(message);
  err.statusCode = 400;
  return err;
}

function ensureString (value, name) {
  if (typeof value !== 'string') throw badRequest(`${name} must be string`);
  return value;
}

function ensureNumber (value, name, min = 0) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < min) throw badRequest(`${name} must be number >= ${min}`);
  return n;
}

function ensureInteger (value, name, min = 0) {
  const n = Number(value);
  if (!Number.isInteger(n) || n < min) throw badRequest(`${name} must be integer >= ${min}`);
  return n;
}

function validateBoss (boss, idx) {
  if (!boss || typeof boss !== 'object' || Array.isArray(boss)) throw badRequest(`bosses[${idx}] must be object`);
  const cardType = ensureString(boss.cardType, `bosses[${idx}].cardType`);
  if (!['sp', 'msp', 'ms'].includes(cardType)) throw badRequest(`bosses[${idx}].cardType invalid`);
  if (!Array.isArray(boss.cardLevel) || boss.cardLevel.length !== 2) throw badRequest(`bosses[${idx}].cardLevel must be [min,max]`);
  const min = ensureInteger(boss.cardLevel[0], `bosses[${idx}].cardLevel[0]`, 0);
  const max = ensureInteger(boss.cardLevel[1], `bosses[${idx}].cardLevel[1]`, 0);
  if (min > max) throw badRequest(`bosses[${idx}].cardLevel min > max`);
  if (!Array.isArray(boss.increase)) throw badRequest(`bosses[${idx}].increase must be array`);
  const soulDrain = boss.soulDrain === undefined ? undefined : Boolean(boss.soulDrain);
  const normalized = {
    name: ensureString(boss.name, `bosses[${idx}].name`),
    hp: ensureNumber(boss.hp, `bosses[${idx}].hp`),
    attack: ensureNumber(boss.attack, `bosses[${idx}].attack`),
    noAttackTime: ensureNumber(boss.noAttackTime, `bosses[${idx}].noAttackTime`),
    cardType,
    cardLevel: [min, max],
    sort: Boolean(boss.sort),
    img: ensureString(boss.img, `bosses[${idx}].img`),
    appearanceTxt: ensureString(boss.appearanceTxt, `bosses[${idx}].appearanceTxt`),
    attackTxt: ensureString(boss.attackTxt, `bosses[${idx}].attackTxt`),
    beAttackedTxt: ensureString(boss.beAttackedTxt, `bosses[${idx}].beAttackedTxt`),
    diedTxt: ensureString(boss.diedTxt, `bosses[${idx}].diedTxt`),
    killPlayerTxt: ensureString(boss.killPlayerTxt, `bosses[${idx}].killPlayerTxt`),
    stageEmoji: ensureString(boss.stageEmoji, `bosses[${idx}].stageEmoji`),
    increase: boss.increase.map((v, i) => ensureInteger(v, `bosses[${idx}].increase[${i}]`, 0))
  };
  if (soulDrain !== undefined) normalized.soulDrain = soulDrain;
  return normalized;
}

function validateAward (award) {
  if (!award || typeof award !== 'object' || Array.isArray(award)) throw badRequest('award must be object');
  const props = award.props;
  if (!(props === '' || typeof props === 'string' || Number.isInteger(Number(props)))) {
    throw badRequest('award.props must be string or integer');
  }
  return {
    teeth: ensureNumber(award.teeth, 'award.teeth'),
    experience: ensureNumber(award.experience, 'award.experience'),
    props: Number.isInteger(props) ? props : (Number.isInteger(Number(props)) && props !== '' ? Number(props) : props),
    propsProbability: ensureNumber(award.propsProbability, 'award.propsProbability')
  };
}

function validateTrialGateLayer (layer, body) {
  const n = ensureInteger(layer, 'layer', 1);
  if (n > TRIALGATE_LAYER_MAX) throw badRequest('layer out of range');
  if (!body || typeof body !== 'object' || Array.isArray(body)) throw badRequest('body must be object');
  if (!Array.isArray(body.bosses) || body.bosses.length === 0) throw badRequest('bosses must be non-empty array');
  return {
    layer: String(n),
    bosses: body.bosses.map(validateBoss),
    award: validateAward(body.award),
    updatedAt: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')
  };
}

async function scanTrialGateLayers () {
  const items = [];
  let ExclusiveStartKey;
  do {
    const r = await ddb.send(new ScanCommand({
      TableName: TRIALGATE_LAYERS_TABLE,
      ExclusiveStartKey
    }));
    items.push(...(r.Items || []));
    ExclusiveStartKey = r.LastEvaluatedKey;
  } while (ExclusiveStartKey);
  const meta = items.find(item => item.layer === '__meta__') || {};
  const layers = {};
  items
    .filter(item => /^\d+$/.test(String(item.layer || '')))
    .sort((a, b) => Number(a.layer) - Number(b.layer))
    .forEach(item => {
      layers[String(item.layer)] = { bosses: item.bosses || [], award: item.award || {}, updatedAt: item.updatedAt || '' };
    });
  return { maxLayer: Number(meta.maxLayer || Object.keys(layers).length || TRIALGATE_LAYER_MAX), layers };
}

async function putTrialGateLayer (layer, body) {
  const item = validateTrialGateLayer(layer, body);
  await ddb.send(new PutCommand({
    TableName: TRIALGATE_LAYERS_TABLE,
    Item: item
  }));
  return { ok: true, item };
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
    console.log('auth denied:', e.message); // 細節只留伺服器端,不回前端
    return reply(event, 403, { ok: false, error: 'forbidden' });
  }

  try {
    if (method === 'GET' && path === '/codes') {
      return reply(event, 200, { items: await scanCodes() });
    }

    if (method === 'GET' && path === '/atlas') {
      return reply(event, 200, await getAtlas());
    }

    if (method === 'GET' && path === '/daily/preview') {
      return reply(event, 200, await dailyPreview());
    }

    if (method === 'GET' && path === '/refs') {
      return reply(event, 200, { items: await scanRefs() });
    }

    if (method === 'GET' && path === '/trialgate/layers') {
      return reply(event, 200, await scanTrialGateLayers());
    }

    if (method === 'POST' && path === '/codes') {
      let body;
      try { body = typeof event.body === 'string' ? JSON.parse(event.body || '{}') : (event.body || {}); } catch {
        return reply(event, 400, { ok: false, error: 'bad json' });
      }
      return reply(event, 200, await addCodes(body.codes));
    }

    if (method === 'POST' && path === '/refs') {
      let body;
      try { body = typeof event.body === 'string' ? JSON.parse(event.body || '{}') : (event.body || {}); } catch {
        return reply(event, 400, { ok: false, error: 'bad json' });
      }
      return reply(event, 200, await addRef(body));
    }

    if (method === 'POST' && path === '/trialgate/boss') {
      let body;
      try { body = typeof event.body === 'string' ? JSON.parse(event.body || '{}') : (event.body || {}); } catch {
        return reply(event, 400, { ok: false, error: 'bad json' });
      }
      return reply(event, 200, await putBossImage(body));
    }

    if (method === 'PUT' && path.startsWith('/trialgate/layer/')) {
      const layer = decodeURIComponent(path.slice('/trialgate/layer/'.length));
      let body;
      try { body = typeof event.body === 'string' ? JSON.parse(event.body || '{}') : (event.body || {}); } catch {
        return reply(event, 400, { ok: false, error: 'bad json' });
      }
      return reply(event, 200, await putTrialGateLayer(layer, body));
    }

    if (method === 'DELETE' && path.startsWith('/codes/')) {
      const raw = decodeURIComponent(path.slice('/codes/'.length));
      const code = normalizeCode(raw);
      if (!code) return reply(event, 400, { ok: false, error: 'invalid code' });
      await ddb.send(new DeleteCommand({ TableName: TABLE, Key: { code } }));
      return reply(event, 200, { ok: true });
    }

    if (method === 'DELETE' && path.startsWith('/refs/')) {
      const raw = decodeURIComponent(path.slice('/refs/'.length));
      await deleteRef(raw);
      return reply(event, 200, { ok: true });
    }

    return reply(event, 404, { ok: false, error: 'not found' });
  } catch (e) {
    const status = e.statusCode || 500;
    console.log('handler error:', e.message);
    // 400 類保留有用訊息(bad json / invalid code / too many codes);500 類不外洩內部
    return reply(event, status, { ok: false, error: status < 500 ? e.message : 'internal error' });
  }
};
