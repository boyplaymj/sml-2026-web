# 每日任務 D3 — 各遊戲埋點（QuestTracker）

> 狀態：**埋點 code 完成、已驗證、未接線 `!每日任務` 面板、未重啟**。每處一行 fire-and-forget、`track()` 內部全 try/catch 絕不拖累遊戲主流程。singleton `QuestTracker.getInstance()` 免 connection（DAO 走共享 DDB client），故各遊戲直接 `require` 呼叫、不需在 discord.js 穿參數。
> 對象：活的遊戲檔在 `model/miniGame/*`（top-level `model/DaVinciCode.js`/`SicBo.js` 等是舊版、discord.js 未 require，不碰）；賓果在 `model/Bingo.js`。

## 埋點清單

| 遊戲(gameKey) | 檔案 | game_play 點 | game_win 點 | 自動局排除 |
|---|---|---|---|---|
| 骰寶(sicbo) | miniGame/SicBo.js | `bet()` 下注後 `button.user.id` | 結算 `playerID` | `!game.isAuto` ✅ |
| 21點(bjm) | miniGame/BlackJack.js | join `button.user.id` | 結算 `result.winner.dcID` | `!game.isAuto` ✅ |
| 射龍門(inbetween) | miniGame/InBetween.js | 開局 `players[]`（forEach） | 中獎 `button.user.id` | 無自動局 |
| 戳戳樂(pokingfun) | miniGame/PokingFun.js | 每戳 `discordID` | **不埋**（抽獎性質、每戳必給獎，不計 win/lose） | 無自動局 |
| 猜數字(upw) | miniGame/DaVinciCode.js | 開局者 `game.players[isOpen].dcID` | 解出 `giveList`（合作制全員） | 無自動局 |
| 1A2B(abcode) | miniGame/ABCode.js | 開局者 `game.players[isOpen].dcID` | 解出 `giveList`（合作制全員） | 無自動局 |
| 猜拳(rps) | miniGame/RockPaperScissors.js | 開局雙方 `[challengerID, creatorID]`（forEach） | `winnerID`（在 `loserID!=''` 內 → 平手不計） | 純手動 |
| PK罰球(pkpenalty) | miniGame/PkPenalty.js | 每次踢 `game.challengerId` | 守住 `isSaved` → `game.challengerId` | kick 恆真人 |
| 推筒子(pusher) | miniGame/Pusher.js | 挑戰者上桌 `button.user.id` | `!winnerIsCreator` 分支 `game.challengerID` | 挑戰者恆真人（甜甜當莊不影響） |
| 猜花(flowertime) | miniGame/FlowerTime.js | 綁定玩家有效猜測 `discordID`（限進 userList） | 中獎名單 `discordIds[]` | — |
| 賓果(bingo) | model/Bingo.js | 建盤 `discordId` | 領獎（完成連線）`authorId` | 無自動局 |
| **簽到(checkin)** | model/DailyCheckIn.js | — | `checkIn()` 成功發獎後 `discordID` | — |
| **發言(post_message)** | discord.js `messageCreate` | 非指令 + 白名單頻道 + ≥5字 `msg.author.id` | — | fail-closed（見下） |

## 設計判斷（非機械照抄 findings）

- **自動局排除**：SicBo / BlackJack 的自動局（甜甜自動開）也流經同一 bet/結算點，用 `!game.isAuto` 擋（防 farm，設計 §4A）。Pusher 的 `isAuto` 指「甜甜當莊」，挑戰者恆為真人 → **不擋**（真人確實在玩/贏）。
- **戳戳樂只埋 play**：每戳必得獎、無 win/lose 概念，若計 game_win:any 會讓「贏任一遊戲」被戳戳樂灌爆 → 只計遊玩。
- **合作制(upw/abcode)**：game_play 記在**開局者**（開局才扣費、單點好埋；「玩一局」門檻＝開一局即可，可接受 joiner 不另計）；game_win 記 `giveList`**全體參與者**（解出全員同額發獎）。
- **猜拳平手不計勝**：埋在 `if (loserID != '')` 區塊內、用 `winnerID`，平手時 loserID 為空自然跳過。
- **PK＝守門**：玩家當門將、沒進球(`isSaved`)才算勝（對齊既有獎勵語意）。
- **猜花只算綁定玩家的 play**：埋在 `userList[discordID]=…`（viewer!=null）分支，未綁定者不計（未綁也無從領獎）。

## fail-closed：post_message 防 farm

P1 種子池含 `q_msg1`/`q_msg3`（post_message 任務），但頻道白名單／每日上限是**待定政策**（DESIGN §8.3）。故 discord.js 埋點採 **fail-closed**：
```
const QUEST_POST_MSG_CHANNELS = new Set([]); // 空 = 不追蹤任何頻道發言
```
上線即開 = farm 洞，因此**空集合預設不觸發**。啟用 q_msg 任務前，先在此填入允許計數的頻道 ID（＋視需要加每日上限），否則發言任務永遠 0 進度（安全側）。

## 🔴 待辦 / 阻斷

1. ✅ **CrossingRoad 已埋（原阻斷已解）**：crossroad 頻道 session 於 `463383f` 補上 `onGamePlay(creatorID, 'crossroad')`，已上線。詳見下方「上線後修正」。
2. ✅ **post_message 白名單已填**：`QUEST_POST_MSG_CHANNELS` 填入 4 頻道（`875598772334379019` / `877434541759922206` / `1109202254805860432` / `1526901206683877556`）；每日上限仍未加（洗頻風險由頻道白名單 + ≥5 字 + 非指令緩解，日後可再加 cap）。
3. **prop 獎交易化**：D2 已知——P1 種子無 prop 任務故可接受；prop 任務正式開放前要補交易化或禁止啟用（沿用 D2 註記）。
4. ✅ **接線 + 重啟（已做）**：`!每日` 面板已在 discord.js 註冊（`b7bb4a9`）並多次重啟生效。`deferUpdate/deferReply` **仍未補**（實測路徑 <200ms、全 bot 慣例不 defer，列可選硬化）。

## 驗證（已跑）

- 14 檔 `node --check` 全過（含 discord.js 二次）。
- `questTracker.test.js`：**37/37**（`NODE_ENV=development node --test`）。
- `QuestTracker.getInstance()` 無 connection 建構成功，四個包裝方法（onGamePlay/onGameWin/onCheckin/onMessage）皆在；miniGame 相對路徑 `../QuestTracker.js`、Bingo `./QuestTracker.js`、discord.js `./model/QuestTracker.js` 皆解析。
- 埋點呼叫沿用專案既有 floating-promise 慣例（如 InBetween `givePoint` 不 await）；`track()` 內部全 catch → 不 reject、不影響遊戲流程。

## Codex 查驗點

1. 各 game_play/game_win 是否埋在正確的「正式局/確定發獎」點（見清單），無重複累加（D1 已修 `:any` 重複 bug，埋點只送一次 `track(base, gameKey)`）。
2. SicBo/BlackJack 的 `!game.isAuto` 是否確實在 play/win 兩點的 `game` 作用域內（已核對在 scope）。
3. post_message fail-closed 是否符合預期（空白名單＝不計）。
4. CrossingRoad 阻斷處置（補埋 or 移除 q_cross 種子）。

---

# 上線後修正（2026-07-17，交 Codex 複驗）

D3 已全上線（`!每日` 面板接線 `b7bb4a9`、post_message 白名單填 4 頻道、UI 自訂 emoji）。上線後真人使用抓到 **2 個真 bug + 1 個原阻斷已解**，均已修並重啟生效。以下請 Codex 複驗。

## 修正 A — 進度併發覆蓋（cross-slot clobber）　commit `415b6d9`

- **症狀**：玩家簽到後「簽到任務」沒解掉（`982276830662909963`，實測 q_checkin 停 0，但同 doc 的 q_msg3=3/3）。
- **根因**：`QuestTracker.track()` 原用 `DailyQuestDAO.setQuests`＝ **`SET quests = :q` 整陣列覆寫**（讀→改記憶體→整包寫回，非原子）。玩家短時間內多事件（簽到 idx0 + 發言 idx2）併發時，後到事件用**舊快照**整陣列寫回，把先前事件的進度洗掉；最後寫入者（post_message）留存 → q_checkin 被蓋回 0。**任何人短時間觸發多個任務事件都會中。**
- **修法**：
  - 新增 `DailyQuestDAO.bumpSlot(discordId, date, index, progress, done)`：按 list index **原子更新單一格** `SET quests[i].progress/done`，`ConditionExpression: quests[i].progress < :p` 擋 progress 倒退（stale 較低寫入被拒、冪等）；`ConditionalCheckFailedException` 吞掉略過。
  - `track()` 改為 `applyProgress` 後**只逐格 bumpSlot 有變動的 index** → 跨格併發互不覆蓋。
  - `setQuests` 保留但加註「非原子、勿用於進度累加」。
- **證據**：questTracker 單元 37/37；**真表併發 smoke**（同時 `track(checkin)` + `track(post_message)`）兩格都保留、都完成（舊碼會被蓋掉一格）；測試列已清。
- **殘留（已知、非本次情境）**：**同一格**極短時間爆發多個事件仍可能少算 1（兩者都讀到同一舊值、都寫同一新值）。要根治可改 atomic `ADD`（但 `done` 需另處理，避免破壞 claim 條件）。日常同格連發（如狂發訊息）才會遇到，影響小。
- **檔案**：`DAO/DailyQuestDAO.js`（+bumpSlot）、`model/QuestTracker.js`（track 改逐格）。

## 修正 B — 合作制只認發起人（UPW / 1A2B）　commit `04b7f27`

- **症狀**：玩家玩了 `!upw` 但 `q_upw`（game_play:upw）沒解（`427445303504011274`，q_play3=any 已滿但 q_upw=0）。
- **根因**：UPW/ABCode 是合作制（`!upw` 開局、`!upwJoin` 加入），但埋點只送 `game.players[isOpen].dcID`（**開局者**）。**join 別人局的參與者玩了不計。**
- **修法**：在發牌 `init()`（此時 `game.players` 已含所有 joiner，下一行還 `shuffle(game.players)`）改為 `game.players.forEach((p) => onGamePlay(p.dcID, key))` → **全體參與者各計一次**。UPW + ABCode 同 pattern 一併修。
  - 一次觸發一場、`game.players` 去重（各玩家一列）→ 每場每人 +1，無重複累加。仍在 `if (!button.isAdmin)` 內（admin 開的局不計，屬邊緣情形）。
- **檔案**：`model/miniGame/DaVinciCode.js`、`model/miniGame/ABCode.js`。
- **已檢視同類**：射龍門（`players[]` 開局全體已計）、猜拳（`[challengerID, creatorID]` 已計）皆 OK；只有「開局者 vs joiner」結構的 UPW/ABCode 踩到。

## 原阻斷已解 — CrossingRoad 埋點　commit `463383f`（crossroad 頻道 session 補）

- 於 `startGame()` 扣入場費後 `onGamePlay(creatorID, 'crossroad')`（單人局、每局一次、`:any` 自動命中）。Claude 已複核 diff：位置/變數/去重/與併發修相容皆正確。已隨重啟生效。

## 受影響玩家手動補償（用 bumpSlot 補進度、走正常領獎）

| discordId | 補的格 | 原因 |
|---|---|---|
| `638704899231580172` | q_cross | crossroad 埋點上線前已玩 |
| `982276830662909963` | q_checkin | 修正 A 併發覆蓋 |
| `427445303504011274` | q_upw | 修正 B joiner 不計 |

> 手動補只補「進度→done、claimed 留 false」，玩家自行開 `!每日` 點領獎，仍走已驗證的 `claimAndCredit` 原子入帳。已卡住的舊資料不回溯。

## Codex 複驗點（本次新增）

1. **bumpSlot 原子性 + 條件**：`SET quests[i].progress/done` + `quests[i].progress < :p` 是否正確擋倒退、且不會漏更新 done；`ConditionalCheckFailedException` 吞掉是否合理（併發搶輸＝已被更高進度寫入，略過對）。
2. **track 逐格更新**：`applyProgress` 後只寫「progress 或 done 有變」的 index，是否涵蓋所有變動格、無漏無重。
3. **殘留同格併發**：是否接受同格爆發少算 1，或要求改 atomic ADD（含對 claim 條件 `done` 的影響評估）。
4. **UPW/ABCode 全體計**：`game.players.forEach` 是否可能重複觸發（`init` 是否可能對同場重入 → 開局費也在此、若重入是既有問題）；admin 開局不計是否可接受。
5. **手動補償**：bumpSlot 直接寫 done 是否有副作用（例如 streak/連續達成之後階段 E 的計數，目前 E 未實作）。
