# 行程部落格系統 — 設計冊 v0.1

> 個人旅遊行程的「後台管理 + 公開部落格」。作者只有站主一人（A 模式）；行程由站主口述、Claude 整理後寫入後台。手機可打勾追蹤旅程進度。

## 0. 範圍與角色

- **作者**：僅站主一人（單作者，非 UGC）。
- **輸入流**：站主把行程丟給 Claude → Claude 整理成結構 → 寫入 DDB（後台亦可微調）。
- **讀者**：任何人可瀏覽「公開」行程（部落格牆 + 內頁）。
- **兩種視圖**：
  - **私密版（自己用）**：看到全部，含 🔒 項目與內部提醒（`note`）。旅行中在手機打勾。
  - **公開版（給別人參考）**：自動隱藏所有 🔒 項目與 `note`。
- 明確**不做**：使用者註冊、投稿、留言、按讚（未來要再議）。

## 1. 資料模型（DynamoDB）

- **表名**：`sml-trip-itineraries`
- **計費**：`PAY_PER_REQUEST`（repo 鐵律）
- **備份**：開啟 **PITR（時間點還原）** — 資料珍貴、要放很久。
- **主鍵**：`id`（partition key，字串 slug，例：`tohoku-2026-0826`）→ 支援「單篇讀取」。
- **GSI1（列表用）**：`type`(PK, 常數 `"trip"`) + `updatedAt`(SK, ISO 字串) → 支援「所有行程依更新時間新→舊列出」。
  - 公開列表 = query GSI1 後**在後端過濾 `visibility="public"`**。單作者低量下可接受；**此過濾是效能取捨、非安全邊界**（安全邊界在單篇的欄位白名單，見 §1 可見性）。
  - **未來擴充**：篇數/草稿變多時，加 `visibility-updatedAt-index`（PK=`visibility`、SK=`updatedAt`），公開列表直接 query `public`，免全撈再濾。v0.1 先不做。

### 單筆項目（Item）結構

```json
{
  "id": "tohoku-2026-0826",
  "type": "trip",
  "slug": "tohoku-2026-0826",
  "title": "東北自駕・寶可夢×吉伊卡哇×ROUND1 大滿貫",
  "subtitle": "8/26–8/30・一家四口・自駕五日",
  "region": "日本・東北",
  "tags": ["自駕", "親子", "寶可夢", "吉伊卡哇"],
  "cover": "https://image.boyplaymj.link/trip/covers/tohoku-2026-0826.jpg",
  "visibility": "public",            // "public" | "draft"
  "privateKeyHash": "sha256:...",    // 只存雜湊，不存明文 key；私密連結用 #k=<明文>（見 §1 私密連結）
  "days": [
    {
      "no": 1, "date": "8/26", "wd": "三",
      "theme": "宮城上陸！拉普拉斯之夜 & 裝備採買",
      "items": [
        { "time": "17:00", "ttl": "飯店 Check-in・拉普拉斯主題房",
          "desc": "開箱主題房、領取周邊", "tag": "🛏️",
          "note": "訂房代號 ABC123（內部備註，公開版不顯示）",
          "private": true }
      ]
    }
  ],
  "createdAt": "2026-07-16T07:00:00Z",
  "updatedAt": "2026-07-16T07:00:00Z"
}
```

- **圖片一律進 S3**（`boyplaymj-image` 的 `trip/covers/`），DDB 只存 URL。**嚴禁把圖片 base64 塞進 DDB**（單筆上限 400KB）。
- 一份行程 JSON 約 5–20KB，遠低於 400KB。1,000 篇約 20MB → 儲存費每月約 $0.005。

### 可見性邏輯（單一資料源，衍生兩視圖）

| 欄位 | 私密版（?k=正確） | 公開版（無 k / k 錯） |
|---|---|---|
| `visibility="draft"` 整篇 | 可看（憑 k） | **404 / 不列出** |
| `item.private=true` | 顯示 | **隱藏該項** |
| `item.note` | 顯示 | **一律隱藏**（note = 內部提醒） |

- **公開連結**：`/t/<id>` → 後端**白名單重組**後回精簡資料。
- **私密連結**：`/t/<id>#k=<明文 key>` —— key 放 **URL fragment（`#`）而非 querystring（`?`）**：
  - fragment **不會**送到伺服器、不進 CDN/伺服器 log、不進 Referer。
  - 前端 JS 讀 `location.hash` 取 key，用 **`X-Trip-Key: <明文>` header**（非 querystring）打 API。
  - 後端把明文 key 雜湊後比對 `privateKeyHash`；符合才回私密完整版。
- **回應標頭**：私密資料一律 `Cache-Control: no-store`；站台設 `Referrer-Policy: no-referrer`（至少 `same-origin`）。
- **過濾＝後端白名單重組（非刪欄位）**：見 §2 序列化規則；公開 API 絕不序列化 `note`、`privateKeyHash`，遞迴略過 `private=true` 的 item。

## 2. 後端 API（Lambda + API Gateway）

| 方法 | 路徑 | 權限 | 說明 |
|---|---|---|---|
| GET | `/trips` | 公開 | 公開行程列表（僅 `visibility=public`，精簡欄位：id/title/cover/region/tags/updatedAt） |
| GET | `/trips/{id}` | 公開 | 單篇公開版（白名單重組，遞迴略過 private item） |
| GET | `/trips/{id}` + `X-Trip-Key` | 憑 key | 單篇私密完整版（key 雜湊比對 `privateKeyHash`；回應加 `Cache-Control: no-store`） |
| GET | `/admin/trips` | 驗證 | 後台：列出全部（含草稿） |
| PUT | `/admin/trips/{id}` | 驗證 | 建立/更新整篇 |
| PATCH | `/admin/trips/{id}` | 驗證 | 局部更新（切 visibility、改單項 private） |
| DELETE | `/admin/trips/{id}` | 驗證 | 刪除 |

- **驗證**：沿用現有後台登入機制（Cognito / gameAdmins 白名單，Phase 4 確認採哪條）。
- 公開端點只讀，無寫入面。

### 公開序列化規則（P2 驗收寫死）

> 公開 API **不是**「拿完整物件刪敏感欄位」，而是**只組出允許欄位的新物件**（白名單）。防止未來新增欄位時忘記過濾而外洩。

- 允許輸出欄位：`id / title / subtitle / region / tags / cover / updatedAt` + `days[]`（每日 `no/date/wd/theme`）+ `items[]` 中 `time/ttl/desc/tag`。
- **遞迴略過** `item.private === true` 的項目。
- **永遠不序列化**：`note`、`privateKey`/`privateKeyHash`、`visibility` 以外的內部欄位。
- **`draft` 無有效 key → 回 404**（與「不存在」不可區分，不得回 200 空殼或 403 洩漏存在性）。
- 錯 key 打在 `public` 行程 → 回公開版；打在 `draft` → 404。

## 3. 後台管理頁

- **行程列表**：全部（含草稿），顯示狀態徽章、更新時間、公開/私密連結一鍵複製。
- **編輯器**：標題/副標/地區/標籤/封面圖上傳（傳 S3 存 URL）；逐日、逐項編輯。
- **逐項 🔒 切換**：每個 item 一個開關 → `private`。
- **公開/草稿開關**：整篇 `visibility`。
- **刪除**（二次確認）。
- 站主主要靠 Claude 灌內容，此頁供**微調、切可見性、複製連結**。

## 4. 前端呈現

- **列表頁（部落格牆）**：讀 `GET /trips`，卡片牆（封面+標題+地區+天數+標籤），新→舊。
- **內頁**：沿用現有 `tohoku-0826.html` 樣式，改成 **data-driven**（依 `?id=` 讀 API），保留：時間軸、打勾（localStorage，key 帶 trip id）、進度條、跳到今天、⚠️ 提醒（僅私密版）。
- 打勾狀態存讀者自己裝置的 localStorage（零成本、免登入）。

## 5. 網域與部署

- **不需購買**：`boyplaymj.link` zone 已在自家 Route53。
- 起步用 `image.boyplaymj.link/trip/`；要部落格感再**免費**開子網域 `trip.boyplaymj.link`（Route53 record + CloudFront）。
- 前端靜態檔 → S3 `boyplaymj-image` + CloudFront；API → APIGW。
- 加 OG 分享卡（貼 Discord/LINE 有預覽圖）。

## 💰 成本控管

依 repo 規則附此段，正典見 **[`tools/COST_CONTROL.md`](../COST_CONTROL.md)**。

- **成本來源與量級**：
  - DynamoDB `sml-trip-itineraries`：`PAY_PER_REQUEST`，個人流量下讀寫費趨近 $0；純文字儲存每月分幣級。
  - S3 + CloudFront（封面圖 / 靜態前端）：沿用現有圖床基礎設施，增量可忽略。
  - **無 LLM、無外部付費 API**：排版由 Claude / 後台人工處理，**不做**「貼一段遊記自動變行程」的自動解析。
- **是否需要四件套（帳本表/月封頂 cap/後台用量卡/kill switch）**：**否**。理由：不燒 LLM、不打付費 API（COST_CONTROL.md §1）。
- **未來若加自動解析（燒 Bedrock）**：屆時本段升級，補齊四件套後才上線。

## 6. 分階段實作計畫（每階段結束交 Codex 查驗）

| 階段 | 內容 | 主要執行 | 產出/驗收點 |
|---|---|---|---|
| **P0** | 本設計冊 | Claude(Opus) | schema/API/成本段齊全 ← Codex 審設計 |
| **P1** | 資料層：建表(PPR+PITR)、DAO、把東北行程灌成第一筆、讀取驗證 | Claude(Fable5) | 能寫入+讀回一致 |
| **P2** | 後端 API：Lambda + APIGW（公開讀 + 後台 CRUD + 可見性過濾） | Claude | 過濾正確、私密不外洩 |
| **P3** | 公開前端：內頁 data-driven + 列表牆 | Claude(Fable5) | 東北行程從 API 正確渲染 |
| **P4** | 後台管理頁：CRUD + 逐項🔒 + 公開/草稿 + 登入 | Claude | 端到端可管理 |
| **P5** | 網域 `trip.boyplaymj.link` + OG 卡 + 收尾 | Claude(Opus) | 上線可分享 |

- 每階段 <25 分鐘、分批回報；重活轉 Fable 5，設計/收尾用 Opus。
- 每階段完成 → 走「轉傳給 Codex」查驗 → 過了再進下一階段。

## 7. 部署現況（跨 session 續作用）

- **P1 ✅** DDB `sml-trip-itineraries`（ap-southeast-1、PAY_PER_REQUEST、PITR ENABLED、GSI `type-updatedAt-index`）；東北行程已灌（id `tohoku-2026-0826`，5 天 29 項）。種子：`seed_tohoku.py`。
- **P2 ✅（公開讀）** Lambda `sml-trip-itinerary`（nodejs20.x）+ HTTP API `f9ayvn4doc`。原始碼 `lambda/index.js`。IAM role `sml-trip-itinerary-role`（DDB 最小權限）。
  - **API base**：`https://f9ayvn4doc.execute-api.ap-southeast-1.amazonaws.com`
  - 公開讀 9 情境端到端測過（含 draft-404、private-item 過濾）。
  - **後台 CRUD（saveTrip/patchTrip/deleteTrip/adminList）已寫入同 handler、沿用 Firebase token+gameAdmins 認證，但尚未 live 測**（P4 配管理頁時測）。
  - **Codex P2 findings 已全修並 redeploy**：patch/delete 加 `attribute_exists(id)` 條件（不存在→404）、saveTrip 明文 key 回應加 `no-store`、`email_verified !== true` 才過、saveTrip 驗 id/slug slug 格式。
- **待辦**：P3 前端吃此 API；P4 後台頁 + 後台端點實測；P5 網域/OG。

---
_v0.3・2026-07-16・P1+P2(公開讀)完成並端到端驗證 → 待 Codex 驗 P2、再進 P3_
