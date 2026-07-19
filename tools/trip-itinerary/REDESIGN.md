# 行程誌 · Diary 編輯風改版規格（REDESIGN v0.3）

> 目標：把 `mode:"diary"`（遊記/回憶版）從「摺疊日卡＋緊湊時間軸」升級成 **雜誌編輯風長捲軸**，
> 視覺以 `preview.html` 為唯一真相來源，資料仍由 DDB → `lambda/index.js` → `t.html` 驅動。
> **`mode:"plan"`（出發前計畫、可打勾）完全不動**——本次只加 diary 分支。

參考檔：
- `preview.html` — 定案視覺（Day 1 真實內容做的樣板，含地圖/gallery/影音/reels/interlude 版位）
- `t.html` — 正式資料驅動模板（要新增 diary 編輯風渲染路徑）
- `lambda/index.js` — `toPublic()` 白名單（**新欄位一定要補進來，否則公開讀被清掉**）
- `seed_hokkaido.py` — 種子（`hokkaido-2026-0524`，mode=diary，visibility=draft）

---

## 1. 保留的骨幹（不可退化）
- **直式時間軸**：每日章節內 moment 走垂直線 + 圓點（preview `.tl/.moment/.dot`）。
- **OSRM 真實路線**：總覽地圖用 OSRM 編碼 polyline（precision 5）畫「跟著道路走」的線，不是直線連點。decode 函式已在 preview.html `decodePoly()`，照抄。
- **多圖 / 直式影音**：item 支援 2 欄圖庫（>4 張出 `+N` 更多磚）、直式照片不裁切置中、9:16 直式上傳影片、IG Reels 內嵌。
- **私密安全**：lambda 既有機制不動——遞迴略過 `private` item、draft 無有效 key 一律 404、絕不吐 `note`/`privateKeyHash`。新欄位同樣要走白名單。

---

## 2. 資料模型（v0.3，全部欄位「新增即向後相容」）

### Trip 層（新增）
| 欄位 | 型別 | 說明 |
|---|---|---|
| `cover` | str | 封面大圖（既有） |
| `kicker` | str | 封面 eyebrow，如 `Hokkaido Road Trip` |
| `dates` | str | 封面日期行，如 `2026.05.24 – 05.31`（缺則退回 subtitle） |
| `overview` | obj | 總覽地圖區，見下 |

`overview`：
```
{
  "lead": "八天環道路線 · 點圖釘看每一天",
  "stops":  [{"no":1,"name":"新千歲機場","ll":[42.775,141.692]}, ...],
  "polyline": "<OSRM 編碼字串 precision5>",
  "stats":  [{"v":"8","label":"天 7 夜"}, {"v":"4","label":"一家人"}, ...]   // 最多 4
}
```

### Day 層（新增）
| 欄位 | 型別 | 說明 |
|---|---|---|
| `no/date/wd/theme/hero` | — | 既有；`theme` 當章節大標，`hero` 僅 plan 模式用 |
| `kicker` | str | 章節 eyebrow，如 `Day 1 · 5/24 週日`；缺則由 `Day {no} · {date}（{wd}）` 組出 |
| `intro` | str | 章節導言段落 |
| `interlude` | obj | 章節結尾滿版圖 `{"img":str,"cap":str}`（可省） |

### Item 層（既有 + 新增，全部 optional）
既有：`time, ttl, desc, tag, stay, addr, parking, note, photos, private`
新增：
| 欄位 | 型別 | 渲染 |
|---|---|---|
| `gallery` | [str] | 2 欄方格；>4 張 → 前 3 張 + 第 4 格蓋 `+N` 更多 |
| `portrait` | bool | 把 `photos[0]`（或 `gallery[0]`）當直式照片，置中不裁切 |
| `caption` | str | 單張/直式照片的 figcaption |
| `video` | obj | `{"src":str,"poster":str}` → 9:16 直式播放器 |
| `reel` | str | IG reel 連結 → 內嵌 9:16（無法內嵌則顯示點擊卡） |

> 設計原則沿用 [i18n]：圖片不內嵌文字，所有文案走 embed/HTML。

---

## 3. lambda `toPublic()` 要補的白名單（關鍵）
在既有 map 上補：
- trip 層：`kicker`, `dates`, `overview`（`overview` 需淺層清洗：stops 只留 `{no,name,ll:[num,num]}`、polyline 限 string、stats 限 `{v,label}`）。
- day 層：`kicker`, `intro`, `interlude:{img,cap}`。
- item 層：`gallery`（限 string 陣列）、`portrait`(bool)、`caption`(str)、`video:{src,poster}`、`reel`(str)。
- **維持**：`private` item 過濾、不吐 `note`（公開版）、不吐 hash。
- `toSummary` 不動（列表只要 cover/title/天數）。

---

## 4. t.html 渲染分支
`renderTrip(trip)` 開頭已判斷 `DIARY = trip.mode==="diary"`。改法：
- `if (DIARY) return renderDiary(trip);`（新函式，走編輯風長捲軸）
- 否則維持現有 plan 渲染（**一行不改**）。

`renderDiary(trip)` 依 preview.html 結構產出：
1. **cover header**：`trip.cover` 底圖 + veil + kicker/h1(title)/sub(subtitle)/dates + 向下 cue。
2. **overview**：sec 標題 + divider + `overview.lead` + `#map` + 4 顆 stat。
   - 地圖：動態注入 Leaflet CSS/JS（t.html 目前沒載）→ 建 map、CARTO voyager tile、decode `overview.polyline` 畫線、`overview.stops` 放編號 pin、`fitBounds`。缺 `overview` 則整段略過。
3. **每日 chapter**：`ch-kicker`(day.kicker) + `ch-title`(theme) + `ch-intro`(intro)。
4. **moments 時間軸**：逐 item 依欄位選版位——
   - 住宿(`stay`)：編輯風 stay-card（amber）。
   - 有 `gallery`：2 欄圖庫（+N）。
   - `portrait`：置中直式照片 + caption。
   - `video`：9:16 vframe（poster + play 鈕）。
   - `reel`：reelframe 內嵌/點擊卡。
   - 否則：純文字 moment（time/ttl/desc）＋單張 `photos[0]`（若有）。
   - 點圖走既有 `openLightbox`。
5. **interlude**：day.interlude 存在 → 滿版圖 + caption。
6. 底部：teaser（下一天預告，可由下一天 theme 自動組）+ footer + 回列表連結。

保留：`esc()` escape、lightbox、`X-Trip-Key` 讀取、錯誤狀態。
diary 模式**不出** appbar 打勾/進度/FAB/chips；保留一個低調的「← 回列表」浮動鈕（右上或左上，避免蓋標題）。

---

## 5. 種子（seed_hokkaido.py）
- Trip 補 `kicker`、`dates`、`overview`（stops 7 點 + polyline + 4 stats，數值抄 preview.html）。
- Day 1 依 preview.html 補 `kicker`/`intro` + 至少一個 `gallery`、一個 `portrait`、一個 `video` 佔位、一個 `reel` 佔位、`interlude`，作為其餘天的填寫範本。
- Day 2–8 先補 `kicker`/`intro`（文案可精簡），媒體版位日後逐日加。
- 維持 `mode:"diary"`、`visibility:"draft"`、沿用既有 `privateKeyHash`（不帶 `--newkey` 不換私密連結）。

---

## 6. 💰 成本控管
本次不新增 LLM／付費 API／新表：沿用既有 DDB `sml-trip-itineraries`（PAY_PER_REQUEST）與 Lambda `sml-trip-itinerary`。地圖 tile 走 CARTO 免費、OSRM polyline 在 seed 階段一次算好存 DDB（不在執行期打 OSRM）。**無額外經常性成本**，免四件套。正典見 `tools/COST_CONTROL.md`。

---

## 7. 驗收
1. `mode:"plan"` 的行程（如東北 tohoku）渲染與行為 100% 不變（回歸）。
2. diary（hokkaido）出現封面／地圖（真實路線非直線）／章節／gallery(+N)／直式照片不裁切／影片與 reel 版位／interlude。
3. 公開讀（無 key）拿得到新欄位、拿不到 `note`/private item；draft 無 key 仍 404。
4. lightbox、回列表、reduced-motion 都正常。
</content>
</invoke>
