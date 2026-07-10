# 甜甜解謎遊戲「偽文件解謎」— Codex 實作交接規格

> 設計者：Claude（SML_Claude）／實作：Codex
> 目標專案：`/opt/sml/sweetbot-next`（discord.js v14.11.0，DynamoDB，區域 ap-southeast-1）
> 版本：v1 免費制
> 最後更新：2026-07-10

---

## 0. 這是什麼遊戲

模仿 Threads 上 solve.quest 的「偽文件解謎」：甜甜貼出一則**表面正常、實則藏線索的文件**（協尋啟事／租屋廣告／徵人啟事…），玩家自己重讀找出破綻，提交答案破關。免費挑戰、破關發牙齒。

**核心體驗**：讀第一次像正常文件，讀第二次全是鉤子。爽點＝玩家自己發現「哪裡不對勁」。

---

## 1. 玩法流程（玩家視角）

```
玩家: !解謎                → 甜甜隨機/指定發一題偽文件 embed，附兩顆按鈕
      [🔍 買提示]  [✏️ 提交答案]

點 [🔍 買提示]             → 花牙齒逐層解鎖提示（鉤子層→矛盾層→鑰匙層），越後層越貴
                             扣費前先確認餘額，deductTeeth 回 false=餘額不足要擋下

點 [✏️ 提交答案]           → 彈出 Modal 文字輸入框，玩家打答案送出
   ✅ 比對通過             → 揭曉真相劇情 embed + 發牙齒 + 寫破關記錄 + (首殺則額外加成)
   ❌ 比對失敗             → 回覆「再想想」，記一次錯誤；冷卻 N 秒；答錯達上限鎖一段時間
```

**鐵律**
- **每題每人只能破關領獎一次**——這是防掏空的命門。提交/發獎前務必查破關記錄表，已破關者不再發獎（可回覆「你已解開此案」）。
- Modal 輸入答案不洗頻道、答案不外露眼前（比 `!解答 xxx` 好，選 Modal）。

---

## 2. 要新增的檔案

| 檔案 | 作用 | 抄哪個現成範式 |
|------|------|--------------|
| `model/PuzzleQuest.js` | 遊戲主邏輯：指令、按鈕、Modal handler、發獎 | `model/VotePool.js`（embed＋按鈕＋TransactWrite） |
| `config/puzzles/*.json` 或 `data/puzzles.json` | 題庫，一題一物件（結構見 §4） | 新增；跟現有 config 放一起 |
| `DAO/DDB/PuzzleSolveDAO.js` | 破關記錄 CRUD | `DAO/VoteBallotDAO.js`（照抄改表名/欄位） |

牙齒收發**沿用現成 DAO，不要另寫**：
- 讀餘額／扣提示費：`DAO/DDB/MarketWalletDAO.js` 的 `getWallet` / `deductTeeth`
- 發破關獎：`DAO/DDB/ViewerDetailDAO.js` 的 `givePoint(discordIds, teeth, 'point', reason)`（自帶流水帳）
  - ⚠️ `givePoint` 會吞 DDB 錯誤（`.catch(()=>{})`）。**發獎＋寫破關記錄要冪等**：用 `TransactWriteCommand` 把「寫破關記錄（conditional put, 不存在才寫）」和發獎綁在一起，或先原子寫記錄成功再發獎，避免重複領。參考 `model/VotePool.js` L177+ 的 transaction 寫法。

---

## 3. 指令與按鈕註冊（照現有 pooled array 模式）

在 `PuzzleQuest.js` 建構時註冊，並在 `discord.js` 掛上（比照其他 model 的掛法）：

```js
this.commands = [
  { key: '解謎', blockCriminal: true, usePermission: 0, tips: 'playPuzzle', func: this.startPuzzle.bind(this) },
  // 可選：!解謎 <題號> 指定題；!解謎進度 看自己破了幾案
];

this.buttons = [
  { key: 'puzzleHint',   blockCriminal: true, usePermission: 0, func: this.buyHint.bind(this) },
  { key: 'puzzleSubmit', blockCriminal: true, usePermission: 0, func: this.openAnswerModal.bind(this) },
];
```

- customId 用 `Config.interactionDataTag`（`-`）夾帶 `puzzleId`，例：`puzzleHint-<puzzleId>`、`puzzleSubmit-<puzzleId>`。
- Modal 提交是 `interaction.isModalSubmit()`——確認 `discord.js` 主 interaction handler 有處理 modal 分支；若無，比照 button 分支新增一段路由到 `this.handleAnswer`。
- 所有 interaction 先 `deferReply({ ephemeral: true })` 或 `deferUpdate`，避免 3 秒逾時。

---

## 4. 題庫 JSON 結構（一題一物件）

```jsonc
{
  "id": "missing-child-2003",        // 唯一鍵，也是破關記錄 PK 的一部分
  "title": "協尋啟事",                // embed 標題
  "docType": "missing_poster",       // 外殼類型（協尋/租屋/徵人…），純標記
  "body": "……偽文件全文（含隱藏線索）……",  // embed 主文
  "footer": "發布於 2003/07/04",       // 可選
  "hints": [                          // 三層提示，index 0→2 由淺到深
    { "cost": 5,  "text": "鉤子層提示…" },
    { "cost": 15, "text": "矛盾層提示…" },
    { "cost": 40, "text": "鑰匙層提示…" }
  ],
  "answer": {
    "accept": ["正解關鍵字", "同義寫法", "諧音容錯"],  // 任一命中即算對
    "normalize": true                  // 比對前做正規化（見 §5）
  },
  "reveal": "……破關後揭曉的真相劇情文……",  // 破關才顯示
  "reward": {
    "base": 100,                       // 不買提示破關的滿額獎
    "perHintPenalty": 25,              // 每買一層提示，破關獎 -25
    "firstSolveBonus": 50,             // 首殺加成（全服第一個解出此題）
    "min": 20                          // 獎勵地板，不低於此
  },
  "limits": {
    "wrongCooldownSec": 15,            // 答錯冷卻
    "maxWrongPerWindow": 5,            // 視窗內答錯上限
    "lockMinutesOnMax": 30             // 達上限鎖多久
  }
}
```

**發獎公式**：`reward = max(min, base - perHintPenalty * hintsBought)`，若首殺再 `+ firstSolveBonus`。

---

## 5. 答案模糊比對（避免答對意思卻卡錯字）

實作一個 `normalizeAnswer(s)`：
1. 去除所有空白、標點、全形→半形
2. 統一大小寫、繁簡不強制但可選
3. 對照 `answer.accept` 陣列，任一 `normalize` 後相等即通過
4. （進階可選）注音/諧音容錯：把常見諧音對映表帶入；v1 可先只做 1–2，把容錯寫進 `accept` 陣列即可，不用寫演算法

---

## 6. DynamoDB 破關記錄表

新表 `sweetbot-puzzle-solve`（PAY_PER_REQUEST，比照其他 sweetbot-* 表）：

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` (PK) | String | `<userId>#<puzzleId>`，天然擋重領 |
| `userId` | String | Discord ID，**一律 `String()`** |
| `puzzleId` | String | 題目 id |
| `solvedAt` | Number | epoch ms |
| `hintsBought` | Number | 破關時已買幾層（決定發了多少獎） |
| `rewarded` | Number | 實發牙齒 |
| `firstSolve` | Bool | 是否首殺 |

進行中的狀態（買了哪些提示、答錯次數、冷卻到期）**可先用 in-memory Map**（比照 RPS/BlackJack 的 `gameList` 用法），bot 重啟即清空可接受；若要持久化再加欄位或另表。

**首殺判定**：對某 `puzzleId` 做 query（GSI 或 scan filter `puzzleId=` limit 1），無任何記錄＝首殺。量小可接受；要嚴謹可加 `firstSolveClaimed` flag 用 conditional write 搶。

---

## 7. 地雷清單（務必遵守）

- [ ] `userId` 一律 `String(discordId)`，DDB 型別敏感
- [ ] `deductTeeth` 回 **false = 餘額不足**，要擋下並回覆玩家，不可當成功
- [ ] `givePoint` 吞錯誤 → 發獎＋寫破關記錄要冪等（TransactWrite 或先原子寫記錄）
- [ ] 每題每人破關**只發一次**：發獎前查 `sweetbot-puzzle-solve` 有無 `<userId>#<puzzleId>`
- [ ] 所有 interaction 先 defer，避免 3 秒逾時
- [ ] Modal answer 分支要真的被 `discord.js` 路由到（確認 isModalSubmit 有掛）
- [ ] **改檔前先跑 `bash check-conflict.sh model/PuzzleQuest.js …`**（併行 AI 快照雷）
- [ ] 不要在 sweetbot-next 留未提交暫時編輯（會被別的 AI 自動快照吃進 commit）
- [ ] 測試先發到私人測試頻道 `903327108451950692`，確認後才進正式

---

## 8. 部署流程

```bash
cd /opt/sml/sweetbot-next
bash check-conflict.sh model/PuzzleQuest.js DAO/DDB/PuzzleSolveDAO.js data/puzzles.json
# …實作、本地 lint / node 語法檢查…
git add -A && git commit -m "feat(game): 偽文件解謎（免費制）"
bash deploy.sh        # 會 push origin/main + systemctl restart sweetbot-next
```
建表：`sweetbot-puzzle-solve`（PAY_PER_REQUEST，PK=id String），可用 AWS CLI 或比照現有建表腳本。

---

## 9. 驗收清單（Codex 自驗＋回報）

1. `!解謎` 能發出偽文件 embed，兩顆按鈕可點
2. 買提示：正確扣牙齒、餘額不足會擋、逐層解鎖、重複買同層不重扣
3. 提交答案：Modal 正常彈出、模糊比對能吃同義/容錯、答對揭曉真相並發獎
4. **重領測試**：同一人同題再解，不再發獎（查得到破關記錄）
5. 發獎公式正確：買越多提示領越少、不低於 min、首殺有加成
6. 答錯冷卻與上限鎖有生效
7. userId 全程 String，無 DDB 型別錯
8. 併發領獎（快速點兩次提交）不會重複發——TransactWrite 擋住

---

## 附：一題完整範例（可直接進題庫）

```jsonc
{
  "id": "rent-topfloor-wangchuan",
  "title": "【出租】市區套房 頂樓加蓋 租金便宜",
  "docType": "rent_ad",
  "body": "坪數 8 坪，開放式衛浴，限女性。\n屋齡 12 年，前房客已搬走，押一付三。\n採光佳，下午四點後日照最強。\n意者電洽 0912-070-408，非誠勿擾。\n地址：忘川路 3 巷 7 號 頂加。",
  "footer": "刊登於社區佈告欄",
  "hints": [
    { "cost": 5,  "text": "頂樓加蓋為何『下午四點後』才日照最強？頂加通常整天曬。這句話不合理。" },
    { "cost": 15, "text": "屋齡 12 年、前房客『已搬走』、押一付三異常便宜、限女性——這間房發生過事。" },
    { "cost": 40, "text": "把電話末六碼 070-408 唸出來，再看『忘川路』是什麼路。這不是租屋廣告。" }
  ],
  "answer": {
    "accept": ["招魂", "找家屬", "找死者家屬", "你想你別走", "這是招魂啟事", "前房客死了", "墜樓"],
    "normalize": true
  },
  "reveal": "這不是租屋廣告。電話 070-408 諧音『你想你別走』，『忘川路』是陰間意象，『限女性』呼應當年墜樓的女房客。刊登者其實是在招魂——想找回那位再也沒能搬走的房客，或她的家屬。你讀懂了藏在日常裡的訃告。",
  "reward": { "base": 100, "perHintPenalty": 25, "firstSolveBonus": 50, "min": 20 },
  "limits": { "wrongCooldownSec": 15, "maxWrongPerWindow": 5, "lockMinutesOnMax": 30 }
}
```
