# 💰 SML 伺服器成本控管規範（正典）

> **這是唯一正典。** 凡是**新開始的機器人遊戲 / 服務**，只要會吃到「額外成本」，設計冊（`CODEX_SPEC*` / `*-HANDOFF.md` / `DESIGN.md`）**必須**含一段「成本控管」並連回本檔。
> 目的：不用每個新專案重新發明帳本、封頂、後台卡；照這裡的預設值做即可。
> 最後更新：2026-07-14

---

## 0. 什麼叫「會吃到額外成本」

只要沾到下列任一項，就算，設計冊就要帶成本控管段：

| 類別 | 具體來源 | 誰付錢 |
|---|---|---|
| **LLM token** | Bedrock 文字生成（Claude）、影像生成（SD3.5） | AWS 帳單 |
| **DynamoDB** | 新表、讀寫流量 | AWS（PAY_PER_REQUEST → 用多少付多少） |
| **Lambda / APIGW** | 後端 action 端點 | AWS（多半免費額度內，但要記在案） |
| **S3 / CloudFront** | 圖床、靜態站、素材 | AWS |
| **外部付費 API** | 綠界金流、第三方資料源等 | 各自 |
| **Claude Code 月費額度** | bridge / 互動式對話燒的 token | Max 訂閱（NT$7790/月，非無限，會撞上限） |

**不算**額外成本、免規範：純前端改動、Discord emoji 金庫（guild emoji 免費）、既有表加欄位（流量沒明顯變化）。

---

## 1. 鐵律預設值（直接照抄，別自行發明）

1. **DynamoDB 一律 `PAY_PER_REQUEST`**（全站 55+ 表都是；別開 provisioned）。
2. **LLM 一律走 Amazon Bedrock**，不要用 Anthropic API key：
   - 算 AWS 帳、IAM 認證、**無 key、無 SSM**、繞開壞掉的 console 儲值。
   - 文字模型 `global.anthropic.claude-opus-4-8`（Opus 4.8 需跨區 inference profile，`apac.`/直接 on-demand 都不行）。
   - 甜甜 EC2 role `sml-claude-ec2` / `sml-puzzle-ddb` 類已授 `bedrock:InvokeModel`；新功能沿用、別另開 key。
   - 影像生成走 Bedrock Stability SD3.5（us-west-2），見 `reference_bedrock_image_gen`。
   - 一律開 **prompt caching**（固定前綴放系統卡/角色卡），省 token。
3. **每個會燒 LLM / 付費 API 的功能**都要有這四件套（照 puzzle 電話 AI 做，見 `puzzle-quest/CASE-09-HANDOFF.md §8`）：
   - **帳本表**：獨立 DDB 表 `<feature>-ai-usage`，`PAY_PER_REQUEST` + **TTL 90 天**，存 per-call 明細（`usage` → `costMicros` 整數，別存浮點）。
   - **原子月彙總**：`rollup#<month>` / `rollup#<場次>` 用 `ADD` 原子累加，隨呼叫即時更新。
   - **月度封頂 cap**：環境變數 `<FEATURE>_AI_MONTHLY_CAP_USD`（預設先抓保守值，如 15）。**呼叫前先查本月累計，超上限就讓功能「忙線 / 降級 / stub」**，不硬打。
   - **後台用量卡**：管理頁加一張卡（本月呼叫數 / 成本 / 距上限 / 各場次分佈），資料走既有 admin Lambda 加一個 `aiUsage` action。
   - **kill switch**：`<FEATURE>_AI_DISABLED=1` 可強制 stub 不計費；**無憑證/未設定時預設回 stub，不報錯、不計費**。
4. **定價用現價**：Opus 4.8 = **$5 / $25**（input / output per 1M tok）；別抄舊稿的 15/75。動工前讀 skill `claude-api` 對一次。
5. **token 預估 preflight**：任何自動化 / 迴圈 / 大量抓取，動工前先估 token 用量 + 報「額度剩多少」再確認才跑（`feedback_token_preflight`）。寧缺勿濫。

---

## 2. 設計冊必附段落（複製貼上，改 `<...>`）

把下面整段貼進新專案的 `CODEX_SPEC` / `HANDOFF` / `DESIGN`：

```markdown
## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：<列出本功能會吃到的：LLM token / DDB 新表 / S3 圖床 / 付費 API…>
- **預估量級**：<每次呼叫約 $X；預估每日/每月 $Y；依 現價 對過>
- **LLM（若有）**：走 Bedrock `global.anthropic.claude-opus-4-8`，開 prompt caching，沿用 role `<role>` 的 `bedrock:InvokeModel`，無 key。
- **帳本**：DDB 表 `<feature>-ai-usage`（PAY_PER_REQUEST + TTL 90 天），per-call 明細 + `rollup#month` 原子彙總（costMicros 整數）。
- **月度封頂**：env `<FEATURE>_AI_MONTHLY_CAP_USD`（預設 <15>）；呼叫前守門，超額→忙線/降級。
- **kill switch**：env `<FEATURE>_AI_DISABLED=1` 強制 stub；無憑證時預設 stub 不計費不報錯。
- **後台可視**：管理頁加「用量卡」，admin Lambda 加 `aiUsage` action。
- **DDB**：所有新表 PAY_PER_REQUEST。
```

功能**不燒 LLM、只有少量 DDB/Lambda** 的，用精簡版：

```markdown
## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：<DDB 新表 <name> / S3 / …>，量級極小（PAY_PER_REQUEST，預估 < $X/月）。
- 所有新表 PAY_PER_REQUEST；無 LLM / 無付費 API，故免帳本封頂。
- 若日後加 LLM，回本規範補齊「四件套」。
```

---

## 3. 月度歸戶 / 監控（既有工具，別重造）

| 想看什麼 | 用哪個 | 位置 |
|---|---|---|
| 各頻道/功能 **Claude token** 佔比 | token-usage report | `tools/token-usage/report.py`（按單價加權） |
| **DynamoDB** 實際用量/成本 | ddb-usage | `tools/ddb-usage/`（近30天曾僅 $1.53） |
| **牙齒經濟**通膨/平衡 | teeth economy 後台 | 遊戲館 `economy.html` + Lambda `sml-teeth-economy` |
| **AWS 總帳**優化 | 見記憶 | `project_aws_cost_optimization`（淨省 ~$28/月） |
| **各功能 AI 帳本**（per-feature） | 該功能後台用量卡 | 例：puzzle `puzzle_manager.html`「☎電話AI用量」 |

新功能的成本，優先歸進上述既有工具（加一列/一張卡），不要另立平行的監控系統。

---

## 4. 相關記憶（recall 用）

`project_aws_cost_optimization`、`feedback_token_preflight`、`reference_bedrock_claude_text`、`reference_bedrock_image_gen`、`reference_token_usage_report`、`project_ddb_actual_usage_dashboard`、`project_teeth_economy_dashboard`、puzzle `CASE-09-HANDOFF.md §8`（帳本四件套範本）。
