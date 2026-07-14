# 試煉之門「附魔(女神祝福)後台」— 可線上檢視+編輯 設計規格 v1（2026-07-14）

Claude 設計，交 Codex 建 + 自驗。延續 `DESIGN.md`（關卡數據後台）同一套路:設定搬 DynamoDB、bot 讀 DDB(fallback JS)、後台 Lambda CRUD、前端可編輯。本規格只處理「附魔 / 女神祝福」。

## 0. 現況（為什麼要搬）
「附魔」= 遊戲內**女神祝福**,目前**寫死**在 `model/RPG/TrialGate.js` 的 `playerIncrease()`,是 `switch(1..6)` 6 個固定分支,後台完全看不到、無法編輯。現行 6 種(= 種子來源,一字不差):

| id | title(embed標題) | desc(效果文字) | stat | value | img |
|----|------------------|----------------|------|-------|-----|
| 1 | 獲得女神的強化 | 基礎攻擊增加20點 | attackAdd | 20 | trialgate/game/buff2.png |
| 2 | 獲得女神的強化 | 基礎攻擊增加10點 | attackAdd | 10 | trialgate/game/buff1.png |
| 3 | 獲得女神的強化 | 基礎攻擊增加5點 | attackAdd | 5 | trialgate/game/buff1.png |
| 4 | 獲得女神的魔法祝福 | 攻擊增幅20% | attackIncrease | 20 | trialgate/game/magic2.png |
| 5 | 獲得女神的魔法祝福 | 攻擊增幅10% | attackIncrease | 10 | trialgate/game/magic1.png |
| 6 | 獲得女神的治療 | 血量增加20點 | hp | 20 | trialgate/game/revival.png |

- `stat` 對應 `playerIncrease` 目前對 player 物件做的三種變更:`attackAdd`(基礎攻擊+)、`attackIncrease`(攻擊增幅%)、`hp`(血量+)。
- 圖 5 張已確認存在於圖床 `https://image.boyplaymj.link/rpg/`(= `rpgImageBase`),各 200/240~350KB。
- **與 `increase` 的關係(重點)**:每層 layer 的 `increase` 陣列(關卡後台已可編)= 「這關 BOSS 限定只能抽到哪幾個祝福 id」的池子。空陣列 = 6 種都可能抽到(均勻)。所以附魔 id 是 `increase` 的外鍵,**id 必須穩定**。

## 1. 儲存:沿用現有表 `sweetbot-trialgate-layers`（不新建表）
DAO 現在已 `Scan` 整張表,故只要多放**一筆特殊 item** 即免費一起讀到:
- PK `layer = "__blessings__"`,屬性 `blessings` = List<Map>。
- 每個 blessing Map 欄位:`id(N,正整數,唯一)`、`title(S)`、`desc(S)`、`stat(S: attackAdd|attackIncrease|hp)`、`value(N,≥0)`、`img(S,rpgImageBase 之下的相對路徑,如 trialgate/game/buff2.png)`。
- 與現有 `__meta__`(maxLayer)、`"1".."10"`(層)並存;`scanTrialGateLayers`/DAO 既有的 `/^\d+$/` 過濾天然會忽略它,不衝突。

## 2. 種子腳本（一次性、冪等）
擴充 `tools/trialgate-roster-admin/seed.js`(或新增 `seed_blessings.js`):把上表 6 種寫成 `__blessings__` 一筆 item。可重跑(PutItem 覆蓋)。種子值 = TrialGate.js 現行寫死值,搬移後行為零改變。

## 3. bot 改動 `model/RPG/TrialGate.js`
### 3a. 保留現行 6 種為 `FALLBACK_BLESSINGS` 常數(檔頭)
把現在 switch 裡的 6 種抽成一個常數陣列(結構同 §1 Map),當 **fallback + 種子的單一事實來源**。不刪。

### 3b. DAO 載入(見 §5)把 `blessings` 併入 `this.layersCache`
`loadConfig()` 回傳物件多帶 `blessings`;`TrialGate.js` 開局載入時 `this.layersCache.blessings` 取用;讀不到/空 → 用 `FALLBACK_BLESSINGS`。**DDB 掛了照常跑**。

### 3c. 重寫 `playerIncrease()` 為資料驅動(取代寫死 switch)
```
const all = (this.layersCache.blessings && this.layersCache.blessings.length)
  ? this.layersCache.blessings : FALLBACK_BLESSINGS;
const ids = this.gameInfo.data.increase;            // 該關限定池(可空)
let pool = (ids && ids.length) ? all.filter(b => ids.includes(b.id)) : all;
if (pool.length === 0) pool = all;                  // ⚠️ increase 指到不存在的 id → 不可空池,退回全池
const b = pool[CommonUtil.getRandomInt(0, pool.length - 1)];
switch (b.stat) {
  case 'attackAdd':      player.attackAdd      += b.value; break;
  case 'attackIncrease': player.attackIncrease += b.value; break;
  case 'hp':             player.hp             += b.value; break;
}
await this.rpgEmbed(message, b.title, `<@${player.dcID}>${b.desc}`, `${Config.rpgImageBase}/${b.img}`);
```
- 行為等價驗證:池 = 全 6 種且均勻時,結果分佈與原 `switch(getRandomInt(1,6))` 相同。
- 未知 `stat` → 不套用效果、不 crash(防呆)。

## 4. 後台 Lambda（擴 `sml-laoshiji-admin`，同 Firebase 認證+白名單）
- `GET /trialgate/blessings` → 讀 `__blessings__` item,回 `{ blessings:[...] }`(無則回種子/空陣列,不 500)。
- `PUT /trialgate/blessings` → **整包替換**,伺服器端驗證後寫 `__blessings__`:
  - `blessings` 為非空陣列;每個:`id` 正整數且**全體唯一**;`title/desc` 非空字串;`stat ∈ {attackAdd,attackIncrease,hp}`;`value` 數字 ≥0;`img` 字串且**限相對路徑**(禁 `..`、禁 `http`/`//` 開頭、須 `.png`/`.jpg` 結尾;實務上限 `trialgate/...` 前綴)。
  - 驗證失敗回 400,不寫入。
- **外鍵完整性(雙向)**:
  - PUT blessings 時,若某層 `increase` 仍引用「本次被刪掉的 id」→ 回 400 並列出受影響層(避免製造孤兒引用)。(需一併 Scan 各層 increase 比對。)
  - 既有 `PUT /trialgate/layer/{n}`(見 `DESIGN.md` §4)**加一條驗證**:`increase` 內每個 id 必須存在於現有 blessings;否則 400。
- key/PK 一律伺服器組,不收前端原始 key。

## 5. DAO `DAO/DDB/TrialGateLayerDAO.js`
`loadConfig()` 在既有 Scan 結果中多抓 `__blessings__`:
```
const bItem = items.find(i => i.layer === '__blessings__');
const blessings = (bItem && Array.isArray(bItem.blessings)) ? bItem.blessings : [];
...
return { maxLayer, layers, blessings };
```
- **不改**既有 layer 的空值檢查(那些照舊);`blessings` 空只代表 TrialGate 會用 FALLBACK,不 throw。

## 6. 後台前端（擴 `sweetbot-site/public/trialgate_admin.html`）
### 6a. 🔮 附魔管理區（新，含檢視+編輯）
- 「關卡數據」頁籤內新增(或新分頁)「🔮 附魔」區:載 `GET /trialgate/blessings`,每個祝福一張卡。
- 每張卡可編:`title`、`desc`、`stat`(下拉 attackAdd/attackIncrease/hp)、`value`;`img` 用文字欄 + **即時縮圖預覽**(`${IMG_BASE}/${img}`),並附 5 張已知圖(buff1/buff2/magic1/magic2/revival)的快選下拉。`id` 唯讀顯示。
- 可**新增/刪除**祝福列;刪除被 layer 引用中的 id 時前端先擋+提示(後端也擋,雙保險)。
- 一顆「儲存全部」→ `PUT /trialgate/blessings`;成功顯示已存。
- 圖片本身的**上傳**沿用現有「🎨 圖片」頁籤流程即可(本區只選路徑,不做上傳)。上傳新附魔圖 = 未來擴充。
### 6b. 讓每層 `increase` 變好懂（順帶,強烈建議）
- 展開某層編輯時,`increase` 從裸數字陣列改成**祝福多選**(勾選框,顯示 id+title+縮圖);儲存回寫成 id 數字陣列(相容既有格式)。
- 總覽表該層可顯示「限定 N 種附魔」小標(空=全部)。

## 7. 機率提醒（設計備註,非 bug）
抽祝福為**池內均勻隨機**。新增/刪除祝福會改變每種出現機率;縮小某層 `increase` 池 = 提高池內命中率。後台編輯時 UI 可提示「共 N 種、均等抽取」。加權(weight 欄位)列為未來擴充,本版不做。

## 8. 分工 / 時序
- Codex 建全部:種子(§2)+ bot FALLBACK 常數與 `playerIncrease` 重寫(§3)+ DAO(§5)+ Lambda 兩路由與雙向外鍵驗證(§4)+ 前端附魔區與 increase 多選(§6)。
- 自驗:`node --check`、scoped eslint、DDB 讀寫、**`playerIncrease` 均勻分佈等價測試(全池時分佈同原 switch)**、驗證分支(非法 stat/負 value/重複 id/壞 img/孤兒 increase 被 400)、fallback 路徑(blessings 空→用常數)。
- **bot 改動 commit 後不自行部署,交使用者**(同關卡後台;未部署前遊戲讀 FALLBACK 值 = 現行值,行為不變)。回 diff + 測試結果。

## 9. 驗收點
1. 種子後 DDB `__blessings__` 6 筆齊,值等於現行 TrialGate.js。
2. 後台改某祝福 value/圖/文字 → DDB 更新;bot(部署後)開新局抽到新值/新圖/新文案。
3. 某層 `increase` 用祝福多選勾 [1,4,6] → 存成 [1,4,6];該關只抽得到這 3 種。
4. 驗證分支:非法 stat、負 value、重複 id、`img` 帶 `..`/`http`、刪除被引用的 id、layer.increase 指到不存在 id — 全被 400 擋。
5. Fallback:清空 `__blessings__` 或 DDB 斷線 → 遊戲用 FALLBACK 6 種正常抽,不 crash。
6. 分佈等價:全池均勻時 `playerIncrease` 各效果出現率與改動前一致。
7. 圖片頁籤、關卡數據既有功能不受影響。

相關:`DESIGN.md`(關卡後台,本規格延續其套路與 §4 layer 驗證)、`model/RPG/TrialGate.js`(`playerIncrease`)、`DAO/DDB/TrialGateLayerDAO.js`、`aws/laoshiji-admin/index.js`、`sweetbot-site/public/trialgate_admin.html`、`config/config.json`(rpgImageBase)。

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- 延續 `DESIGN.md` 同一套路與同表：沿用既有 DDB 表 `sweetbot-trialgate-layers`（`__blessings__` 一筆 item，**不新增表**）＋擴既有 Lambda；祝福圖 5 張已在圖床 `image.boyplaymj.link/rpg/`，**不新增圖床成本**。
- 表 **PAY_PER_REQUEST**；**無 LLM／無付費 API**，故免「帳本表＋月度封頂」四件套。
