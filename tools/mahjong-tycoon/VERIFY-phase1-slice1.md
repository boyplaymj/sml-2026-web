# 🔍 Codex 查驗請求 — 模擬麻將館 Phase 1 Slice1(已提交,請「查驗」非「實作」)

> 提出:Claude(2026-07-17)。對象:Codex。
> **重點:此 slice 已由 Codex 先前提交、程式+config+數值皆到位。本請求是獨立複驗+裁決一處 doc-vs-impl 落差,不是重做。**

## 0. 範圍與已提交狀態

- 主檔 `sweetbot-next/model/miniGame/MahjongTycoon.js`、`sweetbot-next/DAO/DDB/MahjongTycoonParlorDAO.js`。
- 相關 commit(HEAD `d7b84ca`):
  - `b1203ba` feat(mahjong): add phase1 loan table slice follow-up(貸款分檔+擴桌)
  - `b743473` fix(mahjong): make settlement treasury updates atomic
  - `e944084` fix(mahjong): advance settlement lock for loan-only ticks
- 設計依據:`PHASE1_SLICE1_HANDOFF.md`(本金三檔已定案 30k/80k/180k)、`CODEX_SPEC_survival.md`(貸款主線)。
- 線上 DDB `mahjong-tycoon-config`(ap-southeast-1)已 published:6 區皆有 `mapPos`+`terrain`;`balance.loan.tiers`=30k/80k/180k、`balance.tables`(baseCost3000/costMult1.6/max6/upkeep40)、`bankruptcy`、`openCostTeeth500`。

## 1. Claude 已驗(請勿重做,除非你不同意)

- `node --check` 兩檔 OK。
- 週還款(等額本息 P·r/(1−(1+r)^−t),r=0.01/t=10):保守 **3168** / 標準 **8447** / 積極 **19005** ✅ 對齊 handoff。
- 買桌成本 `3000·1.6^(tables−2)`:第 3~6 桌 = **3000/4800/7680/12288** ✅。
- 提款防呆 `withdrawable = max(0, 金庫 − principalRemaining)`:剛開館(金庫=本金)可提 0、獲利後才放行 ✅。
- DAO 原子性:`applySettlement` treasury 走 delta 累加(`if_not_exists(#treasury,:zero)+:treasuryDelta`)+ 樂觀鎖 `#lastSettledAt=:expectedLastSettledAt`;`withdraw`/`buyTable` 各自條件寫入;`loan` 絕對覆寫但與 treasury/tables 不交疊 → 併發不互洗 ✅(此為前次 vet 結論,本人複讀認同)。

## 2. 🔴 請 Codex 裁決:唯一 doc-vs-impl 落差(違約後果)

`applyLoanDue`(MahjongTycoon.js:295-344)目前行為:
- 金庫足 → 扣等額本息、principalRemaining 遞減、missedStreak 歸零;
- 金庫不足 → 累加 `arrears`、`missedStreak++`、更新 `collectionStage`(0/1/2);
- 紅線(`missedStreak ≥ defaultStreakToClose` 或 `arrears > bankruptcyArrears`)→ `bankrupt` → settle 倒店。

**落差**:handoff §2.4 / survival 規格的 Stage1(滯納金加成、利率跳升、信用降、寬限窗)與 Stage2(暴力討債:器具損壞→維修/downtime、停業零收入、嚇跑客+負評)**實質後果尚未施加** → 現況是「有記帳(collectionStage/arrears/credit 欄位)無後果」。

**請裁決**:(a)這是有意的 MVP 分層(違約細節留下一 slice),還是漏做?
- 若(a):請確認欄位齊備足以之後接後果,並建議在 handoff/CONTENT 標註「Stage1/2 後果=下一 slice」以免文件誤導。
- 若(b):請開 finding 指出最小補做範圍(建議只補 Stage1 的滯納率/寬限,Stage2 暴力討債綁事件系統仍留 Phase3)。

## 3. 請 Codex 複核的邊界/迴歸點

1. **貸款利息/本金收斂**:末期 `due=min(weeklyPayment, principalRemaining+ceil(利息))` 是否讓 `principalRemaining` 精確歸零?有無殘 1🦷 尾數?
2. **maxLoops=52 與離線上限不對稱**:收入受 `OFFLINE_CAP_HOURS=12` 上限,但貸款迴圈可跑到 52 週(以 `nextDueTs` vs `now`)。長期棄館 → 收入被夾、貸款照扣 52 週 → 破產。確認此不對稱是有意(棄館=輸)且 52 週上限不會漏扣/超扣。
3. **deterministic**:狂刷面板(同 `weekIndex`)不重扣——目前靠 `nextDueTs` 前進而非 hash;確認多次 settle 落在同一週界不會重複扣款(樂觀鎖 `e944084` 應已擋,請確認 loan-only tick 也推進鎖)。
4. **併發**:同時 `buyTable`+`withdraw`+settle 不互洗(treasury 不漂、tables 不跳)。
5. **提款防呆 DAO 層**:`withdraw` 條件僅 `#treasury >= :amount`,防呆的「保留未償本金」在 handler 算 amount;確認無法藉併發把本金保留額提走。
6. **迴歸**:Phase0 選點/開館/刷新/提款/看地圖/reopen + 舊 `mjt:` 按鈕全可用;新 `mjt:chooseLoan`/`mjt:buytable` customId 無衝突;開館寫入 `districtSnapshot`;孤兒區(districtId 不在 config)退 snapshot 不崩。

## 4. 驗收對照(handoff §6)

§6 的 8 點驗收請逐條確認現況是否已滿足(1 原子/2 選額度/3 週還/4 提款防呆/5 基礎違約/6 擴桌 flow-bound/7 不迴歸/8 terrain·mapPos)。第 5 點即 §2 的裁決點。

## 5. 交付方式

Codex 完成後,請把 findings(採納/不採納+理由)回貼此頻道;Claude 收斂後決定違約後果補不補,再與其他 4 條線協調一次 restart 部署(見 [[project_sweetbot_release_train]] 治理:直接 commit 落 main,勿走 release train)。**部署時機由 gameboy 定,本 slice 已安全躺 main 不流失。**
