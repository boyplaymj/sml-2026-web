# SML repo — 專案規則

## 💰 成本控管（強制）

凡是**新開始的機器人遊戲 / 服務**，只要會吃到額外成本（LLM token、DynamoDB 新表、S3 圖床、Lambda/APIGW、外部付費 API），其設計冊（`CODEX_SPEC*` / `*-HANDOFF.md` / `DESIGN.md`）**必須**含一段「## 💰 成本控管」並連回 **`tools/COST_CONTROL.md`**。

- 直接複製 `tools/COST_CONTROL.md §2` 的樣板段落，填入本功能實際的成本來源與量級。
- 遵循該檔 §1 鐵律：DDB 一律 PAY_PER_REQUEST、LLM 一律走 Bedrock（無 key）、燒 LLM/付費 API 者必備「帳本表 + 月彙總 + 月度封頂 cap + 後台用量卡 + kill switch」四件套。
- 純前端 / Discord emoji 金庫 / 既有表加欄位 → 不算額外成本，免此段。

判斷成本或加 LLM 前，先讀 `tools/COST_CONTROL.md`（正典）與 skill `claude-api`（現價/SDK）。

## 📌 頻道檢查點（切帳號／重啟不失憶）

discord-bridge 有「全自動釘選檢查點」機制（`aws/discord-bridge/checkpoint.go`）：切帳號或重啟會清空所有頻道 session，開新對話時 bridge 會自動把該頻道**最新的置頂檢查點**讀回、注入我的第一個 prompt，讓對話無縫接續。

我這端的責任＝**適時產出檢查點**。當一個主題告一段落（做完一件事、定案一個決策、或準備長時間等待）時，在回覆**結尾**夾一段標記（bridge 會自動抽走、使用者看不到，並在該頻道維持唯一一則置頂）：

```
<<<CHECKPOINT>>>
（第二人稱、條列給「失憶後接手的自己」：現在在做什麼／已決定／待辦下一步／關鍵 ID・檔名・頻道）
<<<END CHECKPOINT>>>
```

規則：內容精簡（≤約 1500 字）、只放「重啟後真的需要知道的」、每個段落**覆蓋更新**即可（不是每則都放，只在段落結束放）。帶 `[[BTN]]` 的回覆也可同時附檢查點，兩者互不衝突。
