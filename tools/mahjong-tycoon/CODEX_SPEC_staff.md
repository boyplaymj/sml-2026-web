# 模擬麻將館 — 員工系統規格

> 對象:Codex 驗證/實作。設計:Claude(2026-07-14,使用者逐項點名)。
> 依附:`DESIGN.md`、`GAMEPLAY.md` 決策3(員工)、`CONTENT.md` §E/§E2、`CODEX_SPEC_clientflow.md`(時段/客群/troubleRisk)、`CODEX_SPEC_fengshui.md` §16(運氣/衰神/貼咖帶賽)、`CODEX_SPEC_floorplan.md`。
> 幣別:牙齒🦷。所有數值 = 後台可調 seed,非硬編碼。
> 定位:**麻將館無荷官**(客人自己打)。員工不硬綁職務,而是**「工作內容任務清單 × 每人每項能力值」技能矩陣**;產能受限於**注意力/工時稀缺**(尖峰同時多事會做不好=人力不足)。

---

## 0. 一句話

把館務拆成一組**任務**;每個員工對每個任務有不同**能力值(0–100,隱藏,面試只給模糊區間)**;排班時人力有限,**同一時段多件事一起來會分身乏術(並發懲罰)** → 尖峰配置與招募互補隊 = 核心經營樂趣。後期用**自動化設備**砍人力,但要付**添購貴+水電+客訴變糟**三重代價。

---

## 1. 工作內容分類(任務清單 `taskId`)

員工**不綁職務**,能力值掛在任務上。任務分四組:

### 前場(客人看得到)
| taskId | 名稱 | demand 來源 / 作用 |
|---|---|---|
| `clean` | 🧹打掃清潔 | 累積髒污(衛生迴圈,髒→聲譽→客流,大戶最敏感) |
| `reception` | 🛎️櫃台接洽 | 帶位/結帳/會員/**客訴化解** → 心情/回頭 |
| `matchmaking` | 🀄找咖湊桌 | 缺咖桌數(招牌,接兩雀APP);填空位=賺檯費 |
| `serving` | 🍽️送餐上桌 | 點餐客數(接 §P 店內銷售);慢→心情↓少賣 |
| `opentable` | 🎴開檯翻桌 | 翻桌次數;開新桌/收桌整理 |
| `sitin` | 🪑貼咖下場 | 找不到第4咖時員工下場湊(特殊,§6) |

### 後場(客人看不到)
| taskId | 名稱 | 作用 |
|---|---|---|
| `cooking` | 🍜料理出餐 | 廚房(接 §P 食物,品質/速度→客單價) |
| `repair` | 🔧維修機台 | 電動桌/洗牌機/冷氣/設備(降 downtime) |
| `errand` | 🛵代買跑腿 | 叫貨/補貨/採買(接進貨,議價省成本) |

### 安全
| taskId | 名稱 | 作用 |
|---|---|---|
| `security` | 🛡️鎮場保全 | 處理鬧事/衝突(**壓衰神帶進來的滋事**,接 §16.5) |
| `watch` | 👁️顧場防弊 | 防逃單/防詐賭/監看(接翹課學生 payRisk、游擊中年人) |

### 管理(店長類,設資格門檻 `requiresLevel`)
| taskId | 名稱 | 作用 |
|---|---|---|
| `scheduling` | 📋排班調度 | 委派排班 |
| `procurement` | 💰叫貨議價 | 成本談判(降進貨成本) |
| `branchmgmt` | 🏢代管分店 | 委派引擎(連鎖 M2) |
| `training` | 🎓帶新人 | 提升同班員工能力/揭露速度 |

> **MVP 子集**=前場6項 + 後場3項 + `security`(運氣系統要它);`watch`/管理類第二階。

---

## 2. 能力矩陣(0–100,隱藏真值 + 面試模糊區間)

```jsonc
employee.skills = { clean:70, reception:40, matchmaking:85, serving:55,
                    opentable:60, sitin:60, cooking:15, repair:20,
                    errand:55, security:30, watch:35 }   // 各任務真值 0–100
```
- **專精 vs 全才**分布 → 招募策略(找咖神85但廚藝15;或均衡無亮點)。
- **面試只給模糊區間**(如「找咖:高」),真值錄用後**逐次揭露**(沿用 tells,§7);`training` 加速揭露。
- 管理類任務需 `requiresLevel`(老闆等級/資歷)才可指派。

---

## 3. 注意力 / 工時模型(核心:能力≠產能)

**能力=做多好;注意力=一次只有一雙手。** 尖峰多件事同時來 → 分身乏術 = 人力不足。

### 3.1 時段切分
結算窗切成 `balance.timeBands`(接 clientflow 尖峰/客群活躍時段)。每個時段 b 獨立算供需。

### 3.2 需求 demand
每時段每任務產生需求量(工時單位),driver 來自既有系統:
```
demand[b][matchmaking] ∝ 缺咖桌數
demand[b][serving]     ∝ 點餐客數(§P)
demand[b][clean]       ∝ 累積髒污
demand[b][opentable]   ∝ 翻桌次數
demand[b][repair]      ∝ 機台故障(損耗/事件)
demand[b][security]    ∝ 滋事發生(§16.5 衰神/客群 troubleRisk)
...
```

### 3.3 派工(A+B 混合)
- **A(玩家)**:排班時給每個在場員工設**主責任務集** `assignedTasks[e]`(範圍)。
- **B(系統)**:範圍內系統自動把該員注意力**丟去當下 demand 最高的未滿足任務**(自動救火)。

### 3.4 並發懲罰(使用者要的核心)
每個員工每時段注意力預算 = 1.0。同時被 N 件 active 需求拉扯 → 注意力分攤 + 手忙腳亂:
```
concurrencyPenalty(N):  1件=1.0 / 2件=0.85 / 3件=0.65 / 4件+=0.4   (seed, balance.staff.concurrency)
有效產出_e_t = skills[e][t] × attentionShare_e_t × concurrencyPenalty(N_e)
```
→ **就算能力都80,尖峰三件同時來,每件都打折做爛**。解法=多請人、每人專注少數任務(薪資 vs 服務品質取捨)。

### 3.5 容量與服務水準
```
capacity[b][t] = Σ_e 有效產出_e_t
serviceLevel[b][t] = clamp( capacity[b][t] / effectiveDemand[b][t] , 0, 1 )
```
`effectiveDemand` = demand 扣自動化(§9)。各任務結算結果按 serviceLevel 縮放。

### 3.6 營業硬條件
某時段關鍵任務(如 `security`/`reception`/`matchmaking`)serviceLevel=0(沒人排/排到能力0) → 該時段**無法正常營業**(零/極低收入但店租照付);空班/遲到同理 → 排班=命門(沿用既有設計)。

---

## 4. 服務不及後果(serviceLevel 低 → 接既有系統)
| 任務低 serviceLevel | 後果 |
|---|---|
| matchmaking | 找咖慢 → 客人等太久走人(流失檯費) |
| serving | 送餐慢 → 心情↓、少賣 §P 商品 |
| clean | 髒污堆積 → 聲譽/客流↓(大戶最敏感) |
| opentable | 翻桌慢 → 桌週轉↓、排隊流失 |
| repair | 機台 downtime → 容客量↓、體驗↓ |
| security | 鎮場不及 → **衰神帶的鬧事失控**(§16.5 懲罰放大) |
| watch | 逃單/詐賭抓不到 → 收入損失(接翹課學生 payRisk) |

---

## 5. 隱藏特質 / 士氣 / 性別安全軸

- **隱藏特質 traits**(面試 tells 帶雜訊,錄用後揭露):勤奮/愛遲到(空班風險)/手腳不乾淨(偷金庫)/人緣好(同事士氣+)/抗壓(尖峰並發懲罰減免)…作用為跨任務修正。
- **士氣 morale**:低→全能力打折、遲到/離職機率↑;薪資/排班公平/裝潢影響。
- **性別安全軸**(沿用):👩降鬧事機率但鎮場弱 / 👨鎮場強無預防 → 混編最佳。
- **薪資**:只算實際排到的班(沿用既有排班定案:早/午/晚/深夜四班,深夜津貼+風險)。

---

## 6. 🪑 貼咖下場(sitin,特殊任務)

- 找不到第4咖時員工下場湊,讓桌開得成賺檯費。
- **吃掉整份注意力**:員工貼咖一整局都不能做別的 → 「用一個人力換一桌檯費」的昂貴決策。
- `sitin` 能力影響陪打體驗:高→氣氛/回頭↑;太爛或太強→客人不爽(心情↓)。
- ⚠️ **非賭博定調**:員工貼咖=**陪玩湊桌服務,不涉賭金輸贏結算**(明文,強調服務非對賭)。
- 🔗 luck 鉤子(§8):未來員工也有隱藏 luckTrait,貼咖時併入 §16.3 桌級傳染(衰神員工帶賽全桌)。

---

## 7. 隱藏 luck(擴充鉤子,Phase 後段)

- 員工 `luckTrait`(隱藏,同客人 §16.6)。**先不實作**,資料模型預留欄位。
- 上線後:員工 `sitin` 下場 → 其 luckTrait 進 §16.3 桌氣場(衰神員工拖全桌、財神員工旺桌)→ 貼咖選誰下場多一層考量。

---

## 8. 自動化層(未來引進,砍人力但三重代價)

每台自動化設備 `catalogs.automation`:對某任務**降 demand 或給無人容量**,但付**添購貴 + 水電 + 客訴變糟 + 失去偵測**:

| 設備 | 省(降demand/給容量) | 犧牲 |
|---|---|---|
| 🎰自助開台機 | `opentable` demand↓(客人自己開) | 失去開檯順手監看滋事/招呼 → **衰神/翹課學生鬧事抓不到**、體驗↓ |
| 📹遠端監視廣播 | `watch` 注意力↓、給嚇阻容量 | 只嚇阻/記錄(降發生率/payRisk),**不能物理壓制**已發生鬧事 |
| 🖥️無人櫃台 | `reception` demand↓(自助結帳/入場) | 失去客訴化解/會員推銷/人情溫度 → 問題客心情↓、回頭↓ |

每台 schema:
```jsonc
{ "id":"self_table","name":"自助開台機","targetTask":"opentable",
  "demandReductionPct":0.6,        // 或 autoCapacity 給無人基礎容量
  "acquisitionCost":8000,          // 🔴添購貴(比請人前期重)
  "utilityUpkeep":40,              // 🔴水電:每tick持續營運成本(進金庫sink)
  "moodMod":-3,                    // 🔴客戶意見變糟(尤其大戶敏感)
  "detectionLoss":{"troubleDetect":-0.5,"payRiskDetect":-0.3},  // 失去真人偵測
  "unlockLevel":3 }                // 綁M1老闆等級,高階自動化才能兼顧偵測
```
- **三重代價** = 添購成本(cost)+ 水電(utilityUpkeep 每tick sink)+ 客訴(moodMod 進 §16.5/reviewChannels)+ 偵測損失。
- 平衡結果:**便宜地段/低價客划算(省薪資>三重代價);高端店寧留真人堆體驗吸大戶**;高階自動化(unlockLevel高)才兼顧偵測。
- 作用在同一注意力模型:`effectiveDemand[t] = demand[t] × (1 − Σ demandReductionPct)`(或 + autoCapacity)。
- ⚠️ 經濟平衡:自動化砍薪資 sink → 要重新校準牙齒通膨 sink(純遊戲數值,非真金成本;水電 upkeep 是新增的補償性 sink)。

---

## 9. 資料模型

### 9.1 config 新增
- `catalogs.staff`:可招募員工模板池(依地點品質丟面試者,沿用便利商店供給;每模板 skills 真值 + traits + 模糊區間定義 + 期望薪資)。
- `catalogs.automation`(§8)。
- `balance.staff`:concurrency 懲罰曲線、timeBands、各任務 demand driver 係數、tells 雜訊/揭露速度、士氣係數、性別安全係數、營業硬條件關鍵任務清單。

### 9.2 parlors 新增
```jsonc
{
  "staff": [
    { "empId":"e_...", "skills":{...真值...}, "revealed":{...已揭露估值...},
      "traits":["diligent"], "traitsRevealed":1, "morale":70, "gender":"F",
      "wage":300, "luckTrait":null }        // luckTrait 預留(§7)
  ],
  "schedule": { "morning":{ "e_...":["clean","reception"] }, "afternoon":{...}, "evening":{...}, "latenight":{...} },  // 班別→員工→assignedTasks(A)
  "automation": ["self_table"]              // 已購自動化設備
}
```
- ⚠️ 寫入走 `UpdateCommand`(§fengshui-13C 同款:PutCommand 整筆覆寫會洗掉並發更新)。
- 連鎖(M2):staff/schedule/automation 跟 `parlorId` 分拆。

---

## 10. UI(接既有面板)
- 面板分頁:**人事**(招募/面試看模糊能力+tells、解僱)、**排班**(四班×員工→拖任務範圍 assignedTasks)、**自動化**(採購/顯示三重代價)。
- customId 前綴 `mjt:staff:`;綁 ownerId;重讀 DDB 不信畫面。
- 尖峰供需可視化:顯示各時段各任務 serviceLevel(紅=人力不足),幫玩家診斷該加人/加自動化。

---

## 11. Phase 歸屬
- **Phase 1**:任務分類 + 能力矩陣 + 面試招募(tells)+ 排班(A+B 派工)+ **注意力/並發模型** + 服務不及後果 + 貼咖 + 營業硬條件。(員工是經營深度核心)
- **Phase 3**:`watch` 防弊深化、管理類(排班委派/議價/帶新人)、員工隱藏 luck(§7,隨 §16 運氣系統)。
- **Phase 5+**:自動化層(§8,進階省力,綁 M1 解鎖)、代管分店(M2)。

---

## 12. 驗收點(給 Codex)
1. config `catalogs.staff`/`balance.staff` 可存/發佈/型錄編輯;能力矩陣 11 任務齊。
2. 面試只給模糊區間、錄用後真值逐次揭露(帶雜訊)、`training` 加速揭露。
3. 每時段每任務 demand 由既有 driver 派生;serviceLevel = capacity/effectiveDemand。
4. **並發懲罰**:同一員工排多任務,尖峰多 demand 同時→有效產出按 concurrencyPenalty(N) 下降(可驗:同員工同能力,單任務 vs 三任務同時,產出明顯低)。
5. A+B 派工:玩家設 assignedTasks 範圍,系統範圍內自動救火最高 demand。
6. 營業硬條件:關鍵任務 serviceLevel=0 → 該時段無法營業(零收入店租照付)。
7. 服務不及後果各任務正確(找咖慢流失/髒污聲譽/鎮場不及鬧事失控…)。
8. 貼咖吃整份注意力、不涉賭金結算、sitin 能力影響體驗。
9. 士氣/隱藏特質/性別安全軸修正生效;薪資只算排到的班。
10. 自動化:降 targetTask demand + 三重代價(添購 cost/水電 utilityUpkeep 每tick sink/moodMod 客訴/detectionLoss);unlockLevel 綁老闆等級;砍薪資後通膨 sink 重校準。
11. 寫入走 UpdateCommand;parlors staff/schedule/automation 並發安全、預留 parlorId 分拆與 luckTrait 欄位。
