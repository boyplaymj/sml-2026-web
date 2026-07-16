# 模擬麻將館 — 氣候系統規格(真實層 + 模擬層雙層天候)

> 對象:Codex 驗證/實作。設計:Claude(2026-07-16,使用者逐項點名/定調)。
> 依附:`DESIGN.md` §2.1.1(天王里正典地圖/terrain)、§17(氣候系統設計)、`CODEX_SPEC_clientflow.md`(客流/客群/timeBand/§5 主流程)、`CODEX_SPEC_staff.md` §13(員工防災準備 mitigations)、`CODEX_SPEC_backend.md`(config 4 section)、`CODEX_SPEC_phase0.md`(parlors 表/worldTick/deterministic hash 慣例)、`CODEX_SPEC_survival.md`(惰性結算/週時鐘)。
> 幣別:牙齒🦷。所有數值 = 後台 `balance.weather` 可調 seed,非硬編碼。時區 = **Asia/Taipei 真實 1:1**(同 survival 週時鐘)。
> 定位:天氣同時「**軟性調客流**(weatherMod 層)」+「**硬性擲極端事件**(淹水/招牌/停電/漏水)」;招牌機制 = **行政放假 vs 實際天象的落差**(颱風假樂透)。**極端(颱風/全台大雨)= 真實層 CWA 全服一致;日常(晴~大雨)= 模擬層各區隨機。**

---

## 0. 一句話

天氣 = **真實層(宏觀/稀有/全服共享,只認 CWA 全國警報)** ⊕ **模擬層(微觀/每日/各區獨立,純確定性函式)**。模擬層是 `weatherAt(districtId, epoch)` 的**純函式**(零儲存、各區獨立、全服天生一致、防狂點重抽);真實層是一個 Lambda 抓 CWA 寫**單一全域狀態列**(要快取 + fallback)。有效天氣經各區 `terrain` 放大成後果:軟性調客流、硬性擲 2-3 天期的天候事件(可被防災設備 + 員工防災班 §13 降損)。

---

## 1. 雙層架構總覽(**已定案 2026-07-16**)

| 層 | 顆粒度 | 觸發源 | 儲存 | 天氣上限 | 目的 |
|---|---|---|---|---|---|
| **真實層** | 全服共享(整個天王里=整個台灣) | **CWA 開放資料的全國級警報**(颱風警報/大範圍豪雨特報) | **需儲存**(全域單列,Lambda 寫) | 颱風/超大豪雨 | 颱風假樂透/災難大事件,與現實+直播社群同步(情緒鉤子最強) |
| **模擬層** | 各區獨立 | **deterministic seed**(worldTick × districtId) | **零儲存**(純函式即時算) | **只到大雨/梅雨(不含颱風)** | 日常客流變化、選址 floodRisk 差異、付費**氣象預報**技巧軸 |

- **為何模擬層不含颱風**:颱風保留真實層,**避免各區自己擲出颱風 → 穿幫「A 區隨機颱風、B 區晴天」**(全台一致的極端只從現實來)。
- **為何真實層只取全國警報**:①颱風一年才幾次,只靠真實會 95% 時間睡著 ②選址 floodRisk 差異若全台一套真實天氣就沒意義 ③氣象預報付費/技巧軸若接真實天氣就廢掉(玩家直接 Google CWA)。**單一縣市的局部警報不取**(留給模擬層各區隨機表現) → **無需錨點縣市、無 `world.realAnchor`**。
- **兩條獨立軸**(設計關鍵):
  - `stormSeverity` — 實際風雨強度 **0–10**(晴→颱風)。真實層由 CWA 警報級別映射;模擬層由 seed 生(上限見 §2)。
  - `holidayDeclared` — 行政放假(停班停課),與 severity **高度相關但不完全一致 → 落差 = 玩點**(§6)。

---

## 2. 模擬層 = 純確定性函式(零儲存,各區獨立)

**核心:模擬層不寫任何 DB。** 任何時刻任何客戶端呼叫同一函式得同一結果 → 全服天生一致 + 防狂點重抽 + 可單元測試。

### 2.1 天氣紀元 epoch(天氣不逐 tick 亂跳)
```
weatherPeriodHours = balance.weather.periodHours     # seed,如 12 或 24(半天/整天一種天氣)
epoch(t) = floor( minutesSinceAnchor(t, Asia/Taipei) / (weatherPeriodHours*60) )
```
- 天氣在一個 epoch 內固定(不每 tick 洗),epoch 換才可能變天。anchor = 固定 UTC 錨點(如賽季起點),**不可用 `Date.now()` 之外的隨機源**。

### 2.2 `weatherAt(districtId, epoch)` → `{ type, stormSeverity, holidayDeclared:false }`
```
seed = hash(districtId, epoch)                        # 同 survival deterministic 慣例(FNV/依既有 util)
month = monthOf(epoch, Asia/Taipei)
probTable = balance.weather.seasonal[month]           # §9 該月各天氣型別機率(不含颱風)
type = weightedPick(seed, probTable, terrainNudge(districtId))   # terrain 微調(低窪↑雨感、熱島↑酷暑)
stormSeverity = severityOf(type, seed)                # 模擬層 clamp 上限 balance.weather.simSeverityCap(如 6)
holidayDeclared = false                               # 模擬層永不放假(放假只從真實層來)
```
- **天氣型別 canonical**:`clear / cloudy / lightRain / heavyRain / plumRain / coldWave / heatWave`(晴/多雲/小雨/大雨/梅雨/寒流/酷暑)。**`typhoon` 不在模擬層**(只真實層 §3 產生)。
- `terrainNudge`:讀 `districts[].location.terrain`(§10.2),`floodRisk` 高 → 提高 heavyRain/plumRain 權重;`heatIsland` 高 → 提高 heatWave 權重;`windExposure` 影響招牌事件(§5)非天氣型別本身。純調權重、不改上限。
- **相鄰 epoch 平滑(可選 seed)**:`balance.weather.persistence` 讓前一 epoch 天氣有黏性(避免晴↔大雨硬跳),仍 deterministic(hash 帶前一 epoch)。

---

## 3. 真實層 = CWA 全國警報(唯一需儲存/需 Lambda)

### 3.1 抓取排程 Lambda `sml-mahjong-weather`(新,小)
- **每 30–60 分**觸發(EventBridge schedule)。抓 **CWA 開放資料平台**:颱風警報(海上/陸上)、豪雨/大豪雨/超大豪雨特報(判是否**涵蓋多縣市=全國級**)、低溫/高溫特報(全國級才取)。
- CWA opendata **免費**(政府開放資料,註冊拿授權碼 `CWA-...`;金鑰存 SSM `/sml/mahjong/cwa-key`,非硬編碼)。
- 映射成一筆全域狀態寫 DDB(§10.4):
```jsonc
world.realWeather = {
  active: true,
  type: "typhoon",                 // typhoon | superHeavyRain | coldSurge | heatAdvisory
  stormSeverity: 9,                // CWA 級別→0-10 映射(balance.weather.cwaSeverityMap)
  holidayDeclared: true,           // §3.2
  startedAt: "2026-08-26T00:00:00+08:00",
  expiresAt: "2026-08-28T00:00:00+08:00",   // 依警報解除/預估;供 fallback 判過期
  fetchedAt: "2026-08-26T09:30:00+08:00"
}
```
- **只認全國級**:陸上/海上颱風警報、或特報涵蓋 ≥ `balance.weather.nationwideCountyThreshold`(seed,如 5)個縣市才置 `active:true`。單縣市局部 → 不寫(留給模擬層)。

### 3.2 `holidayDeclared`(行政放假)
- MVP:由 `type=typhoon` 且 `stormSeverity ≥ balance.weather.holidaySeverityGate`(seed) **機率性**宣告(映射現實「颱風假常見但不必然」)→ deterministic by `hash(dateTaipei)` 不因刷面板變。
- 進階(可選 Phase 3+):接**行政院人事行政總處「停班停課」開放資料**直接讀真值,取代機率映射。留 `balance.weather.holidaySource = "map" | "gov"` 開關。

### 3.3 🔴 快取 + fallback(硬性要求)
- 遊戲端讀 `world.realWeather` **加 60–120s 記憶體快取**,別每次結算打 DDB。
- **fallback = 降級純模擬層**:`world.realWeather` 缺失 / `fetchedAt` 過期(> `balance.weather.realStaleMinutes`,如 180)/ Lambda 掛 / CWA 改格式 → **視為無真實警報,核心迴圈照跑模擬層**,絕不因外部依賴掛掉。(呼應 §17.1 工程要點)

---

## 4. 有效天氣(合併真實 ⊕ 模擬,再經 terrain)

```
effectiveWeather(districtId, t):
  sim  = weatherAt(districtId, epoch(t))
  real = world.realWeather (快取, active 且未過期 才算)
  if real.active:
     # 真實層全服套用:整個天王里一起,但後果看各區 terrain
     type          = real.type
     stormSeverity = max(real.stormSeverity, sim.stormSeverity)
     holidayDeclared = real.holidayDeclared
  else:
     type=sim.type; stormSeverity=sim.stormSeverity; holidayDeclared=false
  return { type, stormSeverity, holidayDeclared, terrain: district.terrain }
```
- **真實層與模擬層共用同一套 terrain 修正、同一條天候事件結算路徑(§5)、同一 weatherMod 客流路徑(§7),不重寫。**

---

## 5. 天候事件(硬性,持續 ~2-3 天,可被 mitigate)

**與 clientflow §6 的選項式隨機事件(`events` section, A/B 選項)不同**:天候事件是**持續型狀態**(進場後活 2-3 天),存在 parlor 上、可被玩家防災降損。

### 5.1 事件型別(接 DESIGN §17.4)
| eventType | 觸發條件(effectiveWeather × terrain) | 影響 | mitigations |
|---|---|---|---|
| `flood` 店面淹水 | heavyRain/plumRain/typhoon × `floodRisk` 高 + 一樓/低窪(floorplan) | 停業或降客 + 設備泡水損壞(電動桌/冰箱) | 抽水機/排水設備 + 防災班(清水溝/堆沙包) → 縮天數/減損 |
| `signfall` 招牌掉落 | 強風/typhoon × `windExposure` 高 | 看板損壞 → buzz/曝光↓ 至修復 + 維修費 +(娛樂化)砸路人賠償 | 防風鐵捲門/防水招牌 + 防災班(收招牌/固定) |
| `blackout` 停電 | typhoon/雷雨 | 電動桌/冷氣/監視器停擺 → 客人跑 | 發電機(停電影響歸零) |
| `leak` 天花板漏水 | 老舊店面/裝潢差 × 連日雨 | 環境/清潔↓,持續數天要修 | 裝潢等級/維修班 |

### 5.2 觸發(惰性結算,deterministic)
- 進入天候窗(effectiveWeather severity ≥ `balance.weather.event[type].severityGate`)時,結算對每個 eventType 擲一次:
```
baseProb = terrainFactor(district, type) × severityCurve(stormSeverity)     # balance.weather.event[type]
mitig    = Σ 已裝防災設備.reduction[type] + 有效防災班產出(§13, 事前權重>事中)
fired    = deterministicRoll( hash(userId, weatherWindowId, type) ) < clamp(baseProb − mitig, 0, 1)
```
- `weatherWindowId` = 該波天候的穩定 id(如 `epoch@type`),**同窗同 type 只擲一次 → 刷面板不重抽、不重複開事件**(同 survival deterministic 鐵律)。
- fired → push 進 `parlor.weather.activeEvents[]`(§10.3),`durationDays` = seed **2–3 天**(真實 1:1),`startedAt` 記當下。

### 5.3 生命週期(持續 2-3 天)
- 每次惰性結算:對 `activeEvents[]` 每筆,依 `startedAt + durationDays` 判是否到期 → 到期移除、期間持續套用影響(降客/降 buzz/停電…)。
- **事中派防災班/裝設備** → 更新該事件 `mitigations`,可**縮短剩餘天數 / 降損**(事中權重 < 事前,§13.2)。
- 面板呈現:專屬**狀態橫幅 + 可行動按鈕**(派清理/叫維修),非一擊即逝(§13 UI)。

---

## 6. 招牌機制:颱風假樂透(使用者點名核心)

四象限 = `holidayDeclared` × `stormSeverity`,套在 clientflow avail 上(§7 的特例):
| | 天象溫和(severity 低) | 天象猛烈(severity 高) |
|---|---|---|
| **有放假** | 🎰 **爆滿樂透** — 本地客群(elderly/mama/roamer/regular)avail ××↑(在家沒事+不能出遠門+店在巷口);tourist/student pattern 位移(停課) | 💀 **災難** — avail ≈ 0 + 高機率觸發 §5 事件(淹水/停電/招牌) + 維修 sink |
| **沒放假** | 平常日(模擬層日常) | 該放沒放 — 客人照上班但 mood↓(weatherMod 負)、少量硬出門 |
- 🎰 爆滿樂透張力:**天上掉的旺場,但要排得出人手才接得住** → 沒排班 = serviceLevel 崩(§staff §3.6)= 爆滿反成負評。→ 天氣把「排班命門」放大(接 §13.3)。
- 係數 `balance.weather.jackpot`:四象限各客群 avail 乘數 + 事件觸發加成。

---

## 7. weatherMod → 客流(軟性,接 clientflow §5)

在 clientflow §5 `avail[c,h]` 主流程**新增一層** `weatherMod`:
```
avail[c,h] ×= weatherMod( effectiveWeather(district, h).type , c )    # balance.weather.mod[type][client]
             ×  jackpotMod( holidayDeclared, stormSeverity, c )       # §6 四象限(放假時取代/疊加)
```
- **per 天氣型別 × per 客群** 一張表 `balance.weather.mod`(7+1 型別 × 10 客群)。設計要點:
  - **麻將=室內避雨/避暑娛樂** → lightRain/heatWave 對「宅在附近」的本地客群(casual/regular/elderly)反而**微升**(沒別的事+來吹冷氣);但 heatWave → 冷氣電費 sink↑(接 survival)。
  - heavyRain/flood → 步行/機車客群(scooterClients: student/casual)↓↓;開車客群(carClients: whale/mama/elderly)較不受影響。**淹水中的區 → location access 直接切斷**(接 clientflow §5.2)。
  - coldWave → elderly↓(怕冷)、餐飲(§P 火鍋/宵夜)↑。
- **與 location 交互**:低窪一樓 flood 事件 active 時,§5.2 `locationAccess` 對步行/機車直接歸低(交通被切),與 weatherMod 疊加。

---

## 8. 氣象預報 = 看新聞(取代付費顧問,**使用者定調:出現在新聞、要主動查看**)

- **不付牙齒、不是設備**。預報出現在遊戲內**📰新聞面板**,玩家要**主動翻**才看得到:
  - **模擬層預報**:因 `weatherAt` 是純函式,未來 epoch 的天氣其實可算 → 預報 = 前算 N 個 epoch,但**加不確定性呈現**:近 epoch 給明確、`balance.weather.forecastHorizonDays`(2–3)外只給**趨勢/機率**(UI 層加噪,非改底層結果)。
  - **真實層預報**:讀 `world.realWeather` 的颱風警報 + expiresAt(跟現實同步)。
- **技巧軸 = 勤查新聞 + 據此預先派防災/囤貨/排班**(§13.4)。因預報的是**模擬層** → 玩家 Google 不到,機制成立。
- staff 端(§13)只**消費**本面板拋出的「預警旗標」(未來 X 天有 severity ≥ gate 的天候)→ 拉起 `disasterprep` demand;預報本體由本系統提供。

---

## 9. 季節性(綁賽季/流年)

- `balance.weather.seasonal[month]`:各月天氣型別機率。梅雨(5–6 plumRain↑)、夏颱(7–9 真實層 typhoon 機率+模擬層 heavyRain↑)、寒流(12–2 coldWave↑)、酷暑(7–8 heatWave↑)。
- 與 fengshui 風水流年一起換季 → 選址要算「這區這季容易淹嗎」(接 §2.1.1 terrain × §9 季節)。

---

## 10. 資料模型

### 10.1 config `balance.weather`(新,全 seed,後台可調)
```jsonc
balance.weather = {
  periodHours: 24, simSeverityCap: 6, persistence: 0.4,
  seasonal: { "1": {clear:.5, cloudy:.2, lightRain:.1, coldWave:.2, ...}, ... "12": {...} },  // 12 月
  mod: { clear:{casual:1,...}, lightRain:{...}, heavyRain:{...}, plumRain:{...},
         coldWave:{...}, heatWave:{...}, cloudy:{...}, typhoon:{...} },   // 8 型別 × 10 客群
  jackpot: { holidayMildMult:{elderly:2.2, mama:1.8, roamer:1.6, ...}, holidaySevereMult:{...},
             noHolidaySevereMoodPenalty:-0.3 },
  event: { flood:{severityGate:6, baseProb:.5, terrainWeight:"floodRisk", durationDays:[2,3]},
           signfall:{severityGate:7, terrainWeight:"windExposure", durationDays:[2,3]},
           blackout:{severityGate:8, durationDays:[1,2]},
           leak:{severityGate:5, durationDays:[2,4]} },
  cwaSeverityMap: { typhoonLand:9, typhoonSea:6, superHeavyRain:8, heavyRain:6, heatAdvisory:5, lowTemp:5 },
  nationwideCountyThreshold: 5, holidaySeverityGate: 8, holidaySource: "map",
  realStaleMinutes: 180, forecastHorizonDays: 3,
  copy: {                                    // 🗞️ 天氣文案庫(CONTENT §R2 已灌初值,後台可編)
    broadcast: { clear:"…", cloudy:"…", lightRain:"…", heavyRain:"…", plumRain:"…", coldWave:"…", heatWave:"…", typhoon:"…" },
    forecast: { near:"…", far:"…", typhoonAlert:"…" },
    event: { flood:{enter:"…",during:"…",clear:"…"}, signfall:{...}, blackout:{...}, leak:{...} },
    jackpot: { boom:"…", disaster:"…", noHolidaySevere:"…" },
    prepCall: "…"
  }
}
```
- **`copy` 文案**:新聞面板/橫幅顯示用,初值見 `CONTENT.md §R2`(甜甜/麻將館口吻),Codex 灌入、後台「天候」分頁可改。純字串、無邏輯。

### 10.2 config `districts[].location.terrain`(新,§2.1.1 正典值)
```jsonc
location.terrain = { floodRisk: "high|med|low", windExposure:"...", heatIsland:"..." }
```
- MVP 3 區正典(DESIGN §2.1.1):溪畔區`{flood:high,wind:low,heat:med}` / 舊城市場區`{flood:med,wind:low,heat:high}` / 海線開闊區`{flood:med,wind:high,heat:low}`。擴充:高地新市鎮`{flood:low,wind:med,heat:low}`。
- **固定不變**(建圖定死的正典,不是 RNG),選址 = 選這間店「永久的天氣體質」。

### 10.3 parlors `weather`(遊戲端 runtime,存 `mahjong-tycoon-parlors`)
```jsonc
parlor.weather = {
  activeEvents: [
    { type:"flood", weatherWindowId:"12345@heavyRain", startedAt:"...",
      durationDays:2, severity:7, mitigations:{ equipment:["pump"], prepDone:0.3 } }
  ],
  lastSettledEpoch: 12345           // 惰性結算游標,避免重算/重擲
}
```
- 寫入走 **UpdateCommand**(同 staff §9.2 / fengshui-13C:PutCommand 整筆覆寫會洗掉並發更新)。

### 10.4 全域真實天氣 `world.realWeather`(新,§3)
- **小表 `mahjong-tycoon-world`**,`PAY_PER_REQUEST`,PK `key`(S)=`realWeather`,單一 item(見 §3.1 schema)。只有 Lambda `sml-mahjong-weather` 寫、遊戲端只讀(加快取)。
- 亦可寄生 config 表加一列 `PK=world`,但**語意上是 runtime 非 admin draft/published**,建議獨立小表更乾淨。

---

## 11. 整合點 / 接口(給既有規格)

| 對象規格 | 接什麼 |
|---|---|
| **clientflow §5** | 新增 `weatherMod` × `jackpotMod` 層(§7);`avail[c,h]` 乘上 |
| **staff §13** | 天候「預警旗標」→ 拉起 `disasterprep` demand;防災班有效產出 → §5.2 事件 `mitigations`;颱風出勤風險讀 severity |
| **equipment/catalogs** | 新增防災類設備(抽水機/發電機/防風鐵捲門/防水招牌),各帶 `reduction[eventType]`;`catalogs` section |
| **survival** | 維修/停電/賠償 = 現金 sink,與貸款週還款時鐘疊加(天氣壞那週現金流壓力最大);heatWave 冷氣電費 |
| **floorplan/location** | `terrain`(§10.2)+ 一樓/低窪判定進 flood 觸發 |
| **events(clientflow §6)** | 天候事件**獨立於**選項式 events section(不塞進 A/B 那套);颱風假樂透可另做一則慶祝/災難敘事事件 |

---

## 12. Phase 歸屬

- **Phase 1(先埋屬性,不動核心)**:`districts[].location.terrain` 上到 config + 後台可編(§10.2);`balance.weather` seed 骨架建好(可留空/預設晴);staff `disasterprep` demand hook 埋(§13,事件源未接前 demand 恆 0)。**此階段天候不影響結算**。
- **Phase 3(天候系統本體)**:模擬層 `weatherAt` 純函式 + weatherMod 客流層(§7)+ 天候事件觸發/生命週期(§5)+ 颱風假樂透(§6)+ 📰新聞面板(§8,含 staff 預警旗標)。真實層 Lambda `sml-mahjong-weather` + `mahjong-tycoon-world` 表 + fallback(§3)。
- **Phase 3+/可選**:`holidaySource="gov"` 接停班停課開放資料真值(§3.2);寒流餐飲聯動深化。

---

## 13. UI(接既有面板)

- **📰新聞分頁**(玩家主動翻):模擬層未來 2–3 天預報(近準遠趨勢,§8)+ 真實層颱風警報(跟現實同步);醒目提示「該排防災班」→ 導到排班(§staff §13.4)。
- **天候狀態橫幅**:當前天氣型別/severity/是否放假;`activeEvents[]` 每筆一條橫幅 + 可行動按鈕(派清理/叫維修/看損失)。
- customId 前綴 `mjt:weather:`;綁 ownerId;重讀 DDB 不信畫面(同既有慣例)。

---

## 14. 驗收點(給 Codex)

1. **模擬層純函式**:`weatherAt(districtId, epoch)` 零 DB、同輸入同輸出;各區獨立(同 epoch 不同區可不同天氣);型別**永不出 typhoon**;severity ≤ `simSeverityCap`。
2. **epoch 穩定**:同一 epoch 內天氣不變,跨 epoch 才可能變;anchor 固定、不用隨機源。
3. **真實層**:Lambda 抓 CWA 只認全國級(≥ `nationwideCountyThreshold` 縣市 或 颱風警報)→ 寫 `world.realWeather`;單縣市局部不寫;CWA key 走 SSM。
4. **fallback**:`realWeather` 缺失/過期/Lambda 掛 → 降級純模擬層,核心結算不掛;讀取有 60–120s 快取。
5. **有效天氣**:真實 active 時全服套用同 type/holiday、severity 取 max、後果仍看各區 terrain;非 active 用模擬層。
6. **天候事件**:severity 過 gate 才擲;`hash(userId, weatherWindowId, type)` **同窗同型別只擲一次**(刷面板不重抽/不重複開);fired 進 `activeEvents[]`,`durationDays` 2–3,惰性到期移除。
7. **mitigations**:防災設備 reduction + 防災班有效產出(§13)降 baseProb/降損/縮天數;事前權重 > 事中。
8. **颱風假樂透**:四象限(holiday × severity)avail 乘數正確;放假+溫和=本地客群爆滿、放假+猛烈=近零客+高事件率+維修 sink。
9. **weatherMod**:per 天氣 × per 客群 表生效(可驗:lightRain 時 elderly avail 微升、heavyRain 時 scooterClients 大降);淹水中 location access 切斷疊加。
10. **氣象預報**:新聞面板近 epoch 明確、horizon 外只趨勢;真實層颱風警報同步顯示;staff 預警旗標據此拋出。
11. **季節性**:`seasonal[month]` 機率生效(梅雨季 plumRain↑、夏季 typhoon(真實)/heavyRain(模擬)↑)。
12. **資料層**:`balance.weather`/`terrain` 可存/發佈/後台編;parlors `weather` 走 UpdateCommand 並發安全;`mahjong-tycoon-world` 單列只 Lambda 寫;全新表 `PAY_PER_REQUEST`。

---

## 💰 成本控管(遵循 tools/COST_CONTROL.md)

- **成本來源**:①**CWA 開放資料 API**(政府開放資料,**免費**,註冊拿授權碼)②小排程 Lambda `sml-mahjong-weather`(EventBridge 每 30–60 分一次,免費額度內)③新 DDB 小表 `mahjong-tycoon-world`(單一 item,`PAY_PER_REQUEST`,量級極小)④config `balance.weather`/`terrain` = 既有 `mahjong-tycoon-config` 表加欄位(流量無明顯變化)。
- **量級**:預估 **< $1/月**(一個 item 讀寫 + 半小時一次 Lambda);模擬層零額外成本(純函式、無儲存)。
- **無 LLM、無付費 API**(CWA 免費),故免「四件套」帳本/封頂。
- **外部依賴韌性**(≠花錢,但列為鐵律):真實層雖免費仍屬外部依賴 → **不可讓核心迴圈依賴其可用性**,CWA 掛/改格式一律降級純模擬層(§3.3 fallback),不報錯、不阻塞結算。
- 所有新表 `PAY_PER_REQUEST`;CWA key 走 SSM 非硬編碼。若日後真加 LLM(如天氣播報生成),回本規範補齊「四件套」。
