# 模擬麻將館 — 後端交接規格(Codex)

> 對象:Codex。前端管理頁 `sweetbot-site/public/mahjong_tycoon_admin.html` 已做完並通過本地渲染驗證(4 子分頁 + 發佈列),等後端。
> 參考既有實作:`sml-random-events`(APIGW+Lambda+DDB+Firebase 驗證) 與前端 `random_event_manager.html` 的接法完全同套。
> 版控慣例:動工前 `check-conflict.sh`;不整檔覆蓋;有 `deploy.sh` 就走它;最後用**實際 API/AWS 回傳**驗證,不只看 code。

---

## 1. API(單一 POST 端點 + action 分派)

- 路徑:`POST /`(APIGW HTTP API,root)。前端 `fetch(API, {method:'POST', body:{action,...}})`。
- Header:`Authorization: Bearer <firebaseIdToken>`、`Content-Type: application/json`。
- CORS:允許 `sweetbot-games` 網域(照 `sml-random-events` 設定複製,含 `Authorization` header)。
- 前端常數:建好 APIGW 後,把端點填進 `mahjong_tycoon_admin.html` 的 `const API = ''`(目前留空 = 本地預覽模式,不打雲端)。

### actions

| action | request body | 行為 | 回傳 |
|---|---|---|---|
| `listConfig` | `{}` | 讀 4 section 的 draft+published | 見下方 §4 |
| `saveSection` | `{ section, data }` | 覆寫該 section 的 **draft**;更新 `updatedAt/updatedBy` | `{ok:true, updatedAt}` |
| `publishConfig` | `{}`(或 `{section}` 只發佈單一) | 把 draft.data 複製到 published;`published.version++` | `{ok:true, versions:{[sec]:v}}` |
| `revertDraft`(可選) | `{section}` | 把 published.data 複製回 draft | `{ok:true}` |

- `section` ∈ `districts` \| `events` \| `catalogs` \| `balance`。
- 失敗一律回 `{ok:false, error:'...'}`(前端 `api()` 靠 `ok===false` 丟例外)。白名單未過 → error 內含字串 `staff`(前端據此顯示「不在工作人員白名單」)。

---

## 2. 驗證(照 sml-random-events)

- 驗 Firebase idToken(project `sml2026newscore`)。
- 比對 **gameAdmins 白名單**(沿用既有那份,別另立)。不在白名單 → `{ok:false, error:'not staff'}`。

---

## 3. DynamoDB

- 表名:`mahjong-tycoon-config`,`PAY_PER_REQUEST`(對齊慣例)。
- Key:
  - PK `section` (S):`districts`/`events`/`catalogs`/`balance`
  - SK `state` (S):`draft` / `published`
- 每個 item 屬性:
  - `data`:該 section 的完整 JSON(見 §5 schema)。用 DynamoDB Map 或 JSON 字串皆可,擇一固定。
  - `version` (N):published item 才有意義;每次 publish +1。draft 可不維護 version。
  - `updatedAt` (S,ISO8601)、`updatedBy` (S,操作者 email)。
- item 大小遠小於 400KB 上限,整段存單一 item 即可,不用拆列。
- **首次讀取空表**:`listConfig` 對缺失 section 回 `draft:null / published:null`;前端會自動填 `SEED` 種子預設(見前端 `SEED`),使用者按儲存/發佈即寫入。也可由 Lambda 首次以 SEED 初始化,但非必要。

---

## 4. listConfig 回傳格式(前端 loadAll 期待)

```json
{
  "ok": true,
  "sections": {
    "districts": { "draft": <data|null>, "published": <data|null>, "version": 0, "updatedAt": "…", "updatedBy": "…" },
    "events":    { "draft": …, "published": …, "version": 0, … },
    "catalogs":  { … },
    "balance":   { … }
  }
}
```
- 缺的 section 可整個省略或給 `{draft:null,published:null,version:0}`;前端都容錯(fallback 到 SEED)。

---

## 5. 4 個 section 的 JSON schema(前端實際送出的 data 形狀)

### 5.1 districts(array)
```json
[{ "id":"night_market", "name":"夜市邊", "emoji":"🏮",
   "baseFlow":120, "clientMix":{"casual":55,"regular":30,"whale":5,"tourist":10},
   "rentLevel":80, "riskLevel":0.35, "enabled":true }]
```
- `clientMix` **十鍵** `casual/regular/whale/tourist/student/elderly/mama/truant/roamer/novice`(散客/雀友/大戶/觀光客/學生/高齡/媽媽/翹課學生/游擊中年人/麻將新手),百分比,建議合計 100(前端只提示不強制)。〔2026-07-11 由 4→10 客群;上方 JSON 範例只列部分鍵為示意〕另每區有 `location{roadside,carParking,scooterParking,freeLotDist,paidLotDist,mrtDist,mrtOpen,mrtClose,archetype,surroundings}` 地段屬性(surroundings=逗號分隔設施 id,長期建議改 array)。canonical 客群清單資料驅動,以 `balance.clientProfiles`/`weights` 的鍵為準。

### 5.2 events(array)
```json
[{ "id":"inspection", "name":"警察臨檢", "scene":"…", "weight":3, "minRisk":0.2,
   "districts":[], "enabled":true,
   "options":[
     {"label":"配合受檢","resultText":"…","effects":{"cash":-200,"reputation":-2,"heat":0}},
     {"label":"塞紅包打發","resultText":"…","effects":{"cash":-800,"reputation":-5,"heat":0}}
   ]}]
```
- `options` 固定 2 個(A/B);`effects` 三鍵 `cash/reputation/heat`(cash 即牙齒)。
- `districts` 空陣列 = 全區皆可觸發;之後可放 district id 限定。

### 5.3 catalogs(object,5 類 array)
```json
{
  "tables":[{"id":"t_basic","name":"普通牌桌","cost":500,"capacity":4,"tier":1}],
  "staff": [{"id":"s_dealer","role":"荷官","tier":1,"salary":120,"effect":"翻桌率+"}],
  "decor": [{"id":"d_clean","name":"基礎清潔","cost":300,"reputation":2}],
  "menu":  [{"id":"m_drink","name":"茶水","cost":200,"appeal":1,"dwell":5}],
  "promo": [{"id":"p_flyer","name":"傳單","cost":100,"heat":10,"decay":0.2}]
}
```

### 5.4 balance(object)
```json
{
  "openCostTeeth":500, "reviveCostTeeth":300, "worldTickMinutes":10,
  "bankruptcy":{"deficitTicksToClose":6,"minReserve":0},
  "rentGrowth":{"base":1.0,"heatMultiplier":0.05,"capPerTick":0.1},
  "weights":{
    "casual": {"price":0.35,"reputation":0.15,"environment":0.10,"food":0.10,"promoHeat":0.10,"dealer":0.10,"tableQuality":0.10,"buzz":0.20,"fengshui":0.10},
    "regular":{…}, "whale":{…}, "tourist":{…}, "student":{…}, "elderly":{…}, "mama":{…}, "truant":{…}, "roamer":{…}, "novice":{…}
  }
}
```
- `weights` **canonical 10 客群 × 9 因子**(`price/reputation/environment/food/promoHeat/dealer/tableQuality/`**`buzz/fengshui`**),全 10 列(client list 資料驅動);每列建議合計≈1(前端顯示 Σ 提示)。〔2026-07-11 由 4 客層×7 因子擴為 10×9;上方 JSON 僅列 casual 完整值為示意,其餘 9 客群同結構〕以後台 SEED 的 `balance.weights` 為準。

---

## 6. 遊戲端讀取(Phase 0 之後,非本次)

- 遊戲(甜甜)只讀 `state=published` 的 4 section 當設定源頭。
- 可加 `getPublished`(免驗證或內部呼叫)給遊戲讀,或遊戲直接 `GetItem` DDB published item。此部分 Phase 0 再定,本規格先把後台寫入面做完。

---

## 7. 驗收點(Codex 自驗)

1. 未帶 token / 非白名單 → `{ok:false}` 且 error 含 `staff`。
2. `saveSection` 後 `listConfig` 讀回同一份 draft。
3. `publishConfig` 後 published.version +1、published.data == draft.data。
4. 前端填入端點後:登入 → 4 子分頁讀得到、改一格存草稿、發佈、重整後 published 生效。
5. 空表首次 `listConfig` 不炸(回 null,前端吃 SEED)。
