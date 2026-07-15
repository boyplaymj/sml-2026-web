# 🀄 麻將館專區 (Parlor Zone)

> **狀態**：設計草案 🔶（Claude 提案，待 gameboy 拍板）
> 一句話：**實體麻將館／俱樂部的官方名錄與合作專區——找店、看優惠、包桌預約、到店打卡。**

---

## 1. 定位與價值

把「線上揪團」延伸到「線下場地」。既有揪團是玩家自約地點；**麻將館專區**是**經營者/俱樂部側**的正式入口：
- **名錄**：合作麻將館的地圖、環境照、設備標籤（電動桌/冷氣/停車/飲料…，可沿用揪團的場地特色標籤）、營業時間、低消。
- **優惠**：兩雀會員專屬折扣、活動。
- **包桌預約**：選館 → 選時段 → 預約（可與 `/create` 開團打通：預約即開一個團局）。
- **到店打卡**：地理圍欄（App 已用 AWS Location geofencing）check-in 給點數/天梯加成。

與現有模組接點：地圖沿用 Leaflet + AWS Location；場地特色標籤與揪團共用；打卡點數回流 APP 內遊戲/天梯；優惠可接兌換系統。

---

## 2. 核心機制（草案）🔶
| 面向 | 內容 |
|---|---|
| 館家資料 | 名稱、地址、經緯度、營業時間、桌數、低消/計時費、設備標籤、環境照（S3） |
| 收錄方式 | 後台人工上架（v1）→ 館家自助申請入駐（v2） |
| 預約 | 時段桌位 → 建立預約 → 通知館家；可轉成揪團團局 |
| 打卡 | geofencing 進場偵測 → check-in → 點數/天梯加成（防作弊：需在圍欄內 + 冷卻） |
| 商業 | 合作館家可為付費/抽成對象（**若涉金流走成本規範**） |

## 3. 資料模型草案 🔶
```
Parlor      { parlorId, name, address, lat, lng, hours, tables,
              minCharge, features[], photos[](S3), partner(bool), status }
Booking     { bookingId, parlorId, userId, slot, tableNo, status }
CheckIn     { userId, parlorId, ts, geoVerified }
```

## 4. API 草案 🔶
`GET /parlors?lat&lng` · `GET /parlor-detail?id=` · `POST /parlor-book` · `POST /parlor-checkin` · `POST /parlor-get-upload-url`（環境照）· 後台 `POST /parlor-upsert`

## 5. 後台管理面板（v2）
館家 CRUD、圖片上傳、上下架、優惠設定、預約檢視、打卡稽核、（入駐申請審核）。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：DDB 新表 `parlor` / `parlor-booking` / `parlor-checkin`（PAY_PER_REQUEST，量級小）；S3 存館家環境照（沿用既有圖床）；AWS Location geofencing（沿用 App 現有帳）。預估 < $2/月。
- 所有新表 PAY_PER_REQUEST；無 LLM。
- ⚠️ **若加入金流**（會員付費/館家抽成/線上付訂金）→ 屬「外部付費 API」，回本規範補齊該段並評估綠界 webhook 風險（見 project_sweetbot_vip_payment 的教訓）。

## 6. 待你拍板
- [ ] v1 收錄用「後台人工上架」還是要做「館家自助入駐」？
- [ ] 打卡加成給什麼（點數/天梯分/優惠券）？
- [ ] 預約是否直接等於開一個揪團團局（與 /create 打通）？
- [ ] 是否涉及金流（決定要不要進金流成本規範）？
