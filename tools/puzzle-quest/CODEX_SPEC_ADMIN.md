# 偽文件解謎 · 遊戲館後台管理 — Codex 實作交接規格

> 設計：Claude／實作：Codex。目標：讓管理員在甜甜遊戲館(sweetbot-games.web.app)管理 `!解謎` 題目：
> ①選目前出哪一題 ②檢視三線索(圖/圖/網站) ③編輯文字欄位(即時生效)。
> 全部**沿用現有模式**，路徑與範本見下。改前先 `bash check-conflict.sh`(遊戲館多AI併行)。

## 0. 資料層(Claude 已建好，勿重建)
- DDB 表 **`sweetbot-puzzle`**(ap-southeast-1, PK=`id`, PAY_PER_REQUEST)：
  - 8 筆題目(id=各puzzle id，欄位=puzzles.json 每題全欄位＋`_type:"puzzle"`)
  - 1 筆設定 `id="__config__"`, `_type:"config"`, `activePuzzleId:""`(空=隨機)
- 海報/對話圖已上 S3：`https://image.boyplaymj.link/pq/assets/<檔名>`(如 rent-poster.png)。
- 網站已在 `https://image.boyplaymj.link/pq/<id前綴>-archive.html`(見各題 clues.site)。

## 1. Lambda `sml-puzzle-admin`（新增）
- **範本照抄** `/opt/sml/score-repo/tools/lambda/sml-random-events/index.js`(認證/CORS/dispatch)＋`sml-teeth-economy/index.js`(verifyIdToken RS256、getAllowlist)。
- 認證：Firebase ID token(RS256自驗，aud/iss=`sml2026newscore`)＋ `config/gameAdmins` 白名單(Firestore REST，快取)。非白名單回 403。
- DDB：`@aws-sdk/lib-dynamodb`，表 `sweetbot-puzzle`。
- Actions(POST JSON `{action,...}`)：
  - `list` → 回全題精簡：`[{id,title,difficulty,active:bool}]`(active = id===config.activePuzzleId)
  - `get {id}` → 回該題完整定義(給檢視+編輯表單)
  - `setActive {id}` → 寫 `__config__.activePuzzleId=id`(id=""表示恢復隨機)。回 ok
  - `update {id, patch}` → 只允許更新**文字欄位**：`intro`、`hints`(陣列，各 text/cost)、`solution`(core/partial 的 any 關鍵詞陣列＋nudge、genericNudge)、`reveal`、`difficulty`。**禁止**改 `clues`(圖/網站)與 `id`。以 UpdateItem/Put 合併寫回。回更新後全題。
- 部署：比照 random-events(打包 zip → `aws lambda create-function`/`update-function-code`，region ap-southeast-1，附 DDB 讀寫 + 網路存取 IAM)。**建新 HTTP API Gateway**，記錄 invoke URL。**IAM/APIGW 建立步驟請列在回報，若權限不足就標明需人工執行。**

## 2. 前端頁 `/opt/sml/sweetbot-site/public/puzzle_manager.html`（新增）
- **範本照抄** `economy.html`：Firebase(sml2026newscore) Google 登入、`getIdToken()`、`fetch(API,{Authorization:'Bearer '+token, body:{action}})`、403→顯示「非管理員」。Tailwind、純 HTML+JS。
- `const API='<新 APIGW invoke URL>'`。
- 版面：
  - 左：題目清單(list)，每題顯示 title＋難度，一顆「**設為目前題目**」(setActive)，目前題標記●。另一顆「恢復隨機」(setActive id="")。
  - 右：選題後(get)顯示：
    - **三線索檢視**：海報圖 `<img src=".../pq/assets/{clues.poster}">`、對話圖同理、網站 `<iframe src="{clues.site}">`(附「開新分頁」連結)。**唯讀**；旁註「圖/網站要改請聯絡開發者重生」。
    - **可編輯表單**：intro(textarea)、提示 hints[0].text＋cost、solution.core 各概念 any 關鍵詞(逗號分隔可編)、partial 的 any＋nudge、genericNudge、reveal(textarea)、difficulty。一顆「儲存」(update)。存成功提示「已生效(甜甜約 1 分鐘內更新)」。
- 部署：`bash /opt/sml/sweetbot-site/deploy.sh`(Firebase hosting，target sweetbot)。

## 3. bot 改讀 DDB `/opt/sml/sweetbot-next/model/PuzzleQuest.js`
**目標**：題庫改從 DDB `sweetbot-puzzle` 載入(可即時反映後台編輯)＋支援指定活躍題。**務必保留靜態 json fallback，絕不可讓 live 遊戲壞掉。**
- 開機：從 DDB scan `_type="puzzle"` 載入成記憶體陣列 `this.puzzleCache`；**失敗或空 → fallback `require('../data/puzzles.json')`**。
- 重載：既有 `poll()`(30s，VotePool式)裡順便每 N 次重載一次 puzzleCache＋讀 `__config__.activePuzzleId` 存 `this.activePuzzleId`。(或另開 60s interval。)後台編輯後約 1 分鐘生效，不需重啟。
- `puzzleById`/`puzzles` 全改讀 `this.puzzleCache`(非 module 頂層 const)。注意：目前 `puzzles` 是模組頂層 require，多處引用，要改成走 cache getter，小心 evaluateAnswer 等純函式仍吃傳入的 puzzle 物件(不受影響)。
- `pickUnsolvedPuzzle`/`startPuzzle`：若 `this.activePuzzleId` 非空 → 出該題(該玩家已解過則回「本題已破，等管理員換題」或仍出以供重看，擇一，建議：已解過就擋提交但可看)；空 → 維持現隨機。
- 圖片解析不變(clues.poster/message 仍是檔名，讀本機 data/puzzle-assets)。
- **這支改動風險最高：Codex 只改檔、不要 deploy/重啟**，交回給 Claude review 後由人工部署。

## 4. 自驗與回報
- Lambda：本地 `node -e` 模擬 event 測 verifyIdToken 分支(可跳過真token)、list/get/setActive/update 對 DDB 的讀寫正確；update 拒絕改 clues/id。
- 前端：語法/載入無誤(可 headless 開頁截圖確認版面)。
- bot：`node --check`；模擬 DDB 空→fallback 靜態 json 不崩；puzzleCache 載入 8 題；activePuzzleId 指定時 pickUnsolved 回該題。
- 回報：改/新增檔清單、APIGW invoke URL、IAM/部署哪些已做/需人工、每項自驗結果。**Lambda 與前端可自行部署到各自環境；bot 改動只交回別部署。**
