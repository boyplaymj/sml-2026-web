# Phase A · ARG 產生器引擎 — Codex 驗收單

**標的**：`tools/puzzle-quest/arg/build.py`（產生器）＋ `mingyan-world.json`（世界圖）＋ `dist/mingyan/`（產物 50 頁）。
**請 Codex**：獨立重跑 `python3 audit.py`、逐條回 pass/fail＋findings；並人工審下列引擎邏輯。

## 我方自審結果（audit.py，全通過）
```
A1 HTML檔數(50)==manifest節點數(50)                       ✅
A2 world.json重算檔名==產物檔名(hash穩定)                  ✅
A3 無指向不存在頁的href                                    ✅
A4 作者文字經 html.escape 逃逸(不破版/防注入)             ✅
```

## Codex 逐條複驗清單

### 1. hash 檔名穩定性
- [ ] `filename()`：`hidden` 節點＝`_` + sha1("arg-"+salt|id)[:8] + ".html"；`file` 覆寫優先。
- [ ] 同一 world.json 重複 build，隱藏頁檔名不變（否則玩家撞見的網址會漂）。
- [ ] **風險點**：若作者改了某節點 `id`（未設 `salt`），其 hash 檔名會變 → 舊連結／WALKTHROUGH 失效。確認這點有在 README/WALKTHROUGH 標註。

### 2. 階段閘門（page_script）
- [ ] 整頁閘門：`NODE_STAGE > 當前階段` → `lock()` 換掉 `#pagebody`。
- [ ] 逐則閘門：`[data-cstage]` 元素階段未到 → `display:none` 且不計入樓層數（`cmt-cnt`）。
- [ ] `?stage=N`(1–9) 覆寫；未帶時先 `applyStage(1)`（避免抓 Firestore 前閃出後段內容）→ fetch 後再套真實階段。
- [ ] **風險點**：Firestore fetch 失敗（離線/CORS）時 fallback 為 stage 1（最保守）——確認 keystone 頁在 fetch 失敗時是「鎖住」而非「洩漏」。

### 3. 檢視原始檔（showSrc）
- [ ] 顯示 `document.documentElement.outerHTML`（含 HTML 註解）→ 等同瀏覽器 view-source、手機可用。
- [ ] HTML 註解上色（`.cm`）只是視覺提示，不改變內容。
- [ ] **安全**：所有作者輸入都過 `esc()`(html.escape, quote=True)；確認沒有任一渲染路徑把作者字串直接塞進 HTML 而未逃逸（尤其 `rawHtml`、`caption`、`text`、`body`）。`note.rawHtml` 是**唯一**信任原始 HTML 的欄位（僅作者用、無使用者輸入）——確認世界圖沒濫用。

### 4. 連結解析與 see 欄位
- [ ] `linkref()`/`linkref_row()`：node id → 檔名；指向不存在節點時 build 直接 `SystemExit`（fail-fast，不產出斷鏈）。
- [ ] `see:[[ref,label]]` 通用相關連結欄：跨階段連結帶 `data-cstage`（會被閘門隱藏）。
- [ ] `comment.link.stage` 可 > `comment.stage`（留言先出現、連到的證物晚點才通）——確認渲染有分別掛 `data-cstage`。

### 5. 清舊檔
- [ ] `main()` 先刪 out 目錄既有 `*.html`/`_manifest.json` 再產出（避免改檔名後留 stale 頁被玩家撞見）。
- [ ] **風險點**：`--out` 指到非預期目錄時會刪該目錄 html。確認只刪 `.html`/`_manifest.json`、不遞迴、不刪其他。

### 6. 產物正確性
- [ ] `_manifest.json` 為 QA 用，**部署時不上傳**（含隱藏頁清單，會洩漏答案位置）。README 已標。
- [ ] 逐頁 `<title>`、麵包屑、footer 虛構聲明都在。

## 已知限制（非 bug，確認可接受）
- 隱藏頁靠「不被連結＋hash 檔名＋S3 無目錄列表」防枚舉；不是加密。玩家拿到 URL 就能看（本來就是 ARG 設計）。keystone 額外靠階段閘門鎖到 S4。
- 產物是純靜態，$0 成本；階段狀態依賴既有 Firestore `sml_config/puzzle_stage`。
