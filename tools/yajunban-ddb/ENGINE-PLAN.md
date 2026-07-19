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
| **餵食**(首片 ✅ 定稿) | 選食物→結算 satiety/friendship/obesity/xp(mood=derived 不落庫)+ 扣背包 | ✅ `feedTxn`(白名單 + careVersion 鎖) | 已完成(範本) |
| 清潔/摸頭(G1/G2 ✅ 定稿) | obesity/friendship/xp 收支 + 每日次數閘門 | ✅ `careTxn`(通用照顧範本:白名單 + careVersion 鎖 + `daily` 當日計數整包覆寫) | 已完成(clean/pet engine 走 `_doCare`;走格子/發酵 obesity 收支待 pH 模型) |
| 移動 | 走一格(扣 khui + 搬桶) | ✅ `WorldDAO.moveTo` | engine 接 |
| 相鄰/偷菜/殘渣 | 找目標 + 複驗 + 拾取 | ✅ `neighbors`/`verifyOccupant`/`pickLoot` | engine 接 + 偷菜寫法 |
| 配點/碎片兌換/技能/轉職 | 消耗+授予(TransactWrite) | 🔶 `consumeItem` 有,**各自寫法未做**;配點玩法設計已鎖草稿 [GROWTH-talent-DRAFT.md](./GROWTH-talent-DRAFT.md)(一般天賦=單 UpdateItem 待 D1 拍板) | 新 DAO 寫法數個 + engine |
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

**首片切片內容(✅ 已實作定稿,Codex 二輪收斂)**
1. config:`food` 分區(每食物 satiety/friendship/obesityChance/obesityInc/xp/pH;**無 mood** — derived)+ caps。走 `ConfigStore`(DDB 後台可調 + baked 預設 + 60s 快取 + save 樂觀鎖)。
2. DAO:`MonsterDAO.feedTxn(userId, foodId, effects, pinCareVersion, now)` = 單一 TransactWrite(Update CORE + `INV#food` qty−1)。
3. engine:`game/yajunban/care.js` `feed()`。
4. DTO:`toStatusDTO(core, virtual)` 玻璃箱。
5. UI:指令 + 面板(**未做**,先後端)。

### ⭐ engine 範本鐵律(照顧子系統一律照抄,Codex P1-5)
下一片(清潔/摸頭/玩耍/…)複製時**必須**遵守,否則漏鎖/破語義:
- **`careVersion` 照顧樂觀鎖**:**所有**改 CORE stored 欄(satiety/friendship/obesity…)的照顧操作,DAO 交易內都要 `setArith('careVersion','+',1)` + `condition careVersion=pinCareVersion`(首次 `attribute_not_exists`);engine 從 `getStatus` 讀 `core.careVersion` 當 pin。像 world 的 posVersion —— 序列化所有照顧操作,防互相覆蓋 RMW 欄。**簽名帶 `pinCareVersion`,不是舊的 `(…, now)`**。
- **`last_interaction=now`**:任何照顧互動(餵食/摸頭/玩耍/清潔)都要同交易 SET,否則 computeVirtualState 仍算 friendship 衰退/孤單/逃跑倒數。
- **DAO 白名單**:每個照顧 DAO 寫法限定可寫欄位集合(如 feed 限 satiety/friendship/obesity_level + xp),防 engine/config bug 污染 schema;**derived 欄(mood 等)絕不落庫**。
- **clamp 在 engine**、**數值全來自 config**、**對外只回玻璃箱 DTO**、**只透過 DAO 讀寫**。
- ⚠️ **已知缺口(Codex P1-6)**:virtual 衰退率(khui/satiety decay…)尚未接 config,仍用 `virtualState.js DEFAULT_RATES`(PLACEHOLDER);`config.DEFAULTS.rates` 已預留分區,完整 wiring 待專案(需鏡射 DEFAULT_RATES 全形狀)。

做完首片 → Codex 二輪收斂 → 當範本,再依序複製到 清潔/成長/世界/任務/堡壘/戰鬥。

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

## ✅ 拍板決策(2026-07-18 使用者定案)
1. **engine 落點**:`sweetbot-next/game/yajunban/`,與現有甜甜遊戲風格對齊。
2. **config**:**走 DDB 設定表(`sweetbot-yajunban-config`,後台可調)**;engine 讀時 merge 到 baked PLACEHOLDER 預設 + 記憶體快取(admin 改動 TTL 內生效)。
3. **首片範圍**:**先後端**(config + DAO 寫法 + engine + DTO + 單測不打 AWS);**未規劃完的系統預留欄位**(結構先在、值先空/placeholder)。UI 等後端範本穩了再接。
4. **數值**:**先放 PLACEHOLDER 佔位**,平衡最後統一調(engine 不編造,值全集中在 config 便於後台改)。

---

## 💰 成本控管
engine 不新增 DDB 表/不燒 LLM(純邏輯 + 既有 DAO);config 若走 DDB 表=1 張小設定表 PAY_PER_REQUEST。維持綠區(對照 `tools/COST_CONTROL.md`)。
