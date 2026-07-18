# ⛩️ 神社 S2-1（引擎擴充 A+B）· Codex 查驗交接單

> **範圍**：STAGE2 §12 的第一格 S2-1。只動 S1 運氣引擎 `computeLuck` 加兩段擴充 + config 欄位 + 測試。**不含 DAO/service**（那是 S2-2~S2-4）。
> **重中之重**：這動到**已簽核的 S1 引擎**，請優先確認 **delta 不破壞 S1**。
> 基準：`tools/jinja-shrine/STAGE2.md §3（擴充A）/§5.2（擴充B）/§9（測試 1-7）`。

## 0. 讀哪些檔
權威在 **sweetbot-next**（commit `40e27ea`，未 push）；Codex 讀本 repo 唯讀副本 `tools/jinja-shrine/impl-s2/`（byte-identical）：
```
impl-s2/model/shrine/ShrineLuck.js        computeLuck 擴充 A（活御守加成）+ B（除厄減免）
impl-s2/model/shrine/defaults.js          + omamoriTypes / yakuHaraiMode / yakuHaraiRechargeable
impl-s2/test/shrineLuck.test.js           9→12（S1 修正）→ 19（S2-1 +7）
impl-s2/migration/seed_shrine_config.js   config#main 補同欄位
```
**測試現況：`node --test test/shrineLuck.test.js` = 19 pass / 0 fail。**

## 1. 擴充 A — 活御守正向加成（ShrineLuck.js 步驟 3）
- [ ] **未回收且未到期**（`!recycled && expireAt > now`）御守 → `axes[o.axis] += o.boost`。
- [ ] **過期未回收**（`expireAt <= now`）→ 仍走**穢れ**（body 按天扣，與 S1 相同，未改行為）。
- [ ] **已回收** → 完全不計。
- [ ] 防髒：無 `expireAt`（非數字）→ 略過；未知 axis / `boost` 非數字 → 略過（不加）。
- [ ] `breakdown.omamoriBoost{軸→Σ}` 正確。
- [ ] 疊加後仍受最終 `clamp[0,100]`。
- [ ] **⚠️ 不破壞 S1 穢れ**：原 test 4（穢れ 3/8、body 47/42）仍綠。

## 2. 擴充 B — 除厄減免（ShrineLuck.js 步驟 4）
- [ ] 厄年 penalty 算法**與 S1 相同**（男 25/42大厄/61、女 19/33大厄/37/61、前後厄、taiyakuExtra）。
- [ ] `fortune.yakuHaraiYear === taipeiYear(now)` → 依 `config.yakuHaraiMode`：`clear`（預設）→ penalty 歸零；`half` → `round(penalty/2)`。
- [ ] **只當年有效**：yakuHaraiYear 為去年 → 照扣（test 18）。
- [ ] 非厄年 → 除厄不影響（test 19）。
- [ ] `breakdown.yakuHaraied` 布林正確。
- [ ] **⚠️ 不破壞 S1 厄年**：原 test 5（男42/女33 -10、缺 gender/birthday 不扣）仍綠。

## 3. config / 防護
- [ ] `defaults.js` 與 `seed_shrine_config.js` 的 `omamoriTypes`（6 守→axis/boost/fee）、`yakuHaraiMode`、`yakuHaraiRechargeable` 一致。
- [ ] config 缺 `yakuHaraiMode` → 引擎 fallback DEFAULT（`clear`），不阻斷。
- [ ] 六軸英文 key（zaiun/shengun/zhiun/body/renyuan/xingyun）一致。

## 4. 測試覆蓋（對 STAGE2 §9 之 1-7）
- [ ] test 13-16（活御守：加成/回收不加/過期穢れ/髒資料略過/clamp）。
- [ ] test 17-19（除厄：clear 歸零+half 減半/去年照扣/非厄年無影響）。
- [ ] 原 S1 之 test 1-12 全數仍綠（無回歸）。

## 5. Findings 回報
沿用前例：Blocking / Non-blocking / Nit，逐條指檔案:行。修正回 **sweetbot-next**（權威）改後同步覆蓋 `impl-s2/`。過了 → 進 **S2-2 御守 DAO+請御守（Fable 5 樣板）**。
