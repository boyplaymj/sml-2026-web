# 每日任務 — 階段 C：後台管理頁（交 Codex 查驗）

## 已上線

| 項目 | 值 |
|---|---|
| 管理頁 | `daily_quest_admin.html`（458 行,純靜態單檔）@ 甜甜遊戲館 |
| URL | https://sweetbot-games.web.app/daily_quest_admin.html （HTTP 200 ✅） |
| NAV | index.html「🎁 獎勵 / 投注」段新增「📋 每日任務」項（已上線） |
| 接的端點 | `https://3v6m67eo5l.execute-api.ap-southeast-1.amazonaws.com`（階段 B Lambda） |
| 檔案位置 | `/opt/sml/sweetbot-site/public/daily_quest_admin.html`（正本；Firebase hosting:sweetbot） |

生成方式：Fable5 照 `earthquake_admin.html` 範本產出 → Claude 覆核 + headless 載入驗證。

## Claude 覆核結果（已驗）

- **語法**：抽出 inline module `node --check` 通過。
- **headless 載入**（Playwright，file://）：無 console error（排除離線 firebase 網路失敗）、頂層綁定未拋例外、gate 正常渲染（截圖確認同 earthquake 深色主題）。
- **API 契約對照 Lambda**（逐一核對）：
  - `api('list')` → 讀 `r.tasks` ✅
  - `api('saveTask',{task})` → 包在 `task`（新增/編輯/啟用 toggle 三處都對）✅
  - `api('deleteTask',{key})` ✅
  - `api('preview',{vipLevel:Number 0..3})` ✅
  - endpoint = `3v6m67eo5l` ✅
- **auth 移植**：initializeApp / getIdToken / `Authorization: Bearer` / `{action,...payload}` body，與 earthquake_admin 一致。
- **event 三層建構器**：分類 A~E → 事件 → 參數（game 下拉 12 款 / text 框）；`buildEvent()` 組字串符合 Lambda `ALLOWED_EVENT_RE`；編輯用 `parseEventToBuilder()` 反解，反解失敗存 `rawEvent` 並黃字警示、`builderTouched` 決定送 raw 或重組（舊資料 event 不會被誤洗）。
- **表單正規化**：title 必填、event 必填、target/weight 夾 ≥1、prop 型 propId 必填、key 空 → 後端自動配號。
- **啟用 toggle**：直接 `saveTask` 送整筆 + 翻轉 enabled，失敗還原勾選。
- **預覽區**：VIP 0~3 → drawCount/pool/totalWeight chip + 難度佔比堆疊條 + 各任務 appearProb 長條（依後端排序）。

## Codex 查驗點（建議拿真 Firebase 帳號端到端）

1. 用白名單 Google 帳號登入 → 應看到 13 則 seed 任務清單。
2. **list**：13 筆、欄位顯示正確、disabled 列灰底。
3. **新增**：key 留空 → 存成 `q_custom_1`；event 用三層選單組（如 A→game_win:指定→bjm = `game_win:bjm`）；存後清單出現。
4. **編輯**：改 weight/reward → 存 → 生效；event 反解回選單當前值正確。
5. **啟用 toggle**：切某任務 enabled → DDB `enabled` 對應改變（配合階段 B 的 toBool 修正）。
6. **刪除**：刪掉剛新增的 `q_custom_1`。
7. **preview**：VIP=0 抽 3 題、VIP=3 抽 6 題；appearProb 與 weight 正相關；停用任務不入池；difficultyMix 比例合理。
8. NAV 從遊戲館首頁可正確進入。

## 已知/待確認（Fable5 提出，Claude 註記）

- prop 型仍保留 rewardExp 欄（Lambda 接受、無害）。
- `quest_complete` 等少數事件中文文案按欄位名推敲,語義若有出入可再調（不影響功能）。

## 尚未做

- D：bot 引擎（QuestTracker + 懶抽 + `!每日任務` 面板 + 埋 4 事件）
- E：streak(P2) + VIP 加題(P3)
