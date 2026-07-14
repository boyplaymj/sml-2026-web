# 模擬麻將館 — 風水系統規格（完整版）

> 對象:Codex 驗證/實作。設計:Claude(2026-07-11)。深度=完整版(五行相生剋 + 5方位槽 + 流年輪換)。
> 依附:`DESIGN.md` v0.2(§2.3 吸引力公式)、`CONTENT.md` §O、事件系統、賽季傳承 M5。
> 定位:打麻將的人信風水影響運氣 → 風水達標 = **大戶/雀友磁鐵**(補足現有吸引力軸缺的「運氣」味)。
> 幣別:牙齒🦷。所有數值 = 後台可調 seed,非硬編碼。

---

## 0. 一句話

館內**方位槽**擺放風水家具,依**五行相生相剋 + 得位 + 流年吉凶**算出 `fengshui 風水分數` → 進吸引力公式(重大戶/雀友);請**風水老師**勘輿/化煞/擇日;**風水事件**雙向擾動。核心樂趣 = 擺設是個**會隨賽季流年變動的佈局謎題**(=「透過系統來管理」)。

---

## 1. 新增數值:風水分數 `fengshui`

- `parlors.fengshui`:0–100,新館 default 20(空館微低)。
- **非累加式**:由 `layout`(方位槽擺設)每次結算重算(§4),不是買越多加越多。
- 與「環境 environment」分離:環境=physical 乾淨舒適,風水=mystical 運氣氣場;大戶兩者都在意。

進吸引力公式(DESIGN §2.3)新增第 9 項:
```
attractiveness += w9 · (fengshui/100)
```
`w9` 依客層(seed):**大戶 0.35 / 雀友 0.25** / 散客 0.10 / 觀光客 0.08 / 學生 0.03。

---

## 2. 方位槽 × 五行

### 2.1 五槽（後天配置,排成「相生環」）
| 槽 | 本命五行 | 相生環相鄰 |
|---|---|---|
| 東 | 木 | 北(水生木)、南(木生火) |
| 南 | 火 | 東(木生火)、中(火生土) |
| 中 | 土 | 南(火生土)、西(土生金) |
| 西 | 金 | 中(土生金)、北(金生水) |
| 北 | 水 | 西(金生水)、東(水生木) |

> 相生鏈:木→火→土→金→水→木。相剋:木剋土、土剋水、水剋火、火剋金、金剋木。

### 2.2 家具（config `catalogs.fengshui`）
每件家具:
```jsonc
{
  "id": "flow_bowl", "name": "流水盆", "emoji": "⛲",
  "element": "水",              // 五行
  "nativeSlot": "北",           // 得位方位(擺這格有加成)
  "effectType": "催財",         // 催財|旺丁|化煞|人緣|鎮宅
  "cost": 900,                  // 一次採購牙齒
  "upkeep": 5,                  // 每tick維護(0=免維護)
  "baseScore": 10,              // 基礎風水貢獻
  "effect": {                   // 對遊戲數值的加成(擺對時全額,擺錯打折)
    "avgSpendMult": 1.08,       // 客單價
    "dahuPull": 0.05,           // 大戶吸引額外
    "flowMult": 1.0,            // 來客量
    "troubleMult": 1.0,         // 鬧事(化煞類<1)
    "buzzDelta": 0.0,
    "moraleDelta": 0.0,         // 員工士氣(鎮宅類)
    "eventShield": 0.0          // 降負面事件機率(化煞類)
  },
  "taboo": ["對門","廁所位"],   // 禁忌(觸發沖煞懲罰,見§4.3)
  "requires": {}                // 解鎖(老闆等級/老師開光)
}
```

---

## 3. 風水老師（顧問,非常駐員工）— config `catalogs.fengshuiMasters`

花牙齒請來、有 cooldown,提供服務:

| 服務 | 效果 |
|---|---|
| **勘輿(掃描)** | 揭露隱藏沖煞 + 給最佳擺位建議(花錢買提示)。JSON 回目前 layout 的扣分點。 |
| **化煞** | 移除一個 active 沖煞/流年凶位懲罰(一段時間)。 |
| **擇日開市/擇吉** | 一次性開運 buff;若同期有開幕/名人/賽事 → 效果加倍。 |
| **開光安神** | 指定一件家具 `effect` 提升(永久或一季)。 |
| **流年調理** | 依當季流年給整套重佈建議。 |

老師分級(仿面試 tells,`accuracy` 準度 + `charlatanRisk` 騙子機率):
| tier | cost | 準度 | 風險 |
|---|---|---|---|
| 江湖術士 | 低 | 低 | **charlatanRisk 高**:可能給錯建議 → 佈局變糟 + 破財事件 |
| 民間師傅 | 中 | 中 | 低 |
| 開運名師 | 高 | 高 | 無;擇日 buff 強 |
| 宗師/國師 | 很貴 | 極高 | 全服稀有(隨機可約/長 cooldown);一次揭全煞 + 大 buff |

---

## 4. 風水分數計算（每次惰性結算重算）

對每個「有擺家具」的槽 i:
```
slotScore_i = item.baseScore
  × 得位係數(§4.1)
  × 相生相剋係數(§4.2)
  − 沖煞懲罰(§4.3)
  × 流年係數(§5)
fengshui = clamp( Σ slotScore_i , 0, 100 )
```
家具的 `effect`(客單價/大戶吸引/化煞…)同樣按**得位/流年**加權後套用到經營結算。

### 4.1 得位（擺對方位）
- `item.element == slot.本命五行` → **得位** ×1.5(seed)。
- `item.element` 被 `slot.本命五行` **相剋**(如金物擺南/火位:火剋金) → **失位** ×0.5 + `effect` 打折。
- 其餘(相生/中性) → ×1.0。

### 4.2 相生相鄰
- 相生環(§2.1)相鄰兩槽,若擺的家具元素構成「生」關係(A 生 B)→ 兩槽各 +bonus(seed +15%)。
- 相鄰構成「剋」關係 → 兩槽各 −penalty(seed −20%)。
- 空槽不參與。→ **鼓勵沿相生鏈佈局、避免相剋相鄰**。

### 4.3 沖煞（硬規則,大扣分）
- 家具擺進自己 `taboo` 標記的位 → **沖煞**,該槽 slotScore 歸 0 或轉負 + 提高風水衰事件機率。
- 例:鏡類擺「對門」= 漏財;流水/魚缸擺「廁所位」= 破財。(taboo 位由 config 定義,勘輿可揭示。)

---

## 5. 流年（綁賽季,持續管理的來源）

- config `balance.fengshui.liunian`(每賽季一組,配合 SML 賽季輪換):
```jsonc
{ "season": "2026Q3", "caiwei": "東", "wuhuang": "中", "suipo": "西" }
```
- **財位 caiwei**:該槽 slotScore ×1.8(seed);擺催財類 effect 加倍。
- **五黃位 wuhuang**:該槽若擺一般家具 → 招凶(×0.4 + 風水衰事件機率↑);**擺化煞類(麒麟/山海鎮/鹽燈)可鎮 → 反而 +bonus**。
- **歲破位 suipo**:該槽 effect 減半。
- 換季 → 財位/凶位換槽 → **上季最優佈局新季未必最優,要重調** = 核心管理循環。
- 接傳承 M5:可留「傳家風水寶物」(一件跨季家具,帶入新季)。

---

## 6. 客人「運氣感受」連動（讓「信風水」有實際後果）

非賭博,「風水影響運氣」落地為:
- **fengshui 高** → 客人主觀手氣旺 → 開心:`客單價↑`(催財類)、`停留/回頭率↑`、`buzz↑`(口碑「福地」)。
- **fengshui 低 + 客人手氣差** → `鬧事機率↑`(「怪風水」砸場,接對應風水衰事件)。
- 用一個 `luckSentiment = f(fengshui, 隨機)` 每結算期影響上述,不需真的模擬牌局輸贏。

---

## 7. 風水事件（併進雙向事件系統 §I）

**有利**:
- 福地口碑(連續高 fengshui)→ buzz 大漲
- 貴人指點 → 免費一次勘輿
- 撿到開運物 → 送一件家具
- 財神夜巡 → 一段時間客單價↑
- 老師報開運日 → 擇日 buff

**有害**:
- 隔壁動土沖煞 → fengshui 暫降
- 員工亂移擺設 → layout 被打亂需重佈
- 流年五黃入中 → 凶位懲罰(未化煞則連鎖衰事)
- 請到假老師破財 → 扣牙齒 + 錯誤佈局
- 漏水淹財位 → 財位家具失效 + 維修費
- 客人輸錢砸場 → 鬧事(fengshui 低時機率高)
- 鏡子對門漏財 → 客訴 buzz↓

觸發權重掛 `fengshui` 高低 + 是否犯沖/五黃 + 老師準度。

---

## 8. 資料模型

### 8.1 config 新增
- `catalogs.fengshui`(家具,§2.2)
- `catalogs.fengshuiMasters`(老師,§3)
- `balance.fengshui`:得位/相生/沖煞係數、`w9ByClient`、`liunian`(每季)、事件權重。

### 8.2 `parlors` 新增
```jsonc
{
  "fengshui": 20,
  "layout": { "東":"money_tree", "南":null, "中":"dragon_turtle", "西":"wudi_coin", "北":"flow_bowl" },
  "fengshuiItems": ["money_tree","dragon_turtle","wudi_coin","flow_bowl"],  // 已購清單(可換槽)
  "masterCooldownUntil": 0,
  "activeBlessings": []   // 擇日/開光等一次性/限時buff
}
```
- 買家具 = 進 `fengshuiItems`;放上槽 = 寫 `layout`(可搬動,搬動不花錢或收小額移位費)。

---

## 9. 家具型錄（seed,待平衡;MVP 先做 ★8）

| id | 名稱 | 五行 | 得位 | 類型 | cost | baseScore | 招牌效果 | MVP |
|---|---|---|---|---|---|---|---|---|
| lucky_bamboo | 🎋開運竹 | 木 | 東 | 旺丁 | 200 | 5 | 來客+,入門 | ★ |
| money_tree | 🌳發財樹 | 木 | 東 | 旺丁 | 500 | 7 | 來客+ | ★ |
| flow_bowl | ⛲流水盆 | 水 | 北 | 催財 | 900 | 10 | 客單價+,擺錯漏財 | ★ |
| fish_tank | 🐟風水魚缸 | 水 | 北 | 旺丁 | 1100 | 9 | 來客+,要維護 | |
| dragon_turtle | 🐉龍龜 | 土 | 中 | 化煞催財 | 800 | 9 | 鬧事−,客單價+ | ★ |
| qilin | 🦄麒麟 | 土 | 中 | 鎮宅擋煞 | 1300 | 9 | 鎮五黃,eventShield | |
| amethyst | 🔮紫晶洞 | 土 | 中 | 人緣 | 1000 | 8 | buzz+ | |
| wudi_coin | 🪙五帝錢 | 金 | 西 | 催財 | 600 | 8 | 大戶吸引+ | ★ |
| bagua_mirror | 🪞八卦鏡 | 金 | 西 | 化煞 | 400 | 5 | 踢館/臨檢−,taboo對門 | ★ |
| guangong | 🗡️關公像 | 金 | 西 | 鎮宅化煞 | 1200 | 9 | 士氣+,防踢館 | |
| caishen | 🧧財神像 | 火 | 南 | 鎮宅催財 | 1000 | 10 | 士氣+,客單價+ | ★ |
| salt_lamp | 🧂鹽燈 | 火 | 南 | 化煞人緣 | 500 | 6 | 鬧事−,buzz+ | ★ |
| shanhai | ⛰️山海鎮 | 土 | (沖位) | 化煞 | 700 | 6 | 負面事件−,鎮沖 | |
| windchime | 🎐五行風鈴 | 金 | 西 | 化煞人緣 | 300 | 5 | buzz+,鬧事− | |

(★=8 個 MVP:開運竹/發財樹/流水盆/龍龜/五帝錢/八卦鏡/財神像/鹽燈,涵蓋五行 + 五種效果類型)

---

## 10. UI（接既有面板）

- 主面板新增「風水」分頁:
  - 顯示 fengshui 分數、5 槽當前擺設(emoji 排成十字/環)、當季流年吉凶位、active blessings。
  - **換槽**:StringSelectMenu 選槽 → 選要放的已購家具;即時預覽分數增減。
  - **採購家具**:同設備採購流程。
  - **請老師**:選 tier + 服務 → ephemeral 確認費用/風險(江湖術士標警告)。
- customId 前綴 `mjt:fs:`;綁 ownerId;重讀 DDB 不信畫面(對齊 Phase 0)。

---

## 11. Phase 歸屬

- **Phase 1~2**:家具採購 + 5 槽擺設 + 五行/得位計分 + fengshui 進吸引力(核心手感)。
- **Phase 3**:風水老師 + 流年輪換 + 風水事件(併雙向事件系統)。
- 流年綁賽季(Phase 5 傳承 M5,傳家風水寶物)。

---

## 12. 驗收點（給 Codex）

1. config `catalogs.fengshui`/`fengshuiMasters` + `balance.fengshui` 可存/發佈/型錄編輯。
2. parlors 新增 fengshui/layout/fengshuiItems,新館 fengshui=20。
3. 採購家具扣款(含退款防呆)、放槽/搬槽正確、只能放已購。
4. 得位 ×1.5 / 失位(被剋)×0.5、相生相鄰 +、相剋相鄰 −、沖煞歸零,計分正確。
5. 流年財位 ×1.8、五黃位懲罰、化煞類鎮五黃反加成,換季重算。
6. fengshui 進吸引力 w9(大戶/雀友權重高可驗:同分佈局大戶佔比上升)。
7. 家具 effect(客單價/大戶吸引/化煞降鬧事/士氣)按得位加權套用結算。
8. 風水老師:勘輿回扣分點、化煞移除懲罰、擇日 buff、江湖術士 charlatanRisk 觸發破財。
9. 客人運氣感受:高 fengshui→客單價/回頭/buzz↑;低 fengshui+衰→鬧事↑。
10. 風水事件雙向觸發、動土/亂移/五黃/假老師懲罰、福地/貴人/財神獎勵。

---

## 13. Codex 審查修正併入(2026-07-11)

**A. 客層 key 固定英文(資料層)。** `w9ByClient` 及各權重表 key 用英文,中文只做 label:
**canonical 10 客群**(2026-07-11 由 5→10):`casual/regular/whale/tourist/student/elderly/mama/truant/roamer/novice`;皆正式客群、都進 clientMix。各客群 w9(fengshui)權重在 `balance.weights` 全 10 列(client list 資料驅動)。
`w9ByClient:{whale:0.35,regular:0.25,casual:0.10,tourist:0.08,student:0.03,elderly:0.40,mama:0.10}`。**👴高齡信風水最重(0.40,居全客群之冠)** → 風水系統與高齡社區地段強咬合;媽媽 0.10。

**B. 隨機效果必須 idempotent。** 風水事件觸發、江湖術士騙子判定、`luckSentiment` 運氣感受**不能每次結算/刷新就重抽**。用 **tick bucket + deterministic seed**(`hash(parlorId, bucketTs)`)或已處理區間記錄,只對新經過的 tick 判定一次。`fengshui` 分數本身由 layout 派生(純函數),重算安全;但由它**衍生的隨機事件**要鎖。

**C. 寫入安全(Phase 1 前置,與宣傳規格共用同一修正)。** `ParlorDAO.save()` 目前 `PutCommand` 整筆覆寫。搬風水家具、採購、結算並發時,stale item 會洗掉 `layout`/`fengshuiItems`。**Phase 1 前**改 `UpdateCommand` 局部更新或加 `revision/updatedAt` 條件寫入(宣傳+風水一起改)。

**D. 多分店拆分。** 未來連鎖(M2)時 `layout`/`fengshuiItems`/`fengshui` 要**跟著 `parlorId` 分拆**,不可沿用「一人一館」的單 PK 結構。設計 parlors 表時預留 `parlorId` 維度(對齊 Phase 1 `mahjong-tycoon-runs`/分店表規劃)。

---

## 14. 空間化升級(2026-07-11,使用者選「真實格子擺放」)

> 使用者定案店面採**坪數格子平面圖**(見 `CODEX_SPEC_floorplan.md`)。有平面圖後,本規格的**抽象 5 方位槽被真實格子方位取代**。以下段落對應調整:

- **§2 方位槽 → 平面圖方位**:不再是 5 個抽象槽。以 `door`/羅盤原點把平面圖分成 東/南/中/西/北**格子區域**(`balance.floor.orientation` 定義)。風水家具擺在**格子座標**上。
- **§4.1 得位**:家具擺在其 `nativeSlot` 對應的**格子區域**內 = 得位 ×1.5;擺在被剋區 = 失位 ×0.5。
- **§4.2 相生相鄰**:改為**平面圖上實際相鄰格**的風水家具構成五行生/剋 → 加/減(取代抽象環)。
- **§4.3 沖煞**:由平面圖幾何實判 — 鏡類(`bagua_mirror`)所在格正對 `door` 直線 = 漏財;水類/廁所設備壓在流年財位區 = 破財。勘輿老師掃出實際犯沖格子。
- **§5 流年**:財位/五黃/歲破改為每季指定的**格子區域**(整片區),非單槽。
- **§8.2 parlors**:`layout{方位槽→家具}` 併入 `floor.objects[]`(kind:'fengshui', 帶 x/y/rot);`fengshui` 分數仍由上式派生。家具新增 `footprint{w,h}` 與 `wallMount`(掛牆=0 格不佔平面,如鏡/風鈴/山海鎮/五帝錢/鹽燈)。**掛牆物仍要記幾何位置** `floor.wallItems[{itemId,x,y,side:'N|E|S|W'}]`(Codex 審查修正 #5),否則「鏡對門」沖煞判不準。
- **未接平面圖前的退路**:Phase 1 平面圖未上線前,可先用抽象 5 槽跑(本規格原文);平面圖上線後切換到格子方位。以 feature flag 控。

---

## 15. 周遭設施運勢 → effective 風水(2026-07-11,使用者「周遭設施影響運勢」)

館的**有效風水分 = layout 風水(§4)+ 地段運勢修正**:
```
locationFortune = Σ_facility( catalogs.surroundings[fid].fortuneMod )   # 該區 location.surroundings 逗號分隔 id
effectiveFengshui = clamp( layoutFengshui + balance.ambience.fortuneToFengshui × locationFortune , 0, 100 )
```
- 設施型錄 `catalogs.surroundings`(後台已上線):🏥醫院 fortuneMod−2 / ⛩️小私廟−2 / 🛕大廟+3 / ⚰️殯儀館−3 / 🌳公園+1 / 🏦銀行+1 / **🎰彩券行(新,2026-07-14)fortuneMod+1·moodMod+1**(旁有彩券行=賭運/求財氛圍,信風水客群小加持、全客群沾點手氣期待感;純周遭設施,不是館內服務,無非賭博疑慮) …
- **信風水客群(elderly/whale/regular,w9 高)最有感** → 選址旁邊有殯儀館/野廟,風水擺再好也被拖;旁有大廟則加持(但大廟 moodMod−2 心情吵,見 clientflow 心情軸)。
- effectiveFengshui 才是進吸引力 w9 的值。

---

## 16. 運氣傳染系統(2026-07-14,使用者點名 — 風水的「臨場放大器」)

> 使用者本意:運氣值主要為了**結合風水**——運氣低 → 客人反應差 → 影響生意/滋事。定案:①**不對稱傳染**(負>正)②**桌級為單位**(4人一桌)③**要熟客層**④**風水能抵抗到某上限、不無敵**⑤**衰神💀/財神🤑都做**。

### 16.1 定位:風水=結構基準,傳染=臨場浮動
- **風水(effectiveFengshui,§15)= 結構性運氣基準**,玩家長期經營的旋鈕,抬高「全桌起跑線」。
- **運氣傳染 = 每桌每晚會變的臨場浮動**。風水**壓制**衰神但**不免疫**(§16.4 上限)→ 逼玩家用座位/占卜/化煞臨場處置,風水不能一鍵通關。
- ⚠️ 本節**取代 §6 的聚合 `luckSentiment`**,升級為 per-customer + 桌級傳染模型;§6 簡化式保留為平面圖/桌級模型未上線前的 fallback(feature flag)。

### 16.2 客人運氣值 `luck`(成桌那刻算,0–100)
每個入桌客人一個隱藏 luck(散客臨時、常客持久,§16.6):
```
luckBase = clamp( 50
  + fengshuiLift(effectiveFengshui)     // §16.4,風水抬基準,吃上限
  + trait                                // 常客=持久 luckTrait / 散客=seededNoise 派生
  + goodsLuck                            // 該客持有/當次開運小物加成,§16.7,吃自己的上限
  + diviBuff                             // 占卜師對人 buff,§16.9,吃自己的上限
  + seededNoise(parlorId, tableId, bucketTs, seat)   // deterministic 雜訊,不現場亂數
, 0, 100)
```
- `effectiveFengshui` 已 fold layout+locationFortune(§15),**不重複加**。

### 16.3 桌級不對稱傳染(負>正)
一桌 4 座算一個偏向低端的「桌氣場」:
```
tableField = mean(luck) − negBias·(mean − min)      // negBias≈0.6(seed),往衰神偏
每座位 i:
  pull = (tableField < luck_i) ? contagionDown       // 被往下拖:強(≈0.5)
                               : contagionUp          // 被往上拉:弱(≈0.25)
  finalLuck_i = clamp( luck_i + pull·(tableField − luck_i) , 0, 100 )
```
→ **一個衰神拖垮全桌(0.5),一個財神只能溫和救場(0.25)**。係數全 seed 於 `balance.luck`。

### 16.4 風水抵抗上限 `fengshuiResistCap`(能抵抗、不無敵)
風水對「缺的運氣」最多補到一個上限點數:
```
fengshuiLift = min( fengshuiResistCap, (effectiveFengshui/100)·luckGainMax )
```
- 例 `fengshuiResistCap=+20`:運氣 10 的衰神,風水拉滿最多到 30 → **變好但仍是麻煩**,穿透上限的負值繼續走 §16.5 後果;財神(85)根本用不到。
- **極端衰神穿透上限** = 風水保平均盤、逼你動座位/占卜/化煞。

### 16.5 後果:低運氣 → 反應差(全接既有系統,不新造後果)
`finalLuck` 低 → 該客反應差,分流到既有管線(全走 deterministic,§16.10):
| 後果 | 接到 |
|---|---|
| 滋事機率↑ | `troubleRisk`(clientflow)→ 鬧事事件(**保全**壓) |
| 心情差→客單價/停留↓ | mood/ambience 係數(clientflow §6.8) |
| 負評湧入 | review driver → `catalogs.reviewChannels`(衰→刷 Threads/地標負評) |
| 回頭率↓ | returnProb → 熟客層(§16.6) |
- **高 finalLuck 反向**:客單價/回頭/buzz↑、更會買開運小物(upsell 正回饋,接 §P 店內銷售)。

### 16.6 衰神💀 / 財神🤑(一對鏡像常客,持久 luckTrait)
| | 💀 衰神 | 🤑 財神 |
|---|---|---|
| `luckTrait` | 持久低 | 持久高 |
| 傳染 | 負傳染強(拖全桌) | 正傳染弱(溫和抬桌,符合不對稱) |
| 招牌價值 | 反覆毒害的難題;**衰神大戶兩難**=留他進帳 vs 趕他乾淨+少負評 | 磁鐵:帶旺+大家想跟贏家同桌→拉湊咖/客流;配桌鎮爛咖 |
| 玩家處置 | 婉拒入場/隔離座位/化煞鎮那格/占卜揪出 | 招待(comp)、指定好位留住 |
- **逐次揭露**(沿用員工面試 tell):常客來 N 次後跳線索(「這位客人最近手氣…」),帶雜訊、逐步確定是衰神/財神。
- **衰神大戶**:數值上要能同時是高 spend + 低 luckTrait,撐起「留他還是趕他」的核心抉擇。

### 16.7 加成來源各自吃上限(防疊無敵)
風水(§16.4)、開運小物(§P)、占卜師(§16.9)三條加成來源**各有各的 cap 分開結算**,不可疊成「無敵衰神也能救」:
```
luckGain = min(fengshuiResistCap, fengshuiLift)
         + min(goodsLuckCap,      goodsLuck)
         + min(diviBuffCap,       diviBuff)
// 三者仍受 luckBase 的 clamp(...,0,100) 總封頂
```

### 16.8 熟客層資料模型(要設計)
- **散客**:luck 純 seededNoise 派生,散場即忘,不存。
- **常客 `parlors.regulars[]`**:上限陣列(如常來前 N=20~30 名,按 visitCount 汰換),每筆:
```jsonc
{ "customerId":"c_...", "clientType":"whale", "luckTrait": 12, "spendTier": 3,
  "visitCount": 7, "revealLevel": 2, "kind": "jinx|god|normal", "heldGoods": ["pixiu"] }
```
- ⚠️ **寫入走 `UpdateCommand`**(記憶/§13-C:ParlorDAO PutCommand 整筆覆寫會洗掉並發更新);roster 設上限避免 item 膨脹,長大再拆獨立表 `mahjong-tycoon-regulars`(PK=parlorId,SK=customerId)。
- 開運小物「持有中」:散客當次有效、**常客可持有累積**(寫 `heldGoods`,持久加成)。

### 16.9 占卜師 🔮(新顧問類,與風水老師平行)— config `catalogs.diviners`
解掉「運氣看不見」的盲點:
| 服務 | 效果 |
|---|---|
| **占卜揭露** | 揭示指定客人/常客的 `luckTrait` 與 kind(揪出衰神/財神);花錢買診斷 |
| **改運 buff** | 對單一客人下**臨時運氣 buff**(化煞的「對人版」,`diviBuff`,吃 §16.7 cap) |
| **開運駐場** | 常駐吸引運勢客群(elderly/whale)→ 客流/buzz↑ |
- 分級沿用**江湖術士 charlatanRisk**(可能誤報/亂改運)→ 準師傅。schema 仿 `catalogs.fengshuiMasters`(tier/cost/accuracy/charlatanRisk/cooldown)。

### 16.10 Determinism(必守,§13-B 同款鐵律)
所有 luck roll、傳染、衰神/財神揭露、占卜結果、抽籤結果**用 `hash(parlorId, tableId, bucketTs, seat)` seed**,不現場亂數;常客 `luckTrait` 一經生成即持久(不重抽)。防玩家狂點刷新重抽運氣。

### 16.11 config / parlors 新增
- config:`catalogs.diviners`(占卜師)、`balance.luck`(negBias/contagionUp/Down/fengshuiResistCap/luckGainMax/goodsLuckCap/diviBuffCap/衰神財神生成率/揭露門檻)。
- parlors:`regulars[]`(§16.8)。

### 16.12 驗收點(給 Codex)
1. luckBase 由 effectiveFengshui+trait+goods+divi+seededNoise 派生,同輸入→同輸出(狂刷不變)。
2. 桌級不對稱傳染:同一衰神令全桌 finalLuck 下拉幅度 > 同級財神上抬幅度。
3. 風水抵抗上限:高 fengshui 也無法把 luck 10 衰神拉過 `fengshuiResistCap`,穿透部分仍觸發 §16.5 後果。
4. 三加成來源各自吃 cap,無法疊成無敵。
5. 低 finalLuck → troubleRisk/負評 driver/回頭↓,高 → 客單價/buzz/開運小物銷量↑。
6. 衰神/財神常客持久、逐次揭露(revealLevel 遞增、帶雜訊)、衰神大戶兩難數值成立。
7. regulars 走 UpdateCommand、上限汰換、heldGoods 持有加成(常客持久/散客當次)。
8. 占卜師揭露/改運 buff/駐場、江湖術士 charlatanRisk 誤報。
