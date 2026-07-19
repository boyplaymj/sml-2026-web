# Phase 2a · 網站伺服器端加固（keystone 閘門）— Codex 驗收單

**目標**：堵掉 Codex High——純靜態頁把 S4 secret 送到瀏覽器、view-source 可提前讀。
**做法**：stage≥4 節點內文**不烘進靜態檔**，收進 `_secret_bundle.json`（不部署 S3），由伺服器閘門按**全服 stage**發放。

## 2a-1（已完成）：build.py 產「殼＋bundle」
- `build.py` 加 `GATE_FROM`（預設 4）＋ `--gate-from N`（0＝關閉全靜態）。stage≥GATE_FROM 節點：
  - 靜態檔只留「殼」（chrome＋`<div id="gate-lock">🔒 載入中…</div>`），`<title>` 用站名不洩節點名；
  - 真內文（crumb＋title＋body）進 `SECRET[檔名]={minStage, html}` → `dist/mingyan/_secret_bundle.json`；
  - 殼載入時讀 Firestore 全服 stage：`cur<minStage`→鎖；`cur>=minStage`→`fetch(gateUrl?case&node)` 注入。
- `--dev` 版**不 gate**（全靜態，供作者預覽/截圖）。
- 被 gate 的 7 頁：`d-electrical(_ca9558ea)`、`d-ledger(_624caea4)`、`d-pigment`、`d-access-named`、`d-timeline`、`del-electrical`、`del-ledger`。

### 我方自審（audit.py 全綠，新增 B6/B7）
```
B6 [加固] 任何靜態html grep 真 core.any(method+motive) → 零命中 ✅（S4內文全不在靜態檔）
B7 [加固] 7個stage≥4節點皆為殼(含gate-lock、無keystone)且入bundle;bundle==7 ✅
B2 還原鏈:gated(del-electrical/del-ledger)→線索移入bundle、靜態殼不洩;非gated(del-safety/del-zhuo S2/S3)維持靜態 ✅
B1/B3/B4/B5 一如既往 ✅
```
> 效果：連瀏覽器原生 view-source 在 stage1 也讀不到 S4 keystone（不在任何靜態檔）；還原鏈的隱藏網址也移到 bundle，到 stage4 才由閘門隨內文發放。

### Codex 複驗 2a-1
- [ ] `python3 build.py mingyan-world.json && python3 audit.py` 全綠（尤其 B6：任何靜態檔零 keystone）。
- [ ] `_secret_bundle.json` 含 7 頁、每頁有 `minStage`；`dist` 內**無**其他洩漏路徑。
- [ ] 部署排除：README 已改 `--exclude "_*.json"`；確認 `_secret_bundle.json` 不會上 S3。
- [ ] `--dev` 版全靜態（供預覽）、正式版 gated——兩者行為如標示。
- [ ] 殼的 `<title>`／麵包屑不洩露節點身分（避免從標題猜內容）。

## 2a-2（已完成，待 Codex 複驗）：閘門 Lambda `sml-puzzle-arg`
**原始碼**：`gate-lambda/`（`index.js`／`cases.json`／`bundles/<case>.json`／`package.sh`／`test.js`）。零 npm 依賴（Node 內建 `https`/`fs`/`path`）。本階段**只寫程式、未建 AWS**（建 Lambda/HTTP API/接線＝2a-3）。
- **端點**：`GET /arg?case=<case>&node=<檔名>`
- **邏輯**：
  1. 讀全服 stage：Firestore `sml_config/puzzle_stage`（REST＋public key，45s 快取）；`puzzleId` 需等於 `cases.json[case].puzzleId`，否則一律鎖。
  2. 查 `bundles/<case>.json` 的 `[node].minStage`；`currentStage >= minStage` → 回 `[node].html`（200, `text/html; charset=utf-8`）；否則 **403**（不回內文）。
  3. `node`/`case` 走白名單 regex（擋路徑穿越）；**未知 node／未知 case → 403（非 404）** — 刻意不區分「不存在」與「未解鎖」，避免用狀態碼列舉哪些節點存在。
  4. stage 讀失敗/逾時/HTTP非2xx/壞JSON → **fail-closed**（回 `{puzzleId:'',stage:1}`＝鎖），**絕不沿用過期舊 stage**；不污染快取 `at`，下個請求立即重試、Firestore 復原自動恢復。（TTL 內才用上一筆好快取）
- **CORS**：`Access-Control-Allow-Origin` 只給 `https://image.boyplaymj.link`（非白名單 Origin 回退此預設）；`OPTIONS`→204。
- **內文來源**：`bundles/<case>.json`＝build 的 `_secret_bundle.json`，`package.sh` 打包時同步進部署包；**更新內文＝重 build＋重跑 package.sh＋重部署 Lambda**。
- **回填（2a-3）**：Lambda 上線後把端點 URL 填進 `mingyan-world.json` config `gateUrl`，重 build（殼才知道去哪 fetch）。現況 `gateUrl:""` → 殼顯示「尚未接上伺服器」鎖頁（預期）。
- **本地驗收**：`node gate-lambda/test.js` → **14 項全綠**（到階 200／未到階 403／跨案 403／未知 node+case 403／路徑穿越 403／缺參數 403／OPTIONS 204／Origin 回退／**fail-closed×4**（先stage4成功後 error→403 不沿用舊cache／timeout／HTTP 503／壞JSON）／超長 case+node 403）。

### Codex Round 1 findings → 已修（2026-07-19）
- **High｜fail-closed 沒成立（沿用過期 stage4 cache 放行）**：已修 — `fetchStage()` 過期後 refresh 失敗一律回 `FAILCLOSED`，不再沿用舊快取；補 HTTP 非2xx、壞JSON、timeout 分支。新增測試「先stage4成功→Firestore error→403」即 Codex 原 repro，現綠。
- **Medium｜未知 case 先讀 bundle 並 cache null（可灌 key）**：已修 — handler 先 `if(!caseCfg) return locked` 才 `getBundle`；bundleCache 只會存 `cases.json` 已知 key。另加 `case<=64`／`node<=128` 長度上限。

### Codex 複驗 2a-2（修正後）
- [ ] 重看 `fetchStage()`：TTL 內用好快取、過期失敗回 FAILCLOSED、不污染 `at`；四類失敗（error/timeout/http/badjson）皆不放行。
- [ ] 低 stage／跨案／未知節點／讀失敗回應 body 不含任何 keystone 字（鈦白/贗品/接地/洗錢）。
- [ ] unknown case 不再寫 bundleCache；長度上限有效。
- [ ] `node test.js` 14/14、`./package.sh` 產 zip 內含 index.js/cases.json/bundles。

## 2a-3（已上線 2026-07-19）：建 AWS ＋ 部署 ＋ E2E
使用者批准後執行，Codex R2 已放行。**基礎設施（ap-southeast-1）**：
- Lambda `sml-puzzle-arg`（nodejs20.x, 128MB, timeout 10s）；exec role `sml-puzzle-arg-role`（僅 AWSLambdaBasicExecutionRole，無 DDB/密鑰）。
- HTTP API `sml-puzzle-arg`（id `uodv2enht1`），**單一路由 `GET /arg`**，AWS_PROXY payload 2.0，`$default` stage auto-deploy。
- 端點 `gateUrl` = `https://uodv2enht1.execute-api.ap-southeast-1.amazonaws.com/arg` → 已回填 `mingyan-world.json` config.gateUrl 並重跑 build.py（50 頁、audit 全綠）。
- S3：`aws s3 sync dist/mingyan/ s3://boyplaymj-image/pq/case13/ --exclude "_*.json"`（50 檔，`_secret_bundle.json` 未上傳，已驗 S3 無此物件）；CloudFront E2IJWN6FWT2XYG 失效 `/pq/case13/*`。

**Codex 6 檢查逐項驗（皆過）**：
1. ✅ zip 由 `package.sh` 現場打包。
2. ✅ 只提供 `GET /arg`（無 `$default` catch-all）。
3. ✅ `gateUrl` 回填後重跑 `build.py`。
4. ✅ S3 deploy `--exclude "_*.json"`；dry-run 確認上傳集無 `_*.json`，S3 實查無 `_secret_bundle.json`。
5. ✅ 直打 API：stage<4／跨案／未知節點 → 403 且 body 無 secret（live）；`_probe` 暫時案（映射現行 live puzzleId、minStage1）直打 → 200 回內文，證 200 分支 wiring 通，測完移除重部署（`_probe` 現 403）。
6. ✅ 部署後 view-source 靜態殼（`d-pigment.html` 等）真 keystone 零命中（audit B6 authoritative 綠；手動 grep 命中的 `接地` 是 stage3 安全紀錄紅鯡魚「接地連續性正常」，不在 solution.core method/motive any-set）。

**E2E（live CDN）**：`forum.html` 200；gated 殼 `d-pigment.html` 200、view-source 零 keystone、指向 gate URL；殼 runtime 打 gate → 403（現行 live `puzzle_stage`=`hongchang-poison-coverup`，mingyan 未 active → 正確鎖）。待 mingyan 真正開案跑到 stage4，內文才由閘門發放。

## 💰 成本（同 PHASE2-DESIGN §G）
Lambda＋HTTP API，讀 stage 可快取，無 LLM、無新 DDB（內文 bundle 進部署包）→ 免費額度內、<$1/月。
