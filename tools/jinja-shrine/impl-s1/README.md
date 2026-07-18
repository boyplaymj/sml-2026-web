# impl-s1/ — S1 程式碼「review 副本」（給 Codex 讀）

⚠️ **這些不是權威檔，是唯讀副本。**

- **權威原始碼**在 `sweetbot-next`（另一個 git repo，已 commit `804a080`，ahead 未 push——因該樹有別 session 在製品故不推）。
- Codex 讀的是本 repo 的 working tree，讀不到 sweetbot-next，故把 S1 這批 byte-identical 複製到這裡供查驗。
- 路徑鏡射權威樹：
  - `model/shrine/ShrineLuck.js` ← 純引擎（命門）
  - `model/shrine/ShrineLuckService.js` ← getLuck 薄包
  - `model/shrine/defaults.js` ← DEFAULT_SHRINE_CONFIG
  - `DAO/DDB/Shrine{Fortune,Omamori,Config}DAO.js` ← 三 DAO
  - `test/shrineLuck.test.js` ← 9 項單測

**查驗清單見 `../VERIFY-S1.md`。** 修正一律回權威樹 sweetbot-next 改，再同步覆蓋本副本。
