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

## 2a-2（待做）：閘門 Lambda `sml-puzzle-arg` + HTTP API
**合約（給實作＋Codex 驗）**：
- **端點**：`GET /arg?case=<case>&node=<檔名>`
- **邏輯**：
  1. 讀全服 stage：Firestore `sml_config/puzzle_stage`（REST＋public key，快取 30–60s）；`puzzleId` 需等於該 case 的 puzzleId，否則視為 stage 1。
  2. 查 `bundle[node].minStage`；`currentStage >= minStage` → 回 `bundle[node].html`（200, `text/html; charset=utf-8`）；否則 **403**（不回內文）。
  3. `node` 不在 bundle → 404。
- **CORS**：`Access-Control-Allow-Origin: https://image.boyplaymj.link`。
- **內文來源**：`_secret_bundle.json` bundle 進 Lambda 部署包（build.py 產）；**更新內文＝重新 build＋重部署 Lambda**。
- **回填**：Lambda 上線後把 HTTP API URL 填進 `mingyan-world.json` config `gateUrl`，重 build（殼才知道去哪 fetch）。
- **驗收**：直打 `?node=_ca9558ea.html` 帶低 stage→403；stage 到→200 且內容正確；跨 origin CORS 對；無 node→404。

## 💰 成本（同 PHASE2-DESIGN §G）
Lambda＋HTTP API，讀 stage 可快取，無 LLM、無新 DDB（內文 bundle 進部署包）→ 免費額度內、<$1/月。
