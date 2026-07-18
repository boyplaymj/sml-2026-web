# ⛩️ 神社 S2-2（御守 DAO + 請御守 service）· Codex 查驗交接單

> **範圍**：STAGE2 §12 第二格。御守表 `getBySk` + `ShrineOmamoriService.grant`（先扣牙齒後寫、失敗退款）+ 單測。
> **不含**：回收（S2-3）、除厄（S2-4）、discord.js、引擎。
> 實作＝Fable 5、已 Opus 覆核。基準：`STAGE2.md §2/§7`＋施工單 `HANDOFF-S2-2.md`。

## 0. 讀哪些檔
權威 sweetbot-next commit `1869d35`（未 push）；Codex 讀 repo 唯讀副本 `tools/jinja-shrine/impl-s2/`（byte-identical）：
```
impl-s2/DAO/DDB/ShrineOmamoriDAO.js         + getBySk（correct-key GetItem）
impl-s2/model/shrine/ShrineOmamoriService.js  grant（命門）
impl-s2/test/shrineOmamori.test.js          7 測
```
**全 shrine 測試：`node --test test/shrineOmamori.test.js test/shrineLuck.test.js` = 26 pass / 0 fail（S2-2 之 7 + S1/S2-1 之 19，S1 未破）。**

## 1. grant 命門（先扣後寫 + 退款）
- [ ] 順序：驗 type → 查餘額 → 扣款 → put → 成功；每步錯誤路徑正確。
- [ ] **餘額不足**（balance < fee）→ `{ok:false,reason:'insufficient'}`，**givePoint 與 put 皆未呼叫**（不扣不寫）。
- [ ] **未知 type** → `{ok:false,reason:'unknown_type'}`，不扣不寫。
- [ ] **put 失敗退款**：put 拋錯 → givePoint 呼叫兩次（`-fee` 後 `+fee`，reason 標退款）→ `{ok:false,reason:'write_failed'}`。
- [ ] **絕不 throw**：未預期錯誤包成 `{ok:false,reason:'error'}`。
- [ ] 牙齒 API 用對：`givePoint([id], -fee, 'point', reason)`；餘額讀 `selectOne({discordId}).point`。
- [ ] axis/boost/fee **一律來自 config**（`omamoriTypes[type]`），逐欄 fallback DEFAULT，**無硬寫數值**。
- [ ] item schema：`sk='omamori#'+randomUUID`、`expireAt=nowEpoch+ttlDays*86400`、`recycled:false`、`source:'juyosho'`。

## 2. config 第二層防護（STAGE2 §6.1）
- [ ] `configDAO.getMain()` 回 null / 拋錯 → deep-merge DEFAULT，仍能請 6 種御守（不炸）。

## 3. DAO
- [ ] `getBySk` 用 `GetCommand` Key=`{discordId:String, sk}`（**非 scan、非 base.get(PK=id)**）；不存在回 null。

## 4. 已知/刻意（非 bug，Opus 已裁）
- **餘額競態**：`selectOne` 查餘額 → `givePoint` 扣款非原子（givePoint 走 `ADD` 不擋負餘額），兩併發請御守理論上可雙雙過閘。此為既有 givePoint 模式固有限制，施工單 §7 已預告，S2 不在此加 conditional update。若 Codex 認為須治理，記為 **Non-blocking** 供 S3/後續。
- **config 讀錯走 DEFAULT 仍收費**：對齊 S1 fail-safe（config 非關鍵）。

## 5. Findings 回報
Blocking / Non-blocking / Nit，逐條指檔案:行。修正回 sweetbot-next（權威）改後同步 `impl-s2/`。過了 → 進 **S2-3 回收 + 功德值（Fable 5）**。
