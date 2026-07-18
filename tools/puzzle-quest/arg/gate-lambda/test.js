// 本地離線測試：mock Firestore stage 讀取，驗閘門發放/鎖定行為（node test.js）
const https = require('https');
const { EventEmitter } = require('events');

let MOCK = { puzzleId: 'mingyan-forgery-coverup', stage: 4 };
https.get = (url, cb) => {
  const res = new EventEmitter();
  res.statusCode = 200;
  cb(res);
  const body = JSON.stringify({ fields: {
    puzzleId: { stringValue: MOCK.puzzleId },
    stage: { integerValue: String(MOCK.stage) }
  }});
  process.nextTick(() => { res.emit('data', body); res.emit('end'); });
  const req = new EventEmitter();
  req.setTimeout = () => {}; req.destroy = () => {};
  return req;
};

const { handler } = require('./index');
const ORIGIN = 'https://image.boyplaymj.link';
const ev = (q, extra = {}) => ({
  requestContext: { http: { method: 'GET' } },
  headers: { origin: ORIGIN },
  queryStringParameters: q, ...extra
});

// 因閘門有 45s stage 快取，測試間強制清快取：改 MOCK 後 sleep 過 TTL 不切實際 → 用 env 關快取
process.env.STAGE_TTL_MS = '0';
delete require.cache[require.resolve('./index')];
const gate = require('./index').handler;

let pass = 0, fail = 0;
async function t (name, run) {
  try { await run(); console.log('  ✅', name); pass++; }
  catch (e) { console.log('  ❌', name, '—', e.message); fail++; }
}
const eq = (a, b, m) => { if (a !== b) throw new Error(`${m}: got ${a}, want ${b}`); };
const KNOWN = 'd-pigment.html'; // bundle 內 minStage 4

(async () => {
  MOCK = { puzzleId: 'mingyan-forgery-coverup', stage: 4 };
  await t('到階(stage4>=4) 回內文 200', async () => {
    const r = await gate(ev({ case: 'mingyan', node: KNOWN }));
    eq(r.statusCode, 200, 'code');
    if (!r.body || r.body.length < 20) throw new Error('body 空');
    eq(r.headers['Access-Control-Allow-Origin'], ORIGIN, 'cors');
    eq(r.headers['Content-Type'], 'text/html; charset=utf-8', 'ctype');
  });

  MOCK = { puzzleId: 'mingyan-forgery-coverup', stage: 3 };
  await t('未到階(stage3<4) 403 不回內文', async () => {
    const r = await gate(ev({ case: 'mingyan', node: KNOWN }));
    eq(r.statusCode, 403, 'code');
    if (r.body.includes('鈦白') || r.body.includes('<')) throw new Error('洩內文');
  });

  MOCK = { puzzleId: 'other-case', stage: 9 };
  await t('別的 case 在跑(puzzleId 不符) 403', async () => {
    const r = await gate(ev({ case: 'mingyan', node: KNOWN }));
    eq(r.statusCode, 403, 'code');
  });

  MOCK = { puzzleId: 'mingyan-forgery-coverup', stage: 4 };
  await t('未知節點 403', async () => {
    const r = await gate(ev({ case: 'mingyan', node: 'nonexistent.html' }));
    eq(r.statusCode, 403, 'code');
  });
  await t('未知 case 403', async () => {
    const r = await gate(ev({ case: 'ghost', node: KNOWN }));
    eq(r.statusCode, 403, 'code');
  });
  await t('路徑穿越 node 被擋 403', async () => {
    const r = await gate(ev({ case: 'mingyan', node: '../cases.json' }));
    eq(r.statusCode, 403, 'code');
  });
  await t('缺參數 403', async () => {
    const r = await gate(ev({ case: 'mingyan' }));
    eq(r.statusCode, 403, 'code');
  });
  await t('OPTIONS 預檢 204 + CORS', async () => {
    const r = await gate(ev({}, { requestContext: { http: { method: 'OPTIONS' } } }));
    eq(r.statusCode, 204, 'code');
    eq(r.headers['Access-Control-Allow-Origin'], ORIGIN, 'cors');
  });
  await t('非白名單 Origin 回退預設網域', async () => {
    const r = await gate({ requestContext: { http: { method: 'GET' } },
      headers: { origin: 'https://evil.example' },
      queryStringParameters: { case: 'mingyan', node: KNOWN } });
    eq(r.headers['Access-Control-Allow-Origin'], ORIGIN, 'cors 回退');
  });

  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();
