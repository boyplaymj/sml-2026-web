# 偽文件解謎 v2 — Codex 實作交接規格

> 設計：Claude／實作：Codex　目標：`/opt/sml/sweetbot-next`（discord.js v14、DynamoDB、ap-southeast-1）
> v1 已上線封測（`!解謎`，純文字），本規格是 v2 大改版。**v1 邏輯多可沿用**，主要改：三線索呈現＋公開作答/首殺延遲結算＋概念命中判定。

## 分工（重要）
- **內容/素材（Claude 負責，陸續提供）**：每題的海報圖、對話截圖、假網站（都已可透過檔名/URL 取用），以及 puzzles.json 的文案、概念、引導語。
- **你（Codex）負責**：bot 端全部程式邏輯。先用**深夜顧店 `nightshift-store-clerk`**（本規格已完整給資料）把引擎做通並自驗；其餘題我補資料後自動套用。

## 環境與 git（務必遵守）
- **只改檔案，不要碰 git**：不要 `git checkout -b`、不要 commit、不要 push、不要跑 deploy.sh/restart.sh。（sandbox 下 `.git` 唯讀，且部署由人工把關。）做完把「改了/新增哪些檔」列出來即可，Claude 會 review→commit→部署。
- 改前可先 `git status` 看乾淨度；用 `node --check` 驗語法。
- 沿用現成 DAO：牙齒收發＝`ViewerDetailDAO.givePoint`（扣款用負數，見 v1）、破關記錄＝`PuzzleSolveDAO`。輪詢結算/TransactWrite 範式抄 `model/VotePool.js`。

---

## 1. 新資料模型（puzzles.json 每題）

```jsonc
{
  "id": "nightshift-store-clerk",
  "title": "【急徵】深夜顧店 時薪 480",
  "difficulty": 2,
  "intro": "有人在社區佈告欄拍下這張徵人傳單，還附了一段對話截圖，說『你自己查查那間店就知道了』。",
  "clues": {
    "poster":  "nightshift-poster.png",   // data/puzzle-assets/ 下的圖(海報)
    "message": "nightshift-chat.png",      // data/puzzle-assets/ 下的圖(對話截圖)
    "site":    "https://image.boyplaymj.link/pq/nightshift-archive.html"  // 可瀏覽網站(用連結按鈕)
  },
  "hints": [
    { "cost": 5,  "text": "先讀那張徵人傳單:時薪異常高、凌晨三點後不准應門、後倉不能開——哪裡不對?" },
    { "cost": 15, "text": "看陳小姐的對話:她說地圖上查不到中山路213號、後倉一直有人敲門、然後就已讀不回了。" },
    { "cost": 40, "text": "去點開那個新聞典藏網站,查『中山路213號』和那間超商的現況。答案在三個線索的交集。" }
  ],
  "solution": {
    "core": [
      { "id": "store_gone", "any": ["不存在","213號","查無此址","歇業","廢止","早就關","倒了","沒這地址","不在了"] },
      { "id": "replacement", "any": ["替身","接替","頂替","祭品","下一個","抓交替","被引誘","補她的位"] }
    ],
    "partial": [
      { "id": "clerk_missing",
        "any": ["陳小姐","前店員","上一個","失蹤","不見","出事"],
        "nudge": "你注意到前一位店員了——但這間『店』本身有什麼問題?去查查那個地址。他們找你來,是要你做什麼?" }
    ],
    "genericNudge": "方向還不太對。三個線索都看了嗎?徵人傳單、陳小姐的對話、還有那個新聞網站——把它們湊在一起才看得出來。"
  },
  "reveal": "中山路根本沒有213號——那間超商1998年就歇業廢止了。你手上的徵人傳單,來自一間25年前就不存在的店。當年最後一個夜班店員陳小姐深夜失蹤,簽到簿卻仍逐時有人代簽。這不是顧店的工作,是要你去頂替那個再也沒簽下一行名字的人。",
  "reward": { "base": 120, "perHintPenalty": 30, "firstSolveBonus": 60, "min": 25 },
  "revealDelayMin": 5
}
```
（v1 舊欄位 `body`/`footer`/`answer.accept` 淘汰；`limits` 沿用 v1 冷卻/鎖定，值見現行 puzzles.json。）

## 2. 答案判定：概念命中式（取代 answerMatches 扁平比對）

```
normalize = v1 的 normalizeAnswer (NFKC+去空白標點)
coreHit  = solution.core   中「any 任一關鍵詞(normalize後)出現在玩家輸入」的概念數
partHit  = solution.partial 中命中的項

判定:
  coreHit == core.length            → SOLVED(破案)
  else 命中任一 partial              → 回該 partial.nudge (多個則取第一個命中)
  else coreHit > 0(部分核心)         → 回「你抓到一部分了,但還缺另一個關鍵。」+ genericNudge
  else                               → genericNudge
```
淘汰 v1 的「input.includes(target) 一律過」寬鬆比對(那會讓枝節誤判過關)。核心概念要**全中**才算對。

## 3. 呈現：`!解謎` 開一個「公開案件」

- `!解謎`（限測試頻道 `903327108451950692`）在頻道**公開**貼出案件訊息:
  - 一則 embed:標題＋`intro`＋難度，`setImage(attachment://poster)`
  - 對話截圖:第二張圖(可用第二個 embed 的 image,或同訊息第二個 attachment)
  - 元件列:**🌐 開啟線索網站**(ButtonBuilder `.setURL(clues.site)` 的 Link 按鈕)、🔍 買提示、✏️ 提交答案
  - 兩張圖用 `AttachmentBuilder(path)` 從 `data/puzzle-assets/<檔名>` 掛載;缺圖則退回只放文字(fallback)。
- 同頻道同一題若已有進行中案件,`!解謎` 顯示現有那則(別重開)。封測階段一次一題即可。

## 4. 結算流程：公開作答 · 暗中對錯 · 首殺延遲

**提交答案(✏️→Modal 打字)：**
1. Bot 在頻道**公開**貼:`🕵️ <@玩家> 提出推理:「<答案原文>」`（**不顯示對錯**）。
2. 判定後**只私訊(ephemeral)給該玩家**:
   - SOLVED → 記破關+發獎(TransactWrite,冪等,每人每題一次)。私訊:`✅ 你解開了!你是第 N 個。真相與首殺榜會在 ${revealDelayMin} 分鐘後公佈,先別爆雷。`**不在此時給看 reveal 全文**(防劇透)。
   - NUDGE → 私訊該引導語。
   - 純錯 → 私訊 genericNudge + 冷卻(沿用 v1 limits)。
3. **防劇透關鍵**:答對者當下不看真相、頻道不顯示誰對——維持懸念。

**首殺延遲公佈(要持久化,重啟不掉,抄 VotePool 輪詢結算)：**
- 第一個 SOLVED 時,在案件狀態記 `firstSolvedAt`、`revealAt = now + revealDelayMin*60000`、`firstSolver`。存 DDB(可用 `PuzzleSolveDAO` 另開一種 record,或新表 `sweetbot-puzzle-round`,PK=`round#<channelId>#<puzzleId>`)。
- 一個 setInterval 輪詢器(啟動時掛,~30s 一次):找 `revealAt<=now 且未 revealed` 的案件 → 頻道**公開**貼揭曉 embed:`🏆 首殺:<@firstSolver>` ＋ `reveal` 全文 ＋(可列出倒數期間解開的名單)＋標記 `revealed=true`,並把原案件按鈕 disable。
- 倒數期間後續 SOLVED 的人:一樣私下發獎+記錄,列進公佈名單。

## 5. 買提示（沿用 v1，僅注意）
- 扣主牙齒 `point`(v1 已修:`ViewerDetailDAO.selectOne({discordID}).point` 讀、`givePoint([id],-cost,'point',原因)` 扣)。逐層解鎖,`hints[]` 三層。提示是**私人**行為(ephemeral),各付各的。

## 6. DynamoDB
- 破關記錄沿用 `sweetbot-puzzle-solve`(PK=`<userId>#<puzzleId>`)。
- 案件回合狀態:新增 `sweetbot-puzzle-round`(PAY_PER_REQUEST,PK=`id` String=`<channelId>#<puzzleId>`),欄位:firstSolvedAt/revealAt/revealed/firstSolver/solvers[]。**建表指令請寫成 migration 檔但別自己跑**(列在回報,由人工建;或若有權限可建,建完註明)。

## 7. 素材檔路徑約定
- 圖放 `data/puzzle-assets/`(海報、對話截圖)。深夜顧店的兩張圖 Claude 會放進去;你先寫成讀該資料夾+檔名,缺檔 fallback 純文字即可,不要因缺圖 crash。
- 網站是外部 URL(image.boyplaymj.link/pq/*.html),用 Link 按鈕,不需 bot 端檔案。

## 8. 自驗(回報時逐條)
1. `node --check` 全部改動檔通過。
2. 概念判定:核心全中才 SOLVED;只中枝節→回該題 nudge;亂打→genericNudge。用 nightshift 舉幾個輸入證明(例:「前店員死了」→只得引導不算對;「這店根本不存在 我是去頂替失蹤的店員」→SOLVED)。
3. 公開作答:提交後頻道出現公開推理訊息且**不含對錯**;對錯只在 ephemeral。
4. 首殺延遲:首殺後 reveal 不即時、由輪詢器於 revealAt 後公佈;殺掉重啟後(狀態在DDB)輪詢器仍會補公佈(講清楚你怎麼保證)。
5. 發獎冪等:同人同題只發一次;併發提交不重複發。
6. 缺圖 fallback 不 crash。

## 9. 回報格式
列出:改/新增檔清單、`sweetbot-puzzle-round` 建了沒、§8 每條自驗結果、待人工確認事項、以及「Claude 要放哪些素材檔進 data/puzzle-assets/、其餘4題還缺什麼資料」。**不要自行部署**,等 Claude review。
