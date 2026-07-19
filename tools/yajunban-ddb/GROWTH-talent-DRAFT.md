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
- 靈魂分數來源(**D3 ✅**):讀**現世靈魂軸(M#PROGRESS soul)**;老靈魂慣性已於轉生 seed 進現世(不另讀 PERMANENT)。軸 DAO 未做時 fallback 全中性。

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
  points: { perEvolution: 1, perKingaku: 1, kingakuMilestones: [500, 2000, 6000] }, // 進化/躍動給點量 + 躍動門檻(exp);後台可調當煞車
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

1. **✅ config `growth.talents`**(§7)—— 結構 + 產酸臂 5 範例節點 + `getTalent(nodeId)` 存取器(其餘臂/真值待 section-talent)。commit `7c7a7b4`。
2. **✅ DAO `MonsterDAO.allotTalent(userId, nodeId, { prereq, cost })`**
   `M#BUILD` 單一 conditional UpdateItem:`SET updatedAt ADD talent_nodes :node, talent_points_available :-cost`,條件 `points≥cost AND NOT contains(node)(冪等) AND contains(全 prereq)`;失敗補一次 ConsistentRead 分類 → `no_build/no_points/already_owned/prereq_unmet/conflict`;非條件錯 rethrow。首次配點 talent_nodes 稀疏→NOT contains 放行、ADD 建 SS。commit `25a5336`。
3. **✅ engine `GrowthEngine.allotTalent(userId, nodeId)`**
   讀 CORE.stage + BUILD nodes/points + PROGRESS soul → 硬閘(stage≥node.stage 讀時判定)+ 軟閘(`computeSoftGate`:現世 soul 算 cost/effectMult,缺→中性)→ config getTalent → DAO → 玻璃箱 DTO(結構透明、裸點數不外流,只揭「還可以點」事件)。DAO 補 `getBuild`/`getProgress`。commit `74e153c`。
4. **✅ 各層測試**(不打 AWS):config 31 / MonsterDAO 101 / growth 20,全 yajunban 635 pass。

> **一般天賦配點主迴圈 = code-complete**(step 1-3)。未 live(engine 階段攢著,未 wire discord.js/面板)。
> **✅ (a) 天賦樹面板 DTO** `GrowthEngine.getTalentTree`:逐節點 owned/stage_locked/prereq_locked/available(+affinity/canAfford)、按臂分組+每臂親和、成本欄含軟閘。commit `abee9fc`(growth 37 測)。
>   - ✅ **玻璃箱取捨已複驗通過(Codex 2026-07-19,無 P0/P1)**:點數以「亮點條 `●●●`(pointsBar)」呈現而非裸整數。結論=可花費點數(配點 budget)屬「須給玩家可規劃資源」的例外,若退成 hasPoints 布林則 `cost:2` 軟閘面板失去意義;亮點條比裸數字含蓄、超 cap 只顯 `＋` 無無上限外流 → **拍板保留**。
> **✅ (b) 進化給點 + 菌核躍動 give-point**(2026-07-19,Fable5 生成×3 + Opus 逐一覆核 PASS):
>   - **給點原語** `MonsterDAO.grantTalentPoint(userId, grantKey, n)`:單一 conditional UpdateItem on `M#BUILD`,`ADD talent_points_available :n, talent_point_grants :key`,條件 `attribute_exists(userId) AND NOT contains(talent_point_grants, :keyStr)` → **claimed-set 冪等**、`attribute_exists` 守衛擋未孵化憑空建幽靈 BUILD;失敗補 ConsistentRead 分類 `no_build/already_granted/conflict`。新增稀疏 SS 屬性 `talent_point_grants`(key=`evo:<stage>`/`kingaku:<m>`),已同步 STAGE3 M#BUILD + 寫入路徑。
>   - **菌核躍動** `GrowthEngine.kingakuCheck(userId)`(**可 live**):讀 CORE.xp → 比隱藏里程碑 `points.kingakuMilestones` → 未領逐一 grant(升序、冪等保底 xp 最終一致下最壞晚給不重複)→ 玻璃箱 DTO 恰三欄 `{pulsed, justPulsed, pointsGained}`(不外流 xp/門檻/總量)。
>   - **進化給點** `GrowthEngine.grantEvolutionPoint(userId, newStage)`:薄封裝 `evo:<stage>` key;完整進化門檻(7門檻/23插槽/外觀重生)屬另片,屆時 stage-up 的 CORE+BUILD TransactWrite 把此給點當 BUILD leg(冪等→拆/合皆安全)。
>   - **給點量煞車語義(Codex 二驗 P2 收斂)**:`perKingaku`/`perEvolution` 經 `sanitizePerPoint` 清洗 —— **正整數才給;`0`=後台煞車(停用該來源);負/小數/NaN=壞 config → fail-safe 停用**(熱路徑不 throw、不神秘退回 1)。kingaku 煞車回 `{pulsed:false}`;evo 煞車回 `{ok:false, reason:'grant_disabled'}`。`kingakuMilestones` 讀時 filter 正整數 + 去重 + 升序。
>   - 測試:DAO +17(→118)、engine +16(→53),**全 yajunban 685 pass / 0 fail**。未打 AWS、未 wire discord/面板。
> **下一步候選**:(c) 💎數值天賦(`talent_unlockable`)另片;(d) 洗點(菌核回溶劑)+ 轉生免費預點;(e) 完整進化門檻(7門檻+23插槽+外觀,把 grantEvolutionPoint 掛進 stage-up TransactWrite)。

### 工程決策(✅ 已拍板 2026-07-19)
- **D1 ✅ 單一 conditional UpdateItem**(非 TransactWrite):消耗(points−cost)與授予(nodes ADD)**同在 `M#BUILD` 兩鍵** → 一發 UpdateItem 即原子。TransactWrite 只在**進化**(同時動 CORE.stage + BUILD)才需要。已同步改 STAGE1 §1-2/§寫入路徑 + STAGE3 §寫入路徑 的標記(免分岔)。
- **D2 ✅ 先只做一般天賦**(`talent_nodes`);💎數值天賦(`talent_unlockable`,stats 跨門檻觸發)留下一片。
- **D3 ✅ 軟閘讀「現世靈魂軸(M#PROGRESS soul)」**,不另讀老靈魂:轉生時新一世靈魂已由 `computeSoulRebirth` start_bias seed 老靈魂慣性 → 讀現世即含老靈魂,少讀一顆。硬度 = **純軟**(只調成本/效果,永不封死)。**靈魂軸 DAO 未做時(ENGINE-PLAN row 40)engine fallback 全中性(cost 1/×1.0)**。唯一待外部 = 軸正式名(section-soul,對 engine 是純字串鍵,不擋結構)。

---

## 9 · 開工前依賴(不擋結構定案)
- 🔵 section-soul:六靈魂軸正式名 + 分數尺度 + 讀取位置(D3)。
- 🔵 section-talent:145 節點真實 effect / 前置圖 / cost 分佈。
- 🔵 菌核躍動 EXP 門檻(§4)。
