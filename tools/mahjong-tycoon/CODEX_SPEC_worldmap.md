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

## 3. 天王里正典地理(§2.1.1 落成 config)

**一張圖、全服共用、相對位置與地勢建圖時定死**(不是 RNG,讓玩家看懂「為什麼我這區先淹」)。天王溪貫穿,MVP 3 區各占一地勢極端軸:

| 行政區 | id(建議) | 相對位置 | 建議 mapPos | `floodRisk` | `windExposure` | `heatIsland` | 租金 | 玩點 |
|---|---|---|---|---|---|---|---|---|
| 🌊 溪畔區 | `riverside` | 西南・臨溪低窪 | `{x:1,y:3}` | **high** | low | med | 低 | 便宜但豪雨先淹→逼抽水機 |
| 🏙 舊城市場區 | `oldtown` | 中央・密集老街 | `{x:2,y:2}` | med | low | **high** | 高 | 最旺最貴,酷暑冷氣最兇 |
| 🌾 海線開闊區 | `seaside` | 東・臨海空曠 | `{x:4,y:2}` | med | **high** | low | 中 | 颱風招牌掉/停電→逼防風+發電機 |
| 🏔 高地重劃(擴充) | `highland` | 北・高地 | `{x:2,y:0}` | low | med | low | 最高 | 安全又新(留 M2/連鎖) |

- **天王溪** = feature 疊層(§4),一串 🌊 tile 沿西南斜貫、繞過溪畔區,讓「臨溪低窪」一眼看懂。
- mapPos/terrain 皆 **config 可調**(後台「地圖區域」每區編);上表為建議正典初值,Codex/Claude 灌入。
- 5×5 對 3–4 區綽綽有餘;之後擴區用剩餘格 + `AUTO_POSITIONS`。

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

## 9. 🔴 開放待決:行政區身分統一(需使用者拍板)

**三套命名並存,MVP 前必須收斂一套**:
| 來源 | 區列 |
|---|---|
| CONTENT §A(後台已上線 6 區) | 🏮夜市邊 / 🏢商辦 / 🏘️巷弄 / 🎓學校旁 / 👴高齡社區 / 🏙️重劃區(+擴充 車站/溫泉) |
| §2.1.1 天候正典(3+1) | 🌊溪畔 / 🏙舊城市場 / 🌾海線 / 🏔高地重劃 |
| 引擎 `DEFAULT_POSITIONS` | `night_market / office / alley`(舊英文 id) |

- **Claude 建議(推薦路徑)**:以 **§2.1.1 天王里正典為準**(最新定案、且 terrain 是地圖教學點),**MVP 收斂成 3 區**,每區**融合「客層味 + 地勢軸」**:
  - 🏙 舊城市場 = 老街市場熱鬧(吃 夜市/散客/游擊/雀友 clientMix)+ heat high
  - 🌊 溪畔 = 平價老社區(吃 高齡/媽媽/散客)+ flood high
  - 🌾 海線 = 空曠好停車(吃 觀光/大戶/開車客)+ wind high
  - 🏔 高地重劃、🎓學校旁等 = Phase 2 擴充區,放地圖剩餘格。
- **代價/需確認**:後台 config **已上線 6 區**(clientMix 已調)→ 收斂成 3 需**config migration + clientMix 重併**(把 6 區客層合進 3 區),且引擎 `DEFAULT_POSITIONS` 要換成新 id。**這動到已部署資料,故必須先拍板**。
- **替代方案**:保留 6 區,每區補 `mapPos`+`terrain` 各放天王里地圖一格(溪畔/舊城/海線當其中 3 個的地勢原型)——不動 clientMix、遷移小,但地圖區較多、terrain 教學不如 3 區乾淨。
- 🅰 收斂 3 區(推薦,乾淨但要遷 config) / 🅱 保留 6 區補 terrain(遷移小但較雜) → **待使用者選**。

---

## 10. Phase 歸屬

- **Phase 0(已上線)**:選點引擎 `MahjongMap.js` + 方向鍵選區開館。
- **Phase 1**:正典地理落 config(§3 mapPos/terrain)+ 天王溪 feature 疊層(§4/§5)+ 我的館 🏠 標記 + status list(terrain 先顯示,天氣欄留空)。**先把 §9 身分統一拍板**再灌。
- **Phase 2**:戰況板(對手密度/熱度色階)+ 選點→對抗入口。
- **Phase 3**:天候 overlay 接上(§6,隨 climate 本體)——天氣 icon/災害橫幅/颱風全服橫幅。

---

## 11. 驗收點(給 Codex)

1. **向後相容**:`render(districts, cursor)` 不傳 `opts` 時輸出與現況一致(既有 Phase 0 選點不迴歸)。
2. **正典地理**:3+1 區依 `mapPos` 落在天王里正確相對位置(溪畔西南/舊城中央/海線東/高地北);`terrain` 值同 §2.1.1/climate。
3. **feature 疊層**:天王溪 🌊 tile 依 `balance.worldmap.features` 畫在游標/區之下、空地之上;river 格 `districtAt` 回 null(不可選、不參與結算)。
4. **格子優先序**:cursor > 我的館 🏠 > 對手 > district > feature > 空地,每格仍剛好一個全形 emoji(對齊不破)。
5. **status list**:每區一行顯示 terrain(legend icon)+ 租金 +(Phase 3)天氣 icon + activeEvents 橫幅;游標區高亮。
6. **天候單一真相源**:天氣/事件只讀 climate `effectiveWeather` + `parlor.weather.activeEvents`,worldmap 不自算。
7. **資料驅動**:size/features/legend/mapPos/terrain 全讀 config,無寫死;缺 `balance.worldmap` 時退化成純 5×5 無河流(不報錯)。
8. **互動守門**:選點/看地圖 customId 帶 ownerId,非 owner 點 → ephemeral 擋;開館重讀 DDB 不信畫面。
9. **§9 身分統一**:依拍板結果,config 區列與引擎 `DEFAULT_POSITIONS` 一致、無孤兒 id;若走 🅰 附 migration。

---

## 💰 成本控管(遵循 tools/COST_CONTROL.md)

- **成本來源**:純前端渲染(Discord embed 文字)+ config `districts[].mapPos/terrain`、`balance.worldmap` = 既有 `mahjong-tycoon-config` 表加欄位,流量無明顯變化。**無新表、無 LLM、無付費 API**。
- 天候 overlay 只**讀** climate 既算好的 `effectiveWeather`,不新增運算/儲存成本。
- 所有既有表維持 `PAY_PER_REQUEST`;emoji 素材(桌/區 tile)走既有金庫產線([[reference_sweetbot_emoji_pipeline]]),Phase 0 用 unicode fallback。故**免帳本封頂**。
