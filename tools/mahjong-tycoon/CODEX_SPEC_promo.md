# 模擬麻將館 — 宣傳系統規格（Phase 3）

> 對象:Codex 驗證/實作。設計:Claude(2026-07-11)。
> 依附:`DESIGN.md` v0.2（§2.3 吸引力公式 / §2.2 分食 / §5 宣傳）、`CONTENT.md` §H。
> 範圍:宣傳系統 = 「投放廣告 → 產生宣傳熱度 + 帶特定客層 + 副作用」。事件系統另有規格。
> 幣別:全程牙齒🦷。所有數值 = **後台可調的 seed 值**,非硬編碼(進 config)。

---

## 0. 一句話

玩家花牙齒投放廣告 → 拉高**吸引力**(搶更多同區客流) + **轉向客層** + 觸發**副作用**。每種廣告有各自主打軸(客量爆發 / 網路聲量 / 常客聲譽 / 對抗虹吸 / 低價凹客),逼玩家依目的組合,不能無腦刷一招。

---

## 1. 新增數值:網路聲量 `buzz`

與既有「聲譽 reputation」**分離**的新軸。

| | 聲譽 reputation(已有) | **buzz 網路聲量(新增)** |
|---|---|---|
| 本質 | 店內口碑/常客氛圍 | 網路能見度/評論星等 |
| 變化速度 | 慢、在地 | 快、volatile |
| 吃這味的客層 | 大戶、雀友重 | 觀光客、散客、學生重;大戶≈0 |
| 上升 | 環境+服務慢養 | KOL好評/媒體採訪/環境好被拍/社群持續經營 |
| 下降 | 鬧事/髒亂 | Google陌生客負評/爆滿服務崩/髒亂被拍/網軍被抓 |

- `parlors.buzz`:0–100,新館 default 30。**(2026-07-11 精化)** buzz 已拆成 **6 網路評價頻道** `catalogs.reviewChannels`(kol/map/threads/ig/fb/line);parlors 存 `reviewScores{6}`(各 0–100),**每客群 buzz = Σ(reviewScores[ch]×channel.audience[客群])**。促銷 buzz 類效果**分流到指定頻道**:kol廣告→kol頻道、search(Google)`negReviewRate`→map頻道負評、social→threads/ig、media→fb/map、astro網軍→刷 threads/map(被抓崩)。各頻道 velocity/trust/volatility/decay 不同(網紅/Threads快漲快跌、地標/LINE慢黏)。詳見 `CODEX_SPEC_clientflow.md` §網路評價 與 CONTENT §H。
- 每 tick 向 baseline(30) **緩慢回歸**(`buzzDecayToBase ≈ 0.3/hr`),避免永久高/永久低。
- 進吸引力公式(§3)。

---

## 2. 客層擴充:新增「學生」

現有客層 `散客 / 雀友 / 大戶 / 觀光客` → **加 `學生`**。
- 特性:**客單價最低**(`avgSpendMult ≈ 0.5`),但提供 **人氣/熱鬧值**(店熱鬧 → 對散客有小幅吸引加成)。
- 綁 🎓大學城區(該區 clientMix 學生佔比高);公車/折價券主帶此客層。
- config `districts[].clientMix` 與 `balance` 的客層權重表都要補 `學生` 欄。

---

## 3. 吸引力公式更新

DESIGN §2.3 現為:
```
attractiveness = w1·聲譽 + w2·環境 + w3·餐飲 + w4·宣傳熱度
               + w5·價格競爭力 + w6·荷官品質 + w7·牌桌品質
```
**新增第 8 項:**
```
               + w8·buzz_norm
```
- `buzz_norm = buzz / 100`。
- **w4 宣傳熱度改為 per-segment**:不同廣告帶不同客層,故宣傳熱度是一個**依客層的向量**(§5),`w4·宣傳熱度` 在對某客層算 attractiveness 時取該客層分量。
- `w8` 權重依客層(seed):觀光客 0.30 / 散客 0.20 / 學生 0.25 / 雀友 0.08 / 大戶 0.02。
- 同區客流仍按各館 attractiveness 做 softmax 分配(DESIGN §2.2)。

---

## 4. 資料模型

### 4.1 config `catalogs.promo`(後台型錄新分頁)
每筆廣告一物件:

```jsonc
{
  "id": "tv",                 // 唯一鍵
  "name": "電視廣告",
  "emoji": "📺",
  "tier": "premium",          // ground|online|event|premium|grey
  "cost": 5000,               // 一次投放牙齒(從館內金庫扣)
  "duration": 48,             // 效果持續(遊戲內 hr)
  "peakHeat": 40,             // 宣傳熱度峰值貢獻
  "shape": "steady",          // 節奏曲線: instant|steady|growth (§5.1)
  "decay": 0.03,              // 熱度衰減率 /hr
  "targetMix": {              // 帶客層權重(和=1),分配 peakHeat 到各客層
    "散客": 0.6, "雀友": 0.3, "大戶": 0.0, "觀光客": 0.0, "學生": 0.1
  },
  "quality": -0.3,            // 客素質 -1..+1 → 影響髒亂/鬧事/臨檢(§6)
  "effects": {
    "regionalPull": 0.25,     // 虹吸:開播期間從全區baseFlow抽此比例直接灌自己(§7)
    "negReviewRate": 0.0,     // 每tick生負評機率 → buzz↓(§8)
    "buzzDelta": 0.0,         // 每tick對buzz的期望增量(+/-)
    "reputationDelta": 0.0,   // 每tick對聲譽增量
    "messMult": 1.15,         // 髒亂速率乘數(>1加速髒)
    "troubleMult": 1.2,       // 鬧事/臨檢機率乘數
    "avgSpendMult": 1.0,      // 帶進來的客客單價乘數(折價券<1)
    "nightBandMult": 1.0      // 深夜時段額外加成(計程車隊)
  },
  "perTickCost": 0,           // 分潤/抽成(聯名/計程車,每tick從營收扣%或定額)
  "cooldown": 0,              // 再投放冷卻(hr),名人站台用
  "localOnly": false,         // true=只對所在區有效(傳單)
  "requires": {}              // 解鎖: {bossLevel, district, equipment...}
}
```

### 4.2 `parlors` 表新增欄位
```jsonc
{
  "buzz": 30,
  "activeCampaigns": [        // 進行中的廣告
    { "promoId": "tv", "startedAt": 1720680000000, "expiresAt": 1720852800000 }
  ]
}
```
- 一種廣告同時**只能有 1 個 active**(重複投放 = 續期/覆蓋,不疊實例);跨廣告可並行,但總熱度有邊際遞減(§5.2)。

### 4.3 config `balance.promo`(平衡參數)
```jsonc
{
  "buzzBaseline": 30, "buzzDecayToBase": 0.3,
  "w8ByClient": {"觀光客":0.30,"散客":0.20,"學生":0.25,"雀友":0.08,"大戶":0.02},
  "heatStackDR": 0.6,         // 多廣告熱度疊加遞減係數(§5.2)
  "overflowNegReview": 0.5,   // 客量>容客量時每單位溢出的負評機率(§9)
  "greyExposureBase": 0.08    // 網軍每tick被抓基礎機率
}
```

---

## 5. 宣傳熱度模型

### 5.1 節奏曲線 `shape`(elapsed = now − startedAt,單位 hr;D = duration)
- **instant**(即時尖峰,KOL/開幕/名人):投放瞬間到峰值,之後 `heat = peakHeat · e^(−decay·elapsed)`。爆得快退得快。
- **steady**(平穩檔期,電視/公車/Google/聯名/計程車):`elapsed<D` 時 `heat = peakHeat`(平台),`elapsed≥D` 後開始 `· e^(−decay·(elapsed−D))` 收尾。
- **growth**(需持續經營,社群/媒體):`heat = peakHeat · (1 − e^(−k·elapsed))` 漸升;**斷更**(過期未續投)則快速回落。獎勵持續投入。

### 5.2 總熱度(per-segment,含邊際遞減)
對客層 s:
```
rawHeat[s] = Σ_campaign ( heat_campaign(t) · targetMix_campaign[s] )
promoHeat[s] = rawHeat[s]^heatStackDR        // heatStackDR≈0.6 → 疊越多回報遞減
```
- 這個 `promoHeat[s]` 就是 §3 公式裡對客層 s 的 `w4·宣傳熱度` 分量。

---

## 6. 客素質 `quality` → 後果

帶進來的客,依該廣告 `quality`(-1..+1)混入該館「當期客群素質」加權平均。低素質:
- `messMult`、`troubleMult` 效果等同「低價客」(對齊定價系統 GAMEPLAY 決策4):**髒亂速率↑、鬧事機率↑、臨檢/消防檢舉風險↑**。
- 逼玩家補保全/清潔人力,否則環境→聲譽→客流負向螺旋。

---

## 7. 虹吸鄰店 `regionalPull`(電視主打)

在多人分食(DESIGN §2.2)前置一步:
```
divertedFlow = districtBaseFlow · regionalPull       // 開播期間
玩家自己 += divertedFlow
剩餘 (1−regionalPull)·baseFlow 再給全區(含自己)做 softmax 分配
```
- 效果 = 同區其他館(含對手玩家/NPC)可分食的池子變小 → 「附近店家來客降低」。
- 屬**對抗性工具**,對手會在地圖看板看到你來客暴增。多台電視同區 → regionalPull 也走邊際遞減(共用 heatStackDR 或另設上限,避免抽乾全區)。

---

## 8. 網路負評 `negReviewRate`(Google 主打)

- 每 tick 以 `negReviewRate` 機率生一則負評 → `buzz -= 隨機(2~5)`。
- 設計意圖:Google 短期拉客量(promoHeat),但**長期侵蝕 buzz**(複利拖累觀光/散客吸引力)→ 越常投越傷,逼玩家搭配養 buzz 的手段(媒體/社群)。

---

## 9. 容量錯配反噬(KOL/爆量廣告的風險閘)

結算時若**湧入客量 > 容客量/湊咖服務量**:
- 溢出客以 `overflowNegReview` 機率生負評(`buzz↓` + 小幅聲譽↓)。
- 對 `shape:instant` 高 `peakHeat` 廣告(KOL/名人/開幕)特別致命 → 投放前要先備桌位+清潔+人力,否則宣傳費打水漂還倒扣 buzz。獎懲對稱。

---

## 10. 廣告型錄(14 筆 seed 值,全部進 config,待平衡)

> 數值為**相對量級起點**,Phase 3 上線後於 `balance` 校準。MVP 先做 ★ 6 個(涵蓋全部主打軸)。

| id | 名稱 | tier | cost | dur(hr) | peakHeat | shape | 主帶客層 | quality | 招牌 effect | MVP |
|---|---|---|---|---|---|---|---|---|---|---|
| flyer | 📄傳單 | ground | 150 | 12 | 8 | steady | 散客(本區) | −0.1 | localOnly,messMult1.05 | ★ |
| social | 📱社群貼文 | online | 50 | 8 | 6 | growth | 散客/觀光 | 0 | buzzDelta +0.5,斷更掉 | ★ |
| coupon | 🎟️折價券 | ground | 200 | 24 | 20 | steady | 散客 | −0.4 | avgSpendMult0.7,messMult1.1 | |
| search | 🔍Google關鍵字 | online | 800 | 24 | 18 | steady | 觀光/散客 | 0 | negReviewRate0.15 | ★ |
| media | 📰媒體專訪 | online | 3000 | 72 | 15 | growth | 全客層 | 0 | buzzDelta+2,repDelta+0.5,**店況差反噬** | |
| opening | 🎉開幕活動 | event | 500 | 6 | 30 | instant | 散客/雀友 | 0 | 一次性爆量,冷清反傷 | |
| tourney | 🃏店內賽事 | event | 600 | 6 | 12 | instant | 雀友 | +0.3 | repDelta+2,賽事桌不收檯費,回頭率↑ | ★ |
| collab | 🤝異業聯名 | event | 700 | 48 | 16 | steady | 依對象 | 0 | buzzDelta+0.8,perTickCost分潤 | |
| bus | 🚌公車廣告 | online | 1200 | 48 | 14 | steady | 學生 | 0 | 學生低客單價 | |
| taxi | 🚕計程車隊 | premium | 400 | 48 | 14 | steady | 觀光/大戶 | +0.1 | perTickCost回扣,nightBandMult1.5 | |
| tv | 📺電視廣告 | premium | 5000 | 48 | 40 | steady | 高齡散客/雀友 | −0.3 | **regionalPull0.25**,messMult1.15,troubleMult1.2 | ★ |
| kol | 🎬KOL影片 | premium | 3500 | 12 | 60 | instant | 觀光爆量 | −0.1 | **messMult1.8**,溢出反噬 | ★ |
| celeb | 🌟名人站台 | premium | 6000 | 24 | 50 | instant | 粉絲觀光/雀友 | 0 | buzzDelta+3,repDelta+1,cooldown168,requires | |
| astro | 📢網軍刷評 | grey | 1000 | 24 | 10 | steady | 全(走buzz) | 0 | buzzDelta+4,**被抓→buzz崩+公關危機事件+罰** | |

(★=14 筆中選 6 做 MVP:flyer/social/search/tourney/tv/kol)

---

## 11. UI(接既有面板)

- 主面板「宣傳」分頁(DESIGN §10 已列):
  - 顯示 buzz、各 active campaign 剩餘時間 + 當前熱度、目前客層熱度分布。
  - 廣告用 **StringSelectMenu** 選(依 tier 分組/依解鎖過濾),選後 ephemeral 確認成本 → 扣金庫投放。
  - customId 前綴 `mjt:promo:`;綁 ownerId 守門;重讀 DDB 不信畫面(對齊 Phase 0 慣例)。
- 名人站台/網軍等特殊項:投放時附風險文案提示。

---

## 12. 金流/防呆

- 投放:**先讀金庫餘額 → 條件扣款失敗退款**(對齊 Phase 0 金流防線)。
- `perTickCost`(聯名分潤/計程車回扣)在惰性結算時從該期營收扣,營收不足則扣到 0 不倒欠。
- 續投同一廣告 = 覆蓋 `startedAt/expiresAt`(重置檔期),不重複建實例。
- 網軍 exposure、負評、溢出反噬都在**惰性結算**時按經過 tick 積分計算(不需即時)。

---

## 13. 驗收點(給 Codex)

1. config `catalogs.promo` + `balance.promo` 可存/發佈,前端型錄分頁可編輯 13 筆。
2. `parlors` 新增 buzz/activeCampaigns,新館 buzz=30。
3. 投放:扣款正確、扣款失敗退款、續投覆蓋不疊實例、餘額不足擋下。
4. 熱度三種 shape 曲線隨時間正確(instant 爆退 / steady 平台後收尾 / growth 漸升+斷更回落)。
5. 多廣告熱度 per-segment 疊加走邊際遞減;吸引力 w8·buzz 生效。
6. 電視 regionalPull 讓同區他館分食池變小(可用 2 館測)。
7. Google negReviewRate 隨時間扣 buzz;KOL 溢出(超容客量)扣 buzz。
8. 低 quality 廣告拉高髒亂/鬧事/臨檢(對齊定價低價客邏輯)。
9. perTickCost 從營收扣、營收不足扣到 0。
10. 網軍被抓觸發 buzz 崩 + 公關危機事件 + 罰款。

---

## 14. Codex 審查修正併入(2026-07-11)

**A. 客層 key 固定英文(資料層)。** 對齊既有 backend spec,`targetMix` / `w8ByClient` / 各權重表的 key 一律用英文,中文只做 UI label:
**canonical 10 客群**(2026-07-11 由 5→10):`casual/regular/whale/tourist/student/elderly/mama/truant/roamer/novice`(散客/雀友/大戶/觀光客/學生/高齡/媽媽/翹課學生/游擊中年人/麻將新手);皆正式客群、都進 clientMix。各客群 w1–w9 權重(含 buzz w8)在 `balance.weights` 全 10 列;client list 資料驅動(見 `CODEX_SPEC_clientflow.md`)。
本規格上文 JSON 範例的中文 key 均以此對映替換(如 `targetMix:{casual:0.6,regular:0.3,whale:0,tourist:0,student:0.1}`)。廣告 `targetMix` 可帶 elderly/mama(如電視偏 elderly、餐飲聯名偏 mama);未列的客群視為 0。**w8 buzz 權重補**:elderly 0.02、mama 0.15。

**B. 隨機效果必須 idempotent(惰性結算硬性要求)。** `negReviewRate`、網軍 exposure、容量溢出負評等**不能每次 retry/面板刷新就重抽**。作法:以 **tick bucket + deterministic seed**(例:`hash(parlorId, promoId, bucketTs)`)決定該 tick 有無事件,或記錄 `lastSettledAt` 已處理區間,只對「新經過的 tick」判定一次。避免玩家狂點面板刷負評/刷被抓。

**C. `regionalPull` 依賴 Phase 2 世界模型 → 需優雅降級。** 電視虹吸是分食前置步,若 Phase 2 同區多館模型尚未完整:電視廣告**先關閉 regionalPull 或降級成只加自己的 promoHeat**(不動別館),待 Phase 2 到位再開真虹吸。實作時以 feature flag 控。

**D. 寫入安全(Phase 1 前置,跨規格共用)。** 目前 `ParlorDAO.save()` 是 `PutCommand` 整筆覆寫;Phase 0 無虞,但一旦有採購/投廣告/結算多互動並發,stale item 會洗掉新欄位。**Phase 1 前**把 settle 改 `UpdateCommand` 局部更新,或加 `revision/updatedAt` 條件寫入(見風水規格同款註記,兩系統一起改)。
