# 甜甜直播應援投票（Live Vote）— 設計冊 v0.1

> 狀態：**玩法主決策已定案（含賠付模型＝固定賠率 B），架構草案，剩數值/護欄小項待確認**。
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

**✅ D1：賠付模型 → 已定案採 B「固定賠率」（使用者 2026-07-16 拍板）**

- **B. 固定賠率（跟莊家對賭）**：押中每票固定拿回 `STAKE × 倍數`；押錯的票 `STAKE` 沒收進金庫。
  - **無彩池、無抽成、無比例分配**：每一票都是「玩家 vs 金庫」的獨立賭注。
  - 金庫淨損益 ＝ `Σ(押錯票 × stake) − Σ(押中票 × stake × (multiplier − 1))`（與 §5 同一口徑）；**可能為負（金庫貼牙齒）** → 見 D-新1 通膨護欄。
  - 倍數建議**每題後台可設**（好猜的題設低倍、難猜設高倍），預設 **×2**。
- 落選未採：A 同注彩池（比例分池）、C 平分制（與 VotePool 重疊）。若日後想換，只需替換 §5 結算函式。

**✅ D-新1：金庫通膨護欄（2026-07-16 定案）** — 固定賠率會讓金庫貼牙齒、是**印鈔源**（對照 [[reference_teeth_economy_baseline]] 每日已印~164k🦷）。
  - **MVP 只做①倍數上限 ×3**（後端強制驗證，見 §8），避免手滑設超高。
  - **②單題賠付封頂列 Phase 2**：每題總賠付超過 `MAX_PAYOUT`🦷 時超出部分縮水/停收；MVP 先靠主播設合理倍數 + economy 後台盯。

**✅ D-新2：倍數預設 ×2**（2026-07-16 定案），每題後台可調，**有效範圍 1.1〜3.0**。

**🟡 D2：無人押中** → B 模型下＝所有押注者都押錯，全數沒收進金庫、無需退款（沒有池子要處理）。**例外**：後台「作廢」整題才退款（見 D5）。

**✅ D4：單票注額 `STAKE` ＝ 50🦷/票**（2026-07-16 定案；每題最多 5 票＝單人單題上限 250🦷）。後台可調。

**🟡 D5：開獎後可否退款某題**（誤開/取消題）→ 保留後台「作廢退款」動作（全額退 `spentTeeth`，仿 VotePool 取消退款）。

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
   │                                       │ 快照 payoutPerWinVote=stake×倍數（模型 B 固定賠率）
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
| `multiplier` | N | **固定賠率倍數**（預設 2.0，每題後台可設，範圍 1.1〜3.0）；押中每票回 `stake × multiplier` |
| `status` | S | `open` / `closed` / `revealed` / `voided` |
| `resolverType` | S | **開獎解析器**（前瞻欄位）：MVP 一律 `manual`（人工選正解）；Phase 2 才實作自動範本（如 `daily_top_score` / `hand_winner`）。MVP 只認 `manual`，其餘值視為未實作、退回人工。 |
| `resolverParams` | M | 自動範本的綁定參數（前瞻欄位，MVP 留空 `{}`）：日後存 `{ matchSetId, round, kyoku, field, optionMap:{optKey→playerId} }` 之類。**MVP 不讀不驗**。 |
| `pool` | M | `{ <optKey>: 票數 }` 原子累加；`total` 總票數（**僅供顯示/熱度，不參與賠付計算**） |
| `answer` | S | 開獎正解 optKey（`revealed` 後） |
| `revealAt` | N | 開獎時戳（epoch ms），領獎窗基準 |
| `createdAt` / `closedAt` | N | 時戳 |
| `payoutPerWinVote` | N | 開獎快照 ＝ `floor(stake × multiplier)`；領獎直接乘押中票數 |

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

## 5. 結算（模型 B：固定賠率）

開獎 `reveal(answer)` 時（**無彩池、無比例、無退款；押錯即沒收**）：
```
payoutPerWinVote = floor(stake * multiplier)     # 開獎快照，之後不變
for 每位下注者:
    claimAmount = picks[answer] * payoutPerWinVote   # 沒押中 answer → 0
    # 押錯的票不動作：下注時已扣的 stake 直接留在金庫（不退）
開 60s 領獎窗（revealAt = now）
```
- **注意**：注額在**下注當下就扣**（§3 扣🦷記票）。開獎只決定「押中的票能領回 `stake×multiplier`」；押錯的票＝已扣的牙齒直接沉金庫。
- **金庫淨損益** ＝ Σ(押錯票 × stake) − Σ(押中票 × stake×(multiplier−1))。倍數>2 且多數押中時金庫會貼牙齒 → D-新1 護欄。

領獎 `claim`：守 `claimed==false` 且 `now-revealAt<=60000` → `givePoint(discordId, claimAmount)`；set `claimed=true`。逾時：面板顯「已蒸發」，不發（已蒸發的是「本可領回的賠付」，玩家淨損＝原扣注額）。

> 作廢 `void`：全額退每人 `spentTeeth`（不論押中與否），status=voided。
> 若日後改回 A（彩池）/C（平分），只需替換本節函式與 `pool`/`multiplier` 欄位語義。

---

## 6. 指令 / 互動面

- `!投票`：開玩家面板 → 列出**本頻道所有 `open` 題**（多題並行）→ 選一題 → 顯選項按鈕（`vote_pick_<key>`）＋剩餘票數 → 按下即扣🦷記票、面板原地更新「你已押 A×3 B×2，剩 0 票」。
- 開獎後面板：`revealed` 題顯「正解＝X／你押中 N 票／可領 M🦷 [領獎]（倒數 60s）」。
- **後台（甜甜遊戲館新頁 `livevote_admin.html`）**：開題（題幹+選項+STAKE+**倍數**+發布頻道選單，仿 VotePool「建局完選公開頻道發布」）、即時票數卡、**截止**鈕、**開獎選正解**鈕、**作廢退款**鈕。認證照 `sml-vote`／`gameAdmins` 白名單（[[project_sweetbot_vote_pool]]）。
- Lambda `sml-livevote` + APIGW：actions＝`open` / `list` / `close` / `reveal` / `void` / `status`（直連 DDB，驗 Firebase token，同步 `gameAdmins`）。

---

## 7. 分期

- **MVP（Phase 1）**：手動開題/截止/開獎、模型 B（固定賠率）、60s 限時領獎、多題並行、後台頁。Overlay 無。
- **Phase 2**：**自動開獎（resolver 範本庫）** ＋自動截止時間；玩家統計榜；Overlay 即時票數/賠率。
  - 方向（框架細節待 Phase 2 設計）：做一套「解析器範本」，**每種題型一支個別撰寫的解析邏輯**，讀計分後台賽果自動判定正解 → 自動 `reveal`+發獎。後台建題時選範本、綁參數（哪場/哪局/選項對應哪位玩家）；沒對應範本的題維持人工開獎。
  - 首批建議範本：`daily_top_score`（當日淨分最高，**按玩家聚合**、避開 [[project_avg_rank_seat_bug]] 半莊換座位雷）、`hand_winner`（指定「第N雀 X風X局」胡牌者/莊家）。
  - **三個前置依賴**（Phase 2 要拉的線）：①**完賽訊號**（計分後台需能判定「該題綁的場次已打完」，如結束狀態或場次數達標）；②**跨系統唯讀資料橋**（甜甜 sweetbot-next 讀 score-repo/broadcast 的 `sml_matches`：給甜甜 role 加唯讀權，或 broadcast 出唯讀 API）；③**身分對應**（選項 optKey → 分數表玩家；接現有 discord_id）。
  - 前瞻相容：`resolverType`/`resolverParams` 欄位 MVP 已預留（見 §4.1），Phase 2 接自動化**免改表/免 migration**。
- **Phase 3**：跨題連押成就、應援排行、與股市盤/賓果盤聯動。

---

## 8. 邊界 / 防呆

- **併發洗票**：計票用 DDB 原子 `ADD` + 條件式（`used + n <= 5`），避免超投。
- **餘額不足**：扣點前查 `getPoint >= n*stake`，不足擋下。
- **重複領獎**：`claimed` 冪等；領獎與開獎快照 `payoutPerWinVote` 綁定（開獎後不再變動）。
- **誤開/取消**：後台 `void` → 全額退 `spentTeeth`。
- **限時領獎公平性**：主播端開獎同步在 Discord 面板貼「開獎！限時 60s 領獎」+ @，倒數清楚（避免玩家錯過蒸發被質疑）。
- **多題狀態機**：`open→closed→revealed`（或 `→voided`），單向；已 `revealed` 不可再收票/改答案。
- **後端強制參數驗證（不可只靠後台 UI 擋）**：開題 action 於 Lambda `sml-livevote` 內硬驗 `1.1 <= multiplier <= 3.0`、`stake > 0`（且建議整數）、`options.length >= 2`、每票 `used + n <= 5`；不合法回錯、不建局。前端後台 UI 的限制只是輔助。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：DDB 新表 `sweetbot-livevote-question` / `sweetbot-livevote-bet`（＋可選 stats 表）、Lambda `sml-livevote`、APIGW 端點；量級極小（純計票/發點，PAY_PER_REQUEST，預估 **< $1/月**，直播場次期間才有流量）。
- 所有新表 **PAY_PER_REQUEST**；**MVP 無 LLM、無付費 API**，故免「帳本/月封頂/kill switch」四件套。
- **Phase 2 若加自動抓答案**用到外部付費資料源或 LLM 判讀 → 回本規範補齊四件套（帳本表 + 月封頂 cap + 後台用量卡 + kill switch），LLM 一律走 Bedrock `global.anthropic.claude-opus-4-8`、開 prompt caching、無 key。
- 監控歸戶：DDB 用量進 `tools/ddb-usage/`；牙齒通膨/發放進 economy 後台，不另立平行監控。

---

## 9. 關聯記憶

[[project_sweetbot_vote_pool]]（競猜池，區隔對照＋後台/Lambda 範本）、[[project_tooth_stock_game]]（股市盤）、[[feedback_game_single_command_buttons]]（一指令開場後全按鈕）、[[project_upw_davinci_stats]]（META#SEQ 連號範本）、[[feedback_sweetbot_announce_flow]]、[[reference_teeth_economy_baseline]]、[[feedback_cost_control_spec]]。
