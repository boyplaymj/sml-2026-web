# ⛩️ 神社 S2-4（御祈禱受付所 — 厄年除厄）· Codex 查驗交接單

> **範圍**：STAGE2 §12 第四格。`ShrineLuck` 匯出 `taipeiYear` + `ShrineFortuneDAO.setYakuHarai` + `ShrineHaraiService.harai` + 單測。
> **不含**：discord.js/UI、開放時間閘（S3）、生日鉤子（S2-5）。
> 實作＝Fable 5、已 Opus 覆核。基準：`STAGE2.md §5`＋施工單 `HANDOFF-S2-4.md`。

## 0. 讀哪些檔
權威 sweetbot-next commit `a9fa8e1`（未 push）；Codex 讀 repo 唯讀副本 `tools/jinja-shrine/impl-s2/`（byte-identical）：
```
impl-s2/model/shrine/ShrineLuck.js         module.exports 加 taipeiYear(唯一引擎改動)
impl-s2/DAO/DDB/ShrineFortuneDAO.js        + setYakuHarai(原子寫年+可選gender)
impl-s2/model/shrine/ShrineHaraiService.js  harai(命門)
impl-s2/test/shrineHarai.test.js           10 測
```
**全 shrine 測試：`node --test test/shrineHarai.test.js test/shrineRecycle.test.js test/shrineOmamori.test.js test/shrineLuck.test.js` = 44 pass / 0 fail（S2-4 之 10 + grant 8 + recycle 7 + luck 19；既有未破）。**

## 1. ⚠️ 引擎同源（最重點）
- [ ] `ShrineLuck.js` **只在 module.exports 加 `taipeiYear`**，`computeLuck`/`taipeiYear` 函式本體與 S1/S2-1 **零改動**（既有 luck 19 測仍綠即證明）。
- [ ] `ShrineHaraiService` 的 `year` 來自 `require('./ShrineLuck').taipeiYear(nowEpoch)`，**與引擎 B 判「本年是否已除厄」同一函式**（不自算年份，杜絕跨年/時區 silent 不生效）。

## 2. harai 命門
- [ ] 驗證順序：gender → config → 生日 → 厄年 → 同年冪等 → 餘額 → 收費 → 寫；每個閘擋下時**不扣不寫**。
- [ ] **非厄年不收費**（`computeYaku` 回 none → `not_in_yakudoshi`）。
- [ ] **同年冪等**：`fortune.yakuHaraiYear === taipeiYear(now) && !rechargeable` → `already_haraied`，不收費；`rechargeable=true` → 允許再除。
- [ ] gender 非 male/female → `gender_required`；生日缺/非 8 碼 → `birthday_required`。
- [ ] 餘額不足 → `insufficient`（不扣不寫）；扣款後 `setYakuHarai` 失敗 → **退款**（givePoint 兩次）→ `write_failed`。
- [ ] config 缺 → fee fallback DEFAULT（gokitou 800）、rechargeable fallback false。
- [ ] 絕不 throw；未預期錯 → `{ok:false,reason:'error'}`。

## 3. DAO `setYakuHarai`
- [ ] 一次 `UpdateCommand`：帶 gender → `SET yakuHaraiYear = :y, #g = :g`（`#g`→'gender'，DynamoDB 保留字）；不帶 gender → 只 `SET yakuHaraiYear = :y`、無 `ExpressionAttributeNames`。
- [ ] Key=`{discordId:String}`（非 base.get id）。

## 4. 已知/刻意（非 bug，Opus 已裁）
- **收費後 setYakuHarai 罕見失敗**：退款路徑已處理；退款也失敗僅 `console.warn`（同 grant/recycle 的跨系統非原子取捨）。列 Non-blocking。
- 施工單原稱「luck20」為筆誤，實為 **luck 19**（該檔未改，19 全綠）。

## 5. Findings 回報
Blocking / Non-blocking / Nit，逐條指檔案:行。修正回 sweetbot-next（權威）改後同步 `impl-s2/`。過了 → 進 **S2-5 生日厄年鉤子（Opus，動既有生日祝賀流程）**，即 S2 最後一格。
