# Phase 2b-2 · bot 關鍵洞察自動推進引擎 — Codex 驗收單

**標的**：`sweetbot-next/model/PuzzleQuest.js`（＋ `test/puzzleStageGate.test.js`）。
**模型**：全服同步；玩家答中「當前階 stageGates 關鍵洞察」→ 全服 stage+1、原地改 embed、不另發、不回看。

## 改了什麼（3 處，皆 opt-in：只對有 `stageGates` 的案生效）
1. **`stageGateAdvanceHit(puzzle, curStage, answer)`**（module fn，已 export）：回答是否命中 `stageGates[from==curStage].advanceAny`。重用既有 `normalizeAnswer`＋`conceptHit`（與 core/partial 同套）。沒 stageGates→false。
2. **`advanceStageOnGate(round, puzzle, fromStage, channelId)`**（class method）：
   - **冪等**：對 round 做 conditional `UpdateCommand`——`ConditionExpression: attribute_exists(id) AND #stage = :from AND attribute_not_exists(firstSolver)`，`SET stage=:from+1`。條件失敗（`ConditionalCheckFailedException`）→ 回 null（已被別人推進/已破案），**不跳兩格**。
   - 成功後 `_writeStageDoc(puzzleId, next)`（寫全服 `puzzle_stage`）＋**原地 edit 面板 embed**（`msg.edit({...panel, attachments:[]})`）；找不到原訊息→靜默不 fallback 重貼（保證不洩版），下次 admin advance 修正。
   - 已在終章（from>=total）→ 直接回 null、不打 DDB。
3. **`handleAnswer` 評估分支**（原 `if(status!=='SOLVED')` 改）：
   - `total=stageCountOf`、`hasGates`、`curStage=clamp(round.stage)`。
   - **win 鎖終章**：`solvedNow = SOLVED && (!hasGates || curStage>=total)`。分階案早階段就算核心全中也**不 win**，只推進。
   - `!solvedNow` → 若 `hasGates && curStage<total && (SOLVED || stageGateAdvanceHit)` → `advanceStageOnGate`。回覆：命中→「🔓 推動了案情…」前綴＋（早猜齊核心→「方向對但未到終章」／否則原 nudge）＋累進答題費。
   - `solvedNow` → 既有 winAndReward 路徑**完全不動**。

## 我方自審（`node --test`）
```
test/puzzleStageGate.test.js  8/8 通過；全套 test/*.test.js  86/86 通過(無回歸)
```
覆蓋：命中當前階、跨階隔離(卓不推S1、高董不推S2)、無 stageGates→false、
Codex 收窄詞不誤命中(我下班了/他拒絕回答/助理怪怪的/怨恨 皆 false;門禁拒絕/卓懷恨 true)、
冪等(正常 from→+1；conditionFail→null 不跳兩格；終章→不打DDB)。

## Codex 逐條複驗
- [ ] **不影響既有案**：無 `stageGates` 的 CASE-09~12 行為不變（`stageGateAdvanceHit`→false、`solvedNow` 走 `!hasGates` 分支＝原邏輯）。
- [ ] **win 鎖終章**：分階案 curStage<total 時核心全中→不 win、改推進；curStage>=total 才 win。確認沒有讓玩家早階段直接 win 的路徑。
- [ ] **冪等**：兩人同時答中同一階→只推進一格（conditional update）。firstSolver 存在時 gate 推進被擋（不與破案併發）。
- [ ] **靜默推進**：只 `msg.edit` 原面板、無新訊息/無 @；找不到原訊息不 repost。符合「不另發、不回看」。
- [ ] **紅鯡魚不誤推進**：S2 咬定「卓是兇手」命中 S2 gate（卓）→ 推進到 S3（正確，S2 本就要你採納紅鯡魚①）；S3 再答「卓」不在 S3 gate→只 nudge。
- [ ] **答題費/獎池/publishGuess** 等既有流程未被破壞（推進與否都照收累進費、猜測照公開）。
- [ ] 錯誤處理：DDB/embed 失敗都 catch、不讓 handleAnswer 拋出。

## 尚未做（下一步）
- **部署**：改的是 `sweetbot-next`，要 `./restart.sh` 才生效（線上未動）；離峰重啟＋私頻實測。
- **stageBonus（§8.1）**：推進給小獎目前**未加**（保持最小改動）；要的話另議。
- 依賴 case 有 `stageGates`（明硯已加；CASE-13 尚未開案 activePuzzleId 空）。

---
## round-2b-2 修正（回應 Codex Medium：Firestore 階段同步失敗未被視為失敗）
- `_writeStageDoc` 改 async **內建重試**（非 2xx→指數退避重試至多 3 次），所有推進路徑(gate/admin)受惠。
- `advanceStageOnGate` **檢查回傳 status**：非 2xx→`console.error` 大聲告警(標明 DDB/Discord 已推進、假網站可能落後、需重新同步)；**不回滾**(DDB 是 Discord 側權威、階段不倒退)。
- 新增測試：Firestore 回 500→仍推進(回 {stage:next})但有告警。`test 9/9、全套 87/87 綠`。
- 未做(留部署/2a-2 前):自動 reconcile(重啟或週期把 puzzle_stage 對齊 round.stage)——目前靠重試＋admin 再推進補救即可。
