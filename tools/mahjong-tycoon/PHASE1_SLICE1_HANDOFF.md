# 模擬麻將館 — Phase 1 第一縱切交接冊(地基 + 求生貸款時鐘 + 擴桌 sink)

> 對象:Codex 實作(甜甜 `sweetbot-next`)。設計:Claude(2026-07-16,Phase 0 真人實測通過後起 Phase 1)。
> 依附:`CODEX_SPEC_survival.md`(貸款主線完整規格)、`CODEX_SPEC_worldmap.md` §9/§10(terrain/snapshot)、`CODEX_SPEC_phase0.md`(現有 parlor/rates/settle)、既有 `model/miniGame/MahjongTycoon.js`。
> 幣別:牙齒🦷。**所有數值 = 後台 `balance` 可調 seed,以下為起始建議、非定案,上線後看真實數據校準。**
> 定位:把 Phase 0「掛機賺牙齒(無目標)」升級成「**借錢開館 → 每週還款求生 → 擴桌成長 vs 還款壓力取捨**」。三塊一起上,讓求生時鐘一上線就有牙齒。

---

## 0. 為什麼三塊綁一起(設計理由,先讀)

- Phase 0 收入天花板 = 2 桌 × 4 座 × 4 翻桌 = **32 客/hr × 20🦷 = 640🦷/hr**,幾乎每區都頂到上限,淨收極高。
- **貸款單獨上會沒有牙齒**:設計冊 seed 的每週還款(保守 528 / 標準 1267 / 積極 2640)不到 5 小時收入就賺回來 → 時鐘無壓力。
- **擴桌 sink 的牙齒 = 資本機會成本(非餓死)**:每🦷 花在買桌 = 少一🦷 還款;想擴張就得加貸 → 放大每週還款 → **過度槓桿誘惑**。這個「還款 vs 成長」取捨跟收入絕對值無關,一定成立 → 這才是求生時鐘真正的張力來源。
- 三塊合流後的核心迴圈:**借錢 → 開館 → 收入進金庫 → 每週被扣還款 → 用結餘擴桌(提升上限)或提前還款(降風險)→ 擴太兇→加貸→還款更重→衰一週就危險**。

---

## 1. 地基(**必做第一棒,擋在所有並發欄位前**)

### 1.1 🔴 `ParlorDAO` PutCommand → UpdateCommand(硬門檻)
- 現況 `save()` 整筆 PutCommand 覆寫 → 這一 slice 要在 parlor 上加 `loan / tables / districtSnapshot` 等欄位,**多互動並發會 stale item 互洗**。
- 改成**針對性 UpdateCommand**(SET 個別欄位 / ADD 原子增減),或加 `updatedAt`/revision 條件寫入。**貸款週扣、擴桌扣款、提款都要走原子更新**(對齊 fengshui §13C / staff §9.2 既有結論)。

### 1.2 config 灌 `terrain` + `mapPos`(6 區,純資料)
- 6 區各補 `mapPos`+`terrain`(值見 `CODEX_SPEC_worldmap.md` §3 正典表)→ 後台 SEED + `mahjong-tycoon-config`。
- 本 slice 用不到天候,但**趁地基一次埋好**;缺值有 fallback(terrain→med / mapPos→AUTO)。

### 1.3 開館存 `parlor.districtSnapshot`(孤兒防呆前置)
- 開館時把該區 `{terrain, rentLevel, clientMix, baseFlow}` 當下值快照進 parlor(worldmap §10.5)。讀取端 districtId 找不到時退快照、不崩。

---

## 2. 求生貸款時鐘(Phase 1 core,規格已在 `CODEX_SPEC_survival.md`)

**本 slice 只做 survival 規格標記的 Phase 1 core**:選額度 + 每週還款 + 提款防呆 + 基礎違約;Stage3 消防 / 增貸多館留後。

### 2.1 開館流程加「選貸款額度」
- Phase 0 開館 = 個人錢包扣開館費(seed 500)。Phase 1 在**確認開館前加一步選額度**(三檔按鈕),借款一次入**館內金庫**(非個人錢包),受提款防呆鎖住(§2.3)。
- parlor 新增 `loan` 物件(schema 見 survival §9.2:`principal / weeklyPayment / principalRemaining / term / weekIndex / nextDueTs / missedStreak / arrears / credit`)。

### 2.2 每週還款(惰性結算,真實 1:1 Asia/Taipei)
- 在既有 `settle()` 裡加:若經過了 ≥1 個還款週界(`nextDueTs`)→ 從金庫扣**等額本息 R**(公式 survival §2:`R = P·wr/(1−(1+wr)^−term)`)、`principalRemaining` 遞減、`weekIndex++`、推進 `nextDueTs`。
- **deterministic**(`hash(parlorId, weekIndex)`,同週序同結果,刷面板不重扣)。金庫不足 → `missedStreak++` + `arrears += 缺額` → 進 §2.4 催債。
- 還清(`principalRemaining ≤ 0`)→ 階段勝利(本 slice 先給「已還清·自由經營」狀態 + 之後可再貸擴張的鉤子)。

### 2.3 提款防呆(沿用並強化)
- Phase 0 提款 = 提走整個金庫。Phase 1 改 **`可提 = max(0, 金庫 − principalRemaining)`**(survival §7)→ 堵「借款立刻提走賴帳鑄幣」。

### 2.4 基礎違約(本 slice = 記帳 + 破產紅線;Stage1/2 實質後果 deferred)
- **本 slice 實作範圍(Codex 2026-07-17 查驗確認)**:`arrears / missedStreak / collectionStage(0/1/2) / credit` 欄位累計 + 破產紅線(`missedStreak ≥ defaultStreakToClose` 或 `arrears > bankruptcyArrears`)→ 破產(接 Phase 0 既有倒店 → 歸零館保留個人牙齒/stats)。補繳可解除。
- 🔴 **Stage1/2 的「實質後果」= 下一 slice**(欄位已齊、足夠接):Stage1 銀行專員(滯納金加成/利率跳升/信用降/寬限窗)、Stage2 暴力討債(器具損壞→維修 downtime/停業零收入/嚇跑客+負評)。目前是「有記帳、無後果」——`collectionStage` 只標級數,尚未施加懲罰效果。補做時建議先只補 Stage1(滯納率/寬限),Stage2 暴力討債綁事件系統留 Phase 3。
- **Stage3 消防綁事件系統,本 slice 不做。**

---

## 3. 擴桌 sink(**本 slice 新設計**,破 Phase 0 固定 2 桌)

### 3.1 機制
- `parlor.tables` 可買(現 Phase0=2),上限 `balance.tables.maxPhase1`(seed 6)。
- **買桌成本(金庫 sink,遞增)**:`cost(下一張) = baseCost × costMult^(tables−2)`。seed `baseCost 3000 / costMult 1.6`(第3桌3000/第4桌4800/第5桌7680/第6桌12288)。
- **每桌每小時維護費(金庫 ongoing sink)**:`upkeepPerHour = tables × upkeepPerTable`。seed `upkeepPerTable 40🦷/hr`。
- **產能已吃 tables**:`seatCapacity = tables×4×4`;`captured = min(baseFlow×0.6, seatCapacity)`。→ **擴桌只在高客流區有效**(alley baseFlow 50→captured 上限 30,買再多桌也吃不滿;night_market 72 才吃得動 4 桌)→ 選址 × 擴桌 emergent 策略。

### 3.2 併入既有 `rates()`(一行改動)
```
netPerHour = incomePerHour − rentPerHour − upkeepPerHour   // 新增 upkeep 項
```
- 儀表板「預估淨收/hr」自動反映;擴桌後 income 上升但 upkeep 也上升 → 邊際遞減,逼玩家算「這區還值不值得再加一桌」。

### 3.3 UI(不破壞既有 customId)
- 儀表板加「🀄 擴桌」按鈕:**新 key `mjt:buytable`**(**勿改既有 mjt: 前綴**,worldmap §7);顯示「下一張桌 花費 X / 產能 +16 客hr / 維護 +40hr」,金庫足夠才 enable。
- 買桌走原子 UpdateCommand(§1.1):條件「金庫 ≥ cost 且 tables < max」→ `ADD tables 1, 金庫 −cost`。

### 3.4 牙齒從哪來(設計自檢)
- **資本機會成本**:買桌的錢 = 不能拿去還款/提款 → 「擴張 vs 還債」取捨。
- **過度槓桿**:想擴張又沒現金 → 加貸(§2 再貸鉤子)→ 每週還款變重 → 衰一週(天候/運氣,未來 Phase)就危險。
- **維護費**:桌越多固定成本越高,淡季/低流量區反噬。

---

## 4. 🔴 經濟再校準(給 Codex + 使用者:數值全暫定)

- Phase 0 base 收入(~640🦷/hr 淨收極高)相對貸款**偏鬆**;本 slice 的擴桌 upkeep + 貸款週扣會**吃掉一部分淨收**,但**base 仍偏富**。
- **策略:先上線、後校準**。不在動工前把數值定死;先用本冊 seed 上線,觀察第一批玩家「每週還得出嗎 / 敢不敢擴桌 / 會不會過度槓桿」再調(全 `balance` 後台可即時改)。
- **貸款本金建議放大到與 Phase 0 收入同量級**(否則還款仍無感),起始建議見 §5;上線觀察後再收斂。
- 未來 Phase(員工薪資/進貨/設備維護)會再壓低淨收 → 那時貸款自然更咬 → **貸款數值屆時二次校準**(本冊已預告)。

---

## 5. 數值錨(起始 seed,使用者可調)

| 項目 | seed | 備註 |
|---|---|---|
| 貸款本金 保守/標準/積極 | **30,000 / 80,000 / 180,000** ✅定案 | 使用者 2026-07-17 拍板採用放大版;放大自設計冊原 5k/12k/25k,對齊 Phase 0 高收入;→每週還款約 3,168 / 8,447 / 19,005 |
| 週利率 / 期數 | 0.01 / 10 週 | 沿用 survival seed |
| 違約:紅線 / 破產欠款 / 滯納率 / 寬限 | 3 期 / 隨本金放大 / 5% / 2 週 | 破產欠款門檻隨本金放大(原 8000 太小) |
| 擴桌 baseCost / costMult / max | 3,000 / 1.6 / 6 桌 | 遞增,funds 大多來自貸款 |
| 每桌維護 upkeepPerTable | 40🦷/hr | ongoing sink |
| 提款防呆 | `max(0, 金庫 − principalRemaining)` | — |

> ✅ **本金三檔已定案(2026-07-17):30,000 / 80,000 / 180,000**。使用者採用放大版(原 5k/12k/25k 對 Phase 0 收入太小、時鐘無感)。其餘 seed(利率/期數/擴桌/違約門檻)仍為起始值,上線後看真實數據於 `balance` 後台校準。

---

## 6. 驗收點(給 Codex)

1. **ParlorDAO** 改 UpdateCommand/原子:貸款週扣、買桌扣款、提款並發不互洗(可驗:同時買桌+提款不會漂）。
2. **開館選額度**:三檔借款入金庫、parlor.loan 初始化、weekIndex/nextDueTs 正確;開館費仍扣個人錢包。
3. **每週還款**:settle 跨還款週界扣 R、principalRemaining 遞減、deterministic(狂刷不重扣);金庫不足→missedStreak/arrears。
4. **提款防呆**:`可提 = max(0, 金庫 − principalRemaining)`,借款無法立刻提走。
5. **基礎違約**:Stage1/2 生效、紅線→破產接既有倒店(保留個人牙齒/stats);補繳解除。
6. **擴桌**:`mjt:buytable` 遞增成本、上限 6、產能 seatCapacity 隨 tables 升、upkeep 進 netPerHour;低流量區擴桌不加 income(flow-bound)。
7. **既有不迴歸**:Phase 0 選點/開館/刷新/提款/舊 mjt: 按鈕全可用;`districtSnapshot` 開館時寫入。
8. **terrain/mapPos** 灌進 6 區 config、後台可編。

---

## 7. 分工 / 順序 / 成本

- **順序**:§1.1 ParlorDAO 原子化 **先做**(擋所有並發欄位)→ §2 貸款 + §3 擴桌 併行 → §1.2/1.3 資料層隨手。
- **分工**:Claude 設計(本冊)+ 驗收;Codex 實作 + 自驗;走「轉傳給 Codex」交棒(見 [[feedback_dev_workflow]])。單塊 <25 分、分階段回報。
- **治理**:sweetbot-next 直接 commit 落 main(別走 release train,見 [[project_sweetbot_release_train]]);測完 revert 臨時編輯避快照雷。

## 💰 成本控管(遵循 tools/COST_CONTROL.md)
- 成本來源:既有 `mahjong-tycoon-parlors`/`-config` 加欄位(loan/tables/snapshot/balance),流量無明顯變化;**無新表、無 LLM、無付費 API**。
- 所有表維持 `PAY_PER_REQUEST`;純遊戲數值 sink(非真金),故免帳本封頂。
