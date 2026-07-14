# 模擬麻將館 — 客流模型規格（地段 × 客群 × 時段）

> 對象:Codex 驗證/實作(Phase 1~2 公式地基)。設計:Claude(2026-07-11)。
> 依附:`CONTENT.md` §A/§F、`DESIGN.md` §2、`CODEX_SPEC_backend.md`、地段/客群後台已上線(sweetbot-games.web.app)。
> 定位:把「每小時實際來哪些客、各館怎麼分」講清楚。串起地段屬性、客群活躍時段、吸引力、湊咖、翻桌、飽和。

---

## 0. 一句話

**每小時每客群的可得客流** = 地段基準 × clientMix × 該客群活躍時段(此小時) × location 便利(此小時,含捷運深夜 gate);再由同區各館的**吸引力(依客層權重)**做 softmax 分食;入館後由 dwell/翻桌/湊咖/飽和/逃單決定實際營收與副作用。

---

## 1. 客群 canonical(10 種)

`casual / regular / whale / tourist / student / elderly / mama / truant / roamer / novice`
散客 / 雀友 / 大戶 / 觀光客 / 學生 / 👴高齡 / 👩‍👧媽媽(家庭主婦) / 🚸翹課學生 / 🎲游擊中年人 / 🌱麻將新手。
- 中文只做 label;所有資料層/公式用英文 key。已同步 DESIGN/backend/promo(w8)/fengshui(w9) 各規格。

## 2. clientProfiles(每客群 9 特性,`balance.clientProfiles`)

| 欄位 | 意義 | 用在 |
|---|---|---|
| `activeStart`/`activeEnd` | 活躍時段(24h,**迄<起=跨午夜**;0–24=全天) | §5 時段 gate |
| `dwell` | 停留/佔桌時長倍率 | 翻桌率、容客占用 |
| `quality` | 客素質 −1..+1(負→髒亂/鬧事) | §6.3 環境/風險 |
| `troubleRisk` | 滋事機率 | §6.3 保全 |
| `payRisk` | 逃單機率(不付錢) | §6.4 |
| `matchDemand` | 配桌需求(湊咖積極度) | §6.5 湊咖 |
| `saturationPenalty` | 飽和負外部性係數 | §6.6 |
| `roundTimeExtend` | 每局配桌 **+N 小時**(→翻桌率↓) | §6.2 |

### 2.1 seed 值(已上線,待平衡)
| client | actStart | actEnd | dwell | quality | trouble | pay | match | satur | roundExt |
|---|---|---|---|---|---|---|---|---|---|
| casual  | 10 | 23 | 1.0 | 0     | 0.05 | 0    | 1.0 | 0   | 0 |
| regular | 14 | 24 | 1.3 | 0.1   | 0.02 | 0    | 1.2 | 0   | 0 |
| whale   | 20 | 4  | 1.5 | 0.2   | 0.03 | 0    | 1.3 | 0   | 0 |
| tourist | 11 | 22 | 0.8 | 0     | 0.03 | 0    | 0.7 | 0   | 0 |
| student | 18 | 2  | 1.6 | -0.05 | 0.08 | 0.05 | 1.1 | 0   | 0 |
| elderly | 6  | 15 | 1.4 | 0.1   | 0.02 | 0    | 1.2 | 0   | 0 |
| mama    | 9  | 16 | 0.9 | 0.1   | 0.02 | 0    | 0.9 | 0   | 0 |
| truant  | 9  | 16 | 1.2 | -0.5  | 0.25 | 0.35 | 1.0 | 0   | 0 |
| roamer  | 0  | 24 | 2.0 | -0.4  | 0.30 | 0.05 | 1.5 | 0.6 | 0 |
| novice  | 14 | 23 | 1.5 | -0.2  | 0.05 | 0    | 1.3 | 0.4 | 1 |

`balance.saturationShareThreshold = 0.25`。

## 3. 地段屬性(每區 `location`)

`{ roadside, carParking, scooterParking, freeLotDist, paidLotDist, mrtDist, mrtOpen, mrtClose, archetype }`
係數 `balance.location`:`carAccessBase/carPerSlot/freeLotNearM/freeLotNearBonus/paidLotFarM/paidLotFarPenalty/scooterAccessBase/scooterPerSlot/mrtNearM/mrtNearBonus/mrtFarM/mrtNightClosed/mrtNightBands/roadsideExposure/roadsideRentMult/roadsideFlyerBonus/carClients/scooterClients/mrtClients`。
- `carClients=[whale,mama,elderly]`、`scooterClients=[student,casual]`、`mrtClients=[student,tourist,casual]`。

## 4. 吸引力權重(`balance.weights`,10 客群 × 9 因子)

`price/reputation/environment/food/promoHeat/dealer/tableQuality/buzz/fengshui`(=DESIGN §2.3 的 w1–w9)。每客群一列(已含全 10 客群)。高齡 fengshui 0.40 最高、媽媽 price 0.03 最低。

---

## 5. 主流程(每小時,惰性結算按經過時段積分)

```
for each hour h(遊戲時區 Asia/Taipei):
  for each client c:
    avail[c,h] = district.baseFlow
               × district.clientMix[c]/100
               × activeWeight(c,h)            # §5.1 活躍時段 gate
               × locationAccess(c,h)          # §5.2 交通/捷運(含深夜 gate)
               × timeBand(h)                  # 既有 §2.4 時段係數(可選)
  # 各客群可得客流 → 同區各館按吸引力分食
  for each parlor p, client c:
    capture[p,c,h] = softmax_over_parlors( attractiveness(p,c) )  # 依 c 的權重列
    inflow[p,c,h]  = avail[c,h] × capture[p,c,h]
  # 入館後結算(§6)
```

### 5.1 活躍時段 gate `activeWeight(c,h)`
- h 落在 [activeStart, activeEnd)(跨午夜要 wrap)→ 1.0(或加軟邊緣衰減);否則 ≈ 0。
- 例:student 18–02 → 白天≈0;roamer 0–24 → 恆 1。

### 5.2 location 便利 `locationAccess(c,h)`(0–1,可 clamp,缺 location 給 neutral 1.0)
- c ∈ carClients → 開車便利 = clamp(carAccessBase + carPerSlot·carParking + (freeLotDist<freeLotNearM? freeLotNearBonus:0) − (paidLotDist>paidLotFarM? paidLotFarPenalty:0))。
- c ∈ scooterClients → 機車便利 = clamp(scooterAccessBase + scooterPerSlot·scooterParking)。
- c ∈ mrtClients → 捷運便利 = 距離曲線(mrtDist<mrtNearM→+bonus; >mrtFarM→↓);**且 h ∈ mrtNightBands(捷運休,00–06)→ 捷運便利歸 0**。→「靠捷運店適合白天不適合通宵」。
- 一個客群可同時吃多條(取 max 或加權,建議 max)。

---

## 6. 入館後結算(各機制)

### 6.1 收益
`檯費/鐘點 × 佔桌時間 + 餐飲`;佔桌時間 ∝ dwell。dwell 高=坐得久(佔容量久)。

### 6.2 翻桌率 / roundTimeExtend
- 每桌每局時間 = baseRound + Σ(該桌客群 roundTimeExtend)。麻將新手 +1hr → 桌被佔久、單位時間局數↓ → **翻桌率/檯費吞吐↓**。
- 影響「單位時間能服務幾輪客」,與 dwell 疊加(dwell=停留,roundTimeExtend=每局變慢)。

### 6.3 客素質 → 環境/風險
- quality 負 → 髒亂速率↑、troubleRisk 生鬧事(保全/監視器降之)、臨檢/消防檢舉↑(對齊定價低價客)。

### 6.4 逃單 payRisk
- 消費有 payRisk 機率不付 → 收入損失;監視器/保全降 payRisk。翻課學生 0.35 最高。

### 6.5 湊咖 matchDemand(接 E2 湊咖系統)
- matchDemand 高 = 積極要被湊桌 → 幫你填滿空位(桌利用率↑);但常伴隨 quality 差/飽和(roamer)。

### 6.6 飽和負外部性 saturationPenalty
- 令 share_c = 該客群佔在場客群比例。若 share_c > `saturationShareThreshold`(0.25):
  `penalty = saturationPenalty_c × (share_c − threshold)` → 扣**聲譽 / 其他客滿意度**(→ 客流/buzz 反噬)。
- 目前 roamer 0.6、novice 0.4;其餘 0。→「某類客人變主力會毀店」。

### 6.7 網路評價 6 頻道 → per-客群 buzz(取代單一 buzz)
- `catalogs.reviewChannels`(kol/map/threads/ig/fb/line),parlors 存 `reviewScores{6}`(0–100)。
- **每客群 buzz = Σ_ch( reviewScores[ch] × channel.audience[c] )** → 進吸引力 w8(該客群權重)。學生看 threads/kol、大戶看 map/line,同店在不同客群眼中口碑不同。
- 頻道各有 velocity(傳播)/trust/volatility(波動)/decay(回歸);促銷/事件/服務品質**分流推動指定頻道**(見 promo §1)。惰性結算按 decay 向 baseline 回歸、按 driver 加減。

### 6.8 周遭設施 → 運勢(接風水) + 心情(滿意度)
- 每區 `location.surroundings`(逗號分隔設施 id)→ 查 `catalogs.surroundings` 彙總:
  - `locationFortune = Σ fortuneMod` → **effectiveFengshui = layout風水 + ambience.fortuneToFengshui×locationFortune**(進 w9,信風水客群有感;見 fengshui §15)。
  - `locationMood = Σ moodMod`(+ 館內裝潢/音響抵銷,上限 ambience.interiorMoodOffsetMax)→ **心情軸**。
- **心情 mood 效果**(balance.ambience 係數):mood 負 → `troubleRisk += moodToTroubleRisk×|mood|`、`客單價 ×(1 − moodToSpendMult×|mood|)`、停留↓、`負評率 += moodToReviewRate×|mood|`(灌 §6.7 頻道)。→ 醫院/工地旁心情差、大廟旺運但吵。

### 6.9 idempotent
- payRisk、troubleRisk、逃單、飽和事件等隨機/門檻效果,惰性結算用 tick bucket + deterministic seed,只對新經過時段判一次(對齊前規格)。

---

## 7. 資料模型

- config(**後台全部已上線**):`districts[].location`、`districts[].clientMix`(10 鍵)、`balance.weights`(10 客群)、`balance.clientProfiles`(10×9)、`balance.location`、`balance.saturationShareThreshold`。DDB 表結構不變。
- parlors(Phase 1~2 遊戲端):結算需存/算 在場客群組成(算 share_c/飽和)、按小時積分。

---

## 8. 驗收點(給 Codex)

1. 每小時 avail = baseFlow×clientMix×activeWeight×locationAccess;跨午夜活躍窗正確(student 白天≈0)。
2. 捷運深夜 gate:mrtNightBands 時段 mrtClients 便利=0(靠捷運店通宵掉客);Asia/Taipei 時區。
3. location 便利 clamp、缺 location 給 neutral、路邊同時吃客流加成 + 租金乘數。
4. 分食 softmax 依客層權重(10 客群列);高齡多的區風水好的館搶更多。
5. dwell 佔容量、roundTimeExtend 降翻桌(novice 在桌→該桌局數↓)。
6. quality/troubleRisk/payRisk(逃單)按 clientProfiles 生效;保全/監視器可降。
7. matchDemand 餵湊咖(填空位)。
8. 飽和:share>0.25 時 saturationPenalty 扣聲譽/滿意度(roamer/novice 可測)。
9. 隨機/門檻效果 idempotent(tick bucket + seed)。
10. 全部係數讀 config,無硬編碼;新增客群/欄位不需改遊戲端公式骨架(資料驅動)。

---

## 9. Codex 審查修正併入(2026-07-11)

**1. 客群 canonical = 10(已全規格同步)。** `casual/regular/whale/tourist/student/elderly/mama/truant/roamer/novice` 皆**正式客群、都進 `district.clientMix`**。DESIGN/backend/promo/fengshui/CONTENT 已全部改成 10(不再有 7 客群字樣)。**client list 資料驅動**:遊戲端從 `balance.clientProfiles`/`weights` 的鍵取得,勿硬編碼。

**2. reviewChannels rollup 要正規化 + clamp。** `buzz_c = Σ_ch( reviewScores[ch] × audience[ch][c] )` 之後 **clamp 0–100**;或除以 `Σ_ch audience[ch][c]`(audience 未正規化時)避免超 100。二擇一,寫死在公式。

**3. 頻道四參數各進哪個公式(明確定義)。**
- `velocity`:driver 推動時分數變化的**放大係數**(高=一次事件推很多)。
- `decay`:每 tick 向 baseline 回歸速率。
- `trust`:該頻道分數進 buzz rollup 的**權重乘數**(高信任頻道影響大)。
- `volatility`:隨機抖動幅度 —— **必須 tick bucket + deterministic seed**,不可每次刷新亂抽。

**4. reviewScores 需要 settle 游標防重複套 driver。** 記 `lastReviewSettledAt`,或把 review 更新**併入 parlor 主 `lastSettledAt` 的單次交易**;driver 只對新經過區間套一次(idempotent)。

**5. surroundings 長期用 array。** `location.surroundings` 後台目前是逗號字串(遊戲端 split 可用);資料層長期建議改 `["big_temple","hospital"]`,免空白/錯字/split 相容問題。Phase 1 遷移。

**6. effectiveFengshui 欄位明確拆(不可重複加)。**
```
layoutFengshui   = 店內擺設分(fengshui 規格 §4)
locationFortune  = Σ surroundings.fortuneMod
effectiveFengshui = clamp( layoutFengshui + ambience.fortuneToFengshui × locationFortune , 0,100 )
```
**進 w9 的只能是 `effectiveFengshui`**;location fortune 不得在別處再加一次。

**7. mood 進負評走 deterministic review driver。** 心情差**不直接扣 reviewScores**,而是產生一個 deterministic review driver(依 tick bucket seed)再分流到 map/threads/ig/fb/line;維持 idempotent 且可驗收(§6.7/6.8 據此實作)。
