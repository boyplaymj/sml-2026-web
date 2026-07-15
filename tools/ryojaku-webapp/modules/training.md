# 🎯 訓練工具 (Training Tools)

> **狀態**：設計草案 🔶（Claude 提案，待 gameboy 拍板）
> 一句話：**麻將實力練習工具集——算台、聽牌、牌效、語音判台，把技術訓練搬進 App。**

---

## 1. 定位與價值

両雀是 elite community，「訓練工具」是**把玩家練強**的一塊，也和天梯/內建遊戲共用同一套規則引擎：
- **算台練習**：出牌型 → 玩家算台 → 對答案（家規台數表可設定）。
- **聽牌訓練**：13 張限時判斷聽什麼、幾台。
- **牌效練習**：給手牌選最佳打牌，比對最佳解。
- **語音判台**：語音報牌型 → 自動判台加總（**已有地基**，見 repo `tools/mahjong-tai`，Codex 三輪複驗過的純邏輯引擎）。

**關鍵**：算台/聽牌/牌效可共用一套「台數規則引擎」，這也是天梯與內建遊戲的地基 → **先把規則引擎定案，三邊受益**。

---

## 2. 模組拆解（草案）🔶
| 工具 | 引擎 | 成本敏感 |
|---|---|---|
| 算台練習 | 台數規則引擎（純邏輯） | 零 LLM |
| 聽牌訓練 | 聽牌計算（純邏輯） | 零 LLM |
| 牌效練習 | 牌效/期望值（純邏輯，較重運算） | 零 LLM |
| 語音判台 | 台數引擎 + **ASR 語音辨識** | ⚠️ ASR（見下） |
| （選）AI 教練講解 | LLM 解說為何這樣打 | ⚠️ 燒 LLM → 四件套 |

**Claude 傾向**：先把**台數規則引擎**定案（沿用 `tools/mahjong-tai` 已驗證的邏輯），算台/聽牌純邏輯先上，**零成本**。語音與 AI 教練是加分項、再評估。

## 3. 與現有 repo 資產的關係
- `tools/mahjong-tai`（兩雀語音判台工具）= 本模組的**引擎地基**，已 commit（3219f86）、Codex 複驗 8 findings 全修。家規台數待對齊。
- 家規台數表 = 三邊（訓練/天梯/內建遊戲）共用的設定，建議收進本後台當單一事實來源。

## 4. API 草案 🔶
`GET /training-drill?type=tai|ting|efficiency` · `POST /training-check`（對答案）· `GET /training-stats`（個人練習進度）· `GET /training-ruleset`（家規台數表）

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **純邏輯練習（算台/聽牌/牌效）**：運算在前端或輕量 Lambda，DDB 只存進度 `training-progress`（PAY_PER_REQUEST，量級小）。無 LLM／無付費 API → 免帳本封頂。
- **語音判台（ASR）**：若走 AWS Transcribe/付費 ASR → 屬付費 API，需列量級並設每次呼叫上限；優先評估本地/免費方案。
- **AI 教練講解（若做）**：走 Bedrock `global.anthropic.claude-opus-4-8` + prompt caching，備齊四件套（帳本 `training-ai-usage` + 月封頂 `TRAINING_AI_MONTHLY_CAP_USD` + kill switch `TRAINING_AI_DISABLED` + 後台用量卡）。

## 5. 待你拍板
- [ ] 先上哪幾個純邏輯練習？家規台數表由誰定、收進後台當單一來源？
- [ ] 語音判台要不要進 App（涉 ASR 成本）還是留本機 CLI 工具？
- [ ] 要不要 AI 教練講解（會進 LLM 成本規範）？
