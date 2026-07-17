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

1. **CrossingRoad 未埋（阻斷 q_cross）**：`model/miniGame/CrossingRoad.js` 受 crossroad-guard hook 保護，只有頻道 `1521305720648241193` 可改（本對話頻道無權，連讀都被擋）。種子 `q_cross`（game_play:crossroad）在埋好前**無法完成** → 需到該頻道補 `onGamePlay(id, 'crossroad')`（落袋檢查點或開局處），或先從 P1 種子移除 q_cross。
2. **post_message 白名單/每日上限**：見上，啟用前必補。
3. **prop 獎交易化**：D2 已知——P1 種子無 prop 任務故可接受；prop 任務正式開放前要補交易化或禁止啟用（沿用 D2 註記）。
4. **接線 + 重啟（未做）**：`!每日任務` 面板尚未在 discord.js 註冊；埋點在重啟前不會執行。Codex 提醒：wire 前補 button handler 的 `deferUpdate/deferReply`，避免 DDB 慢時互動逾時。

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
