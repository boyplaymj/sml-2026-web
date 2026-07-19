# 牙菌斑 — 配點(天賦樹)玩法 × 引擎設計草稿 v0.1

> 定位:engine 階段「配點/碎片兌換/技能/轉職」子系統的**第一片(一般天賦配點)**設計。
> 對齊 [ENGINE-PLAN.md](./ENGINE-PLAN.md) 盤點表、[STAGE1-access-patterns.md](./STAGE1-access-patterns.md) §1-2、[STAGE3-schema-DRAFT.md](./STAGE3-schema-DRAFT.md) M#BUILD。
> ⚠️ **數值全 PLACEHOLDER**(平衡最後統一調,同 config 決策④);本片先鎖**結構與邏輯**,真值等 section-talent/section-soul。
> 💰 成本控管:**免**。不燒 LLM、不開新 DDB 表(複用既有 `M#BUILD` 顆 + 既建 `sweetbot-yajunban-config` 表),純既有表加欄/加設定分區。

---

## 0 · 圖例(正典/提案/待外部)
- 🟢 **正典**:STAGE1/3/4 已定稿,不可擅改。
- 🟡 **本片提案**:Claude 提、待使用者拍板的玩法/數值(可改)。
- 🔵 **待外部設計冊**:要 section-talent / section-soul 才能灌真值,不擋結構定案。

---

## 1 · 一句話核心(🟡)
天賦點**稀缺**,一世點不滿整棵樹 → 玩家必須**取捨出一條自己養的菌株路線**;平常怎麼玩(行為→靈魂軸)**決定哪條路好走**,但軟閘不硬鎖,保留逆練自由。

## 2 · 玩法迴圈(🟡)
養/戰 → 累 XP 進化 → 得點 → 開天賦面板(硬閘擋深、軟閘標成本)→ 點一條專精 → 影響戰鬥/解職/外觀 → 轉生沉澱成老靈魂 → 下一世那條路更順。

---

## 3 · 天賦樹結構

### 3.1 六臂 ↔ 靈魂軸 ↔ 菌學風味(🟡 配對;🔵 軸名待 section-soul)

| 臂(公會) | node 前綴 | 靈魂軸 | 真實口腔菌風味 |
|---|---|---|---|
| 產酸 acid_smith | `acid_*` | 代謝 | 產酸脫鈣、耐酸生存(變異鏈球菌) |
| 基質 matrix_builder | `matrix_*` | 共生 | 胞外多醣基質、生物膜骨架 |
| 拓殖 pioneer | `pioneer_*` | 拓殖 | 早期定殖、快速附著(血鏈球菌) |
| 橋接 bridger | `bridge_*` | 堅韌 | 共聚橋接跨物種黏附(具核梭桿菌=牙菌斑橋樑菌) |
| 毒素 toxin_chemist | `toxin_*` | 侵略 | 白細胞毒素、組織侵襲(牙齦卟啉單胞菌) |
| 謀略 schemer | `scheme_*` | 詭謀 | 免疫逃避、群體感應操控 |

六靈魂軸 = **代謝 / 共生 / 拓殖 / 堅韌 / 侵略 / 詭謀**(1:1 對六臂;軸名待 section-soul 對齊)。

### 3.2 節點總數(🟢 骨架 ≈145)
```
        ╔═ 轉生疊加層 center_reborn_1..8 ═╗  🔒不吃當世點(老靈魂階梯,ancestral_talents 解鎖)
        ╚═══════════════╤════════════════╝
                   ● 共通根(s≥1,免費)
   ┌────────┬────────┼────────┬────────┬────────┐
 產酸     基質     拓殖     橋接     毒素     謀略
 t1(s≥1) … t5(s≥5) 每臂 ~5 層 × ~3 節點 ≈ 15
   ↓前置鏈(同臂往深走)
6 臂 ≈ 90 + 共通根 ~10 + 💎數值天賦 ~15 + 轉生層 ~30 ≈ 145 ✅(對齊 STAGE3 line 13)
```
- node id 形狀(🟢):`<臂>_<子道>_<層>`,如 `acid_A_1` / `center_reborn_2`。
- **靜態定義表不落怪獸 item**(🟢 STAGE3 line 13)→ 存 config `growth.talents`(見 §7)。

---

## 4 · 點數經濟(🟡 數值 PLACEHOLDER)

| 來源 | 給點 | 一世小計 | 正典 |
|---|---|---|---|
| 進化(S2~S6 各 +1) | +1 ×5 | 5 | 🟢 STAGE1「進化 +1」 |
| 菌核躍動(隱藏 EXP 里程碑,如 500/2000/6000 exp) | +1 ×3 | 3 | 🟢 來源既定 / 🔵 門檻待定 |
| **一世上限** | | **≈ 8 點** | 🟡 |

145 節點只給 ~8 點 → 逼出 build 分化;後台可調當煞車。

---

## 5 · 雙閘門(配點的靈魂)

### 5.1 硬閘 = 階段深度(🟢)
tier N 節點需 `stage ≥ N`。`stage` 單調不倒退 → engine **讀時判定即安全**(不需鎖)。

### 5.2 軟閘 = 靈魂親和(🟡 機制;成本/效果調節,不封死)
| 節點軸 vs 你的靈魂 | 點數成本 | 效果倍率 |
|---|---|---|
| 親和臂(靈魂 top-2 軸) | **1 點** | **×1.2** |
| 中性臂 | 1 點 | ×1.0 |
| 相斥臂(靈魂 bottom-1 軸,分數 < 門檻) | **2 點** | ×1.0(**仍可點,不封**) |

- 「軟親和」是 🟢 既定詞(STAGE1 §1-2「雙閘門:階段深度+靈魂軟親和」);折扣/加成/2點懲罰是 🟡 提案。
- 靈魂分數來源(🔵):現世靈魂軸(PROGRESS soul)+ 老靈魂 `PLAYER#PERMANENT.soul_legacy.affinity`(STAGE4);讀哪顆為準 = **D3 待拍板**。

---

## 6 · 節點種類 / 洗點 / 轉生 / 玻璃箱

### 6.1 三類節點(🟡)
1. **被動數值**:小幅 stat/pH/菌氣(戰鬥讀靜態平衡表)。
2. **機能解鎖**:技能槽 +1、外觀插槽、**轉職入口**(如 `acid_slot` 解 acid_smith)。
3. **💎數值天賦**:另一套,靠 `stats` 跨門檻解(`talent_unlockable`),**不吃這條配點** → **本片不做,下一片**。

### 6.2 洗點(🟡)
- 一世**不可自由洗點**(決策有重量)。
- 稀有道具「**菌核回溶劑**」全額退點一次(道具消耗,掉落極低)。

### 6.3 轉生互動(🟢 重置語義 / 🟡 起手給法)
- 轉生 `talent_nodes` 清空重點(新一世,🟢 STAGE4)。
- 當世**點最多的臂** → `ancestral_talents` ADD 該 theme(🟢 永久 SS);下一世該臂 **t1 免費預點 ×1** + 該軸靈魂起手 bias(🟡)。

### 6.4 玻璃箱 DTO(🟢 不外流裸值,STAGE3 §玻璃箱)
- 點數 → `●●●○○`(亮=可用),不給數字。
- 節點狀態 → 🔒未達階段 / ◎可點 / ●已點 / ⚠可點但相斥(2點)。
- 效果 → 只給方向敘述,不給裸數字。

---

## 7 · config `growth.talents` schema(🟡 結構;值 PLACEHOLDER)

```js
growth: {
  points: { perEvolution: 1, kingakuMilestones: [500, 2000, 6000] }, // 進化+1 / 躍動門檻(exp)
  softGate: { affinityTopN: 2, repelBottomN: 1, repelThreshold: -30,  // 軸親和判定
              onAffinityEffectMult: 1.2, repelCostMult: 2 },
  respecItemId: 'nucleus_solvent',        // 菌核回溶劑(全額洗點一次)
  rebirthFreePreplacePerLife: 1,          // 轉生下一世免費預點數
  // 靜態天賦定義表:key=nodeId,稀疏;effect 交戰鬥/面板平衡表詮釋
  talents: {
    acid_A_1: { arm: 'acid', axis: 'metabolism', tier: 1, stage: 1, cost: 1, prereq: [],
                kind: 'passive', effect: { pH: -0.1 } },
    acid_A_2: { arm: 'acid', axis: 'metabolism', tier: 2, stage: 2, cost: 1, prereq: ['acid_A_1'],
                kind: 'passive', effect: { atk: 2 } },
    acid_A_3: { arm: 'acid', axis: 'metabolism', tier: 3, stage: 3, cost: 1, prereq: ['acid_A_2'],
                kind: 'passive', effect: { descaleDmgPct: 8 } },
    acid_B_1: { arm: 'acid', axis: 'metabolism', tier: 1, stage: 1, cost: 1, prereq: [],
                kind: 'passive', effect: { starveSickResist: 1 } },
    acid_slot: { arm: 'acid', axis: 'metabolism', tier: 3, stage: 3, cost: 1, prereq: ['acid_A_2'],
                 kind: 'unlock', unlock: { jobEntry: 'acid_smith' } }
    // 其餘 5 臂鏡像;💎數值天賦另分區(下一片)
  }
}
```

---

## 8 · DAO / engine 分層計畫(照 feed/clean/pet 範本)

1. **config `growth.talents`**(§7)—— 先結構 + 產酸臂範例節點,其餘臂/真值待 section-talent。
2. **DAO `MonsterDAO.allotTalent(userId, nodeId, { prereq, cost })`**
   對 `M#BUILD` 的寫入,條件:`talent_points_available >= cost` AND `contains(全部 prereq)` AND `NOT contains(nodeId)`(冪等防重複扣點);`ADD talent_nodes :node, talent_points_available :-cost`。
   回 `{ ok } / { ok:false, reason:'no_points'/'prereq_unmet'/'already_owned' }`。
   - 首次配點:`talent_nodes` 稀疏不存在 → `contains` 回 false → `NOT contains` 為 true(允許)、`ADD` 建立 SS。
3. **engine `GrowthEngine.allotTalent(userId, nodeId)`**
   讀 status(CORE.stage + BUILD nodes/points + soul)→ 硬閘(stage≥node.stage)+ 軟閘(算 cost/mult)→ 查 config 節點定義 → 呼 DAO → 回玻璃箱 DTO。
4. **各層測試**(不打 AWS,同 care 片流儀)。

### 待拍板工程決策
- **D1 · 單一 UpdateItem vs TransactWrite**:消耗(points−)與授予(nodes ADD)**同在 `M#BUILD` 兩鍵** → 單一 conditional UpdateItem 即原子。STAGE1/3 標「TransactWrite」偏保守。**Claude 傾向單發 UpdateItem**(WRU 減半、更簡單);因與 canon 標記不一致,需先合意(避免重演 daily wrapper 分岔)。
- **D2 · 先只做一般天賦**(`talent_nodes`),💎數值天賦(`talent_unlockable`)留下一片。**傾向分開**。
- **D3 · 軟閘讀哪顆靈魂**:現世靈魂軸(PROGRESS)vs 老靈魂 `PERMANENT.soul_legacy.affinity`;硬度(軟=改成本/效果,非硬擋)。**待 section-soul 確認**。

---

## 9 · 開工前依賴(不擋結構定案)
- 🔵 section-soul:六靈魂軸正式名 + 分數尺度 + 讀取位置(D3)。
- 🔵 section-talent:145 節點真實 effect / 前置圖 / cost 分佈。
- 🔵 菌核躍動 EXP 門檻(§4)。
