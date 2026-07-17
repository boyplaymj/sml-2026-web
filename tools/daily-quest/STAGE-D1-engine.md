# 每日任務 — 階段 D1：bot 引擎 + DAO（交 Codex 查驗）

> 位置:`/opt/sml/sweetbot-next`(甜甜 bot)。**純 code、未接 discord、未重啟、不影響線上**（新檔沒有任何現有程式 require 它）。

## 新增檔案（5）

| 檔 | 內容 |
|---|---|
| `DAO/QuestConfigDAO.js` | 讀 `sweetbot-quest-config`（`listEnabled` 供懶抽） |
| `DAO/DailyQuestDAO.js` | `sweetbot-daily-quest` 複合鍵（discordId+date）：`getDoc` / `createIfAbsent`(條件式擋併發重抽) / `setQuests` / **`claimSlot`(冪等原子領獎)** / **`markRerollUsed`(冪等)** |
| `DAO/QuestStreakDAO.js` | `sweetbot-quest-streak` 存取器（streak 邏輯屬階段 E，先備妥） |
| `model/QuestTracker.js` | 引擎:純函式 + 懶抽 + `track()` + singleton |
| `test/questTracker.test.js` | 30 條純函式單測 |

均繼承 `DAO/DDB/DDBBaseDAO.js`（region ap-southeast-1，共享 client，無需 MySQL connection）。

## 設計要點

- **05:00 切日**：`dateKeyOf()` 台灣時區、05:00 前算前一天。
- **懶抽**：`getOrCreateToday()` — 今日文件不存在才抽；VIP 決定張數（3+vipLevel，`ViewerDAO.getByDcID().vipLevel`）；依 weight 不重複抽（`weightedDraw`）；`createIfAbsent` 用 `attribute_not_exists(discordId)` 條件式，**併發搶輸則改讀既有**（不會抽兩份）。
- **快照**：抽出當下把 title/desc/target/reward 快照進 quest 格 → 後台事後改 config 不影響今天已抽出的任務。
- **event 比對**（`eventMatches`）：無冒號事件需 key=null；`base:any` 對任意；`base:xxx` 需 key 相符。
- **進度**（`applyProgress`）：純函式、不就地改動；已 done 不再累加；progress 封頂在 target；回 `newlyDone`。
- **一點兩用**：`onGamePlay` 同時發 `game_play:any` + `game_play:<game>`；`onGameWin` 對 winners 去重後各發 `:any`+`:<game>`。
- **fire-and-forget**：`track()` 全程 try/catch，埋點失敗只 console.log，**絕不中斷遊戲主流程**。
- **領獎原子性**（給 D2 用）：`claimSlot` 條件 `done=true AND claimed=false` → 同格不會被領兩次（即使並發）。

## 驗證（已跑）

- **語法**：5 檔 `node --check` 全過。
- **單測**：`node test/questTracker.test.js` → **30/30 斷言通過**（dateKeyOf 邊界 / weightedDraw 抽數·不重複·權重·全0備援·n>pool / eventMatches 全分支 / applyProgress 封頂·跳過done·不就地改·newlyDone / toQuestSlot 型別強制·首格rerollable）。
- **DDB 整合**（對真表跑一輪測試 id 再刪除）：
  1. 懶抽建立 3 題（真 config 13 池抽出 q_msg3/q_sicbo/q_upw）、reward 快照正確、idx0 rerollable ✅
  2. 二次 `getOrCreateToday` 回同一份（assignedAt 相同，不重抽）✅
  3. `track` 匹配事件 → progress 封頂達標 done ✅
  4. `claimSlot` 首次 true、二次 false（冪等）✅
  5. `markRerollUsed` 首次 true、二次 false（冪等）✅
  6. 測試列已清除 ✅

## Codex 查驗點

1. 複合鍵 `getDoc/createIfAbsent/setQuests` 正確;條件式 `attribute_not_exists(discordId)` 能擋併發重抽。
2. `claimSlot` / `markRerollUsed` 的 `ConditionExpression` 冪等（並發只有一方成功）。
3. `weightedDraw` 加權不重複、n>pool、全0權重不爆（已測，複驗邏輯）。
4. `eventMatches` / `applyProgress` 邊界；快照欄位齊全（D2 面板/領獎要用）。
5. singleton `getInstance()` 無 connection 可安全建立（供 D3 各遊戲 require）。
6. 確認**未接線**：`grep -rn QuestTracker discord.js` 應無結果（D1 不動主流程）。

## 尚未做

- **D2**：`model/DailyQuest.js` — `!每日任務` 面板（embed + 領獎鈕/重抽鈕）+ givePoint 發獎（'point'/'experience'）+ claimSlot 冪等。
- **D3**：埋點（checkin / 5 遊戲 play+win（isAuto 排除）/ post_message）各加一行 `QuestTracker.getInstance().onXxx()`。
- 之後：wire discord.js 註冊指令/按鈕 + **restart（單獨問時機）**。
