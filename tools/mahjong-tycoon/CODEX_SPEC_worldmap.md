# 模擬麻將館 — 世界地圖規格(天王里選點圖)

> 對象:Codex 驗證/實作 + Claude 手動接圖。設計:Claude(2026-07-16)。
> 依附:`DESIGN.md` §2.1/§2.1.1(天王里正典地理/terrain)、§13(共用地圖)、§17/`CODEX_SPEC_climate.md`(天候 overlay)、`CODEX_SPEC_clientflow.md`(客層/地段)、`CODEX_SPEC_backend.md`(config districts section)、`CODEX_SPEC_floorplan.md`(**另一層**店面圖,勿混)。
> 既有實作:**`sweetbot-next/model/miniGame/MahjongMap.js`(134 行,已上線 d8ea4e7)**——本規格**建構在此引擎之上、不重造**,只補正典地理 + 河流/地勢/天氣疊層 + 戰況板。
> 定位:天王里**選點圖**(一格=一行政區,選在哪開館)。**≠ 店面平面圖**(`CODEX_SPEC_floorplan.md`,一格=一坪,擺桌用)。

---

## 0. 一句話

世界地圖 = **一張資料驅動的 emoji 網格**:config `districts[]` 的 `mapPos` 定座標、`terrain` 定地勢、程式 `MahjongMap.js` 畫格子 + 游標導航。在既有引擎上加三件:**①天王里正典地理(天王溪 + 地勢定死)②河流/地標 feature 疊層 ③天候 + 戰況 overlay**。選點 = 選這間店「永久的天氣體質 + 客層 + 租金」。

---

## 1. 兩層地圖分野(先講清楚,本規格只管 Layer 1)

| | **Layer 1 · 世界地圖(本規格)** | Layer 2 · 店面平面圖(`CODEX_SPEC_floorplan.md`) |
|---|---|---|
| 一格 | 一個行政區 | 一坪 |
| 看什麼 | 天王里全區,**選在哪開館** | 店內,**怎麼擺桌/設備/風水** |
| 程式 | `MahjongMap.js`(已上線) | `MahjongFloorPlan.js`(待做) |
| Phase | Phase 0 選點已用 / Phase 2 戰況板 | Phase 1 |

- 兩層共用同一套做法(config 定座標 + 程式畫 emoji 格 + 游標導航),但**是兩個模組、兩張圖**,勿硬併。

---

## 2. 既有引擎盤點(`MahjongMap.js`,建構在此之上)

現況(**已上線、Phase 0 選點在用**):
- `MAP_W=5 / MAP_H=5` 五乘五網格;`TILE_EMPTY='⬜'`(街廓空地)、`TILE_CURSOR='📍'`(游標)。
- **每格剛好一個全形 emoji**(修過 cursor 疊區域格變兩 emoji 的對齊 bug);列以單一空白分隔。
- `layout(districts)` → `{id:{x,y}}`:座標**優先吃 `district.mapPos`(後台可設)→ 再固定表 `DEFAULT_POSITIONS` → 再 `AUTO_POSITIONS` 自動落位**(避已用格)。
- `render(districts, cursor)`:優先序 **cursor > district.emoji > 空地**。
- `districtAt / clampCursor / canMove / moved`:游標落區判定 + 方向鍵邊界 disable。
- **資料驅動**:引擎不寫死區,全讀 config。
- 🔴 **待訂正**:`DEFAULT_POSITIONS` 只有舊 3 區 `night_market/office/alley`(英文 id,便利商店時代),與 §2.1.1 天王里正典區、CONTENT 6 區都對不上 → 見 §9 開放待決。

**本規格擴充引擎的四點**(§5 細述):① feature 疊層(河流/地標)② 我的館/對手標記 ③ 天氣 + 戰況 status list ④ 正典 mapPos/terrain 灌 config。**皆向後相容**:不改既有 `layout/render` 呼叫端就退化成現況。

---

## 3. 天王里正典地理(§2.1.1 落成 config)—— **定案 🅱:保留既有 6 區、每區補 terrain+mapPos**

**一張圖、全服共用、相對位置與地勢建圖時定死**(不是 RNG,讓玩家看懂「為什麼我這區先淹」)。天王溪貫穿;§2.1.1 的三個地勢極端軸(溪畔/舊城市場/海線)**實現為既有 6 區中最合適的 3 個**,其餘 3 區給梯度地勢。**不動已上線 clientMix,只加 `mapPos`+`terrain`。**

| id(已上線) | name | emoji | 相對位置 | 建議 mapPos | flood | wind | heat | 租金 | 地勢原型 / 玩點 |
|---|---|---|---|---|---|---|---|---|---|
| `night_market` | 夜市邊 | 🏮 | 中央・密集老街 | `{2,2}` | med | low | **high** | 中(80) | **舊城市場原型**·最旺·酷暑冷氣最兇 |
| `alley` | 社區巷弄 | 🏘️ | 西南・臨溪低窪 | `{1,3}` | **high** | low | med | **低(45)** | **溪畔原型**·最便宜但豪雨先淹→逼抽水機 |
| `redevelopment` | 重劃區 | 🏙️ | 東・開闊臨海 | `{4,2}` | low | **high** | low | 高(130) | **海線原型**·空曠好停車·颱風招牌掉/停電→防風+發電機 |
| `office` | 商辦區 | 🏢 | 北・高地商業 | `{2,0}` | low | med | med | 最高(150) | 高地安全·玻璃帷幕曬·最貴 |
| `school` | 學校旁 | 🎓 | 西・河岸校區 | `{0,2}` | med | med | low | 中(90) | 校園綠地·近溪有堤 |
| `elderly_community` | 高齡社區 | 👴 | 南・老社區坡 | `{2,4}` | med | low | med | 低(55) | 老社區·地勢溫和 |

- **天王溪** = feature 疊層(§4),🌊 tile 沿西南角 `(0,4)(1,4)(0,3)` 緊貼溪畔(`alley`),讓「臨溪低窪先淹」一眼看懂。
- **地勢極端各只一個**(flood→alley/wind→redevelopment/heat→night_market),避免多區同災、選址差異模糊;其餘三區 med 梯度。
- mapPos/terrain 皆 **config 可調**(後台「地圖區域」每區編);上表為建議正典初值。
- 參考渲染(5×5,🏠= 玩家已開館時疊):
```
    x0    x1    x2    x3    x4
y0  ⬜    ⬜   🏢商辦 ⬜    ⬜
y1  ⬜    ⬜    ⬜    ⬜    ⬜
y2 🎓學校 ⬜  🏮夜市  ⬜  🏙️重劃
y3 🌊    🏘️巷弄 ⬜    ⬜    ⬜
y4 🌊    🌊  👴高齡  ⬜    ⬜
```
- 5×5 容 6 區 + 河流綽綽有餘;擴充池(車站/溫泉,CONTENT §A)之後用剩餘格 + `AUTO_POSITIONS`。

---

## 4. 資料模型

### 4.1 config `districts[].{mapPos, terrain}`(既有 section 加欄位,非新表)
```jsonc
{ "id":"riverside", "name":"溪畔區", "emoji":"🌊",
  "mapPos": { "x":1, "y":3 },
  "terrain": { "floodRisk":"high", "windExposure":"low", "heatIsland":"med" },
  "baseFlow":..., "clientMix":{...10鍵...}, "rentLevel":..., "riskLevel":..., "location":{...} }
```
- `terrain` 已由 climate/DESIGN §2.1 定義,**worldmap 與 climate 共用同一份**(§10.2 of climate);此處只負責**上到地圖 + 渲染**。

### 4.2 config `balance.worldmap`(新,地圖靜態 feature + 圖例)
```jsonc
balance.worldmap = {
  size: { w:5, h:5 },                          // 覆寫引擎 MAP_W/H(可選,預設沿用 5×5)
  features: [                                  // 河流/地標靜態疊層(非行政區、不可選)
    { x:0, y:4, tile:"🌊", label:"天王溪" },
    { x:1, y:4, tile:"🌊" }, { x:0, y:3, tile:"🌊" }
  ],
  legend: { floodRisk:"🌊", windExposure:"💨", heatIsland:"🔥" }   // status list 用
}
```
- **features = 純視覺 + 敘事**,不參與選點/結算(踩到 river tile 的格不是行政區、游標可經過但 `districtAt` 回 null)。
- 無新 DDB 表;`mahjong-tycoon-config` 既有 `balance` section 加 `worldmap` 鍵即可。

---

## 5. 渲染擴充(`MahjongMap.js` 向後相容加參數)

`render(districts, cursor, opts?)` 的 `opts` 新增可選欄位;不傳 = 現況。**格子優先序(高→低)**:
```
📍 cursor  >  🏠 我的館(myParlorPos)  >  🎯 對手標記(rivals, Phase2)  >  district.emoji  >  feature.tile(河流/地標)  >  ⬜ 空地
```
- `opts.features`(來自 `balance.worldmap.features`):底層河流/地標。
- `opts.myParlorPos`:玩家已開館的區 → 疊 🏠(一眼看到自己在哪)。
- `opts.rivals`(Phase 2):對手 NPC/玩家館密度 → 疊標記或熱度色階(emoji 無底色 → 用強度 emoji 如 🔴🟠🟡 或數字)。
- **天氣不畫在格子上**(一格一 emoji 塞不下)→ 走 §6 status list。

### 5.1 地圖下方 status list(embed 一欄,取代格上塞資訊)
grid 之下附每區一行,把選點要看的資訊攤開:
```
🌊 溪畔區  ·🌊high 💨low 🔥med ·租低 ·今:🌧️大雨 ·⚠️淹水中
🏙 舊城市場·🌊med 💨low 🔥high·租高 ·今:☀️晴
🌾 海線開闊·🌊med 💨high🔥low ·租中 ·今:⛅多雲
```
- terrain 用 `balance.worldmap.legend` icon;天氣/事件來自 §6。游標所在區可高亮(►前綴)。

---

## 6. 天候 overlay(接 `CODEX_SPEC_climate.md` §4)

- 每區當前天氣 = `effectiveWeather(districtId, now)`(climate §4:真實層 active 則全區同 type、後果看 terrain;否則模擬層各區獨立)。
- 地圖 status list(§5.1)每區顯示:**今日天氣 icon + 進行中 `activeEvents[]` 橫幅**(🌊淹水/🪧招牌/🔌停電/💧漏水)。
- **真實層颱風警報**:地圖頂加全服橫幅(「⚠️颱風警報·全里戒備」),呼應 climate §6 颱風假樂透。
- 天氣 icon 對照 climate 天氣型別:☀️clear/⛅cloudy/🌦️lightRain/🌧️heavyRain/🌫️plumRain/❄️coldWave/🔥heatWave/🌀typhoon。
- 只讀 climate 的 `effectiveWeather` + `parlor.weather.activeEvents`,**worldmap 不自算天氣**(單一真相源)。

---

## 7. 互動

- **Phase 0(已上線)選點開館**:方向鍵移 📍 游標(`canMove` 邊界 disable)→ 落在空區 → 確認開館(`districtAt` 取該區 terrain/clientMix/租金寫進 parlor)。customId 前綴 `mjt:map:`,末段放 ownerId 守門(仿既有面板)。
- **已開館後看地圖**:游標可自由逛,自己的區疊 🏠;選點面板變「看戰況」(唯讀)。
- **Phase 2 戰況板**:同區多間館 → 顯示對手密度/熱度、可作為削價/踢館目標入口(接 §J 對抗);地圖從「選點器」升級成「動態戰況板」。

---

## 8. 世界 tick(地圖是動態,非靜態背景)

接 DESIGN §2.4 世界 tick(5–15 分低頻)——地圖每 tick 可能變:
- 區域 `heat` 熱度波動 → 帶動 `rentLevel` 租金(熱區變貴,逼成長/外擴)。
- 對手 NPC 進駐/退場(Phase 2)。
- 全服天候事件推進(真實層警報起落 → 頂部橫幅變化)。
- **渲染即時反映**:玩家每次開地圖都重讀 config + climate 狀態,不快取過期畫面(重讀不信畫面,同既有慣例)。

---

## 9. 行政區身分統一(**已定案 🅱,2026-07-16 使用者選**)

**背景**:曾三套命名並存——CONTENT §A 已上線 6 區(夜市邊/商辦/巷弄/學校旁/高齡社區/重劃區)、§2.1.1 天候正典 3+1 區(溪畔/舊城/海線/高地)、引擎 `DEFAULT_POSITIONS` 舊 3 區 id。

**定案 🅱 = 保留既有 6 區、每區補 `mapPos`+`terrain`**(不收斂成 3、不遷 clientMix):
- 6 區 **id/name/emoji/clientMix 全維持已上線值不動**(零 clientMix 遷移風險)。
- §2.1.1 三地勢原型(溪畔/舊城市場/海線)**降為 terrain 標籤**,實現在 3 個既有區上(alley/night_market/redevelopment,§3 表);不再是獨立行政區名。
- 🏔 高地重劃**不另立**(重劃區 redevelopment 已在圖上當海線原型);北高地位置給 office 商辦。
- **實作觸點(Phase 1,皆走 config、不改結算邏輯)**:
  1. config `districts[]` 6 區各補 `mapPos`+`terrain`(§3 表)→ 走後台 SEED / 「地圖區域」編輯,寫進 `mahjong-tycoon-config`。
  2. 引擎 `MahjongMap.js` 的 `DEFAULT_POSITIONS` 更新成 6 區真 id 的正典座標(§3),當 config 沒設 mapPos 時的 fallback(**非阻塞**:一旦 config 有 mapPos 就覆蓋它)。
- **零 migration 破壞**:只加欄位,舊資料缺 `terrain`/`mapPos` 時 → terrain 視為全 med(climate fallback)、mapPos 走 DEFAULT/AUTO 落位,不報錯。

---

## 10. 區域生命週期(加 / 調 / 停用 / 下架 + 孤兒館防呆)

地圖**資料驅動 → 加區、調區是後台常態操作,引擎零改動**。四種變更 × 安全等級 × 對「已在該區開館的玩家」的處理:

### 10.1 ➕ 加區(安全,後台現成)
- 後台「地圖區域」有**新增區域鈕**(push 一筆 district 草稿)。填 `id/name/emoji/clientMix(10鍵)/rentLevel/riskLevel/baseFlow/terrain/location`;`mapPos` 不填 → 引擎 `AUTO_POSITIONS` 自動落位。
- 天候/客流/風水**自動套用新區**(全資料驅動,無需改遊戲端公式)。
- 可綁**解鎖 gate**(`unlockLevel` 老闆等級 / `season` 賽季)→ 高階或檔期才開的新區(CONTENT §A 擴充池 車站/溫泉同理)。
- 盤面不夠 → 調 `balance.worldmap.size`(5×5→6×6…),引擎讀 config 尺寸。

### 10.2 🔧 調區(數值即時生效,重大改動要公告)
- 任何欄位後台可編、草稿→發佈兩段式;發佈後 bot 讀取(30–60s 快取 or 重啟保證,見 [[reference_change_effect_cheatsheet]])。
- `clientMix/rentLevel/riskLevel/baseFlow/location/surroundings` 調整 → 下次結算即套用,安全。
- 🔴 **`terrain` / 大幅租金 屬「玩家選址時的承諾」**:玩家開館時是衝著「這區的天氣體質/租金」來的,中途暗改觀感差 → 建議**重大地勢/租金變更走公告 + 生效緩衝**(非硬性,但列為運營守則)。

### 10.3 ⏸️ 停用區(`enabled:false`,安全下架的預設手段)
- **新玩家不可選**(選點面板/`districtAt` 開館流程過濾 `enabled:false`)。
- **既有館照常營運**(不動 parlor);地圖仍渲染該區但**淡化顯示**(如加註 🚫/灰底 legend),讓該區館主看得到自己的 🏠。
- 這是「想收掉一區」的**首選**——零資料破壞、可隨時再 `enabled:true` 復活。

### 10.4 🗑️ 硬刪區 + 孤兒館政策(**需拍板的唯一子項**)
- **預設鐵律:該區有 active parlor 時，後台刪除鈕擋下**(先查綁定館數 > 0 → 不准硬刪,提示改用 §10.3 停用 / §10.4 封存)。避免 parlor `districtId` 指向不存在的區變孤兒。
- 真要徹底下架 → 走**「封存搬遷」流程**(推薦預設,數值 seed 可調):
  1. 區標 `retiring:true` + 寬限窗 `balance.worldmap.retireGraceDays`(seed,如 7 天,真實 1:1)。
  2. 期間該區館主收通知,二選一:**遷館**(保留 等級/金庫/stats/成就,換 `districtId` + 重置 floorplan 綁定與 terrain 體質,類似軟性「搬家」非破產)/ **領補償關店**(退等值牙齒到個人錢包)。
  3. 寬限結束仍未處理 → 系統**自動補償關店**(退 seed 比例牙齒),再從 config 移除該區。
- 🅰 遷館 / 🅱 補償關店 的**補償公式與寬限天數 = seed 待定**(唯一開放旋鈕);流程骨架如上先定。

### 10.5 孤兒館防呆(遊戲端 fallback,硬要求)
- 遊戲端讀 parlor 時 `districtId` **不在 config**(被刪/改名/資料異常)→ **不可崩**:terrain 視為全 med、clientMix/租金用**通用預設或該 parlor 快照的最後已知值**、地圖標記回退,面板提示「此區已調整」。
- 呼應 §9:缺 `terrain`/`mapPos` 一律有 fallback(med / AUTO),讀取端永不因區資料變動而掛。

---

## 11. Phase 歸屬

- **Phase 0(已上線)**:選點引擎 `MahjongMap.js` + 方向鍵選區開館。
- **Phase 1**:正典地理落 config(§3 mapPos/terrain)+ 天王溪 feature 疊層(§4/§5)+ 我的館 🏠 標記 + status list(terrain 先顯示,天氣欄留空)。**先把 §9 身分統一拍板**再灌。
- **Phase 2**:戰況板(對手密度/熱度色階)+ 選點→對抗入口。
- **Phase 3**:天候 overlay 接上(§6,隨 climate 本體)——天氣 icon/災害橫幅/颱風全服橫幅。
- **生命週期(§10)**:加區/調數值/停用 = 後台能力,**Phase 1 隨資料層即可用**;🗑️封存搬遷 + 遷館/補償(§10.4)較重,排 **Phase 3+**(牽動 parlor 搬遷與補償結算);孤兒館 fallback(§10.5)**Phase 1 就要有**(讀取端防呆是硬要求)。

---

## 12. 驗收點(給 Codex)

1. **向後相容**:`render(districts, cursor)` 不傳 `opts` 時輸出與現況一致(既有 Phase 0 選點不迴歸)。
2. **正典地理**:6 區依 `mapPos` 落在天王里正確相對位置(§3:夜市中央/巷弄西南臨溪/重劃東/商辦北/學校西/高齡南);`terrain` 值同 §3 表、地勢極端各只一區(flood→alley/wind→redevelopment/heat→night_market)。
3. **feature 疊層**:天王溪 🌊 tile 依 `balance.worldmap.features` 畫在游標/區之下、空地之上;river 格 `districtAt` 回 null(不可選、不參與結算)。
4. **格子優先序**:cursor > 我的館 🏠 > 對手 > district > feature > 空地,每格仍剛好一個全形 emoji(對齊不破)。
5. **status list**:每區一行顯示 terrain(legend icon)+ 租金 +(Phase 3)天氣 icon + activeEvents 橫幅;游標區高亮。
6. **天候單一真相源**:天氣/事件只讀 climate `effectiveWeather` + `parlor.weather.activeEvents`,worldmap 不自算。
7. **資料驅動**:size/features/legend/mapPos/terrain 全讀 config,無寫死;缺 `balance.worldmap` 時退化成純 5×5 無河流(不報錯)。
8. **互動守門**:選點/看地圖 customId 帶 ownerId,非 owner 點 → ephemeral 擋;開館重讀 DDB 不信畫面。
9. **§9 身分統一(🅱)**:6 區 clientMix 維持不動、只加 mapPos+terrain;引擎 `DEFAULT_POSITIONS` 更新成 6 區真 id 正典座標;無孤兒 id;缺 terrain/mapPos 時 fallback(med/AUTO)不報錯。
10. **加/調/停用(§10.1–10.3)**:後台新增區草稿→發佈後遊戲端讀到新區(引擎無改動);`enabled:false` 區新玩家選不到但既有館照跑、地圖淡顯示;數值調整下次結算生效。
11. **下架防呆(§10.4–10.5)**:有 active parlor 的區硬刪被擋(改走停用/封存);孤兒館(districtId 不在 config)遊戲端**不崩**、terrain 退 med、面板提示;封存搬遷寬限/補償走 seed。

---

## 💰 成本控管(遵循 tools/COST_CONTROL.md)

- **成本來源**:純前端渲染(Discord embed 文字)+ config `districts[].mapPos/terrain`、`balance.worldmap` = 既有 `mahjong-tycoon-config` 表加欄位,流量無明顯變化。**無新表、無 LLM、無付費 API**。
- 天候 overlay 只**讀** climate 既算好的 `effectiveWeather`,不新增運算/儲存成本。
- 所有既有表維持 `PAY_PER_REQUEST`;emoji 素材(桌/區 tile)走既有金庫產線([[reference_sweetbot_emoji_pipeline]]),Phase 0 用 unicode fallback。故**免帳本封頂**。
