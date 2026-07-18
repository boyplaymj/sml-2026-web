# ⛩️ 甜甜神社 — S1 運氣引擎 · Codex 查驗交接單

> **範圍**：S1 = 把「運氣」算成六軸有效值供跨遊戲讀取。純函式 `computeLuck` 命門 + 3 DAO + `getLuck` 薄包 + 單測。
> **不在範圍**：不接任何遊戲、不改 discord.js、無後台頁（wiring 是 S4、後台是 S5）。
> **基準規格**：`tools/jinja-shrine/STAGE1.md`（演算法逐條）＋ `tools/jinja-shrine/DESIGN.md`（六軸語義、PvP 鐵律、成本）。

## 0. 讀哪些檔
權威在 **sweetbot-next**（commit `804a080`，未 push）；Codex 讀本 repo 的 **唯讀副本** `tools/jinja-shrine/impl-s1/`（byte-identical，路徑鏡射）：
```
impl-s1/model/shrine/ShrineLuck.js          純引擎（命門，Opus 親寫）
impl-s1/model/shrine/ShrineLuckService.js   getLuck / getLuckAll 薄包
impl-s1/model/shrine/defaults.js            DEFAULT_SHRINE_CONFIG（鏡射 seed）
impl-s1/DAO/DDB/ShrineFortuneDAO.js         PK=discordId
impl-s1/DAO/DDB/ShrineOmamoriDAO.js         PK=discordId + SK=sk，Query 分頁
impl-s1/DAO/DDB/ShrineConfigDAO.js          PK=key，單列 key='main'，60s 快取
impl-s1/test/shrineLuck.test.js             9 項矩陣（node:test）
```
> 修正回 sweetbot-next 改，再覆蓋副本。**測試現況：`node --test test/shrineLuck.test.js` = 9 pass / 0 fail。**

## 1. 命門查驗 — `computeLuck`（純度＋演算法對規格）
逐條對 `STAGE1.md §2` 演算法：
- [ ] **純度**：`computeLuck` / `computeYaku` / 公式 helper 全不碰 DDB、不取現在時間（`nowEpoch` 一律由呼叫端注入）。可離線單測。
- [ ] **base**：`fortune.base` 有值採之，缺則六軸皆 50；只採六軸合法 key 且為 number。
- [ ] **有效 buff**：`expireAt <= nowEpoch` 過期忽略；`axis` 非六軸之一跳過；`delta` 非 number 跳過（防髒資料）。
- [ ] **穢れ**：僅對 `!recycled && expireAt <= nowEpoch` 的御守，`daysExpired = floor((now-expireAt)/86400)`，`body -= daysExpired * config.kegareDailyDecay`；未到期/已回收不扣；多張累加；**只扣 body**。
- [ ] **厄年**：`kazoe = 台北曆年(nowEpoch) - birthYear + 1`；`computeYaku` 表對 §4（男 25/42大厄/61、女 19/33大厄/37/61、前厄-1/後厄+1）；penalty 為負、大厄本厄額外疊 `taiyakuExtra`。**缺 gender 或 birthday（非 8 碼）→ level='none' 不扣**（保守鐵律）。
- [ ] **clamp**：六軸最後夾 [0,100]。
- [ ] **綜合運**：`sougou = round(mean(六軸))`。
- [ ] **breakdown**：玻璃箱透明化（base / buffDelta / kegarePenalty / yakuLevel / yakuPenalty）。

## 2. DAO 查驗（correct-key、非 scan、分頁）
base `DDBCompatibleBaseDAO` 的 `get/update/delete` **寫死 PK=`id`**，shrine 表 PK 不同，故三 DAO 用 doc client + 正確 key 自寫——**這是重點**：
- [ ] `ShrineFortuneDAO.getByPlayer` 用 `GetCommand` Key=`{discordId}`（非 scan、非 base.get）。
- [ ] `ShrineOmamoriDAO.listByPlayer` 用 `QueryCommand` KeyCondition on `discordId`，**do-while 分頁抓完 `LastEvaluatedKey`**（全站鐵律）；不是 scan。
- [ ] `ShrineConfigDAO.getMain` 用 `GetCommand` Key=`{key:'main'}`；60s 記憶體快取；讀失敗/查無回 null（呼叫端 fallback DEFAULT）。
- [ ] 三 DAO `super('sweetbot-shrine-*')` 全名開頭 `sweetbot-` → base line ~94 原樣保留、不觸發 TABLE_MAP 誤映射（已核，但請覆核）。
- [ ] `this.ddb` / `this.tableName` 確為 base 暴露屬性（已核 line 97/94）。

## 3. `getLuck` 薄包（fail-safe 鐵律）
- [ ] **fail-safe**：任何 DAO 錯 / 查無 / axis 非六軸 → **回 50**，`console.warn`，**絕不 throw 給呼叫端遊戲**（`getLuck`、`getLuckAll` 皆然）。
- [ ] **快取**：per-instance `Map` key=discordId，TTL 60s，存整包挑 axis。
- [ ] **接線**：`getLuckAll` 併發讀 fortune+omamori+config+viewer；`viewerDAO.getByDcID` 取生日（已核存在 ViewerDAO line 71），`.getByDcID().catch(()=>null)` 單獨吞錯不拖垮整包。
- [ ] `birthday` 由 viewer `YYYY-MM-DD` → `replace(/-/g,'')`；`gender` 取自 `fortune.gender`（S2 才會寫，故 **S1 實務上厄年不觸發** = 預期）。

## 4. 測試覆蓋（對 STAGE1 §6 九項）
- [ ] 9 項全綠、且斷言值對規格（尤其 #5 厄年 -10=honyaku(-6)+taiyakuExtra(-4)、#7 helper 邊界 0.9/1.0/1.1、#4 穢れ累加）。
- [ ] `nowEpoch` 固定注入（測試不依賴 wall-clock）。

## 5. 成本 / 鐵律
- [ ] **無 LLM、無付費 API**：純算 + DDB 讀，`DESIGN.md §成本` 免四件套。read-only hot path，無背景 job（lazy compute）。
- [ ] **PvP 不動勝率**：`probWeight` 僅 export 供 S4 PvE/經濟；S1 未接遊戲故本階段僅查註記在位（`STAGE1 §3` 鐵律，S4 逐遊戲再查）。

## 6. 已知/預期（非 bug）
- S1 gender 恆缺（S2 御祈禱才收）→ 厄年 penalty 生產環境不觸發，僅單測用注入值驗算法正確。
- 生肖本命年 fallback、buff `source` 依賴 = 往後階段。
- DDB 三表已於 S0 建成上線（`VERIFY`/migration 見 `tools/jinja-shrine/migration/`）。

## 7. Findings 回報格式
沿用 S0：分 **Blocking / Non-blocking / Nit**，逐條指檔案:行。修正回 **sweetbot-next**（權威）改後同步覆蓋 `impl-s1/` 副本，勿只改副本。
