# 両雀 Ryōjaku — 源碼校正正典（SOURCE OF TRUTH）

> 2026-07-17 工程師交付三份完整原始碼專案（frontend / backend / admin_frontend），由 4 個平行探勘萃取後彙整。
> **本檔為正解**，取代 `SPEC.md`（前端逆向）與 `ENGINEER_ADMIN.md`（後台逆向）中的 🔶 推斷。
> 源碼在 `/tmp/ryo-docs/ext_*`（repo 外，含機密不入 git）。

---

## 0. 系統總覽
- **後端**：Go，module `mahjongclub-backend`，架構 = **一顆 Lambda 一個 API endpoint**（`cmd/lambdas/apis/mahjongclub_*/main.go`），共 **~47 支**。
- **前端 App**：React 18 + TS + Vite + **React Router v6（HashRouter）**，**MapLibre GL**（⚠️非逆向誤判的 Leaflet；Leaflet 是「後台」用的）、Tailwind、Web Push PWA。
- **後台 admin**：React + TS + Vite，Leaflet 熱力圖。
- **雲**：AWS ap-southeast-1（新加坡），DynamoDB 24 表（`MahjongClub_` 前綴）+ 多顆 API Gateway + WebSocket API + S3 圖床。
- **主 API GW**：`yg7y0xkb50.execute-api.ap-southeast-1.amazonaws.com`
- **WebSocket**：`wss://ek5dythoh9.execute-api.ap-southeast-1.amazonaws.com/prod?userId=&token=`
- **抵用券另一顆 GW**：`00pox0hvv4.execute-api.ap-southeast-1.amazonaws.com/prod`

## 1. 認證與身分（⭐ 對我們 L0 LINE 橋最關鍵）
- **雙軌身分**：`userId`（App 用戶，`APP_xxx`）或 `lineID`（LINE Bot 用戶，**加密**，`ENCRYPTION_KEY`）。多數端點兩者皆收（query `?userId=` / `?lineID=`）。
- **User 表已有 LINE 綁定欄位**：`lineId` / `encryptedLineId` / `accountType`（`linebot`|`app`）。`app_login` 支援用 `encryptedLineId` 直接登入。
- ⚠️ **現況 LINE 只是「備援登入」，不是 LIFF、沒有 LINE miniapp**。主登入 = email/password。→ 我們的「LINE-first/LIFF」是**新方向**（要新做 LIFF 入口），但底層 LINE↔App 綁定資料模型已存在可接。
- **User JWT**：HS256，claims `{userId,email}`，**30 天**。`JWT_SECRET`（有寫死 fallback 預設值 = ⚠️安全隱憂，建議工程師改）。
- **Admin JWT**：`POST /admin/login`（Lambda `mahjongclub_admin_login`）→ 查表 `MahjongClub_AdminUsers`（`username` PK、**bcrypt** passwordHash、role），claims `{sub,role}`，**24h**。
- **角色只有兩級**：`admin`（分析+推播）vs `super_admin`（全解鎖）。**無細粒度權限旗標**。`boy` = `admin` → 這就是 vouchers 回 403、ops 頁被藏的原因。

## 2. 後台 admin — RBAC 對照（源碼確認）
前端 route guard 只是 UX（`requireSuper` → 非 super 導回 `/`），真正授權在後端 enforce。

| 頁面/路由 | 前端需 super? | 後端角色 | 端點 |
|---|---|---|---|
| Dashboard `/` | 否 | 任何登入 | `admin_dashboard_get_stats` |
| 8 個 `/analysis/*` | 否 | 任何登入 | `admin_analysis` |
| 全體推播 `/push` | 否 | admin+ | `admin_push_all`（後端其實 super_admin，但 sidebar 對 admin 顯示） |
| 用戶名單 `/users` | **是** | admin/super | `admin_users` |
| 內容審核 `/moderation` | **是** | super | `admin_moderation`（suspend/unsuspend/ban） |
| 序號管理 `/vouchers` | **是** | **super（403 擋 admin）** | `admin_vouchers`（另一顆 GW） |
| 行銷活動 `/activities` | **是** | admin+ | `admin_activities` |
| 活動指令 `/event-commands` | **是** | super | EventCommands |
| 版端更新 `/versions` | **是** | super | `admin_versions`（min/latest/forceUpdate） |
| 帳號系統設置 `/settings` | **是** | super | `admin_admins`（增/刪管理員、改 role） |
| 點數歷史 | — | admin+ | `admin_point_history`（查 PointTransactions） |
| 操作日誌 `/logs` | — | 任何登入 | `admin_logs`（AdminAuditLogs） |

## 3. 前端 App — 12 路由（逆向 100% 命中）
`/`(Home feed) · `/search`(找場,all/nearby GPS) · `/messages`(聊天列表) · `/chat/:roomId`(即時聊天) · `/create`(開團+地圖+AI生描述) · `/event/:id`(團局詳情/報名/主揪審核/評價) · `/post/:id`(社群貼文詳情) · `/profile`(設定/統計/兌換碼/邀請) · `/notifications` · `/rate-game/:id` · `/rate-user` · `/ledger`(麻將記帳)

## 4. API 端點全表（46 HTTP + 1 WS，逆向只猜到 31）
> 前端呼叫路徑 → 後端 Lambda。Auth 欄：U=userId/lineID、A=admin JWT、-=公開。

**認證/版本**：`/app-version-config`(-) · `/app-register`(-,新用戶+50、邀請人+獎) · `/app-login`(-,email/pw或encryptedLineId) · `/verify-user`(LINE備援)
**團局**：`/search-games` · `/create-game`(**−120點**) · `/game-detail` · `/my-games` · `/game-register` · `/accept-registration` · `/reject-registration` · `/cancel-game` · `/cancel-registration`（全 U，主揪操作驗 host）
**評價**：`/submit-rating`(👍/👎+comment) · `/ratings` · `/user-comments`
**用戶**：`/user-info` · `/user-profile`(GET/POST,含 lineId 綁定) · `/notifications`(GET/POST已讀)
**推播**：`/vapid-key`(-) · `/subscribe-push` · `/unsubscribe-push` · `/subscription-status` · `/claim-push-bonus`(**首次+50**)
**點數**：`/redeem-code`(碼值) · `/daily-bonus`(**+10,連七+50**)
**社群**：`/community-create-post` · `/community-get-posts` · `/community-get-user-posts` · `/community-get-post-detail` · `/community-like-post` · `/community-add-comment` · `/community-like-comment`
**上傳**：`/get-upload-url` · `/community-get-upload-url` · `/event-get-upload-url`（S3 預簽章）
**聊天**：`/chat/rooms` · `/chat/history` · `/chat/room-info` · `/chat-mark-read` · `/chat/get-upload-url` · **WS** `sendMessage`（room 廣播）
**記帳**：`/ledger`(GET/POST/PUT/DELETE) · `/ledger/summary`
**後台代理**：`/admin/activities`(GET/POST)

## 5. 點數/雀幣經濟（⭐ grant() 對接點）
- **流水表 = `MahjongClub_PointTransactions`**：PK`userId` + SK`TIME#<ts>#<uuid>`，欄位 `type`(CREDIT/DEBIT)/`amount`/`balanceBefore`/`balanceAfter`/`reason`(繁中)/`source`(功能名)/`metadata`{gameId,code}；GSI `userId-createdAt-index`。
- **寫入器 = `shared/points.go` `UpdateUserPoints()`**：改 `Users.points` 同時 shadow-log 到 PointTransactions（async goroutine，失敗不阻塞主流程）。
- **現行費率**：開團 −120｜每日簽到 +10（連七 +50）｜邀請雙方各 +50〜（app_register，邀請人數值待與工程師確認 50 vs 100）｜首開推播 +50｜兌換碼依碼值。
- → **我們 grant() 發雀幣直接沿用 `UpdateUserPoints`**，points 有完整流水、非裸 int。

## 6. DynamoDB 24 表（`MahjongClub_` 前綴）
| 表 | PK | SK | GSI |
|---|---|---|---|
| Users | userId | - | email-index, invitedBy-index |
| Games | gameId | - | status-createdAt-index, gameId-createdAt-index |
| Registrations | gameId | userId | gameId-createdAt-index |
| RatingComments / Ratings | gameId | fromUserId | toUserId-createdAt-index 等 |
| Community(單表:Post/Comment/Like) | postId | sortKey(METADATA/COMMENT#/LIKE#) | authorId-createdAt-index |
| **PointTransactions** | userId | TIME#… | userId-createdAt-index |
| Ledger(麻將記帳) | userId | LEDGER#… | - |
| ChatRooms / ChatUserMemberships / ChatMessages / ChatConnections | 各異 | 各異 | UserID-index 等 |
| Notifications | userId | createdAt | - |
| PushSubscriptions_MultiDevice | userId | deviceId | - |
| AdminUsers / AdminAuditLogs / AdminConfigs | - | - | - |
| RedeemCodes / EventCommands / EventRedemptions / ActivityVouchers / DailyClaims / APITokenStats | - | - | - |
| **LineBot-User-Profiles / -Sessions**（AI顧問+LINE） | user_id | - | - |

**設計**：多表混合；只有社群走單表 SK 前綴；聊天拆 4 表。Games/Notifications/Chat 有 TTL 自動清。

## 7. 兩套 AI（成本/vendor 注意）
- **前端 App**：**Google Gemini** 生成開團描述/標題建議/自然語言解析（非媒合）。
- **後端**：`internal/services` 整組 **OpenAI** 顧問媒合（consultant/red_thread_generator 紅線/smart_form/typing_delay），存 `LineBot-User-Profiles`。
- ⚠️ 兩套都**不是 Bedrock**（Gemini + OpenAI）→ 若要納入我們成本控管體系需注意（外部付費 API，對照 `COST_CONTROL.md`）。

## 8. 逆向 vs 正解 — 校正清單
| 項目 | 逆向猜測 | 源碼正解 |
|---|---|---|
| 前端路由數 | 12 | **12 ✓ 完全命中** |
| API 端點數 | 31 | **46 HTTP + 1 WS**（漏了社群7/記帳5/聊天/推播獎金） |
| App 地圖庫 | Leaflet | **MapLibre GL**（Leaflet 是後台用的） |
| 報名審核 | 標為「缺口」 | **早有** accept/reject 端點（主揪自審） |
| points | 疑似裸 int 無紀錄 | **有 PointTransactions 流水表 + shadow log** |
| 後台 ops 台 | 「缺一層」 | **源碼全寫好**，只是 RBAC 對 admin 鎖住 |
| LINE 整合 | L0 要新建 | 底層綁定/加密**已存在**；但 LIFF 入口確實要新做 |
| 抵用券 | 同一 API | **獨立 GW** `00pox0hvv4` |

## 9. 給工程師的待確認（更新版）
1. 給一組 **super_admin** 帳號，才看得到 users/moderation/vouchers 實際後台。
2. 邀請獎勵數值：app_register 邀請人是 +50 還是 +100？（兩處敘述不一）
3. `JWT_SECRET` 寫死 fallback 建議移除/強制環境變數。
4. 我們要接 grant() 發雀幣 → 確認可直接呼叫內部 `UpdateUserPoints` 或需新開 admin 端點。
5. LINE-first/LIFF 入口要新建，但可重用既有 `encryptedLineId`/`accountType` 綁定 → 一起規劃。
