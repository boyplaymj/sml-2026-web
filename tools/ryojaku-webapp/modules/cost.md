# 💰 成本控管 (Cost & Usage)

> **狀態**：儀表板已建、資料待接 🔶
> 一句話：**一頁看清「客戶用量」與「實際花費成本」，並集中管理各功能的月封頂/kill switch。**
> 對應正典：`tools/COST_CONTROL.md`。本頁即該規範要求的「後台用量卡」中央版。

---

## 1. 為什麼需要

両雀是要長期營運的服務。老闆視角要能隨時回答三個問題：
1. **有多少人在用、用多兇？**（客戶用量）
2. **這個月燒了多少錢、燒在哪？**（實際花費：伺服器、資料庫、流量、LLM…）
3. **會不會失控？**（每個燒錢功能有沒有封頂、能不能一鍵關）

---

## 2. ⚠️ 資料來源現況（重要）

両雀後端跑在**工程師的另一個 AWS 帳號**（API Gateway `yg7y0xkb50`，非我們帳號 380931373365）。
因此**真實用量與帳單數字目前接不到**，儀表板先以佔位/手動資料呈現，等下列任一條路打通即可即時化：

| 要接的東西 | 最佳來源 | 過渡方案 |
|---|---|---|
| **客戶用量**（人數/活躍/各模組活動量） | 工程師後端開一支 `/admin-metrics` 彙總端點，或給 DDB 唯讀 | 手動月填 `cost.json` |
| **API 呼叫量** | 工程師帳號的 API Gateway CloudWatch 指標 | 手動 |
| **實際 AWS 成本** | 跨帳號唯讀 role（Cost Explorer + CloudWatch），或每月 Cost Explorer CSV | 手動月填 |

> 一旦拿到存取權，仿 `tools/ddb-usage` / `project_ddb_actual_usage_dashboard` 的做法寫一支 `gen_cost.py`
> 定時產出 `admin/cost.json`，本頁直接讀 → 自動化。

---

## 3. 儀表板內容

### A. 客戶用量
- 使用者：總數 / DAU / MAU / 本月新增
- 各模組活動量：開團數、貼文數、聊天訊息、評分數、記帳筆數、推播訂閱數
- API 呼叫量：總量 + 各端點 Top N

### B. 實際花費成本（本月，按 AWS 服務拆）
- **伺服器 / 運算**（EC2 或 Fargate，若有常駐）
- **Lambda**（呼叫數 × 時長）
- **API Gateway**（請求數）
- **DynamoDB**（PAY_PER_REQUEST 讀寫）
- **S3**（圖片儲存 + 傳輸）
- **CloudFront**（流量）
- **AWS Location Service**（geofencing / places / 地圖搜尋 — ⚠️ 單價偏高，重點盯）
- **Bedrock / LLM**（若 App 內遊戲/訓練工具上了 AI）
- **推播**、其他
- → **月合計 + 近 6 個月趨勢**

### C. 治理（接 COST_CONTROL.md 四件套）
- 每個燒 LLM / 付費 API 的功能：**本月累計 / 月封頂 cap / 距上限 %**（超額→降級）
- **kill switch** 狀態（各功能是否 `*_AI_DISABLED`）
- 告警門檻（達 cap 的 80% 提醒）

### D. 單位經濟
- 成本 / 使用者、成本 / 團局 — 判斷可持續性與定價空間

---

## 4. 資料結構 `admin/cost.json`（本頁直接讀）

```
{ updated, currency, dataSource("placeholder"|"manual"|"engineer-api"|"cross-account"), note,
  usage:{ users:{total,dau,mau,newThisMonth},
          activity:{eventsCreated,posts,chatMessages,ratings,ledgerEntries,pushSubscribers},
          apiCalls:{total, byEndpoint:[{path,count}]} },
  cost:{ month, total, byService:[{service,amount}], trend:[{month,amount}] },
  governance:{ llmCaps:[{feature,capUSD,spentUSD,killSwitch}], alerts:[] },
  unitEconomics:{ costPerUser, costPerEvent } }
```
`null` 值 → 前端顯示「待接資料 —」。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **本頁本身**：純前端 + 讀一份 JSON，零額外成本。
- **角色**：本頁即正典要求的「後台用量卡」中央實現；各燒 LLM 功能（APP 內遊戲 AI 出題、訓練工具 AI 教練）的帳本 `*-ai-usage` + 月封頂 + kill switch，統一在此頁 C 區可視化。
- 所有新表 PAY_PER_REQUEST；LLM 一律走 Bedrock 無 key。

## 5. 待你拍板 / 待工程師
- [ ] 用量/帳單走哪條路：工程師開端點？跨帳號唯讀 role？還是先手動月填？
- [ ] 成本要不要含「我們這側」的支出（此後台 CDN、Bedrock 若我方代跑）一起看，還是只看両雀後端？
- [ ] 要不要設每月總成本告警門檻（例：超過 $X 通知）？
