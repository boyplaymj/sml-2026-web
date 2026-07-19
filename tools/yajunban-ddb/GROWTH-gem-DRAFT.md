# 牙菌斑 — 💎數值天賦環 × 引擎設計草稿 v0.1

> 定位:engine 階段「成長」子系統的 **(c) 💎數值天賦環**(數值跨門檻解鎖的另一套天賦,平行於 [GROWTH-talent-DRAFT.md](./GROWTH-talent-DRAFT.md) 的一般配點環)。
> 對齊 [STAGE1-access-patterns.md](./STAGE1-access-patterns.md) row 70/71(數值天賦解鎖檢查/標記可習得)、[STAGE3-schema-DRAFT.md](./STAGE3-schema-DRAFT.md) M#BUILD `talent_unlockable` + M#CORE `stats`。
> ⚠️ **門檻/effect 全 PLACEHOLDER**(真值待 section-talent);本片鎖結構與邏輯。
> 💰 成本控管:**免**(不燒 LLM、不開新表、純既有表加欄/加設定)。

---

## 0 · 一句話核心
6 種戰鬥數值(hp/atk/def/magic/spd/luck,靠碎片兌換提升)跨過門檻 → 對應 💎gem 天賦變「**可習得**」→ 玩家**主動習得**(免點)→ 給被動 effect。**不吃一般配點**(與配點環兩套獨立)。

## 1 · 拍板決策(2026-07-19)
- **D-c1 兩步(可習得 → 習得)**:跨門檻 = 標記「可習得」(`talent_unlockable` ADD)+ 發解鎖事件;玩家再主動「習得」(免費、不吃一般點)才生效。對齊 STAGE1 row 71「標記可習得 + 解鎖事件」與 STAGE3「unlockable=可習得待點」;主動採收比自動長出有養成感。
- **D-c2 習得存獨立 `talent_gems` SS**(不併進 `talent_nodes`):數值環 vs 配點環語義分開,戰鬥/面板讀取不混。→ M#BUILD 新增稀疏屬性 `talent_gems`。
- **D-c3 觸發 + 冪等**:`gemCheck(userId)`(仿 `kingakuCheck`)在數值變動後呼叫 → 讀 `CORE.stats` 比 config 門檻 → 未標且已達的 `ADD talent_unlockable`(claimed-set 冪等,重跑不重複標)。
- **D-c4 習得 = 原子搬移**:`learnGem(userId, gemId)` 單一 conditional UpdateItem:`DELETE talent_unlockable :gem` + `ADD talent_gems :gem`,條件「在 unlockable 且 不在 gems」→ 可習得→已習得 原子搬移。

> **Codex 階段1 二驗收斂(2026-07-19)**:P1-1 `markGemUnlockable` 條件補 `NOT contains(talent_gems)` 保三態互斥(否則已習得 gem 被重標);P1-2 STAGE3 M#BUILD `talent_gems` 已回填正典+孵化缺省+寫入路徑;P2-1 兩 DAO 用 raw `UpdateCommand`(非 builder,避免 `REMOVE` 刪整包 SS);P2-2 config `getGemTalent` 補測(讀/null/override deep-merge)。

## 2 · 狀態機(每 gem)
```
   stat < threshold ─────────────────► [locked]     (面板:🔒 未達)
   stat ≥ threshold(gemCheck 標記)──► [unlockable]  (talent_unlockable;面板:💠 可習得)
   learnGem(玩家主動,免點)──────────► [learned]     (talent_gems;面板:💎 已習得,effect 生效)
```
- 三態互斥;`talent_unlockable` 與 `talent_gems` 兩 SS 不重疊(learn 時原子搬移)。
- effect 於戰鬥/面板讀 `talent_gems` 成員 → 查 config gemTalents[gemId].effect(靜態平衡表,不落庫)。

## 3 · config `growth.gemTalents`(值 PLACEHOLDER)
```js
gemTalents: {                                          // key=gemId(稀疏)
  gem_atk_1: { stat: 'atk', threshold: 20,  effect: { atkPct: 5 } },
  gem_atk_2: { stat: 'atk', threshold: 50,  effect: { atkPct: 12 } },
  gem_hp_1:  { stat: 'hp',  threshold: 100, effect: { hpPct: 5 } },
  gem_def_1: { stat: 'def', threshold: 20,  effect: { defPct: 5 } },
  gem_spd_1: { stat: 'spd', threshold: 15,  effect: { spdPct: 5 } }
  // magic/luck + 高階門檻鏡像待 section-talent
}
```
存取器 `ConfigStore.getGemTalent(gemId)`(缺=null)。

## 4 · DAO / engine 分層(照 (b) 範本)
> ⚠️ **兩個 DAO 都用單顆 raw `UpdateCommand`(仿 `grantTalentPoint`),非 `YajunbanTransactionBuilder`**(Codex (c) P2-1):builder 只做跨顆 TransactWrite,且其 `.remove()` 是 `REMOVE path`(刪整包屬性),**不是** DDB Set-元素 `DELETE`。learnGem 的 `DELETE talent_unlockable :gem` 是 raw UpdateExpression 的 Set-元素刪除(只刪該 gem,保留其餘)。

1. **DAO `markGemUnlockable(userId, gemId)`**(單顆 raw UpdateCommand on M#BUILD):`ADD talent_unlockable :gem`,條件 `attribute_exists(userId) AND NOT contains(talent_unlockable, :gemStr) AND NOT contains(talent_gems, :gemStr)`。⚠️ **`NOT contains(talent_gems)` 不可省**(Codex (c) P1-1):否則已習得的 gem 因 stat 仍達標被 `gemCheck` 重標回 unlockable,破壞三態互斥。分類 `no_build/already_unlockable/already_learned/conflict`。
2. **DAO `learnGem(userId, gemId)`**(單顆 raw UpdateCommand):`SET updatedAt DELETE talent_unlockable :gem ADD talent_gems :gem`,條件 `attribute_exists(userId) AND contains(talent_unlockable, :gemStr) AND NOT contains(talent_gems, :gemStr)`。可習得→已習得 原子搬移(同顆兩集,單 UpdateItem 即原子,免 Transact)。分類 `no_build/not_unlockable/already_learned/conflict`。
3. **engine `gemCheck(userId)`**:讀 CORE.stats + BUILD(unlockable/gems)→ 比 gemTalents 門檻 → 未標、未習得、已達的逐一 markGemUnlockable(engine 先讀 BUILD 過濾 learned,DAO 條件再保險)→ 玻璃箱 DTO(揭「💠N 個新數值天賦可習得」事件,**不外流裸 stats/門檻**)。
4. **engine `learnGem(userId, gemId)`**:驗 config 有此 gem → 呼 DAO → 玻璃箱 DTO(揭「習得💎」+ 方向敘述)。
5. **engine `getGemPanel(userId)`**:讀 stats + unlockable + gems → 逐 gem 狀態 locked/unlockable/learned(玻璃箱:met 布林 + 狀態,**不給裸 stats/門檻數值**,對齊配點環玻璃箱)。

## 5 · schema 影響(STAGE3 M#BUILD)
- 既有 `talent_unlockable`(SS):本片正式啟用(可習得 pending 集)。
- **新增 `talent_gems`(SS,稀疏)**:已習得數值天賦集(learn 時 unlockable→gems 原子搬移)。空 SS 不寫、缺省視為空。

## 6 · 開工前依賴(不擋結構)
- 🔵 section-talent:各 gem 真實 stat/threshold/effect + 數量。
- 🔵 碎片兌換(另片):寫 CORE.stats 的來源;本片只讀 stats,不管誰把它變大。
