# 模擬麻將館 — 貸款求生時鐘規格(主線骨幹)

> 對象:Codex 驗證/實作。設計:Claude(2026-07-14,使用者拍板)。
> 依附:`DESIGN.md`(貨幣兩口袋/倒店)、`CONTENT.md` §K/§L、`CODEX_SPEC_staff.md`(注意力被催債佔用)、`CODEX_SPEC_fengshui.md` §16(運氣→收入波動)、事件系統 §I(消防檢舉)。
> 幣別:牙齒🦷。**所有數值 = 後台 `balance.loan` 可調 seed,以下數字皆待 Phase 1 校準,非定案。**
> 定位:**這是整局的心跳**。跟銀行貸款到天王里開館 → **定期還款=求生時鐘** → 還不出=階段化催債→違約破產(roguelike 重來);還清=階段勝利轉擴張。

---

## 0. 一句話

開局玩家選貸款額度(起步規模 vs 還款壓力);**每週(真實 1:1)從館內金庫扣等額本息**;繳不出走**三階段催債**(專員→暴力→消防檢舉,全用既有系統施壓)→紅線違約破產。守信→信用升→利率降可增貸開分店。

---

## 1. 開局貸款(玩家選額度=第一個抉擇)

借多少 = 起步規模 vs 還款壓力,綁選點開館:
| 檔 | 借額(seed) | 起步 | 壓力 |
|---|---|---|---|
| 🐢保守 | 5,000 | 巷弄小店 | 輕,成長慢 |
| 🚶標準 | 12,000 | 一般店面 | 平衡 |
| 🚀積極 | 25,000 | 好地段大店 | 重,衰一晚就危險 |

- 額度上限受**信用評級**(§5)+老闆等級 gate;首貸給固定三檔。
- 借款一次入**館內金庫**(非個人錢包);受提款防呆(§7)鎖住不能立刻提走。

---

## 2. 還款節奏(真實時間 1:1)

- **每週還款**:週期 = 7 真實天(Asia/Taipei,固定週幾扣款,如每週一 12:00)。
- **期數 term**:seed 10 週,**創業 run 落在賽季內**(配合 SML 直播賽季,§8 賽季結算)。
- **攤還=等額本息**(定案):每週固定金額,時鐘節奏穩定直覺。
  ```
  週還款額 R = P · wr / (1 − (1+wr)^(−term))     # P=本金, wr=週利率(seed 0.01), term=期數
  ```
  每期還款拆本金+利息,`未償本金 principalRemaining` 遞減。
- **甜甜還款日前一天提醒**(engagement 鉤子;接 bot 通知)。

---

## 3. 求生時鐘機制

每週還款日,系統**惰性結算時**自動從**館內金庫 vault** 扣 R:
- `vault ≥ R` → 正常:vault−R,principalRemaining 依攤還表遞減,信用+(§5),清空該期欠款。
- `vault < R` → 該期**欠繳** `arrears += (R − 可扣部分)`,進**催債梯度**(§4),`missedStreak++`。
- 全 deterministic(hash(parlorId, 還款週序);同輸入同結果,不因刷面板重抽)。

---

## 4. 違約催債梯度(階段化,用既有系統施壓 — 使用者點名)

**不是一擊死**:給搶救空間但層層加壓(正好接運氣波動:這週衰神砸場沒錢、下週拚回來)。階段由 `missedStreak`/`arrears` deterministic 推進:

### Stage 1 — 🤵 銀行專員拜訪(首次欠繳)
- 滯納金(arrears × 滯納率)+ **利率跳升** + 信用降 + 給 **1~2 週寬限**補繳。
- 🔗 **佔用店員注意力**:專員上門期間要派店員應付 → 那段時段被佔的員工**本職 serviceLevel 下降**(接 `CODEX_SPEC_staff.md` §3 注意力模型:等同多一件 active demand 搶注意力)。

### Stage 2 — 💢 暴力討債(連續欠繳)
討債集團上門,三選一或組合(seed):
- **器具損壞**:隨機設備損壞 → `repair` demand 暴增 + downtime(容客量↓)。
- **無法開業**:當日/當時段強制停業 = **零收入但店租照付**。
- **客人被嚇跑**:客流流失 + 聲譽/心情暴跌 + 負評灌 reviewChannels。
- 🔗 保全(`security`)**略減嚇跑幅度但擋不住器具損壞/停業**(討債針對債務非客人鬧事)。

### Stage 3 — 🚒 被檢舉消防違規(欠繳惡化)
- 被(銀行施壓/對手/討債方)檢舉 → **消防臨檢**:罰款 / 勒令停業整改 / 需花錢改善消防設備才能復業。
- 接**既有消防檢舉事件**(§I;原定價系統低價客也會招消防檢舉,此處共用機制)。可直接觸發停業危機。

### 紅線 → 違約破產
- `missedStreak ≥ 違約紅線`(seed 3 期)**或** `arrears > 破產門檻` → **本局結束**(§8 破產重來)。

> 各階段可補繳解除:補齊 arrears + 滯納金 → missedStreak 歸零、退回正常。

---

## 5. 信用評級(守信正回饋)

- `credit`:0–100 或等級制。準時還→升;欠繳/違約→降。
- 高信用 → **利率降 + 可貸額度升**(增貸門檻);低信用 → 利率升 + 額度縮。
- 破產重來後信用處理:每賽季重置 or 帶前次違約污點(§8,待定,seed 先每季重置)。

---

## 6. 加碼貸款 / 擴張

- 信用達標 + 老闆等級到 → 可**增貸**(開分店/擴店)。
- 增貸抬高 `principalRemaining` 與週還款額 R → 壓力上升,換更多館收入 → **滾動擴張 vs 過度槓桿**取捨。
- 多館(M2)時各 parlorId 的 loan 分拆記帳;總部面板總覽總負債。

---

## 7. 提款防呆(已定,公式)

個人錢包 vs 館內金庫兩口袋;提款(金庫→個人錢包=全站通膨水龍頭)時:
```
可提金額 = max( 0, vault − principalRemaining )
```
- **貸款未清只能提「超過未償本金的淨利」** → 堵「借一大筆立刻提走賴帳鑄幣」。
- 提款走 DDB 條件扣金庫 + 讀回驗 point/log(沿用 Phase 0 金流防線)。

---

## 8. 勝負條件 / 破產重來(roguelike)

- **還清全部貸款(principalRemaining=0)→ 階段勝利**:脫離求生期,轉擴張/自由經營,解鎖成就徽章。
- **違約破產 → 本局結束**:
  - 歸零:所有館 / 金庫 / 經營資產 / 分店 / 老闆等級。
  - **保留**:個人牙齒錢包 + 成就徽章 + 稱號 + 傳承點種子(接 M5 傳承)。
  - **可再貸重來**(roguelike):重新選額度開局。
- **賽季結束**:依整季表現結算傳承點(接 `CONTENT.md` M5)。

---

## 9. 資料模型

### 9.1 config `balance.loan`(全 seed)
```jsonc
{
  "tiers": { "conservative": 5000, "standard": 12000, "aggressive": 25000 },
  "weeklyRate": 0.01, "term": 10,
  "lateFeeRate": 0.05, "rateBumpOnMiss": 0.005, "graceWeeks": 2,
  "defaultStreak": 3, "bankruptcyArrears": 8000,
  "credit": { "onPayDelta": +3, "onMissDelta": -15, "rateByCredit": [...], "limitByCredit": [...] },
  "collection": {
    "stage1": { "officerAttentionCost": 0.5 },
    "stage2": { "equipDamage": 1, "forceCloseBands": 2, "scareFlowMult": 0.5, "securityMitigate": 0.3 },
    "stage3": { "fireInspectFine": 2000, "closeUntilFixed": true }
  }
}
```

### 9.2 parlors 新增
```jsonc
{
  "loan": {
    "principal": 12000, "principalRemaining": 10800, "weeklyRate": 0.011,
    "term": 10, "weekIndex": 2, "nextDueTs": 0,
    "arrears": 0, "missedStreak": 0, "collectionStage": 0,
    "credit": 55, "graceUntilWeek": null
  }
}
```
- ⚠️ 寫入走 `UpdateCommand`(同 fengshui §13-C 覆寫雷);多館分拆 parlorId。

---

## 10. UI(接既有面板)

- 儀表板顯示:**未償本金 / 下次還款倒數 / 週還款額 / 信用評級 / 催債階段警示燈**。
- 開局:選貸款額度(三檔,附起步規模 vs 壓力說明)。
- 提款:即時算「可提金額 = 金庫−未償本金」,不足顯示鎖定原因。
- 增貸:信用/等級達標才亮;顯示增貸後新週還款額。
- customId 前綴 `mjt:loan:`;綁 ownerId;重讀 DDB 不信畫面。

---

## 11. Phase 歸屬

- Phase 0 已有「最小倒店」。本規格把它**深化成完整求生迴圈** → **Phase 1**(貸款+每週還款時鐘+提款防呆+基礎違約)。
- **催債梯度 Stage 1~3** 隨對應系統成熟:Stage1(注意力)綁 staff Phase 1;Stage2(器具/客流)Phase 1~2;Stage3(消防檢舉)綁事件系統 Phase 3。
- 增貸/多館 loan 分拆 → Phase 5(連鎖 M2);破產傳承種子 → Phase 5(M5)。

---

## 12. 驗收點(給 Codex)

1. `balance.loan` 可存/發佈/型錄編輯;開局三檔額度入金庫、受提款防呆鎖。
2. 每週(真實 1:1,Asia/Taipei)還款日惰性結算扣 R,等額本息攤還表正確、principalRemaining 遞減。
3. 還款 deterministic(同週序同結果,刷面板不重抽/不重扣)。
4. vault<R → 欠繳、arrears/missedStreak 累加、進催債 Stage1。
5. **Stage1 專員佔店員注意力**:對應時段被佔員工本職 serviceLevel 下降(接 staff §3)。
6. **Stage2 暴力討債**:器具損壞觸發 repair demand/downtime、強制停業零收入店租照付、嚇跑客流+負評;保全略減嚇跑不擋損壞。
7. **Stage3 消防檢舉**:罰款/停業整改,接既有消防檢舉事件。
8. 補繳解除:補齊 arrears+滯納金 → missedStreak 歸零退回正常;寬限期正確。
9. 紅線(defaultStreak/bankruptcyArrears)→ 違約破產:歸零館/等級、保留個人牙齒+成就+傳承種子、可再貸重來。
10. 信用評級升降 → 利率/額度連動;增貸抬高 principalRemaining/R、多館 loan 分拆 parlorId。
11. 提款防呆:可提 = max(0, vault−principalRemaining),DDB 條件扣+讀回驗防鑄幣。
12. 還清 principalRemaining=0 → 階段勝利+成就;賽季結束結算傳承點。
