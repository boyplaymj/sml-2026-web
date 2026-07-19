# ⛩️ 神社 S2-5（生日祝賀・厄年鉤子）· Codex 查驗交接單 — S2 最後一格

> **範圍**：STAGE2 §12 第五格（末）。在既有生日祝賀流程附「厄年 → 要不要除厄」提示。
> **Opus 親做**（動既有 `model/HappyBirthday.js` 生日流程，風險控管）。
> **鐵律**：厄年鉤子純選配、**fail-safe**，任何錯絕不影響生日祝賀主流程。

## 0. 讀哪些檔
權威 sweetbot-next commit `f981ce2`（未 push）；Codex 讀 repo 唯讀副本：
```
impl-s2/model/HappyBirthday.js         + _yakuHint、giveRole 注入一條件 field、constructor/imports
impl-s2/test/birthdayYakuHint.test.js  8 測
```
**測試：`node --test test/birthdayYakuHint.test.js` = 8 pass / 0 fail。全神社套件（birthday+harai+recycle+omamori+luck）= 54 pass / 0 fail。**

## 1. 查驗點
- [ ] **Fail-safe**：`_yakuHint` 全程 try/catch，shrine fortune 讀取/算法任何錯 → 回 `null`；`giveRole` 只在 `yakuHint` 非 null 時 `addFields`。→ 生日祝賀主流程（身分組、發訊息、冪等 redis）**零改動、零風險**。
- [ ] **gender 缺不附**：`fortune.gender` 非 male/female（含 fortune=null）→ null（保守）。
- [ ] **厄年算法同源**：用 `require('./shrine/ShrineLuck.js')` 的 `computeYaku`/`taipeiYear`（與引擎/御祈禱同一套），非自寫。
- [ ] **今年已除厄不嘮叨**：`fortune.yakuHaraiYear === taipeiYear(now)` → null；去年除厄（2025）→ 仍提示（除厄只當年）。
- [ ] **生日非 8 碼** → null。
- [ ] 注入位置：祝賀 embed 既有 field 之後、`ActionRowBuilder` 之前，附 `⛩️ 甜甜神社・厄年提醒` field（inline:false）。
- [ ] **未掃到他 session 在製檔**：本 commit 僅 `model/HappyBirthday.js` + `test/birthdayYakuHint.test.js` 兩檔（sweetbot-next 另有 daily-quest/emoji 在製，未納入）。

## 2. 測試覆蓋（8）
大厄/前厄提示、缺 gender（3 種）、非厄年、今年已除厄不附、去年除厄仍附、生日非 8 碼、**fortune 讀取拋錯 → null（fail-safe）**。

## 3. Findings 回報
Blocking / Non-blocking / Nit。修正回 sweetbot-next 改後同步 `impl-s2/`。**過了 → S2 全數完成（S2-1~S2-5）。** 後續為 S3（Discord 設施 UI）/ S4（跨遊戲 wiring）/ S5（後台）+ 奧社聽牌試煉遊戲本體；另整批 sweetbot-next 未 push 未部署（bot restart 待挑時機）。
