# 牙菌斑怪獸 · 全專案進度看板

> 單頁鳥瞰:從設計到上線的整條 pipeline。更新於 2026-07-18。
> 詳細設計在同資料夾 `STAGE*.md`;DAO 程式在 `sweetbot-next/DAO/DDB/yajunban/`(非本 repo)。

## 🚦 一句話狀態
**資料層(DDB + DAO + rebirth)全交付 ✅;遊戲邏輯層 engine 已開工——餵食垂直切片(範本)後端定稿 ✅,其餘子系統照範本鐵律逐條複製中;UI/後台管理頁尚未開工。**

---

## 管線總覽

| 階段 | 內容 | 狀態 |
|---|---|---|
| ① 遊戲設計 | 玩法/種族/成長/戰鬥/堡壘/轉生(設計冊 `yajunban_design.html` + STAGE1) | ✅ 完成 |
| ② DDB 資料模型設計 | STAGE1–9c(存取模式→schema→ledger→lazy→battle→GSI→world→DAO 工程→建表→DAO 計畫) | ✅ 完成(多輪 Codex 二驗) |
| ③ 建表 migration | 核心 4 表 + 堡壘 5 表(共 9 表)實建上線 @ap-southeast-1 | ✅ 完成 |
| ④ **DAO 層**(資料存取) | 基礎設施 + A/B/C/D/E + rebirth 組裝,**492 測試不打 AWS** | ✅ **完成(本階段成果)** |
| ⑤ 設定表(config) | 群感閾值/道具 60 目錄/天賦技能公會平衡表(不落怪獸 item) | 🔴 未開工 |
| ⑥ 遊戲邏輯層(engine) | 餵食/戰鬥/出征/糖潮/任務/轉生 的業務邏輯 + 數值計算(呼叫 DAO) | 🟡 **開工中**:餵食垂直切片(範本)後端定稿(config+feedTxn+care+DTO,Codex 三輪);其餘子系統照 [ENGINE-PLAN 範本鐵律](./ENGINE-PLAN.md) 複製中 |
| ⑦ 戰鬥即時引擎 | 3×3/8 步管線/19 狀態/pH(記憶體,結束才寫 1 次) | 🔴 未開工 |
| ⑧ Discord UI | 指令 + 面板 embed + 按鈕互動(discord.js wire) | 🔴 未開工 |
| ⑨ 遊戲館後台管理頁 | 數值調校/內容管理(如其他遊戲的 admin) | 🔴 未開工 |
| ⑩ 美術/emoji 素材 | 怪獸立繪/道具 emoji/面板圖(i18n:圖不內嵌文字) | 🔴 未開工 |
| ⑪ 階段 10 賽季歸檔 | 賽季軟重置 + 對帳工具(ledger replay + season/guild-index) | 🔴 未開工(設計亦未做) |
| ⑫ 上線 + E2E 驗證 | migration 已建但遊戲未 live;無端到端測試 | 🔴 未開工 |

---

## ④ DAO 層明細(已完成)

| DAO | 表 | 測試 | Codex |
|---|---|---|---|
| 基礎設施 | TransactionBuilder + pagination | 19 | — |
| A MonsterDAO | monster(+rebirth) | 47 | 2+3 輪 |
| B LedgerDAO | ledger | 39 | 2 輪 |
| C BattleDAO | battle(+敗方 pos 重生) | 111 | 2 輪 |
| D WorldDAO | world | 95 | 2 輪 |
| E FortressDAO 等 5 表 | fortress/raid/sugar-pulse/guild-pool/ledger | 194 | 3 輪 |
| **合計** | **9 表** | **492** | 每個都多輪收斂 |

**A/C/D 交會點閉環**:pos 重生 + 轉生繼承(散在 Monster 孵化 / Battle 結算 / World OCC)全串起。

---

## 🔴 剩餘 TODO(依優先序)

**A. 要讓遊戲「能玩」的大塊(未開工)**
1. **設定表**(⑤):平衡數值/道具目錄/天賦技能表 → schema + 建表(小)。DAO 的 PLACEHOLDER 費率(khui/soul EWMA/移動成本)要接這裡。
2. **遊戲邏輯層 + 戰鬥引擎**(⑥⑦):整個業務邏輯與數值,呼叫既有 DAO。**最大一塊**。
3. **Discord UI**(⑧):指令/面板/按鈕。
4. **遊戲館後台管理頁**(⑨)+ **美術素材**(⑩)。

**B. 資料層收尾(小,低風險)**
5. `isConditionalOnlyCancellation` 現 **6 份複製** → 抽共用 helper。
6. `rebindAppAccount` 換綁(Delete 舊 APP# + Put 新 + Update PERMANENT.appAccountId condition,單一 TransactWrite)。
7. 熱操作 `lifeId` guard(rebirth Codex P1-4 後續:防舊世代熱操作與轉生交錯)。
8. INV#/LOOT 掉落 `cap`-in-txn(cap 需 OR 條件,待定案)。

**C. 賽季/維運**
9. **階段 10 賽季歸檔 + 對帳工具**(⑪):設計 + 實作。

---

## 💰 成本控管
7 表無 LLM、無付費 API、全 PAY_PER_REQUEST → 綠區(對照 `tools/COST_CONTROL.md`);主成本=高頻寫的 WRU,已用 lazy compute/單筆非交易/秒級 TTL 壓到最低。
