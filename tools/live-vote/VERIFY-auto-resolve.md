# 直播應援投票 — 自動開獎（Phase 2）驗收單（交 Codex）

> 對象：Codex ／ 目的：獨立複驗「完賽自動開獎」新功能。
> 口徑（使用者 2026-07-18 拍板）：**觸發＝當場這半莊完賽**、**分數/排名/勝負基準＝當場淨分**（sml_logs deltas 按選手名聚合）。

## 一、改了什麼（4 檔）

### A. bot 新檔 `sweetbot-next/service/LiveVoteResolver.js`
讀 Firestore（`sml2026newscore`，匿名 read）：`sml_matches/{matchId}.status` 判完賽、`sml_logs(matchId)` 按選手名算當場淨分→名次/勝負/最高連莊。`evaluate(question)` 回 `{finished, answer:optKey|null, detail, error}`。Firestore 解析與 `StockMarketEngine.js` 同一套（刻意各自持有一份，避免跨遊戲耦合）。

### B. bot `sweetbot-next/model/LiveVote.js`
- `require` resolver；新增 `AUTO_CHECK_INTERVAL_MS=15000`、`this.autoCheckedAt` 節流 Map。
- `poll()` 加 `needsAutoResolve = isAutoResolvable(q) && autoDue(q.questionId)` 分支。
- `isAutoResolvable`：`resolverType` 以 `auto_` 開頭且 status ∈ {open,closed}。
- `tryAutoResolve`：`evaluate` → 未完賽不動作；完賽但 `answer=null` → **退回人工開獎**（log warn，不開）；有 answer → `applyReveal`。
- `applyReveal`：`closeIfOpen`（open→closed 止票）→ 重讀確認 closed → 快照 `claimAmount=押中票×floor(stake×multiplier)` → `revealClosed`（closed→revealed，開領獎窗）。

### C. bot DAO `sweetbot-next/DAO/LiveVoteQuestionDAO.js`
新增 `closeIfOpen`（條件式 open→closed，ConditionalCheckFailed 靜默 false）、`revealClosed`（條件式 closed→revealed，寫 answer/revealAt/payoutPerWinVote，回 revealAt 或 null）。

### D. Lambda `score-repo/tools/lambda/sml-livevote/index.js`
新增 `validateResolver(body, options)`；`openQuestion` 改存驗證後的 `resolverType/resolverParams`（原寫死 `manual`/`{}`）。其餘 action 未動。

### E. 後台 `sweetbot-site/public/livevote_admin.html`
開題表單加「開獎方式」區：manual／auto_condition／auto_winner。場次與選手下拉**瀏覽器端直讀 Firestore**（`fbQuery` runQuery `sml_matches`/`sml_logs`），Lambda 不碰 Firestore。列表加「🤖 自動」標。

## 二、要 Codex 複驗的點

### V1. 止票與快照的競態（最重要）
- [ ] `applyReveal` 先 `closeIfOpen` 再 `listByQuestion`：closed 後 `pick()` 的三方 TransactWrite（pool 更新 ConditionExpression `status = open`）會失敗 → 確認 close 之後不可能再有新票混進快照。
- [ ] `revealClosed` 條件式 `status = closed`：與**人工開獎（Lambda reveal，也要求 closed）**、**作廢（void）**併發時，只會有一方成功、另一方 ConditionalCheckFailed 靜默讓步 → 不會重複開獎/重複發獎。
- [ ] `applyReveal` 中途若題已被人工 reveal/void：重讀 `fresh.status !== 'closed'` 即 return，不會覆蓋。

### V2. payout 口徑與 Lambda 一致
- [ ] `floor(safeStake × safeMultiplier)`、`claimAmount = picks[answer] × payout` 與 Lambda `revealQuestion` 完全一致（safeStake/safeMultiplier 對非法值回退預設，與 Lambda validateStake/validateMultiplier 對齊）。
- [ ] 領獎沿用既有 `claim()`：`claimed` 冪等 + `now-revealAt<=CLAIM_WINDOW_MS`；`revealClosed` 的 `revealAt=Date.now()` 讓 3 分鐘窗從自動開獎那刻起算。

### V3. 判定正確性（LiveVoteResolver）
- [ ] `computeMatchStats`：淨分按 `playerNames` 名字聚合（非座位）；名次由淨分 desc、rank 從 1；`dealerN` 取該場每位選手最大值。（已用合成 fixture 驗過 4 人淨分/名次/連莊，但請複核 deltas 為負、同分、缺 playerNames 的邊界。）
- [ ] `auto_condition`：`win`=rank1、`lose`=rank===ranked.length、score/rank/dealerN 走 compare(op,value)；達成→yesKey 否→noKey。
- [ ] `auto_winner`：win/lose/rank 取 target 選手 → `optionMap` 反查 optKey；**正解選手不在 optionMap → answer=null → 退回人工**（不 void、不亂發）。
- [ ] `finished=false`（未完賽/查無場次/無 matchId）全部安全略過、下輪再試。

### V4. Lambda validateResolver 硬驗
- [ ] `auto_condition` 強制**恰 2 選項**、yesKey 須為選項 key、win/lose 不需 op/value、其餘 metric 需合法 op + 有限數 value。
- [ ] `auto_winner`：metric ∈ {win,lose,rank}、rank 為正整數、optionMap 每個 key 須為合法選項且選手名非空、至少一組。
- [ ] `manual` 或未帶 resolverType → 存 `{resolverType:'manual', resolverParams:{}}`（不回歸）。
- [ ] 非法 resolverType/缺 matchId → 不建局、回錯。

### V5. 後台 optKey 對齊（前端↔Lambda）
- [ ] 前端送 options 為純字串陣列，Lambda `normalizeOptions` 依序給 key `a,b,c…`；前端 `keyAt(i)=char(97+i)` 用**過濾空白後**的 `currentOptions()` 索引建 yesKey/optionMap → 兩邊索引一致（注意 `.filter(Boolean)` 去空造成的位移已用同一 `currentOptions()` 對齊）。
- [ ] 改動選項後未重按「讀取場次/選手」→ winMap 可能對不到 → 已在 UI 提示；請確認即使對錯，Lambda 驗證會擋（optionMap key 非選項→回錯）。

### V6. 讀取節流/成本
- [ ] 自動題每 15s 才查一次 Firestore（`autoDue`）；`sml_matches` 單 doc GET 便宜、只有 `status==='finished'` 才拉 `sml_logs`。確認不會每 5s 狂打 Firestore。
- [ ] 純讀 Firestore、無 LLM/付費 API（成本控管 §💰 已註記）。

### V7. 不回歸
- [ ] 手動題（resolverType 缺或 manual）流程完全不變：poll 的 needsAutoResolve 為 false。
- [ ] 既有下注/領獎/作廢/面板刷新未受影響（自動開獎後 panelState≠status → 下輪自動刷出「開獎+領獎鈕」）。

## 三、E2E 手動測試（使用者側）
1. 後台開一題 auto_winner「這半莊誰第一名」，選項＝當場 4 位選手、各自綁對應選手，綁定該場 matchId → 發布。
2. Discord 押幾票 → 該半莊在計分後台打到完賽（`status=finished`）。
3. ≤15s 內 bot 自動截止+開獎，面板顯正解＝實際冠軍、開領獎窗；押中者 3 分鐘內領獎入帳、流水帳「直播應援投票中獎」。
4. 反例：開一題 auto_condition「賊恩 分數>99999」（必不達成）→ 完賽後自動開獎正解＝「否」那個選項。

## 四、已知取捨（非 bug，供聚焦）
- **分數單位**＝當場累積淨分（與股市盤 score 同源、螢幕上素點淨分），非賽季積分 pts。使用者已確認採當場淨分。
- **連莊數**取 `sml_logs.dealerN` 該場最大值；若 dealerN 語義為 0-based，請回報，UI 提示可調。
- 自動開獎後面板刷新有最多 ~5s 延遲（下一輪 poll）；claim 窗 3 分鐘足夠吸收。
- resolver 的 Firestore 解析與 StockMarketEngine 重複約 25 行（刻意解耦，非疏漏）。
