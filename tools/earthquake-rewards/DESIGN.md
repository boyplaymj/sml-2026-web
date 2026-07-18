# 甜甜「地震速報領牙齒」— 設計冊 v0.1

> 狀態：**決策已定案，架構草案，待交 Codex 實作。**
> 核心概念：接**中央氣象署（CWA）真實地震資料**，只要台灣有**有感地震**發生，就在指定頻道自動冒出一個限時領獎事件 —— 像隨機事件一樣不停冒，但**不是亂數，是現實驅動**。順便讓玩家知道「喔，原來剛剛在晃」。
> 關聯：[[隨機事件翻修 tools/random-event-renovation]]（獎勵/按鈕慣例沿用）、[[成本控管 tools/COST_CONTROL.md]]。

---

## 1. 玩法（使用者已定案）

1. **觸發**：台灣**任何有感地震**（大小通吃）發生 → 頻道自動貼一張「地震卡片」+ 領獎按鈕。
2. **領取窗口**：小地震 **45 秒**；大地震（震度 5 以上）**90 秒**。過期按鈕失效。
3. **一人一次**：每個地震（以**地震編號**為準）每位玩家只能領一次。
4. **獎勵 = 震度**：震度幾級就領幾顆牙齒（見 §3 對照表）。
5. **兩層事件**：
   - 🟢 **小地震（震度 1~4）「快閃領牙齒」**：單顆按鈕、純臨場感。
   - 🔴 **大地震（震度 5 以上）「防災問答」**：卡片附一題**地震防災二選一**，答對牙齒 **×2**、答錯仍給基礎牙齒 + 公布正解，答完顯示「🧠 地震小知識」。
6. **不洗版**：只發到**指定頻道**（沿用現有頻道，`EARTHQUAKE_CHANNEL_ID` 設定；待填）。

---

## 2. 資料源：中央氣象署開放資料平台（CWA Opendata）

- 官方、**免費**；註冊 email 取一組 **Authorization Key**（`https://opendata.cwa.gov.tw/user/authkey`）。存 SSM `/sml/cwa/opendata-key`。
- **同時吃兩個資料集**才能大小通吃，用**地震編號**合併去重：

| 資料集 ID | 內容 | 頻率 |
|---|---|---|
| **E-A0015-001** 顯著有感地震報告 | 規模較大 / 廣泛有感 | 約每週幾次 |
| **E-A0016-001** 小區域有感地震報告 | 小區域有感（震度多在 1~3） | 一天可能好幾次 |

- 端點：`GET https://opendata.cwa.gov.tw/api/v1/rest/datastore/{datasetId}?Authorization={key}&limit=5&sort=time`
- 回傳含每筆 `EarthquakeNo`（地震編號，去重主鍵）、`EarthquakeInfo`（`OriginTime` 發生時間、`MagnitudeValue` 規模、`FocalDepth` 深度、`Epicenter.Location` 震央地名、經緯度）、`Intensity`（各地最大震度，取全國**最大震度** `MaxIntensity` 當獎勵依據）。
- ⚠️ CWA 只發布**有感**地震 → 天生「有震度才有事件」，無感微震不會洗版，剛好。
- ⚠️ 是**輪詢**不是即時推播：報告在地震後幾分鐘發布，對「領牙齒」無影響。

---

## 3. 獎勵公式（震度 → 牙齒）

| 最大震度 | 牙齒 | 層級 |
|---|---|---|
| 1 / 2 / 3 / 4 | 1 / 2 / 3 / 4 🦷 | 🟢 快閃 |
| 5弱 / 5強 | 5 / 6 🦷 | 🔴 防災問答 |
| 6弱 / 6強 | 7 / 8 🦷 | 🔴 防災問答 |
| 7 | 10 🦷（大地震彩蛋） | 🔴 防災問答 |

- 大地震層**答對 = 基礎牙齒 ×2**（例：震度 7 答對 = 20🦷）；答錯仍給基礎。
- 數值後台可調（存 config，見 §6），先以本表為初始值。
- **通膨無虞**：牙齒給得極小（多為 1~4），就算頻繁觸發，對牙齒經濟衝擊極低（DAU~45、日印鈔 ~164k🦷 基線，見 [[牙齒經濟實測基線 reference_teeth_economy_baseline]]）。

---

## 4. 架構（新 pattern：主動推播，非被動觸發）

> 現有 `model/RandomEvent.js` 是「**有人在頻道聊天才觸發**」的被動模式。
> 地震事件相反：**沒人講話也要自己冒出來** → 需要一顆**輪詢器**主動 push 到頻道。

```
        每 60 秒
甜甜 bot ──setInterval──▶ 打 CWA E-A0015 + E-A0016
                              │ 取最新數筆，逐筆看 EarthquakeNo
                              │ 已在 dedup 表 → 跳過
                              │ 新編號 → 寫 dedup 表（冪等）→ 開事件
                              ▼
                    依 MaxIntensity 分層 → 貼卡片到 EARTHQUAKE_CHANNEL_ID
                              │ 🟢 單顆領獎鈕（45s）
                              │ 🔴 防災二選一（90s）
                              ▼
              玩家點按鈕 → 冪等檢查領取名冊 → ViewerDetailDAO.givePoint(震度牙齒)
```

### 輪詢器（新檔 `model/EarthquakeEvent.js`）
- **跑在甜甜 bot 內**用 `setInterval(60_000)`，**不另開 Lambda**（最省、狀態就近）。
- 首次啟動先「**暖機**」：把當下最新地震編號全部寫進 dedup 表**但不發事件**（避免重啟後把歷史地震全補發洗版）。
- 每輪：抓兩資料集 → 合併 → 對每個沒看過的 `EarthquakeNo`，用 **DDB 條件寫入**（`attribute_not_exists`）搶占，搶到才發事件（多實例 / 重啟安全）。
- fire-and-forget、全 `try/catch`，**絕不影響 bot 主流程**；API 失敗只 log、下輪重試。
- 領取窗口用記憶體 timer 管理按鈕失效；重啟後未過期事件視為結束（可接受，事件本就短命）。

### DDB 兩張表（全 `PAY_PER_REQUEST`）
- **`sweetbot-earthquake-log`** — 去重 + 領取名冊。
  - `pk = EarthquakeNo`、`sk = "meta"`：地震資訊快照、`maxIntensity`、`reward`、`tier`、`quizKey`(大地震題目)、`postedAt`、`expireAt`。
  - `pk = EarthquakeNo`、`sk = "claim#<discordID>"`：領取紀錄（冪等擋二領）、`answer`(選項)、`correct`、`points`、`claimedAt`。
  - 可加 **TTL 30 天**自動清老資料。
- **`sweetbot-earthquake-quiz`** — 防災題庫（後台可增修，見 §5）。

### 沿用現成
- `ViewerDetailDAO.givePoint(discordID, n, reason)` 發牙齒（`reason='earthquake:<No>'` 可供 [[牙齒經濟後台 project_teeth_economy_dashboard]] 歸戶）。
- 按鈕 / embed 慣例照 `RandomEvent` 與「[[一指令開場後全按鈕 feedback_game_single_command_buttons]]」。

---

## 5. 防災題庫（Tier 2，靜態預寫）

- **不燒 LLM**：防災內容品質可控、避免 AI 亂教錯的自保知識。
- 存 `sweetbot-earthquake-quiz`，每則：`key`、`question`、`optionA`、`optionB`、`correct`(A/B)、`explain`(小知識解說)、`enabled`、`weight`。
- 觸發大地震時**隨機抽一題**，題號存進該地震 meta（同一地震所有玩家同題、答案一致）。
- MVP 先種 **10~12 題**，例：

| 題目 | A | B | 正解 | 小知識 |
|---|---|---|---|---|
| 地震當下在室內，第一件事？ | 衝去開門 | 躲桌下抓桌腳護頭 | **B** | 開門浪費逃命時間；國際通則是「趴下 Drop・掩護 Cover・穩住 Hold」。 |
| 搖晃時在高樓，該不該搭電梯逃? | 立刻搭電梯下樓 | 走樓梯、別搭電梯 | **B** | 地震可能停電受困電梯；務必走樓梯。 |
| 開車遇到強震怎麼辦? | 加速開離 | 減速靠邊停、開雙黃燈 | **B** | 路面可能龜裂/落物，靠邊停最安全。 |

- 後台管理頁（遊戲館，仿 [[隨機事件翻修 project_random_event_renovation]] 的 `vote_manager`/`random_events` 模式）可增刪改題。

---

## 6. 後台 / 設定

- 遊戲館加一頁「🌏 地震事件」：可調**獎勵對照表**、**窗口秒數**、**輪詢開關 / kill switch**、**題庫 CRUD**、近況（最近觸發的地震 + 領取人數）。
- 設定存 `sml_config`（或 DDB config 表）；甜甜端輪詢讀取（仿其他遊戲後台）。
- **環境變數**：
  - `EARTHQUAKE_CHANNEL_ID`（推播頻道，**待填**）
  - `EARTHQUAKE_POLL_SEC`（預設 60）
  - `EARTHQUAKE_DISABLED=1`（kill switch，關掉輪詢）
  - CWA key 走 SSM `/sml/cwa/opendata-key`。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：CWA 開放 API（**免費**）；DDB 新表 `sweetbot-earthquake-log`、`sweetbot-earthquake-quiz`，量級極小（PAY_PER_REQUEST，預估 < $1/月）。輪詢跑在既有甜甜 bot 內、**不另開 Lambda / APIGW**。
- 所有新表 PAY_PER_REQUEST；**無 LLM / 無付費 API**，故免帳本封頂四件套。
- 唯一外部依賴＝CWA 免費 Key；有速率上限但每 60 秒 2 次呼叫遠低於限額。設 `EARTHQUAKE_DISABLED` kill switch 可隨時停。
- 若日後改用 LLM 生題或生成播報文，回本規範補齊「四件套」。

---

## 7. 待辦 / 開放項

- [ ] **頻道**：確認 `EARTHQUAKE_CHANNEL_ID`（使用者選「用現有頻道」，待指定哪一個）。
- [ ] 申請 CWA Opendata Key → 存 SSM。
- [ ] 校正 CWA 回傳欄位名（`MaxIntensity` 實際 JSON 路徑、震度字串格式「5弱/5強」對照）。
- [ ] 種 10~12 題防災題庫。
- [ ] 決定大地震是否 `@everyone` 或身分組提醒（目前預設不 tag，避免半夜擾民）。
