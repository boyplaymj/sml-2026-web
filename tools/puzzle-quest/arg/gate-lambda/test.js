// 本地離線測試：mock Firestore stage 讀取，驗閘門發放/鎖定行為（node test.js）
const https = require('https');
const { EventEmitter } = require('events');

// MOCK.mode: 'ok'(預設) | 'error'(網路錯) | 'http'(非2xx) | 'badjson'
let MOCK = { puzzleId: 'mingyan-forgery-coverup', stage: 4, mode: 'ok' };
https.get = (url, cb) => {
  const req = new EventEmitter();
  req.setTimeout = () => {}; req.destroy = () => {};
  if (MOCK.mode === 'error') { process.nextTick(() => req.emit('error', new Error('mock net fail'))); return req; }
  const res = new EventEmitter();
  res.statusCode = MOCK.mode === 'http' ? 503 : 200;
  res.resume = () => {};
  cb(res);
  const body = MOCK.mode === 'badjson'
    ? '<<not json>>'
    : JSON.stringify({ fields: {
        puzzleId: { stringValue: MOCK.puzzleId },
        stage: { integerValue: String(MOCK.stage) }
      }});
  process.nextTick(() => { res.emit('data', body); res.emit('end'); });
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

  // ── fail-closed：先成功 cache stage4，再 Firestore 失敗 → 不可沿用舊 stage 放行 ──
  await t('先stage4成功後 Firestore error → 403(不沿用舊cache)', async () => {
    MOCK = { puzzleId: 'mingyan-forgery-coverup', stage: 4, mode: 'ok' };
    let r = await gate(ev({ case: 'mingyan', node: KNOWN }));
    eq(r.statusCode, 200, '先成功');
    MOCK.mode = 'error';
    r = await gate(ev({ case: 'mingyan', node: KNOWN }));
    eq(r.statusCode, 403, 'error後');
    if (r.body.includes('鈦白') || r.body.includes('贗品')) throw new Error('洩內文');
  });
  await t('Firestore timeout(error) → 403', async () => {
    MOCK = { puzzleId: 'mingyan-forgery-coverup', stage: 4, mode: 'error' };
    const r = await gate(ev({ case: 'mingyan', node: KNOWN }));
    eq(r.statusCode, 403, 'code');
  });
  await t('Firestore HTTP 503 → 403', async () => {
    MOCK = { puzzleId: 'mingyan-forgery-coverup', stage: 4, mode: 'http' };
    const r = await gate(ev({ case: 'mingyan', node: KNOWN }));
    eq(r.statusCode, 403, 'code');
  });
  await t('Firestore 壞 JSON → 403', async () => {
    MOCK = { puzzleId: 'mingyan-forgery-coverup', stage: 4, mode: 'badjson' };
    const r = await gate(ev({ case: 'mingyan', node: KNOWN }));
    eq(r.statusCode, 403, 'code');
  });
  MOCK = { puzzleId: 'mingyan-forgery-coverup', stage: 4, mode: 'ok' };
  await t('超長 case/node → 403', async () => {
    let r = await gate(ev({ case: 'm'.repeat(65), node: KNOWN }));
    eq(r.statusCode, 403, 'long case');
    r = await gate(ev({ case: 'mingyan', node: 'n'.repeat(129) + '.html' }));
    eq(r.statusCode, 403, 'long node');
  });

  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();
