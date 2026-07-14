# 模擬麻將館 — 坪數制平面圖系統規格

> 對象:Codex 驗證/實作。設計:Claude(2026-07-11)。深度=真實格子擺放(使用者選)。
> 依附:`DESIGN.md`、`CONTENT.md`、`CODEX_SPEC_fengshui.md`(方位槽→平面圖方位,本規格同步升級)。
> 定位:店面 = 坪數格子平面圖,擺桌/設備/風水都在同一張圖上搶格子 → 容客量、租金、風水方位全部空間化。
> 幣別:牙齒🦷。數值 = 後台可調 seed。

---

## 0. 一句話

店面是 **W×H 格的平面圖**(1 格 = 1 坪)。玩家把**麻將桌組 / 設備 / 風水家具**當圖章擺上去,受**不重疊 + 走道連通**約束;容客量 = 擺得下幾組桌,租金 = 坪數 × 區域租金,風水得位/沖煞 = 真實格子方位判定。

---

## 1. 網格與單位

- **1 格 = 1 坪**。店面 = `w × h` 格,`area = w·h`。
- 店面大小由 config `catalogs.storeSizes` 定義(小 3×3=9 / 中 4×5=20 / 大 5×8=40 / 旗艦 7×9=63),開館選一種;可花 `cost` 牙齒**擴店**(換更大規格,保留已擺設備盡量沿用座標,放不下的退回倉庫)。
- `門口(door)` = 固定一格(預設下緣中央),是走道連通的起點。

## 2. 物件 = 圖章(stamp)

每個可擺物件有 `footprint{w,h}`(佔幾格)、`rot`(旋轉 0/90/180/270)、座標 `(x,y)`(左上角格)。
- **麻將桌組**:預設 `2×2`(= 桌 1 坪 + 4 座 ×0.5 + 走道分攤 1 = 4 坪);座位半坪的帳折進 footprint(拆分係數在 `balance.floor`)。VIP 包廂桌 `3×2`。
- **設備**(Phase 1 equipment/services):各有 footprint(櫃檯/廚房/廁所/冰箱…)。
- **風水家具**:`wallMount:true` 的(鏡/風鈴/山海鎮/五帝錢/鹽燈)= **0 格掛牆/桌上**,不佔平面;其餘佔 `footprint`(魚缸 1×2,其餘 1×1)。
- **裝潢/牆面**:貼牆不佔格。

## 3. 擺放規則(深度來源)

1. **不可重疊**:圖章佔的格子不能與其他非牆掛物件或牆體重疊、不可超出店界。
2. **走道連通(硬規則)**:從 `door` 出發,經**空格(走道)**用 4 向連通,必須能到達**每一組桌與每個需操作的設備所在圖章的相鄰格**。走不到的桌 = **停用(不計容客量、不產收)**。→ 塞太滿把走道塞斷會反傷。
3. **最小走道寬** `minAisleWidth`(預設 1 格):可選進階約束(要求主通道連續空格寬度)。MVP 先只做「連通」,寬度留參數。
4. 擴店/搬遷時重跑一次規則,失格物件退倉。

## 4. 容客量 / 租金 / 坪效

```
可用桌組 = 通過「連通」檢查且未被設備擠掉的桌組數
容客量   = 可用桌組 × seatsPerTable(4)
租金/tick = districtRentLevel × area × storeSize.rentMult
坪效     = 期營收 / area   (排行榜/成就可用)
```

## 5. 擁擠度 → 舒適 / 風險

```
density = 已佔格(含桌/設備/佔地風水) / area
```
- `density > crowdComfortThreshold`(0.75):環境舒適↓、**大戶吸引↓**(最敏感)、鬧事/意外/消防檢舉機率↑。
- `density < ` 過低:舒適↑但租金浪費、坪效差。
- 甜蜜點 `sweetSpotDensity`(0.6)附近給環境小加成。→ 留白 vs 塞桌的張力。

## 6. 風水空間化(升級 fengshui 規格,取代抽象 5 槽)

> 原 `CODEX_SPEC_fengshui.md` 的「5 方位槽」在有平面圖後改為**真實格子方位**。fengshui 規格 §2/§4/§5 對應更新(見該檔更新段)。

- **方位判定**:以 `door` / 羅盤原點把平面圖分成 東/南/中/西/北 區域(`balance.floor.orientation` 定義哪邊是哪方位)。
- **得位**:風水家具擺在其 `nativeSlot` 對應的**格子區域** → 得位 ×1.5(§fengshui §4.1);擺錯區/被剋區 → 失位 ×0.5。
- **相生相鄰**:改為**格子上實際相鄰**的風水家具構成五行生/剋關係 → 加/減分(取代抽象環)。
- **沖煞(真格子)**:
  - 鏡類(`bagua_mirror`)所在格**正對 door 那一直線** → 漏財沖煞(slotScore 歸零 + 風水衰事件率↑)。
  - 廁所/水類設備壓在**流年財位區** → 破財。
  - `taboo` 由平面圖幾何判定(勘輿老師掃出實際犯沖的格子)。
- **流年財位/五黃位** = 每季指定的**格子區域**(非單槽),整片區加成/懲罰。

## 7. 資料模型

### 7.1 config(後台已建,Fable 併入)
- `catalogs.storeSizes`:`{id,name,w,h,area,cost,rentMult}`。
- `catalogs.tables[].footprint{w,h}`;`catalogs.fengshui[].footprint{w,h}` + `wallMount`;(Phase1)`equipment[].footprint`。
- `balance.floor`:`{ cellPing, tableGroup{w,h}, seatPing, seatsPerTable, aislePingPerTable, minAisleWidth, crowdComfortThreshold, sweetSpotDensity, orientation{origin,東,南,中,西,北} }`。

### 7.2 parlors 新增
```jsonc
{
  "storeSize": "medium",
  "floor": {
    "w": 4, "h": 5,
    "door": { "x": 1, "y": 4 },
    "objects": [
      { "kind": "table",   "itemId": "t_basic",   "x": 0, "y": 0, "rot": 0 },
      { "kind": "equip",   "itemId": "e_counter", "x": 2, "y": 0, "rot": 0 },
      { "kind": "fengshui","itemId": "flow_bowl", "x": 3, "y": 4, "rot": 0 }
    ]
  }
}
```
- `fengshui`/`layout` 舊欄(抽象槽)→ 併入 `floor.objects`(kind:'fengshui');`fengshui` 分數仍由 §6 派生。
- 多分店(M2):`floor` 跟 `parlorId` 分拆(對齊 fengshui 規格 D 註)。

## 8. UI — 遊戲端格子編輯器(**重用 `MahjongMap.js`**)

- **強烈重用**:`sweetbot-next/model/miniGame/MahjongMap.js` 已有 emoji 網格 + 📍游標 + 方向鍵移動 + 邊界 disable + 資料驅動座標。平面圖編輯器**沿用同一套**,只換:
  - 格子內容 = 該格被哪個圖章佔(桌🀄/設備依 emoji/風水依 emoji/空格⬜/門🚪/游標📍)。
  - 互動:方向鍵移游標 → 選「放置(選型錄項)/旋轉/移除」按鈕 → 落子;即時重繪 + 顯示 density/容客量/連通警告。
- customId 前綴 `mjt:floor:`;綁 ownerId;重讀 DDB 不信畫面(對齊 Phase 0)。
- 面板顯示:坪數、已佔/可用格、容客量、density 舒適燈號、走道連通警告(有孤立桌就紅字)。

## 9. Phase / 分工

- **後台 config**(Claude+Fable,已建):footprint/wallMount/storeSizes/balance.floor。
- **遊戲端格子編輯器 + 規則引擎**(Codex,Phase 1):MahjongMap.js 擴充、連通性 BFS、density、風水方位判定、擴店搬遷。
- **容客量/租金**串進惰性結算(Codex,Phase 1~2)。

## 10. 驗收點(給 Codex)

1. config storeSizes/footprint/wallMount/balance.floor 可存/發佈/編輯(後台已具備)。
2. parlors 新增 `storeSize`/`floor{w,h,door,objects[]}`;開館依 storeSize 建空平面圖 + 門口。
3. 擺放:不重疊、超界擋下、wallMount 不佔格。
4. 走道連通 BFS:孤立桌被標停用、不計容客量/收益;塞斷走道可重現。
5. 容客量 = 可用桌組 ×4;租金 = rentLevel×area×rentMult。
6. density 擁擠懲罰(大戶最敏感)、甜蜜點加成。
7. 風水空間化:得位(格子區域)、實際相鄰相生剋、鏡對門沖煞、流年財位區;fengshui 分數正確。
8. 擴店:換大規格保留可容納物件、放不下退倉。
9. 編輯器沿用 MahjongMap.js 游標/邊界;customId 綁 owner;重讀 DDB。
10. 座位半坪/走道係數等全部讀 `balance.floor`,無硬編碼。

---

## 11. Codex 審查修正併入(2026-07-11)

**1. MahjongMap.js「重用概念、不硬改」。** 現有 `MahjongMap.js` 是固定 5×5 世界地圖工具(`MAP_W/MAP_H` 寫死、render 吃 districts),別把它的 `layout(districts)` 硬改成 floorplan。**新建 `MahjongFloorPlan.js`**,重用它的概念(單 emoji 格 / 📍游標 / 方向鍵 / 邊界 disable),平面圖最大 7×9、有 footprint/多格物件/門/wallMount。保留 world map API 不破壞。

**2. 單一分析純函式。** 做 `analyzeFloor(floor, catalogs, balance)` 一次回傳 `{ reachableCells, activeTables, capacity, density, fengshui, warnings }`,**UI 與惰性結算共用**,避免兩套判斷分裂(呼應 §9 結算來源單一化)。

**3. 物件 instance id。** `floor.objects[]` 加 `objectId`(唯一),否則兩張同款普通桌無法穩定指定移除哪張:`{ objectId, kind, itemId, x, y, rot }`。

**4. 倉庫欄位(退倉落地)。** floor 只存已擺上圖的物件;**parlors 加 `storage`(或 `ownedItems`)** 放已購未擺/擴店退倉的設備與風水。否則「放不下退倉」只在文字、資料層接不起來。採購→進 storage;擺放=storage→floor.objects;移除/退倉=反向。

**5. wallMount 要記掛載位置。** `wallMount:true` 不佔格正確,但仍要記掛在哪:`{ x, y, side:'N|E|S|W' }`,否則八卦鏡/風鈴/山海鎮這類 0 格物件缺幾何位置,§6「鏡對門」沖煞判不準。(fengshui §14 同步。)

**6. 門口/通行格定義。** `door` 格視為 **walkable 且不可放物件**。桌組啟用條件:MVP 先採**任一相鄰空格可達 door** 即啟用(規格明寫);之後可升級成需多個座位側可達。

**7. 🔴租金單位遷移(重要,防暴增)。** Phase 0 的 `rentLevel` 語意是「每 tick 整區租金水位」;新公式 `rentLevel × area × rentMult` 等於改成「每坪租金」→ 會直接暴增。**Phase 1 前要欄位改名或 migration**,例如 `rentPerPingPerTick`,並校準數值,別讓現有 parlor 租金一夕爆掉。

**8. 擴店 = 先預覽後提交(deterministic)。** 擴店用確定性 transform:優先保留原座標;door anchor 若變更採 door-anchored 平移;再跑重疊/超界/連通檢查。有效物件保留、無效進 storage。**提交前 UI 顯示「保留 N 件 / 退倉 M 件」**再確認。

**9. 結算來源單一化。** Phase 1 後容客量一律從 `floor.objects` 的 active table 推導;`parlor.tables`(Phase 0 舊欄)只當 fallback/cache,**不可與 floor 並列為真相來源**。

**10. 寫入安全前置(與宣傳/風水規格共用)。** Phase 1 前把 `ParlorDAO.save()` 從整筆 `PutCommand` 改 `UpdateCommand` 局部更新或加 revision/updatedAt 條件寫入。floor.objects 頻繁增刪,並發覆寫風險比其他系統更高。

> 上述 3/4/5 使 parlors 資料模型定版為:`storeSize` + `floor{w,h,door,objects[{objectId,kind,itemId,x,y,rot}], wallItems[{itemId,x,y,side}]}` + `storage[]`。§7.2 以此為準。
