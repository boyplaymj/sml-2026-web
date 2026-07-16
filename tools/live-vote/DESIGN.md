# 甜甜直播應援投票（Live Vote）— 設計冊 v0.1

> 狀態：**玩法主決策已定案，架構草案 + 1 個關鍵待拍板（賠付模型）**。
> 定位：配合 **Daily 直播**的即時應援／預測小遊戲，用**花牙🦷下注**，主播/後台當場**截止＋開獎**。
> 與既有系統的關係：
> - 不是 `VotePool`（[[project_sweetbot_vote_pool]]，`!競猜開局`）：那是「一人一票、平分池、不抽成、賽前開一局」。
>   本系統要**每題多票、可分散押、多題並行、直播即時節奏、限時領獎**，需求差異大 → **獨立系統**。
> - 不是股市盤（[[project_tooth_stock_game]]）：那是多空非對稱的操盤養股；本系統是單題二元/多選的短打應援。
> 指令：`!投票`（暫定）。關鍵互動 ID 前綴：`vote_`（例：分散押 `vote_spread_yes`）。

---

## 1. 玩法（使用者已定案）

1. **貨幣**：花牙齒🦷下注（`ViewerDetailDAO.givePoint`／扣點沿用現成）。
2. **每題票數上限**：每人每題最多 **5 票**。
3. **可分散押**：5 票可**分散押在不同選項**（例：3 票押 A、2 票押 B），對沖自便。
4. **不可改票**：投出去**不可撤回、不可改**（只能在剩餘票數內繼續加押）。
5. **多題並行**：可同時開**多道題目**，各自獨立截止／開獎／領獎。
6. **截止**：由**後台／主播**手動截止（Phase 2 可加自動截止時間）。截止後不再收票。
7. **開獎**：**MVP 由後台手動選正確答案**；自動抓答案（比分/牌型/賽果 API）列 **Phase 2**。
8. **領獎**：開獎後**限時 1 分鐘、手動領**（面板「領獎」鈕）；**逾時未領 → 蒸發**（不補發）。
9. **Overlay**：直播畫面上的即時票數/賠率 overlay **待議**（Phase 2/3）。

---

## 2. 待拍板（交 Codex 前需使用者確認）

**🔴 D1：賠付模型（唯一關鍵未定案）** — 下注後「贏了拿多少」？三個候選：

- **A. 同注彩池（parimutuel，推薦）**：每票固定注額 `STAKE`🦷。開獎後，**該題總池**（＝所有票 × STAKE）**扣掉抽成**後，**按押中選項的票數比例**分給押中者。
  - 押中每票回報 ＝ `總池 ÷ 押中總票數`（自然形成賠率；冷門押中賺多）。
  - 全部人都押中 → 幾乎原注退回；沒人押中 → 見 D2。
  - 對齊「可分散押」：分散＝降低變異，符合「應援」而非「梭哈」。
- **B. 固定賠率**：押中每票固定拿 `STAKE × 倍數`（如 ×2）。單純好懂，但**要金庫貼錢**、無法反映熱度、易被套利 → 不推薦。
- **C. 平分制（同 VotePool）**：押中者平分總池、與票數無關 → 但這樣「5 票 vs 1 票」意義弱、和既有 VotePool 高度重疊 → 不推薦。

> 建議採 **A**。以下架構以 A 為準，B/C 只差結算函式。

**🔴 D2：無人押中時的池子** → 選一：①全額退回（安全，推薦 MVP）／②滾入下一題／③沒收進金庫。建議 **①退回**。

**🔴 D3：抽成 rake** → `RAKE%`（建議 **0%** MVP，與 VotePool 一致「不抽成」；日後要沉牙齒再開，後台可調）。

**🟡 D4：單票注額 `STAKE`** → 建議 **50🦷/票**（5 票＝最多 250🦷，比 VotePool 的 200 略高上限但可分批）。後台可調。

**🟡 D5：開獎後可否退款某題**（誤開/取消題）→ 建議保留後台「作廢退款」動作（全額退，仿 VotePool 取消退款）。

---

## 3. 架構

```
主播/後台                          甜甜 bot（sweetbot-next）              玩家
   │  開題(題幹+選項+STAKE)  ──▶  LiveVote.openQuestion() ─建局─▶ DDB
   │                                                      │
   │                                       !投票 面板（按鈕/選單）◀── 玩家
   │                                       vote_pick_<opt> → 扣🦷、記票（原子）
   │  截止  ──────────────▶  LiveVote.close()（stopBetting）
   │  選正解 開獎 ─────────▶  LiveVote.reveal(answer)
   │                                       │ 計算彩池分配（模型 A）
   │                                       │ 開 60s 領獎窗
   │                                       ▼
   │                              面板顯「你押中 N 票，可領 M🦷」領獎鈕
   │                                       │ vote_claim → givePoint（冪等）
   │                              60s 到 → 未領作廢（掃描/惰性判定）
```

**沿用現成（省開發）：**
- 扣點／發點：`ViewerDetailDAO.givePoint`（負數扣、正數發）。
- 單指令開場、其後全按鈕面板、同訊息重繪不洗版：範本 `InBetween.js` / `VotePool`（[[feedback_game_single_command_buttons]]）。
- 後台管理頁 + Lambda + APIGW 認證閘：照 `vote_manager.html` / Lambda `sml-vote`（`bu17majxb4`）模式（[[project_sweetbot_vote_pool]]）。
- 冪等防重領（`claimed` 標記）：仿 VotePool。

**新做的核心：**
- `LiveVote.js`（甜甜端遊戲模組）：開題/收票/截止/開獎/彩池結算/領獎窗。
- **原子計票**：投票用 DDB `ADD`／`UpdateItem` 原子累加票數與扣點，避免併發洗票。
- **限時領獎窗**：開獎時記 `revealAt`；領獎守門 `now - revealAt <= 60s`，逾時惰性作廢（不需背景 timer，惰性判定 + 面板刷新即可；主播端顯示倒數）。

---

## 4. 資料模型（DDB，全 PAY_PER_REQUEST）

建議 **2 張新表**（或併 1 張用 sort key 分型；先寫 2 張清楚）：

### 4.1 `sweetbot-livevote-question`（題目/彩池）
| 欄位 | 型別 | 說明 |
|---|---|---|
| `questionId` (PK) | S | `q_<場次>_<序>`；場次連號建議走 META#SEQ 原子（仿 UPW，重啟不歸零，[[project_upw_davinci_stats]]） |
| `channelId` | S | 發布頻道 |
| `title` | S | 題幹 |
| `options` | L | `[{key, label}]`（key 例 `yes`/`no`/`a`/`b`…；互動 ID＝`vote_pick_<key>`） |
| `stake` | N | 單票注額🦷（預設 50，後台可調） |
| `status` | S | `open` / `closed` / `revealed` / `voided` |
| `pool` | M | `{ <optKey>: 票數 }` 原子累加；`total` 總票數 |
| `answer` | S | 開獎正解 optKey（`revealed` 後） |
| `revealAt` | N | 開獎時戳（epoch ms），領獎窗基準 |
| `rakePct` | N | 抽成（預設 0） |
| `createdAt` / `closedAt` | N | 時戳 |
| `payoutPerWinVote` | N | 開獎時算好快照（總池扣成 ÷ 押中票數），領獎直接乘票數 |

### 4.2 `sweetbot-livevote-bet`（每人每題下注）
| 欄位 | 型別 | 說明 |
|---|---|---|
| `questionId` (PK) | S | |
| `discordId` (SK) | S | |
| `picks` | M | `{ <optKey>: 票數 }`，`used` 累計（守 ≤5） |
| `spentTeeth` | N | 已扣總🦷（作廢退款用） |
| `claimed` | BOOL | 冪等防重領 |
| `claimAmount` | N | 開獎後算出可領（0＝沒押中） |
| `updatedAt` | N | |

> 玩家歷史/統計榜（可選 Phase 2）：另存彙總 `sweetbot-livevote-stats`（押中率/淨收益），或沿用 point-log 事後聚合（[[reference_teeth_economy_baseline]]）。

---

## 5. 結算（模型 A：同注彩池）

開獎 `reveal(answer)` 時：
```
winVotes = pool[answer]                 # 押中總票數
if winVotes == 0:                       # D2 無人押中
    → 全額退回（每人退 spentTeeth），status=voided-refunded
else:
    grossPool = pool.total * stake
    net       = grossPool * (1 - rakePct)
    payoutPerWinVote = floor(net / winVotes)     # 整數🦷，餘數沉金庫或不計
    → 每人 claimAmount = picks[answer] * payoutPerWinVote
開 60s 領獎窗（revealAt = now）
```
領獎 `claim`：守 `claimed==false` 且 `now-revealAt<=60000` → `givePoint(discordId, claimAmount)`；set `claimed=true`。逾時：面板顯「已蒸發」，不發。

> B（固定賠率）：`claimAmount = picks[answer] * stake * 倍數`（金庫貼）。
> C（平分）：`claimAmount = winner 均分 net`，與票數無關。

---

## 6. 指令 / 互動面

- `!投票`：開玩家面板 → 列出**本頻道所有 `open` 題**（多題並行）→ 選一題 → 顯選項按鈕（`vote_pick_<key>`）＋剩餘票數 → 按下即扣🦷記票、面板原地更新「你已押 A×3 B×2，剩 0 票」。
- 開獎後面板：`revealed` 題顯「正解＝X／你押中 N 票／可領 M🦷 [領獎]（倒數 60s）」。
- **後台（甜甜遊戲館新頁 `livevote_admin.html`）**：開題（題幹+選項+STAKE+發布頻道選單，仿 VotePool「建局完選公開頻道發布」）、即時票數卡、**截止**鈕、**開獎選正解**鈕、**作廢退款**鈕。認證照 `sml-vote`／`gameAdmins` 白名單（[[project_sweetbot_vote_pool]]）。
- Lambda `sml-livevote` + APIGW：actions＝`open` / `list` / `close` / `reveal` / `void` / `status`（直連 DDB，驗 Firebase token，同步 `gameAdmins`）。

---

## 7. 分期

- **MVP（Phase 1）**：手動開題/截止/開獎、模型 A、60s 限時領獎、多題並行、後台頁。Overlay 無。
- **Phase 2**：自動抓答案（賽果/比分/牌型來源）＋自動截止時間；玩家統計榜；Overlay 即時票數/賠率。
- **Phase 3**：跨題連押成就、應援排行、與股市盤/賓果盤聯動。

---

## 8. 邊界 / 防呆

- **併發洗票**：計票用 DDB 原子 `ADD` + 條件式（`used + n <= 5`），避免超投。
- **餘額不足**：扣點前查 `getPoint >= n*stake`，不足擋下。
- **重複領獎**：`claimed` 冪等；領獎與開獎快照 `payoutPerWinVote` 綁定（開獎後不再變動）。
- **誤開/取消**：後台 `void` → 全額退 `spentTeeth`。
- **限時領獎公平性**：主播端開獎同步在 Discord 面板貼「開獎！限時 60s 領獎」+ @，倒數清楚（避免玩家錯過蒸發被質疑）。
- **多題狀態機**：`open→closed→revealed`（或 `→voided`），單向；已 `revealed` 不可再收票/改答案。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：DDB 新表 `sweetbot-livevote-question` / `sweetbot-livevote-bet`（＋可選 stats 表）、Lambda `sml-livevote`、APIGW 端點；量級極小（純計票/發點，PAY_PER_REQUEST，預估 **< $1/月**，直播場次期間才有流量）。
- 所有新表 **PAY_PER_REQUEST**；**MVP 無 LLM、無付費 API**，故免「帳本/月封頂/kill switch」四件套。
- **Phase 2 若加自動抓答案**用到外部付費資料源或 LLM 判讀 → 回本規範補齊四件套（帳本表 + 月封頂 cap + 後台用量卡 + kill switch），LLM 一律走 Bedrock `global.anthropic.claude-opus-4-8`、開 prompt caching、無 key。
- 監控歸戶：DDB 用量進 `tools/ddb-usage/`；牙齒通膨/發放進 economy 後台，不另立平行監控。

---

## 9. 關聯記憶

[[project_sweetbot_vote_pool]]（競猜池，區隔對照＋後台/Lambda 範本）、[[project_tooth_stock_game]]（股市盤）、[[feedback_game_single_command_buttons]]（一指令開場後全按鈕）、[[project_upw_davinci_stats]]（META#SEQ 連號範本）、[[feedback_sweetbot_announce_flow]]、[[reference_teeth_economy_baseline]]、[[feedback_cost_control_spec]]。
