# SML repo — 專案規則

## 💰 成本控管（強制）

凡是**新開始的機器人遊戲 / 服務**，只要會吃到額外成本（LLM token、DynamoDB 新表、S3 圖床、Lambda/APIGW、外部付費 API），其設計冊（`CODEX_SPEC*` / `*-HANDOFF.md` / `DESIGN.md`）**必須**含一段「## 💰 成本控管」並連回 **`tools/COST_CONTROL.md`**。

- 直接複製 `tools/COST_CONTROL.md §2` 的樣板段落，填入本功能實際的成本來源與量級。
- 遵循該檔 §1 鐵律：DDB 一律 PAY_PER_REQUEST、LLM 一律走 Bedrock（無 key）、燒 LLM/付費 API 者必備「帳本表 + 月彙總 + 月度封頂 cap + 後台用量卡 + kill switch」四件套。
- 純前端 / Discord emoji 金庫 / 既有表加欄位 → 不算額外成本，免此段。

判斷成本或加 LLM 前，先讀 `tools/COST_CONTROL.md`（正典）與 skill `claude-api`（現價/SDK）。
