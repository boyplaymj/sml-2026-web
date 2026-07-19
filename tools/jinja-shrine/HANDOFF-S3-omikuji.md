# 🛠️ S3-omikuji 施工單：抽御神籤(おみくじ)@ 授與所

> **任務**：授與所「抽御神籤」——花牙齒抽籤、只當日首抽計運勢、凶籤強制【結ぶ】否則每日大量扣運、抽到即出籤紙圖卡。
> **權威樹**＝`/opt/sml/sweetbot-next`。做完 `node --test` 全綠 → Opus 覆核 → 同步 `tools/jinja-shrine/impl-s3/` → Codex 驗。
> **規格正典**：`DESIGN.md §2`（v0.3 規則 + §2.4 圖像）、籤池種子 `omikuji_pool.json`（33 張）、樣式 `omikuji_art/compose_pool.py`。
> **不要做**：御朱印（另單）、奧社試煉、其他設施；不動 S1 引擎既有公式（只可**加**一段 pendingKyo 讀取，見 §5）。

---

## 0. 定案規則（照做，數值全 config 可調）
- **每抽 100🦷、不限次數**（`config.omikuji.drawFee` 預設 100）。
- **只有「當日首抽」計運勢**：台北時區日界。首抽 → 套 6 軸 buff（覆蓋前一日 omikuji buff）；第 2 抽起**照扣 100🦷 但不改運氣值**（只回籤詩卡）。
- **凶籤(凶/小凶/半凶/末凶/大凶)當日首抽** → 進「未結ぶ」狀態，出【結ぶ】鈕：
  - 手動按 → 化解（清 pendingKyo、移除本次 omikuji 負 buff）。
  - 不按 → **每日大量扣運**（lazy 累積，比御守穢れ兇；大凶 ×2），直到結ぶ或隔日首抽覆蓋。
- **重抽逃不掉**：只有首抽計數，抽到凶後再抽不蓋掉它。

---

## 1. 照抄的既有接口（別另寫）
- **扣費/查餘額** `DAO/DDB/ViewerDetailDAO.js`：`givePoint([id], -100, 'point', '抽御神籤')`；givePoint 是 ADD 不擋負餘額 → **先 `selectOne({discordId})` 查 `point` 再扣**（同 ShrineOmamoriService.grant）。
- **config** `DAO/DDB/ShrineConfigDAO.js.getMain()`：可能 null/缺欄 → **deep-merge `DEFAULT_SHRINE_CONFIG`**（同 grant 寫法）。
- **fortune 表** `DAO/DDB/ShrineFortuneDAO.js`：已有 `getByPlayer` / `put`(整包覆寫) / `appendBuff`(原子 list_append) / `addMerit`。本單新增方法見 §4。
- **運氣引擎** `model/shrine/ShrineLuck.js.computeLuck({fortune, ...})`：讀 `fortune.buffs[]`（每筆 `{axis, delta, expireAt}`，過期忽略）。omikuji buff 就是往這陣列放（帶 `source:'omikuji'`）。
- **授與所面板** `model/shrine/Shrine.js`：設施操作鈕在 `facilityActionRow`（見 `facility==='juyosho'` 段，已有「請御守」鈕 `shract juyosho/omamori`）→ **加一顆「抽御神籤」鈕** `shract juyosho/omikuji`。互動路由在 `handleAction`；按鈕註冊在建構子 handler 表（照 `shromamori` 那筆加 `shromikuji`/`shrmusubu`）。
- **service 樣板**：整支照 `model/shrine/ShrineOmamoriService.js` 結構（injectable deps、`_daos()`、try/catch 不 throw、回 `{ok, reason}`）。

---

## 2. 新增：籤池 DAO `DAO/DDB/ShrineOmikujiPoolDAO.js`
> ⚠️ **表已上線(S0)，PK=`omikujiId`(S)、非 `id`**（Codex 用 describe-table 回讀確認；base DAO 寫死 PK=id 不可用 → doc client 自寫）。**照此 PK，別重建表。**
- `listAll()`：Scan 全表**必分頁**（`ExclusiveStartKey` 迴圈），回 33 筆。給 service 快取（60s）用，抽籤不必每次 Scan。
- 每筆 schema（=`omikuji_pool.json` 一筆，**已對齊表 PK + 每 item 內嵌 axis**）：`{ omikujiId, rank, shi:[4], kaie, items:{ 商賣/爭事/學問/健康/戀愛/旅行: {score, text, axis} } }`。

## 2b. 種子 migration `migration/seed_omikuji_pool.js`
> ⚠️ **表已有舊 12 筆是舊 schema**（`omikujiId/waka/sougou`，id 前綴 `ok-*`）。新 33 筆是 `shi/kaie`、id 前綴 `omikuji-*`。**兩格式混掃會壞** → seed 必須 **clear-then-seed**。
- **步驟**：①Scan 全表既有 key（分頁）→ 逐筆 `Delete`（清掉舊 12 筆 `ok-*`）；②讀 `tools/jinja-shrine/omikuji_pool.json` 的 `pool[]` 逐筆 `Put`（key=`omikujiId`）。冪等（重跑=先清再灌，結果恆為那 33 筆）。
- 建表冪等 CreateTable（PAY_PER_REQUEST，PK=`omikujiId`）若未建。跑完驗**恰 33 筆、全為新 schema**（無 `waka`/`sougou` 殘留）。
- ⚠️ 這是**內容池非玩家資料**，清舊安全（無資料損失）。

---

## 3. 新增：`model/shrine/ShrineOmikujiService.js`

### `draw(discordId, now)` → `{ ok, slip, counted, rank, pendingKyo, card }` | `{ok:false, reason, need, have}`
1. deep-merge config；`fee = cfg.omikuji.drawFee ?? 100`。
2. 查餘額，不足 → `{ok:false, reason:'insufficient', need:fee, have}`。
3. 扣 `fee`（givePoint 負）。
4. 抽階：依 `cfg.omikuji.weights`（11 階權重）加權隨機 → rank；再從該 rank 的籤中等機率抽一張 slip（pool 快取）。
5. **判當日首抽**：`today = 台北時區 YYYY-MM-DD(now)`；`counted = (fortune.omikujiDrawDate !== today)`。
   - **counted=true（首抽）**：
     - 生成 6 筆 buff：`{axis: items[x].axis, delta: items[x].score, expireAt: now + base*mult, source:'omikuji'}`（**axis 直接讀 item.axis**，種子已內嵌）；`base=cfg.omikuji.buffBaseHours*3600`(預設 12h)、`mult=cfg.omikuji.rankTtlMultiplier[rank]`。
     - **覆蓋制**：呼叫 `fortuneDAO.replaceOmikujiState(discordId, {date:today, rank, buffs:6筆, pendingKyo})`（§4，一次性移除舊 omikuji buff + 寫新的 + 設/清 pendingKyo + 更新 omikujiDrawDate/omikujiTodayRank）。
     - 若 rank 為凶類 → `pendingKyo = { rank, date: today }`；否則 `pendingKyo = null`（清除）。
   - **counted=false（重抽）**：不動 buff/pendingKyo/date，只回籤詩卡（`counted:false`）。
6. 回 `card`（§6 給 Shrine.js 組 embed）。
7. **軸對照已內嵌種子**（每 item 帶 `axis`：商賣→zaiun、爭事→shengun、學問→zhiun、健康→body、戀愛→renyuan、旅行→xingyun）→ service 不必自建對照表，直接讀 `item.axis`。

### `musubu(discordId, now)` → `{ ok, reason? }`（結ぶ）
- 讀 fortune；若無 `pendingKyo` → `{ok:true, reason:'nothing_to_bind'}`（冪等）。
- `fortuneDAO.clearKyo(discordId)`：清 `pendingKyo` + 移除本次 omikuji 負 buff（source:'omikuji' 且 delta<0 者）。回 `{ok:true}`。

---

## 4. fortune 表新增欄位 + DAO 方法
新增欄位（存在 `sweetbot-shrine-fortune` 既有 item 上）：
- `omikujiDrawDate`(S, 台北日)、`omikujiTodayRank`(S)、`pendingKyo`({rank,date}|null)。
- omikuji buff = `buffs[]` 內 `source:'omikuji'` 的筆。

新增 DAO 方法（doc client、correct-key `{discordId}`）：
- `replaceOmikujiState(discordId, {date, rank, buffs, pendingKyo})`：一次 Update — 先濾掉舊 `source==='omikuji'` 的 buff（read-modify-write 或 UpdateExpression 覆寫 `buffs`）、append 新 6 筆、SET omikujiDrawDate/omikujiTodayRank/pendingKyo。**注意併發**：首抽一天一次、衝突機率極低，用單次 Update + 覆寫 buffs 即可（不必 TransactWrite）。
- `clearKyo(discordId)`：REMOVE pendingKyo + 濾掉 `source==='omikuji' && delta<0` 的 buff。

---

## 5. 引擎擴充（ShrineLuck，**加法、保既有 20 test 綠**）
`computeLuck` 尾段（算完 kegare/yaku penalty 後）**加一段 pendingKyo drain**，比照既有 kegare 累積寫法：
- 若 `fortune.pendingKyo` 存在：`daysUnresolved = floor((now - epoch(pendingKyo.date台北0時)) / 86400)`；
  `drain = cfg.omikuji.unbindDrainPerDay(預設15) × (daysUnresolved+1) × (rank==='大凶'?2:1)`，**設上限**（`cfg.omikuji.unbindDrainCap` 預設 120）避免無限。
- 扣 `body` 與「綜合運」（綜合=六軸均值衍生，實作上對 body + 對每軸各扣一部分或只扣 body；**與設計一致：body/綜合 各 −drain**）。收斂進 `breakdown.pendingKyoPenalty`。
- ⚠️ config 缺 `omikuji` 區塊 → drain=0（fail-safe，不因缺設定誤扣）。既有測試不帶 pendingKyo → 行為不變（必須驗 20 test 仍綠）。

---

## 6. Discord 卡片（Shrine.js）
- **抽御神籤鈕**：授與所面板加 `shract juyosho/omikuji` → 呼叫 `service.draw` → ephemeral 更新。
- **卡片** = embed + 籤紙圖：
  - `image.url = ${cfg.omikuji.imageBaseUrl}/${slip.id}.png`（預設 base 見 §7；圖已上圖床）。
  - title=`🎴 ${rank}`、color=吉類紅/凶類藍；description=`詩曰 ${shi.join('・')}` + `解曰 ${kaie}`；6 欄位=六軸 `items[x].text`。
  - footer：counted=true→「當日首抽・已賜運勢 ｜ 初穂料100🦷」；counted=false→「本日已抽過・此籤僅供玩賞 ｜ 初穂料100🦷」。
  - 凶類且 counted 且 pendingKyo → 加 action row：【結ぶ（化解厄運）🎋】=`shrmusubu` + 可選【再抽（100🦷）🎴】=`shract juyosho/omikuji`。
- **結ぶ 按鈕** `shrmusubu` → `service.musubu` → 更新 embed（移除按鈕、footer 改「已結ぶ・厄運已化解」）。

---

## 7. config 新增區塊（`defaults.js` + seed_shrine_config）
```js
omikuji: {
  drawFee: 100,
  buffBaseHours: 12,
  rankTtlMultiplier: { 大吉:2, 吉:1.5, 中吉:1.25, 小吉:1, 末吉:1, 末小吉:1, 凶:1, 小凶:1, 半凶:1.25, 末凶:1.5, 大凶:2 },
  weights: { 大吉:60, 吉:140, 中吉:180, 小吉:180, 末吉:140, 末小吉:90, 凶:100, 小凶:50, 半凶:30, 末凶:20, 大凶:10 },
  unbindDrainPerDay: 15, unbindDrainCap: 120,
  imageBaseUrl: 'https://image.boyplaymj.link/omikuji-preview/pool'
}
```
> ⚠️ **imageBaseUrl 待搬永久路徑**：目前 33 張在 `omikuji-preview/pool/`（預覽路徑）。上線前把圖 cp 到穩定路徑（如 `shrine/omikuji/`）並改此值；素材不進 git。

---

## 8. 測試（`test/shrineOmikuji.test.js`，stub deps）
1. 首抽扣 100、counted=true、6 buff 依 score/軸/expireAt 正確、omikujiDrawDate=今日。
2. 同日重抽：扣 100、counted=false、**不動 buff/pendingKyo/date**。
3. 餘額<100 → 不扣不寫、reason=insufficient。
4. 首抽凶類 → pendingKyo 設定、卡片帶結ぶ；`musubu` → 清 pendingKyo + 移除負 omikuji buff。
5. 覆蓋制：隔日首抽 → 舊 omikuji buff 全清、換新。
6. 權重抽階分佈（大數次抽樣，各階>0、大凶最稀）。
7. ShrineLuck：帶 pendingKyo → body/綜合按 drain 扣且不超 cap；不帶 → 既有 20 test 全綠。
8. config 缺 omikuji → fee fallback 100、drain=0（fail-safe）。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）
- 純 DDB（既有 fortune/config + 新 omikuji-pool，皆 PAY_PER_REQUEST）+ 圖床（33 張預生成、$0）。**無 LLM、無付費 API** → 免四件套。抽籤是牙齒 sink（每抽 100🦷）。
