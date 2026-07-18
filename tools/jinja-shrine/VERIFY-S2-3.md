# ⛩️ 神社 S2-3（古札納所回收 + 功德值）· Codex 查驗交接單

> **範圍**：STAGE2 §12 第三格。`ShrineOmamoriDAO.recycle`（條件寫）+ `ShrineFortuneDAO.addMerit`（ADD）+ `ShrineOmamoriService.recycle`（冪等）+ 單測。
> **不含**：御祈禱除厄（S2-4）、discord.js、引擎（穢れ 已於 S2-1 引擎處理，回收只改 `recycled` 旗標）。
> 實作＝Fable 5、已 Opus 覆核。基準：`STAGE2.md §4/§7`＋施工單 `HANDOFF-S2-3.md`。

## 0. 讀哪些檔
權威 sweetbot-next commit `24c3eed`（未 push）；Codex 讀 repo 唯讀副本 `tools/jinja-shrine/impl-s2/`（byte-identical）：
```
impl-s2/DAO/DDB/ShrineOmamoriDAO.js        + recycle（+import UpdateCommand）
impl-s2/DAO/DDB/ShrineFortuneDAO.js        + addMerit（+import UpdateCommand）
impl-s2/model/shrine/ShrineOmamoriService.js  + recycle（_daos 加 fortuneDAO；既有 grant 未動）
impl-s2/test/shrineRecycle.test.js         7 測
```
**全 shrine 測試：`node --test test/shrineRecycle.test.js test/shrineOmamori.test.js test/shrineLuck.test.js` = 34 pass / 0 fail（S2-3 之 7 + grant 7 + luck 20；既有未破）。**

## 1. recycle 命門（冪等 + 順序）
- [ ] **順序**：先 `omamoriDAO.recycle` 條件寫成功、**才** `fortuneDAO.addMerit`（不先給功德）。
- [ ] **冪等**：`recycle` 回 false（已回收/不存在）→ `{ok:false,reason:'already_recycled_or_missing'}`，**addMerit 未呼叫**（功德只給一次）。
- [ ] merit 來自 config `meritOnRecycle`，getMain null/throw → fallback DEFAULT（50）。
- [ ] **絕不 throw**：DAO 拋非 Conditional 錯 → service `{ok:false,reason:'error'}`、addMerit 未呼叫。

## 2. DAO
- [ ] `recycle`：`UpdateCommand` Key=`{discordId:String, sk}`、`SET recycled=:true`、`ConditionExpression 'attribute_exists(sk) AND recycled = :false'`；`ConditionalCheckFailedException` → 回 false（冪等、非 throw）；其他錯往上拋。
- [ ] 複合鍵 → 天然只能回收自己的御守（別人的 sk 配自己 discordId 不命中）。**非 scan、非 base.get(id)**。
- [ ] `addMerit`：`UpdateExpression 'ADD merit :n'`、Key=`{discordId}`、原子累加。

## 3. 已知/刻意（非 bug，Opus 已裁）
- **回收成功但 addMerit 罕見失敗**：御守已標 `recycled=true` 但功德未入，service 回 `{ok:false,reason:'error'}`。跨 item 非原子（同 grant 的「扣款→寫表」類），施工單既定取捨。列 **Non-blocking**，S3 可從 `console.warn` log 做補償。
- 併發同 sk 回收 → ConditionExpression 序列化，只一次成功 → 功德只給一次（原子保證）。

## 4. Findings 回報
Blocking / Non-blocking / Nit，逐條指檔案:行。修正回 sweetbot-next（權威）改後同步 `impl-s2/`。過了 → 進 **S2-4 御祈禱除厄（Fable 5，接引擎 B）**。
