# D2 惰性結算 + 在途看板 + 提款 — Fable 5 實作交接

> 目標:把 D1 派出的在途列車接成閉環 —— 開面板自動惰性結算(抵達回沖車站金庫、釋放月台)、在途看板、提款到玩家錢包。做完 Phase 0「派車→等→收錢→提款」手感閉環。
> **Phase 0 = NPC 目的地**:`recipientCollectReward`(收件人取貨獎勵)與「互取貨閘」是**玩家↔玩家**機制 → **延到 Phase 1**,D2 不做。
> 慣例照 `TrainTycoon.js` 現有寫法 + `commitDispatch.js` 的分層(pure txn builder + DAO `sendTransact`),零硬編、復用引擎。

## 動到的檔案
- 新 `model/miniGame/trainTycoon/commitSettle.js`(結算落地薄接線,鏡像 commitDispatch):
  - `buildSettleTxn({ userId, sk, netDelta, transitTable, stationTable, now })` **純函式** → 回 TransactWrite input:
    - `Update` station:`SET treasury = if_not_exists(treasury,:z) + :net, updatedAt = :now`(**只碰 treasury/updatedAt**,不碰 pairFatigue → 與並發派車疲勞 update 屬性不相交、互不覆蓋)。
    - `Delete` transit:Key `{userId, sk}` + `ConditionExpression: 'attribute_exists(userId)'`(並發雙開面板時,transit 已被刪 → 整筆交易失敗、**不重複回沖**)。
    - `ClientRequestToken` = `${userId}-${sk}`.slice(0,36)(冪等)。
  - `applySettlement({ transitDAO, stationDAO }, batchResult, { userId, now })` async:逐筆 `settled` → `transitDAO.sendTransact(buildSettleTxn(...))`;**全部成功後**才 `stationDAO.setLastSettled(userId, batchResult.nextLastSettledAt)`(Codex 守則①:游標最後推)。回 `{ credited, count, releasedSlots }` 供面板顯示。
  - `commitSettle.test.js`:純 txn 形狀(只碰 treasury、Delete 有 attribute_exists、net 帶對)+ orchestrator(逐筆 sendTransact、游標最後、某筆失敗不推游標)。
- `model/miniGame/TrainTycoon.js`:
  - 新 `settleNow(uid)` helper:`get station → listArrivedBefore(uid, now) → batchSettle(transits, {lastSettledAt: station.lastSettledAt, now}, cfg, Math.random) → applySettlement(...)`。回結算摘要(結算幾班、入帳多少)。
  - **開面板/刷新/切到儀表板或在途分頁時先跑 `settleNow`**(無到期車時 batchSettle count=0、零寫入,cheap)。dashboard embed 可帶「剛結算 N 班,入帳 X🦷」note。
  - `transit` 分頁 → 新 `transitPayload`(換掉佔位):`listAll(uid)` 列**未抵達**列車(`arriveAt > now`)顯示目的地/編組/ETA 倒數;已抵達的在 settleNow 已結掉。
  - 提款:儀表板加「提款」鈕 `rrt:withdraw` → `withdrawAll(uid)`。
  - 引擎:`require('./trainTycoon/settle.js').batchSettle`、`require('./trainTycoon/commitSettle.js')`。
- **不改** settle.js(純)、不改 DAO(用既有 `sendTransact`/`setLastSettled`/`withdraw`/`listArrivedBefore`/`listAll`)、不改 discord.js。

## 結算模型(自動、原子、冪等)
1. `now = Date.now()`;`station = await StationDAO.get(uid)`(拿 `lastSettledAt`,無站或非 active → 跳過)。
2. `arrived = await TransitDAO.listArrivedBefore(uid, now)`(sk<=now);餵 `batchSettle(arrived, {lastSettledAt, now}, cfg, Math.random)`(內部再以 `arriveAt > lastSettledAt` 嚴格篩 = 冪等關鍵)。
3. **每筆 `settled` 原子落地**:`sendTransact(buildSettleTxn({ userId:uid, sk:s.sk, netDelta:s.net, ... , now }))`。
   - **treasury 記 `s.net`**(= revenue − fuel;loss 時 net = −fuel,燃料照扣 → treasury 可為負,破產機制 `bankruptcy` 是後續,不在 D2 處理)。
   - 月台**靠刪 transit 自動釋放**(platformUsed = transit 筆數,無獨立 counter)。
4. 全部成功 → `setLastSettled(uid, nextLastSettledAt)`(最後、單獨 targeted SET)。
   - 原子刪 transit 已是主冪等保證:即使 setLastSettled 失敗,重跑時已刪的 transit 不會再被 listArrivedBefore 撈到 → 不雙發錢。游標是二次保險 + 省重掃。

## onTime(準時加成)Phase 0 決策 — 需你/Codex 拍板
`settleDispatch` 吃 `onTime` 布林算レム加成,但 transit 沒存這欄,要結算時算。Phase 0 NPC 自動結算**沒有「玩家及時取貨」的時序**。
- **建議:Phase 0 `onTime = true`**(NPC 抵達即收,レム加成生效)。「取貨要及時」的張力等 Phase 1 玩家↔玩家 + 手動取貨才有意義。
- 餵 batchSettle 前把每筆 transit `{...t, onTime: true}` 補上(或在 settleNow 組 dispatch 時帶)。**不要自創時間窗參數**。

## 提款 withdrawAll(uid)
1. `amount = Math.floor(station.treasury)`;≤0 → 提示「金庫沒錢可提」。
2. `await StationDAO.withdraw(uid, amount, now)`(既有:條件式 `status=active AND treasury>=amount`,原子扣、防雙花)。
3. `const w = await this.applyWalletDelta(uid, amount, '火車大亨提款')`(驗證式錢包,+amount)。
4. **錢包入帳失敗 → 回沖 treasury**(`addTreasury(uid, amount, now)`)避免金庫被扣但錢包沒進。
5. 成功 → 重繪儀表板顯示新金庫/錢包。綁操作者、防連點(withdraw 條件式已擋餘額不足重複提)。

## Codex 驗收點
1. **游標最後推**:`setLastSettled` 只在所有 per-transit 交易成功後呼叫;中途失敗不推。
2. **treasury 不被派車疲勞覆蓋**:結算交易只 targeted SET treasury/updatedAt,**絕不整站 PUT**;與 commitDispatch 的 pairFatigue SET 屬性不相交。
3. **冪等**:同一 transit 不雙結(原子 Delete + attribute_exists 條件 + 游標);並發雙開面板不重複回沖。
4. **月台釋放**靠刪 transit,結算後 `listAll` 筆數下降 = 月台回收。
5. **提款**條件式原子扣 + 錢包入帳失敗回沖;綁操作者。
6. **onTime=true** 一致套用(或依拍板);零硬編、金額全走 config/引擎。
7. 回歸:d1 62 / p1 19 / p2 43 / engine 222 全綠;新 `commitSettle.test.js` 全綠。

## 怎麼跑
`node model/miniGame/trainTycoon/commitSettle.test.js`(新)+ `node trainTycoon.d1.smoke.js` + 若加 d2 smoke 則 `node trainTycoon.d2.smoke.js` + 引擎 222 回歸。

## 不要做
- 不做 `recipientCollectReward` / 互取貨 / 客運 / 升級 / 事件領取(Phase 1+)。
- 不 `git commit`(Opus 覆核後提交)。不碰工作樹裡別 session 的 tax 檔。
