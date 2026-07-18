# 影片製作專案管理 — 設計冊 v0.1

> 站主口述工作事項 → Claude 整理成結構化任務 → 寫入後台。前台以**月曆＋時間軸**總覽、專案內頁可**依時間/重要性排序**、任務**打勾即劃掉**。架構比照 [`tools/trip-itinerary`](../trip-itinerary/DESIGN.md)（行程誌系統），沿用同一套 Firebase 登入白名單。

## 0. 範圍與角色

- **作者**：僅站主一人（單作者，非 UGC）。
- **輸入流**：站主在 Discord 頻道丟白話工作事項 → Claude 整理成結構 → 寫入 DDB（後台亦可微調）。
- **讀者**：站主自己（私人工具，非公開牆）。前台走**不公開連結**進，`GET /projects` 列表回全部（沒有 public/draft 二分，因單一使用者私人用）。
- 明確**不做**：使用者註冊、投稿、留言、LLM 自動解析（排版由 Claude/後台人工）。

## 1. 資料模型（DynamoDB）

- **表名**：`sml-video-projects`
- **計費**：`PAY_PER_REQUEST`（repo 鐵律）
- **備份**：開啟 **PITR** — 資料珍貴。
- **主鍵**：`id`（partition key，字串 slug，例：`crossroad-promo`）→ 單專案讀取。
- **GSI1（列表用）**：`type`(PK, 常數 `"vproj"`) + `updatedAt`(SK, ISO) → 所有專案依更新時間新→舊列出。

### 單筆專案（Item）結構

```json
{
  "id": "crossroad-promo",
  "type": "vproj",
  "slug": "crossroad-promo",
  "title": "捍衛路權宣傳片",
  "subtitle": "路口安全・30 秒短片",
  "cover": "https://image.boyplaymj.link/vproj/covers/crossroad-promo.jpg",
  "status": "active",                 // "active" | "done" | "archived"
  "tasks": [
    {
      "tid": "t1",                    // 專案內唯一（後台/patch 定位用）
      "title": "拍攝路口空景",
      "date": "2026-07-20",           // ISO yyyy-mm-dd；可空（未定日）
      "importance": 3,                // 3=高🔴 2=中🟡 1=低⚪
      "status": "todo",               // "todo" | "done"
      "tag": "拍攝",                   // 企劃/拍攝/剪輯/上字/配樂/發布…（自由字串）
      "note": "早上光線佳，備空拍機",
      "doneAt": null                  // 完成時間戳（打勾時寫入）
    }
  ],
  "createdAt": "2026-07-16T07:00:00Z",
  "updatedAt": "2026-07-16T07:00:00Z"
}
```

- **圖片一律進 S3**（`boyplaymj-image` 的 `vproj/covers/`），DDB 只存 URL。**嚴禁把圖片 base64 塞進 DDB**（單筆上限 400KB）。
- 一份專案 JSON 約 3–15KB，遠低於 400KB。

### 排序與衍生視圖（前端計算，單一資料源）

| 視圖 | 規則 |
|---|---|
| 按時間序 | 任務依 `date` 升冪；無 `date` 者沉底（歸「未定日」） |
| 按重要性 | 任務依 `importance` 降冪，同級再按 `date` 升冪 |
| 完成劃掉 | `status="done"` 的任務顯示刪除線、下沉（或視圖切「隱藏已完成」） |
| 月曆 | 跨全部專案，把有 `date` 的任務標在對應日格 |
| 時間軸 | 跨全部專案，所有有 `date` 的任務依日期排成一條線，標出工作跨足的日期範圍 |

## 2. 後端 API（Lambda + API Gateway）

| 方法 | 路徑 | 權限 | 說明 |
|---|---|---|---|
| GET | `/projects` | 公開讀* | 專案列表（摘要：id/title/subtitle/cover/status/任務數/待辦數/日期範圍/updatedAt） |
| GET | `/projects/{id}` | 公開讀* | 單專案完整（含 tasks） |
| GET | `/calendar` | 公開讀* | 跨專案任務攤平（每筆帶 projectId/projectTitle/date/importance/status/title），供月曆＋時間軸 |
| POST | `/admin`（body.action） | 驗證 | `adminList` / `saveProject` / `deleteProject` / `patchTask` / `toggleTask` |

*註：單一使用者私人工具，前台走不公開連結；讀端不做 public/draft 過濾。若日後要真正保密，於讀端加 Firebase 驗證或 CloudFront 簽名。**此為取捨、非強安全邊界**。

### 後台 action

- `adminList` — 列出全部專案。
- `saveProject` — 建立/更新整個專案（含 tasks 陣列）。沿用既有 `createdAt`；驗 `id`/`slug` 格式 `[A-Za-z0-9_-]`。
- `deleteProject` — 刪除（`attribute_exists(id)` 條件，不存在→404）。
- `patchTask` — 局部改單一任務欄位（title/date/importance/tag/note）。
- `toggleTask` — 打勾/取消：切 `status` todo↔done，`done` 時寫 `doneAt`。**供「頻道回報做完了→我幫你劃掉」用**。

- **驗證**：沿用行程誌那套 Firebase ID token（RS256，Google securetoken 公鑰）+ Firestore `config/gameAdmins` 白名單，`ALLOWED_EMAILS` 為 fallback。

## 3. 後台管理頁（`video_admin.html`，遊戲館，Firebase 登入）

- **專案列表**：狀態徽章、更新時間、任務數/待辦數、前台連結一鍵複製。
- **編輯器**：標題/副標/封面圖上傳（傳 S3 存 URL）/專案狀態；任務逐筆編輯（事項/日期/重要性/分類/備註）。
- **任務打勾**：每筆一個勾 → `toggleTask`。
- **刪除**（二次確認）。
- 站主主要靠 Claude 灌內容，此頁供微調、打勾、複製連結。

## 4. 前端呈現（首頁 + 內頁）

- **首頁**（`index.html`）：
  - **當月月曆**：讀 `GET /calendar`，有任務的日子標點/數字，點日子看當天事項；可切月。
  - **時間軸**：所有任務依日期排成縱向時間線，標出工作跨足的日期範圍與各專案色帶。
  - **專案卡牆**：讀 `GET /projects`，卡片（封面+標題+狀態+待辦數），新→舊。
- **內頁**（`p.html?id=`）：讀 `GET /projects/{id}`：
  - 排序切換鈕：**時間序 ↔ 重要性**。
  - 任務清單：勾選框（打勾→刪除線，打 `toggleTask` 寫回 DDB）、重要性色標、日期、分類標籤、備註。
  - 進度條（done/total）、跳到今天、隱藏已完成切換。

## 💰 成本控管

依 repo 規則附此段，正典見 **[`tools/COST_CONTROL.md`](../COST_CONTROL.md)**。

- **成本來源與量級**：
  - DynamoDB `sml-video-projects`：`PAY_PER_REQUEST`，個人流量下讀寫費趨近 $0；純文字儲存每月分幣級。
  - S3 + CloudFront（封面圖 / 靜態前端）：沿用現有圖床基礎設施，增量可忽略。
  - **無 LLM、無外部付費 API**：排版由 Claude / 後台人工，**不做**「貼一段話自動變任務」的自動解析。
- **是否需要四件套（帳本表/月封頂 cap/後台用量卡/kill switch）**：**否**。理由：不燒 LLM、不打付費 API（COST_CONTROL.md §1）。
- **未來若加自動解析（燒 Bedrock）**：屆時本段升級，補齊四件套後才上線。

## 5. 分階段實作計畫（每階段 <25 分、分批回報，重活可轉 Fable5，收尾用 Opus）

| 階段 | 內容 | 產出/驗收點 |
|---|---|---|
| **P0** | 本設計冊 | schema/API/成本段齊全 |
| **P1** | 資料層：建表(PPR+PITR)、GSI、灌第一筆種子、讀回驗證 | 能寫入+讀回一致 |
| **P2** | 後端 API：Lambda + APIGW（列表/單筆/calendar/後台 CRUD+toggle） | 端點端到端測過 |
| **P3** | 前台：首頁月曆+時間軸+專案牆、內頁排序+打勾 | 從 API 正確渲染、打勾寫回 |
| **P4** | 後台管理頁：CRUD + 任務打勾 + 登入 | 端到端可管理 |
| **P5** | 收尾：部署前台到圖床、OG 卡、串頻道日常流程 | 上線可用 |

## 6. 部署現況（跨 session 續作用）

**P0–P5 全部完成並上線（2026-07-16）：**

- **P1 資料層 ✅** DDB `sml-video-projects`（ap-southeast-1、PAY_PER_REQUEST、PITR ENABLED、GSI `type-updatedAt-index`）。種子 `seed_demo.py`（id `demo-crossroad-promo`，7 任務、1 完成，示範用之後換真資料）。讀寫一致已驗。
- **P2 API ✅** Lambda `sml-video-projects`（nodejs20.x、role `sml-video-projects-role` DDB 最小權限）+ HTTP API `fa87vpf8x9`。
  - **API base**：`https://fa87vpf8x9.execute-api.ap-southeast-1.amazonaws.com`
  - 公開讀端到端測過：`/projects`（摘要含 taskCount/todoCount/日期範圍）、`/projects/{id}`、`/calendar`（無日期任務正確排除）、404/401 邊界。
  - 後台 action：`adminList/saveProject/deleteProject/patchTask/toggleTask`，沿用 trip 那套 Firebase token + gameAdmins 白名單認證。**後台寫入待首次登入實測（同 trip P4）。**
- **P3 前台 ✅** 上圖床 `image.boyplaymj.link/vproj/`（S3 `boyplaymj-image`、CloudFront `E2IJWN6FWT2XYG`）。
  - 首頁 `index.html`：月曆（彩點/今天高亮/點日看清單/切月）＋時間軸（跨專案、標日期範圍）＋專案牆（進度條）。
  - 內頁 `p.html?id=`：排序切換（時間序↔重要性）、打勾劃掉（本機層 localStorage 覆蓋 DDB 權威值）、進度條、隱藏已完成、未定日沉底。Playwright 全互動截圖驗過。
- **P4 後台 ✅** `video_admin.html`（遊戲館，已 deploy `sweetbot-games.web.app`、NAV 已加「🎬 影片製作專案」）。列表/建立/編輯（tasks JSON 即時驗證+預覽可打勾）/改狀態/刪除/複製前台連結。登入閘渲染無 error 已驗。
- **P5 ✅** 前台上線、遊戲館上線。

**日常流程**：站主在頻道丟白話工作事項 → Claude 整理成 tasks 結構寫進後台（或直接 `saveProject`）→ 前台自動排好；「XX 做完了」→ Claude 用 `toggleTask` 標記完成 → 前台劃掉。

**待辦/未來**：真實專案取代 demo 種子；封面圖流程（S3 `vproj/covers/`）；要真正保密再於讀端加驗證；OG 分享卡；子網域 `vproj.boyplaymj.link`（可選）。repo `tools/video-projects/` 尚未 commit。

---
_v0.2・2026-07-16・P0–P5 全上線_
