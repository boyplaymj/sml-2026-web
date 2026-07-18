# 日本マップコード 產生器 — 設計冊（甜甜功能版）

> 個人版 PWA 已上線（`image.boyplaymj.link/mapcode/`）。本冊是把它做成**甜甜 bot 功能 + 遊戲館後台管理**、並開放社群用戶使用的設計。
> 核心價值：日本自駕時，把 Google 地圖地點 / 中日文名稱 → 車機能吃的マップコード，並解掉「同名抓錯、碼不準」兩大痛點。

---

## 0. 決策鎖定（使用者已拍板 2026-07-15）

| # | 項目 | 決定 |
|---|---|---|
| 1 | 指令 | **`!map`** |
| 2 | 存地點 | **要**（出發前先查好存起來，行前清單） |
| 3 | 對象 | **未來開放社群用戶**（先私人頻道測，再開放） |
| 4 | 後台 | 甜甜**遊戲館後台新增管理分頁**（照 `mahjong_tycoon_admin.html` 模式） |
| 5 | 名稱搜尋 | **要**（中/日文名稱 → 自動找地標 → 出碼） |

---

## 1. 三種輸入 → 一個碼

1. **Google 地圖連結**（含短網址 `maps.app.goo.gl`）
   - 短網址由**甜甜後端 follow redirect 展開**（伺服器端無 CORS 限制，這是 PWA 做不到、甜甜能贏的關鍵）。
   - 從展開後 URL 抓**真圖釘 POI**（`!3d`緯 / `!4d`經，各自獨立抓，順序無關），不抓地圖中心 `@`。
2. **座標**：直接貼 `緯度, 經度`。
3. **名稱搜尋**（中/日文）：`!map 東京駅` / `!map 大阪城`。

### ⚠️ 名稱搜尋一律走免費 OSM（Nominatim），不用 Google API
- 實測（2026-07-15）OSM 對 東京駅/東京車站/大阪城/白い恋人パーク/五稜郭 都找得到。
- **不用 Google Maps API 的原因**：（a）Google ToS 禁止把其地理編碼結果拿去產生他家導航碼、且禁止儲存/快取 → 跟「存地點」直接衝突；（b）按次計費，公開規模燒錢。
- 逆地理編碼（反問「○○県○○市」用）同樣走 OSM / 國土地理院，免費。

### 🎯 同名消歧（補「抓錯地點」痛點）
- 名稱搜尋**回傳前 2–3 個候選**，每個顯示 `縣市 + 附近`，讓用戶用按鈕選。
- 實測反例：`札幌時計台` OSM 第一筆是**栃木県日光市的同名複製品**（非北海道本尊）→ 若只取第一筆就錯。故**強制多候選選擇**，不自動採用第一筆。

---

## 2. 指令與互動流程（一指令開場、之後全按鈕）

```
用戶：!map 大阪城
甜甜：🔎 找到這些地點，哪一個？
      [① 大阪府 大阪市 中央区・大阪城]
      [② 東京都 …（若有同名）]
      [✏️ 都不是，改貼連結/座標]
用戶：（點 ①）
甜甜：📍 大阪府 大阪市 中央区（附近：大阪城）
      ┌─────────────────────
      │ マップコード  1 378 073
      │ 高精度        1 378 073*19    偏移 ~2m
      └─────────────────────
      [💾 存起來] [🎯 高精度] [🗺️ 看地圖] [🔁 重查]
```
- 貼連結/座標則跳過候選、直接進確認卡。
- 「存起來」→ 問一句備註名（或直接用搜尋詞）→ 寫入該用戶清單。
- `!map` 無參數 or `!map 清單` → 列出我存的地點（分頁按鈕），每筆可一鍵複製碼。
- 碼放程式碼區塊，手機 Discord 點一下複製。

---

## 3. 引擎（重用，不重寫）

- 直接沿用個人版 `mapcode.js`（encode 改編 MIT `bespired/mapcode` + 自寫 decode round-trip）+ `zonecoords.js`（1163 zone 表）。
- **移植到 Node**：把 `window.*` 改成 module export，其餘不動。已本地驗證 encode 對「札幌時計台」base 碼（zone+block+unit）命中官方 `9 522 206`，`*core` 高精度會在同格內小漂 → 對用戶**主打基本碼、高精度標 best-effort + 顯示偏移**。
- 出碼一律附 round-trip 偏移（>25m 標警告），維持個人版的「看得到準不準」。

---

## 4. 資料模型（DynamoDB，PAY_PER_REQUEST）

**表 A：`sweetbot-mapcode-saved`（用戶存的地點）— 已上線 P3**
- PK `pk` = `userId`（discordId）；**單筆 item 存整份清單**：`items[]`（陣列，上限 20 筆）+ `updatedAt`。
- 每筆 `items[i]`：`label`, `near`, `base`(基本碼), `hi`(高精度碼), `lat`, `lon`, `ts`。
- 為何單 item 不用 SK 多 item：清單量極小（≤20），一次 get / 一次 put 就搞定，最省 RCU/WCU。
- 用途：行前清單。互動：結果卡 **💾 存起來** → 加進清單；面板 **📋 我的清單**（ephemeral，只有本人看得到）→ 下拉刪除。

**表 B：`sweetbot-mapcode-cache`（名稱/座標 → 結果快取）**
- PK `qkey`（正規化查詢字串 or 座標格點）, 屬性：`candidates`(JSON), `ts`, TTL 30–90 天
- 用途：公開規模下**避免重複打 OSM**（尊重 Nominatim 用量政策 + 加速）。MVP 可先只做表 A，公開前再加表 B。

（座標/碼運算純函式，不佔表。）

---

## 5. 後台管理分頁（遊戲館）— P4 已上線（2026-07-15）

新頁 `mapcode_admin.html`（已上線 sweetbot-games.web.app、已註冊 index.html 卡片）。
**架構決定**：不新開 Lambda/APIGW；設定走 Firestore **`sml_config/mapcode`**（同 bingo/flowertime 模式），甜甜 `MapCode.js` REST 讀 + 60s 快取。後台頁用 Firebase compat 直接讀寫該 doc（`sml_config` 世界可寫 → 甜甜端做 sanity 夾限把關）。
- ✅ **kill switch**：`sml_config/mapcode.disabled=true` → `!map` 回「維護中」不開面板。（原設計寫 env `MAP_DISABLED` 改為 Firestore 旗標，才能後台一鍵切、免重啟。）
- ✅ **精選地標覆蓋庫**：`overrides:[{name,lat,lon,label}]`。名稱搜尋先查此庫，命中（正規化完全相等 或 覆蓋名含查詢）→ 釘本尊座標，治同名抓錯。甜甜端夾限日本範圍（緯 24–46/經 122–154）防下毒。後台頁含「貼 Google 連結/座標自動填」。
- ✅ **用量卡**（2026-07-15 補上）：`!map` 埋點 → 甜甜記憶體累加、每 60 秒批次 flush 進 Firestore `sml_config/mapcode_usage`（保留最近 14 天）。後台頁畫 tiles（開場數/名稱搜尋/連結座標/覆蓋命中/**OSM 命中率**）+ 每日明細表。埋點：`open→opens`、`resolveAndShow→linkCoord`、`searchAndShow→srchName`＋`ovHit`/`osmHit`/`osmMiss`。

---

## 6. 法律 / 免責（隨功能顯示）

- 「マップコード」為 **DENSO 註冊商標**、官方演算法需付費授權；本功能用**社群逆向**演算法，**非官方、近似值**，回覆附免責一行。
- **現況（免費社群福利）= 低風險**：沒賣、沒上架、沒當商品 → 實務可接受，同個人版等級。
- **翻臉線**：一旦要**收費 / 獨立上架 / 商品化**，須回頭談 **ZENRIN Maps API 授權**（初期約 36 萬円＋月 6 萬起）。
- 名稱搜尋/逆地理編碼**用 OSM 不用 Google API**，避開 Google ToS（見 §1）。OSM 需標註 attribution。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：DDB 新表 `sweetbot-mapcode-saved`（已建，PAY_PER_REQUEST；＋公開後 `sweetbot-mapcode-cache`）、admin Lambda 加 action。量級極小（每次存/讀清單各 1 RCU/WCU，預估 < $1/月）。
- **外部 API**：OSM Nominatim / 國土地理院 = **免費**（非付費 API）；靠表 B 快取降低請求量、尊重 Nominatim 用量政策（≤1 req/s、須 attribution）。
- 所有新表 PAY_PER_REQUEST；**無 LLM / 無付費 API，故免帳本封頂四件套**。
- 若日後加 LLM（如中文→日文正規化、AI 消歧），回本規範補齊「四件套」。

---

## 7. 分階段實作（每階段 < 25 分，可交 Codex 驗）

- **P0** 引擎移植：`mapcode.js`+`zonecoords.js` → Node module，單元測試對官方 base 碼。
- **P1** `!map` 座標/連結（含短網址後端展開）→ 確認卡 + 出碼 + 偏移。私人頻道測。
- **P2** 名稱搜尋 + 多候選消歧按鈕（OSM）。
- **P3** ✅ 已完成上線（2026-07-15）：存地點（表 A，單 item/user 上限 20）+ 面板「📋 我的清單」ephemeral 檢視 + 下拉刪除。
- **P4** ✅ 完成上線（2026-07-15）：遊戲館後台頁 `mapcode_admin.html` — kill switch + 精選地標覆蓋庫（`sml_config/mapcode`）+ 用量卡（`sml_config/mapcode_usage`，甜甜 60s 批次 flush）。
- **P5** 公開前：加快取表 B、attribution、開放頻道與權限。

## 8. 未定 / 待議
- 中文名稱命中率（車站「駅↔車站」用字差異）→ 是否加輕量同義詞正規化（先觀察 OSM 命中，不夠再說）。
- 精選地標覆蓋庫是否 MVP 就上（治同名抓錯最有效，但多一張維護表）。
- 存地點上限 / 分類（行程分天？）→ 看實際使用再加。
