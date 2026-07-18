# 両雀 工程師既有後台 — 逆向整理

> ✅ **2026-07-17 已由工程師交付的原始碼校正 → 正解請看 [`SOURCE_TRUTH.md`](./SOURCE_TRUTH.md)**。本檔保留逆向過程；與正典衝突處以正典為準（例：報名審核非缺口、ops台源碼齊全只被RBAC鎖、vouchers走獨立GW、boy=admin非super_admin）。
>
> 逆向自 https://admin.jiomj.com/（帳號 boy / boy123，2026-07-17 探勘）。
> 這是**前工程師做的既有後台**，非我們 `admin/` 下的設計模組。純逆向紀錄，供 L1/L2 後台設計參考。

## 一句話定性（修正版 — 比表面看到的多）
表面上（`boy` 帳號能看到的側邊欄）是一個**唯讀分析儀表板 + 全體推播**。
但**扒開 JS bundle 後發現：完整的營運操作台其實已經寫好了**，只是被 RBAC 權限鎖住 —
`boy`（role=`admin`）看不到、隱藏路由會被導回首頁、部分端點回 403 Forbidden。
首頁系統公告自己也寫「v2.0.0 新增管理員權限控制模組」。
→ 結論：**營運層不是缺口，是已存在但被權限藏起來**。要拿到需要更高權限帳號（super_admin）。

## 權限分層（RBAC，2026-07-17 實測）
- `boy` / `boy123` = role `admin`，能用：9 個分析頁 + 推播 +（後端層）users 列表、logs。
- `/admin/vouchers` 對 `boy` 回 **403 Forbidden** → 抵用券模組需更高權限。
- 隱藏前端路由（`/users` `/moderation` `/vouchers` `/versions` `/settings` `/activities` `/event-commands`）
  在部署版**全部 redirect 回 `/`** → 有 route guard，`boy` 不夠格。

## 技術棧
- 前端：React + Vite SPA，S3 + CloudFront（`両雀 | 管理後台`，System v2.0.0）。與正式前端 webapp 同一套技術棧。
- 後端 API：`https://yg7y0xkb50.execute-api.ap-southeast-1.amazonaws.com`
  — **與正式前端 App 同一個 API Gateway**（新加坡 ap-southeast-1），後台端點掛在 `/admin/*` 前綴。
- 認證：`POST /admin/login` → 回 JWT（HS256，`role: admin`，`sub: boy`，exp 約 24h）。前端存 token 後帶在後續請求。
- 視覺：深色主題（`#05060f`）、cyan 漸層點綴、左側導覽 + 卡片 + 折線/長條/熱力圖（Leaflet 地圖）。設計質感不錯。

## 導覽結構（3 分區 / 10 頁）

### 核心數據
| 頁面 | 路由 | API | 內容 |
|---|---|---|---|
| 數據總覽 | `/` | `GET /admin/stats`, `GET /admin/analysis/traffic` | 總覽儀表板：總用戶/今日新增/招募中團局/已滿/總團局/待處理報名，近 7 日新增用戶、開局數、流量、報名趨勢圖，系統公告 |

### 數據分析（8 頁，全部唯讀）
| 頁面 | 路由 | API | 重點指標 |
|---|---|---|---|
| 用戶深度分析 | `/analysis/users` | `GET /admin/analysis/users` | 總註冊、今日新增、開啟推播比例、次日留存、簽到 DAU 趨勢、**潛在儲值需求用戶**（頻繁開局+低點數）、**高點數大戶名單**（餘額 >5000 點） |
| 團局深度分析 | `/analysis/games` | `GET /admin/analysis/games` | 累積團局、開桌數、完成率、平均時長、熱門時段 24h 分佈、團局狀態分佈、**地理位置熱力圖 + 縣市團局數**（Leaflet） |
| 社群互動分析 | `/analysis/social` | `GET /admin/analysis/social` | 今日貼文/按讚、優質作者、互動趨勢、每日發文量 |
| 聊天室深度分析 | `/analysis/chat` | `GET /admin/analysis/chat` | 總聊天室、WebSocket 在線人數、近 7 日訊息、熱門聊天室 Top10 |
| 計帳次數深度分析 | `/analysis/ledger` | `GET /admin/analysis/ledger` | 麻將計帳簿：總記帳筆數、使用人數、團局整合比例、心情回饋分佈、來源（手動 vs 團局關聯）、系統依賴度 |
| 流量深度分析 | `/analysis/traffic` | `GET /admin/analysis/traffic` | 各模組 API 請求量（核心/牌局/社群/即時通訊/用戶中心/計帳），動作分佈細項 |
| Token 使用分析 | `/analysis/token` | `GET /admin/analysis/token` | JWT 使用率追蹤（新版 App 推廣進度），帶/無 Token 請求、三階段強制目標、各端點使用率 |
| 邀請碼成效分析 | `/analysis/invite` | `GET /admin/analysis/invite` | 總邀請註冊數、每日趨勢、邀請人數分布 |

### 營運管理
| 頁面 | 路由 | API | 內容 |
|---|---|---|---|
| 全體推送通知 | `/push` | `POST /admin/push`（點發送時觸發） | 向所有訂閱 Web Push 的用戶發廣播：標題/內容/跳轉網址 + 手機預覽。**唯一的寫入操作** |

## 完整後端端點清單（從 JS bundle 撈出，含隱藏）
> `*` = 前端 router 有頁面但被導回首頁；`403` = boy 帳號被 RBAC 擋。

| 端點 | 方法 | 狀態 | 用途 / 回傳 |
|---|---|---|---|
| `/admin/login` | POST | ✅ | 帳密登入 → JWT（HS256, role, sub, exp≈24h） |
| `/admin/stats` | GET | ✅ | 總覽儀表板數字 |
| `/admin/analysis/{users,games,social,chat,ledger,traffic,token,invite}` | GET | ✅ | 8 個分析頁資料 |
| `/admin/push-all` | POST | ✅(未觸發) | 全體 Web Push 廣播 |
| `/admin/users` | GET | ✅ 需 `?page=&limit=` | **用戶列表**：id/displayName/**email**/status/role/points/lastLoginAt/createdAt |
| `/admin/users/points/history` | GET | 未測 | 單一用戶點數異動歷史 |
| `/admin/logs` | GET | ✅ | 管理員操作審計日誌（DynamoDB attr 格式，如 UPDATE_CONFIG） |
| `/admin/activities` | GET | * | 活動（前端有 route，導回首頁） |
| `/admin/moderation/reports` | GET | * | 檢舉列表 |
| `/admin/moderation/action` | POST | * | 審核處置（下架/封鎖等） |
| `/admin/vouchers` | GET | **403** | 抵用券/優惠券列表 |
| `/admin/vouchers/update` `/admin/vouchers/delete` | POST | 403 | 抵用券增改刪 |
| `/admin/config/version` | GET | 500* | 版本/強制更新設定（minVersion/forceUpdate/maintenanceMode/updateUrl） |
| `/admin/admins` | GET | * | **多管理員帳號管理**（新增/權限） |

→ 也就是說後端**已經有**：用戶管理、點數歷史、內容審核、抵用券、版本/維護模式控制、多管理員 RBAC。這些正是「營運操作台」該有的東西，工程師都做了，只是沒對 `boy` 開放。

## 關鍵資料 schema（實測回傳）
- `stats.data`：`users{total,newToday,activeToday,growthRate}` / `games{total,active,recruiting…,full…}` / `registrations{total,pending,accepted,acceptanceRate}` / `community` / 各 `*Trend[]`
- `analysis/users.data`：`totalUsers` / `highPointsUsers[50]{userId,nickname,points,gamesHosted}` / `lowBalanceFrequentHosts` / `pointsFrequency[]{points,count}` / `pushStats{count,rate,deviceDistribution[]}` / `retention{day1,day7,day30}` / `trends[14]{date,dau,new}` / `versionDist[]{name,value}`
- `analysis/games.data`：`totalGames/completedRate/timeSlots[24]/distribution[]/locations[]{lat,lng}/regionCounts{縣市:數}/…Trend[]`
- `analysis/ledger.data`：`totalEntries/uniqueUsers/manualCount/integratedCount/integrationRatio/moodStats[]/trends[14]`
- `analysis/traffic.data`：`totalHits/categoryDistribution[6]/actionBreakdown{core,games,community,chat,user,ledger}[]/trends[7]`
- `analysis/token.data`：`overview{today,yesterday}{total,withToken,withoutToken,tokenRate}/byEndpoint[]/trends[14]`
- `admin/users` item：`{id, displayName, email, status:'active', role:'user', points, lastLoginAt, createdAt}` ← **點數就在 user 物件上**

## 探勘當下的真實數據（2026-07-17）
- 總用戶 **13,416**、開啟推播 5,296（39.5%）、次日留存 45.5%
- 累積團局 35、完成率 92.5%、平均時長 124 min；縣市分佈以台南(7)、新北/彰化(5)為多
- 計帳筆數 **25,102**、使用人數 1,709，但**團局整合率 0.0%**（幾乎全是手動輸入 25,064 vs 團局關聯 38）→ 計帳功能與團局系統實質脫鉤
- 待處理報名 **286**（主揪尚未審核，接受率 74.1%）
- JWT/Token 使用率 45.8%，新版 App 推廣中（三階段漸進強制）
- 邀請註冊 535，高點數大戶如 Lulu 1,106,000 點、Grace 819,240 點

## 對我們設計的意義（重點）
1. **後端 API 就是這顆** `yg7y0xkb50`（新加坡），後台端點 `/admin/*` 與 App 端點共用同一 API Gateway → 我們做 L1/L2 `grant()` 時，要接的就是這套後端。
2. 既有後台**只有分析 + 推播**，缺一整層**營運操作台**（用戶管理/點數調整/團局審核/內容審核/報名審核/封鎖）。286 筆待審報名目前後台無介面可審 → 這是明顯缺口。
3. **點數（雀幣）已在跑**且有大戶（百萬級餘額）——與我們「雀幣/牙齒不互換、雀幣獨立錢包」的設計一致，但既有後台沒有點數發放/調整入口。
4. 計帳簿與團局整合率 0% → 產品層已知的斷點，設計時可考慮補這條整合。
5. Token 三階段強制 = 工程師正在把舊版無 token 請求逐步淘汰，我們的 L0 身分橋若要打這套 API，要走帶 JWT 的新版路徑。

## 缺口 vs 已存在（修正）
**已存在（後端有、前端有頁但被鎖）**：用戶管理、點數異動歷史、內容審核(moderation)、抵用券、版本/維護模式、多管理員 RBAC、操作審計 logs。
→ 想用只要拿到 super_admin 權限帳號 / 放開 route guard 即可，不必重做。

**仍是真缺口（連端點都沒看到）**：
- 團局審核 / 報名審核（286 筆待處理 pending，只有分析頁看得到數字，沒有處置端點）
- 金流 / 儲值訂單管理（Token 分析出現 `web_subscription_status` → 有訂閱機制，但無訂單/發票後台）
- 客服對話 / 工單

## 待辦 / 待問工程師
1. 有沒有 super_admin 帳號？想看被鎖住的 users/moderation/vouchers 實際 UI。
2. 抵用券(vouchers)模組是做完還是半成品？（403 擋住看不到）
3. 報名審核（286 筆 pending）目前是怎麼處理的？有沒有 App 端主揪自審、還是根本卡著？
4. 這套後端 = App 正式後端，我們 L1/L2 `grant()` 要接的就是它，需要拿到寫入端點文件。

---

# 後台資料字典（Data Dictionary）
> 從 API 回傳反推。⭐=已實測確認欄位；🔶=由畫面/指標推斷、待工程師確認。

## A. 底層資料實體（推斷的領域模型 / DynamoDB 表）

### User 用戶 ⭐（`/admin/users` 直接回這些）
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` ⭐ | str | `APP_xxxx` 格式主鍵 |
| `displayName`/`nickname` ⭐ | str | 暱稱 |
| `email` ⭐ | str | Google 登入信箱（PII） |
| `status` ⭐ | str | `active` / (可能 banned/suspended) |
| `role` ⭐ | str | `user` / `admin` |
| `points` ⭐ | int | **雀幣點數餘額**（直接掛在 user 上） |
| `lastLoginAt` ⭐ | ISO8601 | 最後登入 |
| `createdAt` ⭐ | ISO8601 | 註冊時間 |
| `gamesHosted` ⭐ | int | 累計開局數（分析頁用） |
| `appVersion` 🔶 | str | 版本分佈用（2.0.1 等） |
| `pushEnabled`/`deviceCount` 🔶 | bool/int | 推播訂閱、裝置數 |
| `invitedBy` 🔶 | str | 邀請人（邀請碼分析用） |
| 分頁：`lastKey` + `meta` ⭐ | | DynamoDB 游標分頁 |

### Game 團局 🔶（`/admin/analysis/games` 聚合來源）
`id` / `hostUserId` / `status`(recruiting/full|ongoing/ended/cancelled/expired) / `region`(縣市) / `lat` `lng` ⭐ / `createdAt` / `startTime` / `durationMin`(平均124) / `capacity` `playerCount` / `title`

### Registration 報名 🔶（stats.registrations：total/pending/accepted/acceptanceRate）
`id` / `gameId` / `userId` / `status`(**pending**/accepted/rejected) / `createdAt` / `clickCount`
→ **286 筆 pending 待審**，這是最需要補處置介面的實體。

### Post 社群貼文 🔶（analysis/social）
`id` / `authorId` / `likes` / `comments` / `createdAt` / `qualityWeight`(優質作者權重)

### ChatRoom / ChatMessage 🔶（analysis/chat）
Room：`id` / `name` / `onlineUsers`(WebSocket) / `messageCount` / `createdAt`
Message：`roomId` / `userId` / `content` / `timestamp`

### LedgerEntry 麻將計帳 🔶（analysis/ledger）
`id` / `userId` / `gameId`(optional，整合率0%) / `source`(manual/game) / `mood`(開心/普通/難過) / `amount`🔶 / `createdAt`

### Invite 邀請 🔶（analysis/invite）
`inviterId` / `inviteeId` / `code` / `createdAt`（分佈：1人/2-3/4-5/6-10/10+）

### PointsHistory 點數異動 🔶（`/admin/users/points/history`，需正確參數）
`userId` / `delta` / `reason` / `balanceAfter` / `timestamp`

### Voucher 抵用券 🔶（`/admin/vouchers`，boy 被 403）
`id` / `code` / `value` / `status` / `expireAt` / `usedBy`

### AdminConfig 版本/維護 ⭐（logs target=AdminConfigs 揭露）
`minVersion` ⭐ / `latestVersion` ⭐ / `forceUpdate` ⭐(bool) / `maintenanceMode` ⭐(bool) / `updateUrl` ⭐

### AdminUser 管理員 🔶（`/admin/admins`）
`username` / `role`(admin/super_admin) / `permissions[]` / `createdAt`

### AdminLog 審計日誌 ⭐（`/admin/logs`，DynamoDB 原生 attr）
`log_id` ⭐ / `admin` ⭐ / `action` ⭐(UPDATE_CONFIG…) / `target` ⭐(表名) / `details` ⭐(JSON string) / `timestamp` ⭐(unix)

### Report 檢舉 🔶（`/admin/moderation/reports`）
`id` / `reporterId` / `targetType`(post/user/chat) / `targetId` / `reason` / `status`(pending/resolved)

### TrafficLog API 流量 🔶（driving analysis/traffic + token）
`category`(core/games/community/chat/user/ledger) / `action`(create_game…) / `hasToken`(bool) / `endpoint` / `timestamp`

## B. 每個後台頁面消費的數據（Consumption view）

| 頁面 | 需要的數據/欄位 |
|---|---|
| 總覽 `/` | User.total/newToday/activeToday；Game.total/active/recruiting/full；Registration.total/pending/acceptanceRate；7日 trends(users/games/reg/traffic) |
| 用戶分析 | User 全表聚合：totalUsers、highPointsUsers(points>5000)、lowBalanceFrequentHosts(開局≥10且points≤360)、pointsFrequency 分佈、pushStats、retention(d1/d7/d30)、DAU(簽到)、versionDist |
| 團局分析 | Game：completedRate、timeSlots[24h]、status distribution、locations[lat/lng]、regionCounts[縣市] |
| 社群分析 | Post：今日貼文/按讚、topAuthors[權重]、發文趨勢 |
| 聊天室分析 | ChatRoom：totalRooms、onlineUsers、messageCount、topRooms[Top10] |
| 計帳分析 | Ledger：totalEntries、uniqueUsers、manual vs integrated、moodStats、14日趨勢 |
| 流量分析 | TrafficLog：categoryDistribution、actionBreakdown、totalHits、趨勢 |
| Token 分析 | TrafficLog.hasToken：today/yesterday tokenRate、byEndpoint、14日趨勢 |
| 邀請分析 | Invite：totalUsage、每日趨勢、邀請人數分佈 |
| 推播 | 寫入：{title, body, url} → 發全體訂閱者 |
| **用戶管理**(鎖) | User CRUD + 調 points + 改 status/role + PointsHistory |
| **內容審核**(鎖) | Report 列表 + moderation/action 處置 |
| **抵用券**(鎖,403) | Voucher CRUD |
| **版本設定**(鎖) | AdminConfig：min/latestVersion、forceUpdate、maintenanceMode、updateUrl |
| **管理員**(鎖) | AdminUser + permissions；AdminLog 審計 |
