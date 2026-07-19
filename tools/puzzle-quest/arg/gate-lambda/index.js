// sml-puzzle-arg — ARG 兔子洞「階段閘門」Lambda（見 PHASE2-DESIGN.md 線 2a / 子階段 2a-2）
//
// 唯一端點（公開、無認證、GET）:
//   GET /arg?case=<caseId>&node=<檔名>
//     → 讀「全服 stage」（Firestore sml_config/puzzle_stage，30–60s 快取）
//       僅當 puzzleId 相符 且 currentStage >= node.minStage 時，回傳該節點機密內文 HTML
//       否則一律 403（不回內文；front-end 殼收到非 2xx → 顯示 🔒 鎖頁）
//
// 為什麼要伺服器閘門：stage>=4 的 keystone 內文若烘在靜態檔，view-source 可繞。
// 2a-1 的 build.py 已把這些節點抽成「殼＋_secret_bundle.json」；本閘門按全服階段發放內文。
//
// 部署包內含（由 2a-3 打包步驟複製）:
//   bundles/<caseId>.json  = 該 case build 出的 _secret_bundle.json（{檔名:{minStage,html}}）
//   cases.json             = { "<caseId>": { "puzzleId": "..." } }（case → 全服 puzzleId 對映）
//
// 💰 成本：讀 Firestore stage（快取）+ 回內文，量級極小、免費額度內、預估 < $1/月；
//         判定純比階段、不燒 LLM（見 PHASE2-DESIGN.md §G）。無新 DDB 表。

const https = require('https');
const fs = require('fs');
const path = require('path');

const FIREBASE_PROJECT = process.env.FIREBASE_PROJECT || 'sml2026newscore';
// stage 讀取用的公開 API key（front-end 也用同一把讀同一份文件；可用 env 覆寫）
const FIREBASE_KEY = process.env.FIREBASE_KEY || 'AIzaSyAZaa_yHu7gsRaj71YL8x3REHfL_V5Tq4w';
const STAGE_DOC_URL = `https://firestore.googleapis.com/v1/projects/${FIREBASE_PROJECT}/databases/(default)/documents/sml_config/puzzle_stage?key=${FIREBASE_KEY}`;

// 全服 stage 快取（單一文件、全服共用）。TTL 45s：推進後最多 45s 生效，換來近乎零讀取成本。
const STAGE_TTL_MS = Number(process.env.STAGE_TTL_MS || 45000);
let stageCache = { at: 0, puzzleId: '', stage: 1 };

// case→puzzleId 對映 與 各 case 機密 bundle：模組載入時讀一次（部署包內靜態檔）
const CASES = loadJson(path.join(__dirname, 'cases.json'), {});
const bundleCache = {}; // caseId → {檔名:{minStage,html}}

// CORS：僅允許 ARG 網站所在網域（全服同步、閘門不需玩家 token）
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || 'https://image.boyplaymj.link')
  .split(',').map(s => s.trim()).filter(Boolean);

// node 檔名白名單字元（防路徑穿越/注入；bundle key 本就是這種形狀）
const NODE_RE = /^[A-Za-z0-9_.-]+$/;
const CASE_RE = /^[A-Za-z0-9_-]+$/;

function loadJson (p, fallback) {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); }
  catch (e) { console.error('loadJson fail', p, e.message); return fallback; }
}

function getBundle (caseId) {
  if (bundleCache[caseId] !== undefined) return bundleCache[caseId];
  const b = loadJson(path.join(__dirname, 'bundles', `${caseId}.json`), null);
  bundleCache[caseId] = b; // 含 null（不存在），避免每次重讀磁碟
  return b;
}

function corsHeaders (origin) {
  const allow = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'GET,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Vary': 'Origin'
  };
}

function reply (code, body, headers, origin) {
  return { statusCode: code, headers: { ...corsHeaders(origin), ...headers }, body: body || '' };
}
// 鎖頁：一律不吐內文（front-end 只看 r.ok，非 2xx 即顯示 🔒）
const locked = (origin) => reply(403, 'locked',
  { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' }, origin);

// 讀全服 stage。回 { puzzleId, stage }。
// 規則（fail-closed）：TTL 內回上一筆好快取；TTL 過期後 refresh 失敗（timeout/error/非2xx/壞JSON）
//   → 回 FAILCLOSED（stage 1、空 puzzleId＝鎖），**絕不沿用過期的舊 stage**。
//   不污染 stageCache.at → 下一個請求會立即重試，Firestore 復原後自動恢復。
const FAILCLOSED = { puzzleId: '', stage: 1 };
function fetchStage () {
  const now = Date.now();
  if (stageCache.at && now - stageCache.at < STAGE_TTL_MS) return Promise.resolve(stageCache);
  return new Promise((resolve) => {
    let settled = false;
    const done = (v) => { if (!settled) { settled = true; resolve(v); } };
    const req = https.get(STAGE_DOC_URL, (res) => {
      if (res.statusCode < 200 || res.statusCode >= 300) {
        console.error('stage http', res.statusCode);
        res.resume(); // drain
        return done(FAILCLOSED);
      }
      let data = '';
      res.on('data', c => { data += c; });
      res.on('end', () => {
        try {
          const f = (JSON.parse(data).fields) || {};
          const puzzleId = (f.puzzleId && f.puzzleId.stringValue) || '';
          const stage = parseInt((f.stage && f.stage.integerValue) || '1', 10) || 1;
          stageCache = { at: Date.now(), puzzleId, stage };
          done(stageCache);
        } catch (e) {
          console.error('stage parse fail', e.message);
          done(FAILCLOSED); // 壞 JSON：不寫快取、不放行
        }
      });
    });
    req.on('error', (e) => { console.error('stage fetch fail', e.message); done(FAILCLOSED); });
    req.setTimeout(3000, () => { req.destroy(new Error('timeout')); done(FAILCLOSED); });
  });
}

exports.handler = async (event) => {
  const h = (event && event.headers) || {};
  const origin = h.origin || h.Origin || '';
  const method = (event.requestContext && event.requestContext.http && event.requestContext.http.method)
    || event.httpMethod || 'GET';

  if (method === 'OPTIONS') return reply(204, '', {}, origin);
  if (method !== 'GET') return reply(405, 'method', { 'Content-Type': 'text/plain' }, origin);

  const q = (event && event.queryStringParameters) || {};
  const caseId = String(q.case || '').trim();
  const node = String(q.node || '').trim();

  // 參數硬驗（形狀 + 白名單 + 長度上限）——不符一律鎖，不洩漏原因差異
  if (!CASE_RE.test(caseId) || !NODE_RE.test(node)) return locked(origin);
  if (caseId.length > 64 || node.length > 128) return locked(origin);

  // 未知 case 先擋：只對 cases.json 已知 key 讀 bundle，避免 public endpoint 灌任意 key 撐爆 bundleCache
  const caseCfg = CASES[caseId];
  if (!caseCfg) return locked(origin);
  const bundle = getBundle(caseId);
  if (!bundle) return locked(origin);

  const entry = bundle[node];
  if (!entry) return locked(origin); // 未知節點：當作鎖（不區分「不存在」與「未解鎖」）

  const { puzzleId, stage } = await fetchStage();

  // 全服當前跑的必須就是這個 case，且階段已到本節點門檻
  if (puzzleId !== caseCfg.puzzleId) return locked(origin);
  const minStage = Number(entry.minStage || 1);
  if (stage < minStage) return locked(origin);

  return reply(200, entry.html, {
    'Content-Type': 'text/html; charset=utf-8',
    // 內文可短快取（階段只前進、單向）；CDN/瀏覽器層再快取無妨
    'Cache-Control': 'public, max-age=30'
  }, origin);
};
