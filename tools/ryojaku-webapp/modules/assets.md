# 🎒 玩家資產層 + 甜甜連動 (Player Assets & Cross-App)

> **狀態**：架構草案 🔶（Claude 提案，待 gameboy 拍板）
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

### 2.2 貨幣（多幣別錢包，一個模型多本帳）
```
Wallet   { personId, realm, currency(雀幣|牙齒), balance }
CoinLedger { personId, currency, delta, reason, sourceGame, refId, ts }  // 每筆可稽核
```
- **雀幣**＝両雀軟貨幣（來自 ingame 小遊戲/簽到/活動），**牙齒**＝甜甜既有經濟。**同一個 Wallet 模型、不同 currency、各自一本 ledger。**
- 🔒 **貨幣紅線（繼承 foundation §2.8）**：雀幣/牙齒都是**軟遊戲幣**——① 永不可兌換現金；② **永不等於也不混入「輸贏點數」**（點數是計分、走 §8a 另軌）；③ 平台不經手金額。跨產品發獎只在**軟幣**之間，碰不到金流紅線。
- **雀幣↔牙齒是否互換 = 待拍板（§6-1）**。預設**不自動互換**，避免一邊通膨傳染另一邊。

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
1. 兩 realm 的 **XP 永不混算**；貨幣**永不自動互換**（除非 §6-1 拍板開閘且經後台管制）。
2. 軟幣**永不兌現金、永不混入輸贏點數**（金流紅線）。
3. 所有發獎走 L2 `grant()` **冪等**——同 idempotencyKey 不重發。
4. 跨產品發獎**必須先有 L0 綁定**（無 `personId` 映射 → 拒發、不猜）。
5. 每筆資產異動可稽核、可後台修正、可申訴回溯。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）
- **成本來源**：DDB 新表 `identity` / `wallet` / `coin-ledger` / `level-state` / `title` / `cosmetic`，全 PAY_PER_REQUEST、量級小。**不新增 LLM**（發獎是規則邏輯）。
- 甜甜側 牙齒 沿用既有 point-log，不另起爐灶 → 無重複成本。
- 若日後外觀走 Bedrock 生成 → 按 [character §9](character) 的圖像成本規範（按張、非迴圈）。

## 6. 待你拍板
- [ ] **雀幣 ↔ 牙齒 關係**：A 完全獨立不互換／**B 獨立錢包 + 受管制單向發獎橋(Claude 傾向)**／C 可雙向兌換。
- [ ] **等級**：兩產品各自 XP（Claude 傾向，護両雀資歷純度）／統一跨產品資歷？
- [ ] **稱號/外觀跨產品**：採 §2.3/§2.4 的 realm + portable 旗標（多半各自、稱號先跨）？
- [ ] **賓果盤承載**：短期 LIFF 嵌入 → 中期抽共享服務（Claude 傾向）？還是直接上共享服務？
- [ ] L0 身分橋要等工程師開 LINE 整合點——**要不要先把 L1/L2 資料層與 grant() 邏輯在我方這側打底**（用自家 AWS），等身分一通就接？
