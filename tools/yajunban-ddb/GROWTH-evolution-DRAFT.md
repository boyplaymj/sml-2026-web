# 牙菌斑 — 進化(升階)門檻 × 引擎設計草稿 v0.1

> 定位:engine 階段「成長」子系統的**進化門檻閘 + stage-up 寫入**片(接在配點 [GROWTH-talent-DRAFT.md](./GROWTH-talent-DRAFT.md) 之後)。
> 對齊 [STAGE1-access-patterns.md](./STAGE1-access-patterns.md) row 38/39(進化門檻檢查/升階寫入)、[STAGE3-schema-DRAFT.md](./STAGE3-schema-DRAFT.md) M#CORE/M#BUILD。
> ⚠️ **門檻數值全 PLACEHOLDER**(真值待 section-growth);本片鎖**結構與邏輯**。
> 💰 成本控管:**本片免**(不燒 LLM、不開新表、純既有表條件寫)。⚠️ **外觀圖生成(e2)另片,會吃 Bedrock 圖生成成本 → 屆時該片必含「💰成本控管」段並連回 `tools/COST_CONTROL.md`**。

---

## 0 · 範圍決策(2026-07-19 拍板)
- **D-e1 外觀圖生成切出去**:本片只做「門檻閘 + stage-up TransactWrite + 進化給點」,**$0**。各階解鎖新插槽要生外觀圖(Bedrock)= 吃成本 → 另立 (e-appearance) 片,獨立成本控管四件套。
- **D-e2 stage-up 不寫 `slots`**:「哪些插槽解鎖」= `f(stage)` 純衍生(STAGE3 line 100 靜態對照),不落庫;`slots` map 只存已生成外觀 URL(歸外觀片)。→ 進化寫入只動 `stage`(CORE)+ 給點(BUILD)。
- **D-e3 門檻 config 驅動、PLACEHOLDER**:`growth.evolution.perStage[2..6]` 各 6 門檻(days/xp/survivalHours/charm/friendship/reputation)+ `requireHealthy`,真值 🔵 section-growth。
- **D-e4 DAO evolve = TransactWrite**:CORE 升階 leg + BUILD 給點 leg 原子;門檻條件當 race 保險;engine 先 pre-check 給玻璃箱提示。
- **D-e5 給點沿用 (b) claimed-set**:BUILD leg `ADD talent_points_available + talent_point_grants evo:<stage>`,條件 `NOT contains(evo:<stage>)` → 與 `grantTalentPoint`/`grantEvolutionPoint` 同一 claimed-set,不雙給。**進化給點的正典路徑 = evolve()**;(b) 的獨立 `grantEvolutionPoint` 為備而未用原語,不另 wire(否則兩 writer 搶同一 evo key)。

---

## 1 · 一句話核心
六階成長(芽孢→蛀牙王);每階要 **6 門檻全達標 + 不生病** 才升階;升階當下 +perEvolution 天賦點。門檻只增不倒(除 friendship 狀態型/sick),故 engine 讀時判定 + TransactWrite 條件雙保險。

## 2 · 七閘門(row 38)
| 閘 | 欄位 | 型別 | 可回退? |
|---|---|---|---|
| 天數 | `born_at`(age≥days ⇔ born_at≤cutoff) | 衍生 | 否(時間單調) |
| EXP | `xp` | 累計型 | 否 |
| 存活 | `survival_hours` | 累計型 | 否 |
| 魅力 | `charm` | 累計型 | 否 |
| 友好 | `friendship` | **狀態型 0–100** | **是**(每天無互動 −1) |
| 聲望 | `reputation` | 累計型 | 否 |
| 健康 | `sick_type = 'none'` | 狀態型 | **是**(生病卡關) |

→ 只有 **friendship / sick_type 會回退** → TransactWrite 條件的真正價值 = 擋「pre-check 後這兩者掉下來」+ 擋雙升(stage race)。其餘門檻單調,pre-check 過了寫時必過,但仍全列進條件當 defense-in-depth。

## 3 · config schema(`growth.evolution`,值 PLACEHOLDER)
```js
evolution: {
  requireHealthy: true,                 // sick_type 須 'none'
  perStage: {                           // key = 目標 stage
    2: { days:1,  xp:100,  survivalHours:6,   charm:10,  friendship:20, reputation:5 },
    3: { days:3,  xp:400,  survivalHours:24,  charm:30,  friendship:40, reputation:20 },
    4: { days:7,  xp:1200, survivalHours:72,  charm:60,  friendship:55, reputation:50 },
    5: { days:14, xp:3000, survivalHours:168, charm:100, friendship:70, reputation:100 },
    6: { days:30, xp:8000, survivalHours:360, charm:160, friendship:85, reputation:200 }
  }
}
```

## 4 · DAO / engine 分層 —— ✅ 已實作(2026-07-19,Fable5 產碼×3 + Opus 逐一覆核 + 全 yajunban 735 pass/0 fail)
1. **DAO `buildEvolveTxn(userId, spec, now)` → TB**(可測 `.build()`);`evolve()` send+分類。
   - CORE leg:`SET stage=:new, updatedAt` 條件 `stage=:cur AND xp≥ AND survival_hours≥ AND charm≥ AND friendship≥ AND reputation≥ AND born_at≤:cutoff AND sick_type=:none`。
   - BUILD leg:`ADD talent_points_available :per, talent_point_grants {evo:<stage>}` 條件 `attribute_exists(userId) AND NOT contains(talent_point_grants, evo:<stage>)`。
   - `ClientRequestToken=evolve#<uid>#<newStage>`(冪等)。**恰一次升階**由 CORE `stage=:cur` 保證(升完 stage=new,再升的 `=cur` 必失敗)。
   - 分類:idx1(BUILD)失敗→`already_evolved`;idx0(CORE)失敗→`not_eligible`;其餘→`conflict`。
   - builder 補 `conditionLte`/`conditionNotContains`(共用 infra,鏡像 `conditionGte`)。
2. **engine `checkEvolution(userId)`**:讀 core → 逐門檻 met/unmet → 玻璃箱 DTO(`canEvolve`/`nextStage`/每閘 met bool + 分帶提示,**不給裸 charm/friendship/xp/門檻數值**,對齊 STAGE3 line 131);已達 stage6 頂 → `atMax`。
3. **engine `evolve(userId)`**:pre-check→不合格回 reasons→合格算 cutoffBornAt/thresholds→呼 DAO evolve→透傳分類。玻璃箱只揭「進化了!→stageN」事件。

## 5 · 開工前依賴(不擋結構)
- 🔵 section-growth:六階 6 門檻真值 + 分帶尺度。
- 🔵 (e-appearance)另片:各階插槽解鎖 → Bedrock 外觀圖生成 + 成本控管四件套。
- 🔵 農場(stage4 開)/二轉(stage6)= 其他片的 `stage>=N` 衍生閘,非本片寫入。
