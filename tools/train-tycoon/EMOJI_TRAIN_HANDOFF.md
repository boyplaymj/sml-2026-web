# 車型 emoji 拼車 — 設計/資產交接

> 使用者點子(2026-07-16):火車一節一節「橫的」剛好能用自訂 emoji 拼起來;到站通知時甜甜直接用 emoji 拼出**那台車本人** @玩家,可愛;稍微 GIF 動更好。
> **兩種呈現並存**:①主面板 Embed = 斜角 iso sprite 大圖(既有計畫,不動)②訊息/通知 = 文字自訂 emoji 把編組一節節拼出來(橫視、可動)。
> **可行性已確認**:`const/emoji.js` 現有 `stage`(3 顆串成橫幅)、`happyBirthday`(8 顆串成一條)就是「多顆自訂 emoji 拼一張寬圖」——本功能同一招。產線全現成:`tools/emoji/`(build/buildSet/upload/registry.json/animateGif/**sliceGif**)。

## 概念:一車型一顆 emoji,按編組串接 = 那台車
- 每個車型(loco×8 + car×8,Phase 0 先做用得到的子集)= **一顆自訂 emoji**(側視橫的一格)。
- 編組字串 = `車頭emoji + 各車廂emoji×節數`,例:D51 掛 3 節コキ → `<:tt_d51:><:tt_koki:><:tt_koki:><:tt_koki:>` → 訊息裡就是一列 4 節的小火車,**長度隨編組**。
- 到站 @通知:`甜甜 @你 <consist> 到站啦!金庫入帳 320🦷`。

## 美術規格(側視,和 iso 面板是不同視角,兩套並存)
- **側視(横)flat 像素**,非斜角(斜角難拼橫排)。畫風對齊遊戲既定的 8-bit 像素調色盤(復用 `tools/train-tycoon/sprites/pixelize.py` 的共用 24 色/或 16 色盤,讓 emoji 與面板同色系)。
- **無縫連接是關鍵**:每顆 emoji 的左右邊要對齊——**軌道線貫穿到邊、車鉤在邊緣**,相鄰兩顆串起來看起來是「連在一起的一台車」(參考 `stage`/`happyBirthday` 的邊緣對齊)。車頭 emoji 車頭朝右(=火車往右開)。
- Discord emoji 是方形(顯示 ~22–48px)、透明底;側視車廂寬扁 → 置中 letterbox 進方形、底部留軌道帶對齊。
- **靜態先行**(每型 1 顆靜態 slot);**動態版當升級**(冒煙/輪子轉,用 `tools/emoji/animateGif.js` 生 GIF emoji、佔動態 slot)。
- 生成路線:沿用 `tools/train-tycoon/sprites/`(bedrock_gen.py 換**側視 prompt**)→ pixelize 正規化 → 裁成 emoji 方格(邊緣對齊)→ 靜態上金庫;動態版走 animateGif/sliceGif。**畫風要先跟使用者對樣**(他對車型美術很講究,先出 1 車頭+1 車廂樣本 iterate 鎖定再批量)。

## 上金庫 + 接程式
- 用 `tools/emoji/`(build/buildSet/upload.js)把成品上到 emoji 金庫 guild(14 個 guild 攤額度,每 guild 50 靜+50 動;16 車型放得下)→ 進 `registry.json`。
- 拿到 emoji ref(`<:tt_d51:id>`)→ 加進 `const/emoji.js` 一個 `train` 區(如 `emoji.tt_d51 = '<:tt_d51:...>'`),與 `emoji.teeth` 同款靜態 map,程式端 `emoji.tt_<catId>` 取用。
- **編組拼字 helper**(新小 util,如 `model/miniGame/trainTycoon/consistEmoji.js`):
  - `consistEmoji({ locoId, cars }, emojiMap)` → `emoji['tt_'+locoId] + cars.flatMap(c => Array(c.count).fill(emoji['tt_'+c.carId])).join('')`。
  - 缺 emoji 時 fallback 到 catalog 的 Unicode `loco.emoji`/`car.kigo`(現有佔位)→ 永不炸。
  - **寬度上限**:編組很長時截斷顯示(如超過 8 節顯示前 N + `…×M`),避免訊息爆長。

## 接入點
**Phase 0(不需新基礎設施,面板內就能用)**:
- 派車確認成功 embed:「已派出 `<consist>` → npc_minato」。
- 在途看板每列前綴該班 `<consist>`。
- 結算 note:「`<consist>` 到站,入帳 X🦷」。
- 車庫/購車清單:車型名旁放單顆 `<:tt_x:>`。

**Phase 1 stretch = 真正的「到站主動 @ping」**:目前 D2 是開面板才惰性結算(被動)。要「車一到甜甜就敲你」需一支**抵達輪詢器**(仿 `model/EarthquakeEvent.js` 輪詢 pattern:定時掃各玩家已抵達未通知的 transit → 發頻道訊息 @玩家 帶 consist emoji → 標記已通知)。這是獨立一塊,和 emoji 資產解耦、可後做。

## 成本
- 純美術一次性烘焙 + Discord 自訂 emoji(免費、算 guild slot);執行期只是字串拼接,**不燒 LLM、不加 DDB**。emoji 生成走既有 Bedrock 一次性幾美元。免成本控管四件套。

## 建議順序
1. **對樣**:先生 1 車頭(D51)+ 1 車廂(コキ)側視 emoji 樣本,拼給使用者看、鎖畫風(靜態先)。
2. 批量生 Phase 0 子集(用得到的車頭/車廂)→ 上金庫 → registry → `const/emoji.js`。
3. `consistEmoji.js` helper + 接 4 個面板點(Phase 0)。
4. (可選)動態 GIF 版升級。
5. (Phase 1)抵達輪詢器做主動 @ping。
