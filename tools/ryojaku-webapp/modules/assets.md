# 🎒 玩家資產層 + 甜甜連動 (Player Assets & Cross-App)

> **狀態**：架構已由 gameboy 拍板(2026-07-16)✅ 五項決策見 §6；下一步交 Codex 打底 L1/L2(§7)
> 一句話：**把「等級/貨幣/稱號/外觀」抽成一個跨產品的玩家資產層，讓同一個人在両雀與甜甜之間帶著資產走——例如賓果盤能在両雀開盤、在對的錢包發獎。**

這一層坐在 [character(RPG)](character) 之上：character 定義「両雀怎麼長角色」，本模組定義「資產怎麼被持有、跨產品怎麼流通」。

---

## 0. 為什麼要獨立一層（不然會長歪）

兩個產品各自有經濟：**両雀=雀幣**、**甜甜=牙齒🦷**（已上線、有通膨基線與稅制）。若不先抽象，未來「賓果盤搬進両雀」會被迫在兩套帳、兩套身分、兩套發獎邏輯裡硬接 → 又臭又長還容易漏發/重發。所以先立**四層**，每層只做一件事：

| 層 | 做什麼 | 對「賓果盤跨產品」的意義 |
|---|---|---|
| **L0 身分橋** | 一個人 = 一個 `personId`；LINE(両雀) ↔ Discord(甜甜) 綁定 | 知道「這個両雀玩家 = 哪個甜甜玩家」才能發對錢包 |
| **L1 資產錢包** | 多資產：等級XP · 多幣別(雀幣/牙齒) · 稱號 · 外觀 | 資產有統一模型，不是散在各遊戲裡 |
| **L2 發獎匯流排** | 單一 `grant()` API：發 X 給某人、冪等、可稽核 | 賓果盤只要喊一次 grant，不管跑在哪 |
| **L3 遊戲承載** | 遊戲邏輯抽成共享服務；各 app 只提供介面殼 | 賓果盤寫一次，両雀(LIFF)與甜甜(Discord)都能跑 |

---

## 1. L0 身分橋（keystone，卡在工程師）

- 一個真人 = 一個 canonical `personId`。**兩邊各自的帳號 id 掛在它底下**：
  ```
  Identity { personId, lineUserId?, discordId?, ytChannelId?, ryojakuUserId?, linkedAt }
  ```
- 甜甜這側已有 Discord↔YT 綁定與反分身；両雀這側身分走 **LINE / LIFF**（foundation §6 open thread）。**綁定動作需工程師開整合點**（LINE 身分驗證），我方無法單邊完成 → 這是整個跨產品的**前置依賴**。
- **反分身共用**：綁定即接 [trust-safety](trust-safety) 的一人一身分，跨產品刷帳更難。

---

## 2. L1 資產錢包（本題核心：等級/貨幣/稱號/外觀）

一個 `personId` 底下持有四類資產，**每類標 `realm`（ryojaku / sweet / shared）**——這個 realm 欄位就是「未來跨產品」的開關：

### 2.1 等級 / 經驗值（資歷，per-realm）
- **兩邊 XP 不混算**：両雀資歷 XP（打真牌、防刷嚴，見 character §2/§5）≠ 甜甜活躍 XP。混算會汙染両雀名片的可信度。
- 共用**檔案視圖**顯示兩條成長線，但**各自獨立計算**。
- `LevelState { personId, realm, xp, level }`

### 2.2 貨幣（兩種軟幣，獨立錢包、不可互換）✅ 拍板
```
Wallet   { personId, currency(雀幣|牙齒), balance }
CoinLedger { personId, currency, delta, reason, sourceGame, refId, ts }  // 每筆可稽核
```
兩種幣、**兩個獨立錢包、永不互換**（gameboy 2026-07-16 拍板），但角色不同：

| 幣 | realm | 是什麼 | 跨產品行為 |
|---|---|---|---|
| **牙齒 🦷** | **shared** | **跨產品共用的「遊戲門票貨幣」**——玩遊戲要花牙齒、也能賺牙齒（概念同甜甜） | **同一個人 = 同一份牙齒餘額**，甜甜賺的在両雀能花、反之亦然。両雀是牙齒的**新水龍頭(賺)+新水槽(花)** |
| **雀幣** | ryojaku | 両雀特有軟幣（若需要獨立於牙齒的経済槓桿再啟用） | 純両雀 native，不跨產品 |

- **牙齒 single source of truth 在甜甜側**（既有 `sweetbot-player-point-log` / `givePoint`）。**両雀當第二個 client**：透過 L0 身分映射 + L2 `grant()` 讀寫**同一本牙齒帳**——不另開一本、不做同步對帳（避免雙帳漂移）。
- 🔒 **貨幣紅線（繼承 foundation §2.8）**：牙齒/雀幣都是**軟遊戲幣**——① 永不可兌換現金；② **永不等於也不混入「輸贏點數」**（點數是計分、走 §8a 另軌）；③ 平台不經手金額。牙齒共用只是**跨 app 共餘額**，不是金錢流動 → 碰不到金流紅線。
- ⚠️ **通膨共池**：両雀發牙齒 = 動到甜甜的共用牙齒池（現基線 ~164k🦷/日）→ 両雀的牙齒發放率**必須納入牙齒經濟監控**，別讓新水龍頭沖垮既有平衡。

### 2.3 稱號（scoped + portable 旗標）
- `Title { personId, titleId, realm, portable(bool), earnedAt }`
- 多數稱號 app-scoped（両雀「千局雀鬼」/甜甜「賓果王」各自展示）；標 `portable` 的可跨產品展示（例如通用榮譽徽章）。稱號是**文字/徽章**，跨產品成本低、最容易先打通。

### 2.4 外觀（inventory，多半 app-scoped）
- `Cosmetic { personId, itemId, realm, slot, source(default|unlock|purchase) }`
- **美術載體不同**：両雀=角色 avatar 組件（character §4）、甜甜=Discord emoji 金庫紙娃娃。故外觀**多半各自為政**，跨產品共用的是「同一套設計語言/通行證進度」，不是同一個檔。跨用只挑做得到的（如共用邊框/主題色）。

---

## 3. L2 發獎匯流排（讓賓果盤「發獎」與承載脫鉤）

任何遊戲（賓果盤、ingame 小遊戲、天梯結算、每日任務）發獎都只呼叫**一個冪等 API**：
```
POST /grant
{ personId, realm, asset(xp|coin|title|cosmetic),
  currency?, amount?, itemId?, reason, sourceGame, idempotencyKey }
```
- **冪等**：同 `idempotencyKey` 只發一次（沿用甜甜賓果盤現有的冪等擋二次發獎經驗）。
- **路由**：`realm` 決定進哪個錢包——賓果盤跑在両雀 → 發雀幣；跑在甜甜 → 發牙齒；**同一份遊戲邏輯，發獎目標由 host 帶入的 realm 決定**。
- **全稽核**：進 CoinLedger/XpLedger，接後台用量與作弊修正。
- 甜甜側可保留現有 `givePoint`/point-log 當 牙齒 realm 的底層實作，`grant()` 只是它的**上層統一入口**（不重寫既有經濟）。

---

## 4. L3 遊戲承載（賓果盤跨產品的三條路）

賓果盤現況：活在甜甜（`Bingo.js` + Firestore，麻將連線盤已上線）。要「在両雀 APP 上創盤/領獎」有三條路：

| 路線 | 做法 | 取捨 |
|---|---|---|
| **A. LIFF 嵌入** | 両雀用 LIFF/webview 嵌甜甜現有後端，發獎透過 L2 指定 realm=雀幣 | **最快**、重用現成邏輯；但兩後端耦合、樣式各異 |
| **B. 抽共享遊戲服務** ⭐ | 賓果盤邏輯抽成**獨立服務**（開盤/下注/截止/開獎/發獎），両雀原生前端 + 甜甜 Discord 前端都 call 它 | 乾淨、可長期擴充到更多遊戲；需一次性重構 |
| **C. 各自實作** | 両雀重寫一份 | ❌ 雙份維護，不建議 |

**Claude 傾向**：**短期 A（LIFF 嵌入先通）→ 中期 B（抽共享服務）**。B 是終局，但先用 A 驗證跨產品發獎鏈（L0→L2）走得通，不必一開始就大重構。

---

## 5. 不變式（給 Codex 寫測試）
1. 兩產品的 **XP 永不混算**（各自 realm）；**雀幣 ↔ 牙齒 永不互換**（兩個獨立錢包）。
2. **牙齒是同一份餘額跨 app 共用**——両雀讀寫的是甜甜那本 canonical 牙齒帳，不另開第二本、不做同步對帳。
3. 軟幣**永不兌現金、永不混入輸贏點數**（金流紅線）。
4. 所有發獎走 L2 `grant()` **冪等**——同 idempotencyKey 不重發。
5. 跨產品發獎/花費**必須先有 L0 綁定**（無 `personId` 映射 → 拒發、不猜）。
6. 每筆資產異動可稽核、可後台修正、可申訴回溯；両雀牙齒發放計入牙齒經濟監控。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）
- **成本來源**：DDB 新表 `identity` / `wallet` / `coin-ledger` / `level-state` / `title` / `cosmetic`，全 PAY_PER_REQUEST、量級小。**不新增 LLM**（發獎是規則邏輯）。
- 甜甜側 牙齒 沿用既有 point-log，不另起爐灶 → 無重複成本。
- 若日後外觀走 Bedrock 生成 → 按 [character §9](character) 的圖像成本規範（按張、非迴圈）。

## 6. 決策（gameboy 2026-07-16 拍板）
- ✅ **貨幣**：雀幣、牙齒**兩個獨立錢包、不可互換**；但**牙齒是跨產品共用遊戲貨幣**——両雀玩遊戲花牙齒、也能賺牙齒，同一人同一份餘額（§2.2）。
- ✅ **等級**：兩產品**各自 XP**、不混算（護両雀資歷防刷純度）。
- ✅ **稱號/外觀**：採 realm + portable 旗標，多半各自、**稱號先跨**（§2.3/§2.4）。
- ✅ **賓果盤承載**：**短期 LIFF 嵌入 → 中期抽共享服務**（§4 A→B）。
- ✅ **打底順序**：L0 身分橋等工程師開 LINE 整合點；**L1 資產錢包 + L2 `grant()` 先在我方這側用自家 AWS 打底**，身分一通就接。

## 7. 下一步（交 Codex 打底 L1/L2）
- **DDB 資料層**（PAY_PER_REQUEST）：`identity`(personId 映射,先建結構待 LINE)、`wallet`(雀幣)、`coin-ledger`、`level-state`、`title`、`cosmetic`。牙齒**不建新表**——走甜甜既有 point-log。
- **`grant()` Lambda**：冪等發獎入口，`realm` 路由(雀幣→両雀 wallet／牙齒→甜甜 givePoint)、idempotencyKey 去重、全稽核。
- **牙齒橋接**：定義両雀後端 → 甜甜經濟後端的**單一寫入 API**（讀寫同一本牙齒帳），含通膨監控掛勾。
- **驗收點交 Codex**：§5 六條不變式寫成測試；賓果盤 grant 冪等（同 key 不重發）端到端。
