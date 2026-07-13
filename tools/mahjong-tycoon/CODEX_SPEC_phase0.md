# 模擬麻將館 — Phase 0 交接規格(Codex）

> 目標:遊戲端最小可玩迴圈——**開館 + 惰性營收 + 求生**。單人先跑通核心手感,之後 Phase 1 才加地圖分食/對抗。
> 實作位置:`/opt/sml/sweetbot-next`(甜甜 Discord bot,Node + DynamoDB)。
> 讀取的設定源頭:後台已上線的 DDB `mahjong-tycoon-config`(只讀 `state=published` 的 section)。
> 慣例:動工前 `check-conflict.sh`;遵守 `AGENTS.md`;`deploy.sh` 部署;**完成用實際 Discord 指令/DDB 回傳驗證,不只看 code**。

---

## 0. 核心概念:兩個「口袋」,同一種牙齒🦷(非兩種貨幣)

使用者定調「都是牙齒」。Phase 0 用**同幣兩口袋**,直觀又能控通膨:

- **個人牙齒錢包**:玩家全站通用的牙齒(既有 point 系統)。
- **館內金庫(treasury)**:這間館持有的牙齒,獨立於個人錢包。

金流:
```
開館  : 個人錢包 −openCostTeeth      (從全站經濟抽走 → sink)
營業  : 惰性營收累積進「館內金庫」    (不直接進個人錢包)
租金/薪資: 從「館內金庫」扣           (sink)
提款  : 館內金庫 → 個人錢包           (← 唯一讓牙齒回流全站的水龍頭,可監控/日後設限)
```
> 這樣「掛機賺的」要**主動提款**才變成個人資產,全站通膨可由提款這關控管(接 [[牙齒經濟後台]] 監看)。Phase 0 提款先不設上限,但每筆提款要寫進 point 流水帳,方便經濟後台看。

---

## 1. Phase 0 範圍(只做這些,其餘留後續 Phase)

✅ 做:單一入口指令 `!模擬麻將館` + 全按鈕面板(選區開館 / 儀表板 / 提款 / 看地圖)、惰性結算、最小倒店判定。
❌ 不做(留後續):地圖客源分食/對手(Phase 1)、宣傳/隨機事件(Phase 2)、即時對抗(Phase 3)、員工管理深度/裝潢/餐飲旋鈕(Phase 1+)。

Phase 0 開的館固定配置:**2 張普通牌桌、無員工**。求生張力來自「**選區**」——租金 vs 客流 vs 風險的取捨。

---

## 2. 讀設定(published)

只需 2 個 section:
- `districts`:每區 `baseFlow`(客流/hr)、`rentLevel`(租金/tick)、`riskLevel`、`clientMix`、`emoji`、`name`、`enabled`。
- `balance`:`openCostTeeth`、`reviveCostTeeth`、`worldTickMinutes`、`bankruptcy.{deficitTicksToClose,minReserve}`。

> `catalogs`/`events` Phase 0 用不到(牌桌預設 t_basic 常數即可,事件 Phase 2)。
> 讀法:GetItem `mahjong-tycoon-config` PK=section, SK=`published`,取 `data`。建議加 30~60s 記憶體快取,別每次結算都打 DDB。缺 section 時 fallback 到與前端相同的 SEED 預設(見 `mahjong_tycoon_admin.html` 的 `SEED`,或直接複製一份常數)。

---

## 3. 資料表 `mahjong-tycoon-parlors`

- PK `userId` (S)。`PAY_PER_REQUEST`。
- 欄位:
  ```
  userId, districtId, status('active'|'closed'),
  treasury(Number, 館內金庫牙齒), tables(Number, Phase0=2),
  openedAt(ms), lastSettledAt(ms),
  stats:{ totalRevenue, totalRent, totalWithdrawn },   // 統計用
  ```
- 一人一館(Phase 0)。closed 的館保留紀錄供統計,可再開。

---

## 4. 惰性結算(核心)

任何指令(`!館`/`!提款`)觸發前先 `settle(parlor)`:

```
settle(parlor, cfg):
  now = Date.now()
  hrs = (now - parlor.lastSettledAt) / 3600000
  hrs = min(hrs, OFFLINE_CAP_HOURS)        // 離線上限,Phase0 建議 12h(避免無限掛機;Phase1 再加客流流失)
  d   = cfg.districts[parlor.districtId]

  revenue = incomeRatePerHour(parlor, d) * hrs
  cost    = rentPerHour(d) * hrs           // Phase0 無薪資
  parlor.treasury += (revenue - cost)
  parlor.lastSettledAt = now
  parlor.stats.totalRevenue += revenue
  parlor.stats.totalRent    += cost

  // 倒店判定
  floor = -(rentPerHour(d) * cfg.balance.bankruptcy.deficitTicksToClose * tickHours(cfg))
  if parlor.treasury < floor:  closeParlor(parlor)   // 倒店:status='closed'
```

### Phase 0 簡化收入公式(尚無對手分食)
```
incomeRatePerHour(parlor, d):
  seatCapacityPerHour = parlor.tables * SEATS_PER_TABLE(4) * TURNOVER_PER_HOUR   // 常數,如 TURNOVER=0.5局/hr
  capturedCustomers   = min( d.baseFlow * CAPTURE_RATE(0.30), seatCapacityPerHour )
  return capturedCustomers * AVG_SPEND_PER_CUSTOMER                              // 常數牙齒/人,如 8
rentPerHour(d):
  return d.rentLevel / tickHours(cfg)      // rentLevel 是「每 tick」,換算成每小時
tickHours(cfg) = cfg.balance.worldTickMinutes / 60
```
> 常數(CAPTURE_RATE / TURNOVER / AVG_SPEND / SEATS / OFFLINE_CAP)先寫死在遊戲端常數檔,調參用;Phase 1 起改由 balance 設定驅動並加入 attractiveness 分食。**數值要調到:便宜區小賺、貴區高風險(租金可能大於收入)**,讓選區有意義、且全站淨鑄出不過量。

---

## 5. 互動:單一指令開場 + 全程按鈕(硬性原則)

> **使用者定調**:整個遊戲**只有一個 `!` 指令**當入口,之後所有操作一律用 **Discord 互動式按鈕/選單**完成,不再新增任何 `!` 指令(讓玩家像玩 WebGame,少打字)。面板隨狀態**重繪同一則訊息**(interaction `update`),不洗版。

### 唯一入口指令
- `!模擬麻將館`(可加別名 `!麻將館`)→ 先 `settle`(若已有館)→ 依狀態叫出**主面板 embed + 按鈕**:

### 主面板狀態機(全按鈕/選單,無指令)
- **A. 尚無 active 館** → 面板顯示選區:
  - 用 `StringSelectMenu`(或每區一顆 `ButtonBuilder`)列出 `enabled` 區域(emoji 名稱、baseFlow、rentLevel、risk 摘要)。
  - 選一區 → 面板更新成「確認開館(費用 openCostTeeth🦷)」+ `✅ 確認開館` / `↩ 重選` 按鈕。
  - 按確認 → 扣個人錢包(不足則面板提示不足)、建 parlor(2 桌、treasury=0、active、lastSettledAt=now)、面板重繪成 **B 儀表板**。
- **B. 有 active 館(儀表板)** → embed 顯示:所在區、館內金庫🦷、桌數、預估淨收/hr、離上次結算時間、status。按鈕列:
  - `🔄 刷新`(重新 settle + 重繪)
  - `💰 提款`(金庫→個人錢包全額正值;寫 point 流水帳 reason='模擬麻將館提款';更新 stats;金庫≤0 提示無可提款;完成後重繪)
  - `🗺️ 看地圖`(切一個唯讀分頁顯示各區資訊,`↩ 返回` 回儀表板)
  - (可選)`🏳️ 關館`
- **C. 剛倒店** → 面板顯示倒店訊息 + `🔁 重新開館` 按鈕(回到 A)。

### 互動實作
- 照 `model/miniGame/InBetween.js` 的 `buttons` 陣列 + customId 帶 tag(`Config.interactionDataTag`)。麻將館建議 customId 前綴 `mjt:` + 動作 + 必要參數(如 `mjt:open:office`)。
- customId **不要**用 `b2b:` / `fwd:` 開頭(bridge 保留)。
- 面板應綁定操作者:非開啟者點按鈕 → ephemeral 提示「這是別人的面板」(或各自獨立面板)。
- 重繪用 `interaction.update({embeds,components})`,同一則訊息。

---

## 6. 倒店

- treasury 跌破 `floor`(見 §4)→ `status='closed'`。
- 玩家可再 `!開館`:若距離倒店在冷卻內(可選)用 `reviveCostTeeth`,否則正常 `openCostTeeth`。Phase 0 最簡:一律 `openCostTeeth` 重開即可,`reviveCostTeeth` 留 Phase 1。
- 倒店只清館、**不動玩家個人牙齒/等級**。

---

## 7. 整合點(sweetbot-next 實際位置)

**7.1 牙齒錢包 API**
- 讀餘額:`ViewerDAO.getPointByDiscordID(discordID)` → `DAO/DDB/ViewerDAO.js:256`(回 `{point, pointLimit, level, ...}`)。
- 加減 + 自動寫流水帳:`ViewerDetailDAO.givePoint(discordIds[], teethCount, 'point', reason)` → `DAO/DDB/ViewerDetailDAO.js:172`(負數=扣款;寫 `sweetbot-player-point-log`)。
  - 開館扣款:`givePoint([uid], -openCostTeeth, 'point', '模擬麻將館開館')`
  - 提款入袋:`givePoint([uid], amount, 'point', '模擬麻將館提款')`
  - **先讀餘額判斷夠不夠再扣**,別扣成負的。
- 範例參照:`model/miniGame/InBetween.js:243,265`。

**7.2 `!` 指令註冊 / 路由**
- 每個遊戲 model 內宣告 `this.commands = [{ key, blockCriminal, usePermission, tips, func }]`(參 `model/miniGame/InBetween.js:69-87`)。
  - `key`=指令字(去 `!`)、`usePermission`=需求 vipLevel(0=全開)、`func`=`this.handler.bind(this)`。
- 在 `discord.js:289-306` 把 `...mahjongTycoon.commands` 展開進 `gameCommands`;訊息路由主流程在 `discord.js:205-335`。

**7.3 遊戲 model 範本** → `model/miniGame/InBetween.js`(constructor 初始化 DAO/commands/buttons → 邏輯 → EmbedBuilder 組回覆 → givePoint 收付)。照它的組織方式做 `model/`(或 `model/miniGame/`)`MahjongTycoon.js`。

**7.4 自有 DDB 表**
- 基底:`DAO/DDB/DDBBaseDAO.js`(共用 client,region 已硬碼 `ap-southeast-1`,SDK v3 `@aws-sdk/*@^3.967.0`)。方法 `get/put/update/query/scan`。
- 新遊戲表 DAO:`class MahjongTycoonParlorDAO extends DDBBaseDAO { constructor(){ super('mahjong-tycoon-parlors'); } async get(uid){ return super.get(String(uid),'userId'); } }`(參 `DAO/DDB/JailCaseDAO.js`)。

**7.5 讀後台設定** → 新 `DAO/DDB/MahjongConfigDAO.js`:
```js
class MahjongConfigDAO extends DDBBaseDAO {
  constructor(){ super('mahjong-tycoon-config'); }
  async getPublished(section){
    const res = await this.ddb.send(new QueryCommand({ TableName:this.tableName,
      KeyConditionExpression:'#s=:s AND #st=:state',
      ExpressionAttributeNames:{'#s':'section','#st':'state'},
      ExpressionAttributeValues:{':s':section, ':state':'published'} }));
    return res.Items?.[0]?.data || null;   // 取 data 欄位
  }
}
```
記憶體快取 30~60s;缺 section fallback SEED(見前端 `mahjong_tycoon_admin.html` 的 `SEED`)。

**7.6 Discord embed + emoji**
- `EmbedBuilder`/`ActionRowBuilder`/`ButtonBuilder`(參 `InBetween.js:99-127`)。
- emoji:`const emoji = require('../const/emoji.js')`;牙齒 = `emoji.teeth`(訊息用 `.replaceAll('{point}', emoji.teeth)`)。按鈕樣式 `const/buttonStyle.js`。

**7.7 治理**(AGENTS.md)
- 動檔前:`bash check-conflict.sh <你要動的檔>`。
- 只 `git add` 自己動的檔(**別 `-A`**)、小步 commit、append 一筆 `CHANGELOG-agents.md`。
- 機密進 `/opt/sml/sweetbot.env`,不入庫。
- 🔴 **關鍵警告(覆蓋 AGENTS 的 staging 流程)**:release train **目前卡住不能跑**(staging 有 16 筆殭屍 commit + registry 衝突,見記憶 project_sweetbot_release_train)。**不要在 staging 開發後按 16:00 發布列車**,會卡死。這次照 puzzle-quest 的作法:**直接在 main 工作區小步 commit,用 hotfix / commit-tree 落 main**,避開 release train。部署走 `./deploy.sh`。落地路徑先跟使用者確認再推。

---

## 8. 驗收點(Codex 自驗,用真實 Discord/DDB)

1. **只有 `!模擬麻將館` 一個指令**;之後全流程按鈕/選單,無其它 `!` 指令。面板操作都是同一則訊息重繪(不洗版)。
2. 面板選區選單正確列出後台 published 的區域(改後台發佈後,遊戲端 60s 內讀到新值)。
3. 選區→確認開館:個人牙齒 −openCostTeeth,DDB 建 parlor,面板重繪成儀表板;已有館時入口直接進儀表板(不重複開)。
4. 掛一段時間按 `🔄 刷新`:金庫依經過時間增加(便宜區)或被租金侵蝕(貴區),數字合理、離線上限生效。
5. 按 `💰 提款`:金庫→個人錢包,個人牙齒增加且 point log 有記錄,金庫歸零,面板重繪。
6. 選貴區且不提款放到跌破 floor → 刷新面板顯示倒店 + 重開按鈕。
7. 牙齒守恆檢查:開館扣的 + 提款進的,和 DDB parlor 金庫/統計對得起來(無平白鑄幣漏洞)。
8. 非開啟者點別人面板按鈕 → 被擋(ephemeral 提示或獨立面板)。

---

## 9. Phase 0 完成後
接 Phase 1:地圖客源 attractiveness 分食 + 對手 NPC + 地圖看板頻道 + 經營旋鈕(員工/裝潢/餐飲/價格)。
