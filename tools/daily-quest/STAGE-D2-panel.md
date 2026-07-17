# 每日任務 — 階段 D2：玩家面板 + 領獎 + 重抽（交 Codex 查驗）

> 位置 `/opt/sml/sweetbot-next`。**純 code、未接 discord、未重啟**（`grep DailyQuest discord.js` 無結果）。

## 新增 / 改動

| 檔 | 動作 | 內容 |
|---|---|---|
| `model/DailyQuest.js` | 新 | `!每日任務` 面板 + `dqClaim`/`dqReroll` 按鈕 handler |
| `DAO/DailyQuestDAO.js` | 改 | 移除 `markRerollUsed`（語意錯）→ 新增 `replaceSlotIfKey`（原子換重抽格） |
| `model/QuestTracker.js` | 改 | 懶抽 item 移除 `rerollSlotUsed` 旗標（重抽非每日一次） |

## 重要語意修正（D1 遺留）

- 設計 §1.3：重抽是「**每天只有 1 格可重抽、該格無限次、每次 80🦷**」＝**空間限制**（只有 idx0 那格），不是每日一次。
- D1 誤做成 `rerollSlotUsed`（每日一次）→ D2 改掉：`replaceSlotIfKey` 支援無限重抽，靠條件式擋雙擊重複扣費。

## 面板（`init`）

- `!每日任務` → `getOrCreateToday`（懶抽）→ embed：每題 title/desc + 進度條 `▰▰▱▱▱ 2/3`（done 顯「🎉 可領取」、claimed 顯「✅ 已領」）+ 獎勵文字 + 今日達成 x/N + 🔥 連續 streak（唯讀，streak 累加屬階段 E）。
- 按鈕：每個 **done && !claimed** 格一顆綠色「領：<title>」；可重抽格一顆灰色「🔄 重抽（80🦷）」；每列 ≤5 顆自動分列。
- customId：`dqClaim{TAG}{discordId}{TAG}{index}`、`dqReroll{TAG}{discordId}`（TAG=`Config.interactionDataTag`=`-`；discordId/index 無 `-` 不會撞）。同訊息 `interaction.update` 重繪。

## 領獎（`onClaim`，冪等）

順序 = **先原子搶 claimed、再發獎**（mark-then-pay，防雙領）：
1. ownerGuard（非本人 → ephemeral 拒絕）
2. 讀 slot：未完成/已領 → ephemeral 快擋
3. `claimSlot(id,date,index)`（條件 `done=true AND claimed=false`）→ 搶輸則 ephemeral「已領過」
4. 搶到才發：point → `givePoint([id], rewardPoint, 'point', reason)`；exp → `givePoint([id], rewardExp, 'experience', reason)`；prop → `Props.giveLogic`
5. `redraw` 同訊息更新 + followUp 公告領到什麼

## 重抽（`onReroll`，無限次）

順序 = **先原子換格、再扣費**（防雙擊重複扣）：
1. ownerGuard；找 `rerollable` 格；claimed 不可重抽
2. 餘額檢查 `ViewerDAO.getByDcID(id).point >= 80`（givePoint 無地板,需先擋）
3. 從 enabled 池排除今日已出現的 key、`weightedDraw` 抽 1 個新任務
4. `replaceSlotIfKey(id,date,index,oldKey,newSlot)`（條件 `key 未變 AND !claimed`）→ 失敗則 ephemeral 重試
5. 成功才 `givePoint([id], -80, 'point', '每日任務重抽')`
6. redraw + followUp

## 驗證（已跑）

- 3 檔 `node --check` 通過。
- **buildPanel 單元**：可領取格才有領獎鈕、已領/未完成格無鈕、可重抽格有重抽鈕、embed 欄位數、customId 格式（`dqClaim-<id>-<index>`/`dqReroll-<id>`）、進度條字串 → 全對。
- **replaceSlotIfKey 整合（真表，測試列後刪）**：正確 key→true 且換成新格保持 rerollable、idx1 未動、stale key→false（擋雙擊）、claimed 格→false、測試列已清 → **9/9 斷言通過**。
- `claimSlot` 冪等已在 D1 對真表驗過（true/false）。

## Codex 二驗修正（2 blocker → 金流交易化）

Codex 抓到金流非原子(givePoint 吞錯 → 標已領卻沒入帳;重抽三步非交易 → 免費重抽/穿底)。已改用**單一 TransactWrite**(對齊 train-tycoon / live-vote 房規):

- **`DailyQuestDAO.claimAndCredit(id,date,index,pointΔ,expΔ)`**:同一交易 =「SET quests[i].claimed(條件 done && !claimed)」+「viewer ADD point/exp」。同生同滅 → 不會標已領卻沒入帳;`TransactionCanceledException` → 回 false(已領)。
- **`DailyQuestDAO.rerollAndCharge(id,date,index,oldKey,newSlot,cost)`**:同一交易 =「SET quests[index]=newSlot(條件 key 未變 && !claimed)」+「viewer ADD -cost(條件 point>=cost)」。→ 雙擊只一方成功、不免費重抽、餘額不穿底。
- **記帳分離**:point-log / tax-ledger 由 `DailyQuest.recordPointLog()` 在交易成功**後**補寫(非餘額正確性關鍵),語義同 `givePoint` 的 log 段;為避免動到共用 `ViewerDetailDAO`(tax session 正在改)改用本檔自有的 PlayerPointLog/TaxLedger DAO。
- **prop 獎**:P1 種子池無 prop 任務;prop 路徑仍走 `claimSlot`(原子標)+`giveLogic`(與現有 DailyCheckIn 發道具同標準,非交易化)→ 已在程式與此處**明確標為未交易化**,待日後有 prop 任務再處理。

**驗證(TransactWrite 對真表,13 斷言)**:claimAndCredit 標claimed+餘額+150🦷/+30exp、二次 false 且不重複入帳；rerollAndCharge 足額換格扣80、餘額<80 → false 且**不扣不換(原子中止)**、slot 未變；測試 viewer+daily 列已清。sweetbot-next `bdaae45`。

## Codex 查驗點

1. **領獎冪等**：`onClaim` 先 `claimSlot` 再 givePoint（mark-then-pay）；雙擊/並發只發一次。
2. **重抽原子**：`replaceSlotIfKey` 條件式（key 未變 + 未領）→ 雙擊不會重複扣 80🦷；扣費在換格成功之後。
3. **餘額地板**：givePoint 無下限,`onReroll` 有先擋 `< 80`。
4. **重抽不重複**：新任務排除今日已出現 key；候選空的處理。
5. ownerGuard（他人不能領/重抽別人的表）。
6. customId 解析與 `Config.interactionDataTag` 一致；面板 update 重繪不洗版。
7. 確認未接線（discord.js 尚無 `DailyQuest` 註冊）。
8. 建議：接線 + 重啟後真人 E2E（領獎入帳、重抽扣費、進度條）。

## 尚未做

- **D3**：埋點（checkin / upw·sicbo·bjm·pokingfun·crossroad 的 play+win（isAuto 排除）/ post_message）各加一行 `QuestTracker.getInstance().onXxx()`。
- **wiring**：discord.js 註冊 `dailyQuest.commands` / `dailyQuest.buttons` + 各遊戲埋點 require。
- **restart**（單獨問時機）。
- **E**：streak+1／解滿 3 題 bonus／連續里程碑（P2）＋ VIP 加題已在懶抽支援、待面板 E2E。
