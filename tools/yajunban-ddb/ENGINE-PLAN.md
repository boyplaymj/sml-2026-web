# 牙菌斑怪獸 · 遊戲邏輯層(engine)規劃

> 規劃冊 · 2026-07-18 · 承接資料層全交付(DAO 492 測試)。本冊定 engine 架構 + 建置順序,尚未實作。
> engine = 「遊戲怎麼運作」;DAO = 「資料怎麼存取」。engine **一律透過 DAO 讀寫,不自己碰 DDB**。

## 🧭 分層與不變式

```
Discord UI(指令/面板/按鈕)   ← ⑧ 未開工
      │ 呼叫
遊戲邏輯層 engine              ← 本冊(未開工)
      │ 讀 config + 呼叫 DAO
設定表 config(平衡數值)      ← ⑤ 未開工(小)
DAO 層(資料存取)             ← ✅ 完成
DynamoDB 9 表                 ← ✅ 完成
```

**不變式**
1. engine **只透過 DAO 讀寫**,絕不自建 DDB client/繞過 DAO(原子性/冪等都在 DAO)。
2. **玻璃箱**:engine 對 UI 只回帶名 DTO(隱藏裸值,STAGE3/8);DAO 回原始 item,engine 轉 DTO。
3. **數值全來自 config**,engine 不寫死平衡值(對接 DAO 的 PLACEHOLDER 費率:khui/soul α/移動成本)。
4. **lazy 讀時算已在 DAO**(computeVirtualState);engine 讀狀態=呼叫 `getStatus` 拿 virtual,不自己算衰退。
5. 位置:`sweetbot-next/game/yajunban/`(新資料夾,一子系統一模組),與 DAO 分離。

---

## 📋 子系統盤點 × DAO 就緒度

| 子系統 | engine 職責 | DAO 現況 | 缺口 |
|---|---|---|---|
| 孵化 | 4 因子種族判定 + 心測抽籤 → 組 items | ✅ `hatch` | engine 算 items |
| **餵食**(建議首片) | 選食物→結算 satiety/mood/friendship/obesity/xp/pH + 扣背包 | 🔶 `consumeItem`/`addItem` 有,**組合 feed TransactWrite 未做** | **新 DAO 寫法 `feedTxn`** + engine |
| 清潔/走格子/發酵 | obesity 收支結算 | 🔴 無 | 新 DAO 寫法(單筆 Update)+ engine |
| 移動 | 走一格(扣 khui + 搬桶) | ✅ `WorldDAO.moveTo` | engine 接 |
| 相鄰/偷菜/殘渣 | 找目標 + 複驗 + 拾取 | ✅ `neighbors`/`verifyOccupant`/`pickLoot` | engine 接 + 偷菜寫法 |
| 配點/碎片兌換/技能/轉職 | 消耗+授予(TransactWrite) | 🔶 `consumeItem` 有,**各自 TransactWrite 未做** | 新 DAO 寫法數個 + engine |
| **戰鬥** | 3×3/8 步/19 狀態/pH **記憶體引擎** + 開戰/結算 | ✅ `startBattle`/`resolveBattle` | **記憶體戰鬥引擎(大)** + engine |
| 堡壘內政/出征/糖潮 | 建堡/資源/raid/claim | ✅ Fortress/Raid/SugarPulse/GuildPool DAO 全有 | engine 接(較薄) |
| 任務/群感/繼承通道 | 進度追蹤 + 發獎 + 遺產 | 🔶 ledger 有,**quest 進度/繼承 TransactWrite 未做** | 新 DAO 寫法 + engine |
| 靈魂 6 軸 | 互動時 EWMA 滑動 | 🔴 無(rebirth 內的深記另計) | soul.version RMW 寫法 + engine |
| 轉生 | 永久死亡判定 → 芽孢輪迴 | ✅ `rebirth` | engine 判定 + 組 newItems |

> 🔑 **重點**:資料層做了「硬」的原子操作;engine 期會**補一批「較簡單」的 per-feature DAO 寫法**(feed/clean/配點/兌換/技能/轉職/quest/soul EWMA),它們也是 TransactWrite/條件寫,仍歸 DAO(維持不變式①)。這批是 engine 階段的隱藏工作量。

---

## 🎯 建置策略:垂直切片先行

不橫向鋪(先做完所有 DAO 寫法再做所有 engine),而是**先打通一條最薄的端到端垂直切片**當範本,驗證整條 stack(config→DAO 寫法→engine→DTO→UI)通,再逐子系統複製。

### 首片建議 = **餵食(feed)**
理由:核心、頻繁、麻雀雖小五臟俱全——踩到 config(食物效果表)、DAO 寫法(CORE+INV# TransactWrite)、computeVirtualState(讀飽食度決定可餵食物)、玻璃箱 DTO(回心情 emoji 不回裸值)、UI 面板(下拉選食物+結果 embed)。打通它=整條分層驗證完畢。

**首片切片內容**
1. config:`food` 表(每食物 satiety/mood/friendship/obesity 機率/pH 效果)——最小 seed。
2. DAO:`MonsterDAO.feedTxn(userId, foodId, effects, now)` = 單一 TransactWrite(Update CORE 結算 + `INV#food` qty−1 條件≥1);沿用既有 builder + 分類。
3. engine:`game/yajunban/care.js` `feed()` = 讀 getStatus 判可餵→查 config→呼叫 feedTxn→回 DTO。
4. DTO:`toStatusDTO(core, virtual)` 帶名標籤(心情 emoji/飽食度描述,不露裸值)。
5. UI:一個指令 + 面板(下拉選食物→結果 embed)。

做完首片 → Codex 二驗 → 當範本,再依序複製到 清潔/成長/世界/任務/堡壘/戰鬥。

---

## 📐 建置順序(垂直切片逐條)

1. **餵食**(首片,建範本 + care.js + config 骨架 + DTO 骨架)
2. **照顧其餘**(清潔/走格子/發酵 → obesity/pH;共用 care.js)
3. **成長**(配點/碎片兌換/技能/轉職 → build.js;各自 DAO 寫法)
4. **世界**(移動/相鄰/偷菜/殘渣 → world engine;DAO 多已就緒)
5. **任務 + 靈魂**(quest.js/soul.js;quest DAO 寫法 + soul EWMA RMW)
6. **堡壘**(fortress engine;DAO 全就緒,engine 較薄)
7. **戰鬥即時引擎**(battle.js;**最大**——3×3/8 步/19 狀態/pH 記憶體;開戰/結算 DAO 已就緒)
8. **轉生判定**(永久死亡偵測 → 組 newItems → rebirth;DAO 已就緒)

> 戰鬥引擎最大最獨立(記憶體暫態,不碰 DDB 直到結算),可與其他切片並行或最後做。

---

## ⚠️ 待拍板決策(開工前)
1. **engine 落點**:`sweetbot-next/game/yajunban/`?與現有甜甜遊戲(如 CrossingRoad.js)風格對齊?
2. **config 落哪**:DDB 設定表 vs JSON 檔 vs 遊戲館後台可調?(影響⑤設計)
3. **首片範圍**:只後端(DAO+engine+DTO,單測)先,還是含 Discord UI 一路到面板?
4. **數值來源**:食物效果等平衡值誰定?(需使用者/設計提供,engine 不編造)

---

## 💰 成本控管
engine 不新增 DDB 表/不燒 LLM(純邏輯 + 既有 DAO);config 若走 DDB 表=1 張小設定表 PAY_PER_REQUEST。維持綠區(對照 `tools/COST_CONTROL.md`)。
