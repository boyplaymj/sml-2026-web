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
`散客=casual / 雀友=regular / 大戶=whale / 觀光客=tourist / 學生=student`。
上文 `w9ByClient:{whale:0.35,regular:0.25,casual:0.10,tourist:0.08,student:0.03}`。

**B. 隨機效果必須 idempotent。** 風水事件觸發、江湖術士騙子判定、`luckSentiment` 運氣感受**不能每次結算/刷新就重抽**。用 **tick bucket + deterministic seed**(`hash(parlorId, bucketTs)`)或已處理區間記錄,只對新經過的 tick 判定一次。`fengshui` 分數本身由 layout 派生(純函數),重算安全;但由它**衍生的隨機事件**要鎖。

**C. 寫入安全(Phase 1 前置,與宣傳規格共用同一修正)。** `ParlorDAO.save()` 目前 `PutCommand` 整筆覆寫。搬風水家具、採購、結算並發時,stale item 會洗掉 `layout`/`fengshuiItems`。**Phase 1 前**改 `UpdateCommand` 局部更新或加 `revision/updatedAt` 條件寫入(宣傳+風水一起改)。

**D. 多分店拆分。** 未來連鎖(M2)時 `layout`/`fengshuiItems`/`fengshui` 要**跟著 `parlorId` 分拆**,不可沿用「一人一館」的單 PK 結構。設計 parlors 表時預留 `parlorId` 維度(對齊 Phase 1 `mahjong-tycoon-runs`/分店表規劃)。
