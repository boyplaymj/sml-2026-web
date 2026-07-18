# 両雀 (Ryōjaku) Web App — 還原規格書

> ✅ **2026-07-17 原始碼已交付並校正 → 正解看 [`SOURCE_TRUTH.md`](./SOURCE_TRUTH.md)**。校正重點：路由12個逆向100%命中；API實為46 HTTP+1 WS（本稿的31偏少）；App地圖是 **MapLibre GL** 非 Leaflet；LINE僅備援登入非LIFF。
>
> **來源**：本文件由 Claude 從已上線前端（`https://d1wa3w4dmfwqc7.cloudfront.net/`）逆向還原，
> 用於在工程師原始碼交付前先行開始開發。
> **可信度標記**：✅ 已從前端確認 ／ 🔶 由字串/欄位名推斷、待原始碼或實測校對。
> 最後更新：2026-07-15

---

## 1. 這是什麼

**「両雀 — ELITE COMMUNITY」** 是一個**封閉制（邀請碼）麻將玩家社群 / 揪團手機 PWA**。
核心是「找場 → 揪團 → 對局 → 記帳結算 → 互相評分累積信譽」的閉環，外加社群貼文、聊天、推播獎勵。

- 定位：台灣麻將玩家的 elite 社群（實測地點字串皆為台北）
- 形態：PWA（要求「加入主畫面」後以 standalone 模式使用；有推播、離線 manifest）
- 語系：`zh-TW`

---

## 2. 技術棧（逆向確認 ✅）

| 層 | 技術 |
|---|---|
| 前端框架 | React + React Router（client-side routing） |
| 打包 | Vite（`/assets/index-*.js` + `index-*.css`，hash 檔名） |
| 樣式 | Tailwind CSS（**走 CDN `cdn.tailwindcss.com`**，config 內嵌於 index.html） |
| 地圖 | Leaflet 1.9.4（CDN unpkg） |
| 地理服務 | AWS Location Service（geofencing / places / search，見 API 區） |
| 分享圖卡 | html2canvas（產生分享圖） |
| 後端 | AWS API Gateway：`https://yg7y0xkb50.execute-api.ap-southeast-1.amazonaws.com`（**ap-southeast-1 新加坡**） |
| 推播 | Web Push（VAPID key） |
| 圖片上傳 | S3 預簽章 URL 流程（各功能自有 `get-upload-url`） |

> ⚠️ Tailwind 走 CDN、無 build-time purge → 正式版效能/離線有隱憂，未來自架時建議改本地建置。

---

## 3. 設計系統（逆向確認 ✅）

- **登入頁**：米色點陣底 + 白卡，極簡高級感。App icon = 黑底白色小鹿/麻將意象。標語 `ELITE COMMUNITY`。
- **App 內部**：深色 **cyberpunk** 風。
  - 底色 `cyber.dark #050b14`、`cyber.slate #0f172a`、玻璃擬態 `rgba(15,23,42,0.6)`
  - 霓虹強調色：cyan `#06b6d4`、pink `#d946ef`、yellow `#facc15`、purple `#8b5cf6`
  - neon 陰影（`neon-cyan/pink/yellow`）、cyber grid 背景、scanline / grid-flow / float / pulse-glow 動畫
- 字體：Inter / Roboto（sans）、JetBrains Mono / Fira Code（mono）
- 斷點自訂：xs 375 / sm 640 / md 832（為大手機拉高平板門檻）/ lg 1024 / xl 1280 / 2xl 1536
- 安全區：`pt-safe` / `pb-safe`（`env(safe-area-inset-*)`）

---

## 4. 畫面路由（逆向確認 ✅）

| 路由 | 畫面 | 說明 |
|---|---|---|
| `/` | 登入 / 首頁 | 未登入顯示登入/註冊（Tab 切換）；註冊需 **邀請碼** |
| `/search` | 尋找團局 | Leaflet 地圖找場（定位、地點搜尋） |
| `/create` | 開局 / 建立紀錄 | 主揪開團 & 建立記帳紀錄 |
| `/event/:id` | 團局詳情 | 團局原始資訊、底台、場地特色、加入/取消 |
| `/my-events` 🔶 | 我的活動 | 參加紀錄 / 開團紀錄（見 `/my-events` API） |
| `/chat/:roomId` | 聊天室 | 加密頻道、圖片上傳、已讀 |
| `/messages` | 訊息列表 | 聊天室總覽 |
| `/notifications` | 通知 | 全部標為已讀 |
| `/post/:id` | 社群貼文 | 貼文詳情、留言、按讚 |
| `/profile` | 個人管理中心 | 個人檔案、勝率統計、設定、兌換獎勵 |
| `/ledger` | 記帳 | 個人財務管理、損益統計 |
| `/rate-game/:id` | 評分團局 | 對場次評分 |
| `/rate-user` | 評分玩家 | 對玩家好評/差評 + 標籤 |

---

## 5. 後端 API 合約（端點皆逆向確認 ✅；欄位為推斷 🔶）

Base：`https://yg7y0xkb50.execute-api.ap-southeast-1.amazonaws.com`
（下表以 `path` 表示；認證方式待確認，推測為 login 後 token/JWT）

### 5.1 帳號 / App
| 端點 | 用途 | 推斷欄位 🔶 |
|---|---|---|
| `GET /app-version-config` | App 版本/強制更新設定（開 App 第一支打的） | — |
| `POST /app-login` | 登入 | `{ email, password }` |
| `POST /app-register` | 註冊 | `{ nickname, email, password, inviteCode }` |
| `POST /verify-user` | 驗證使用者 | `{ ... }` |

### 5.2 揪團 / 團局 / 地圖
| 端點 | 用途 | 推斷欄位 🔶 |
|---|---|---|
| `GET /search` | 找場（列表/地圖） | query: `lat,lng,...` |
| `GET /terrain` | 地圖地形/圖層資料 | — |
| `GET /game-detail` | 團局詳情 | `?id=` |
| `GET /my-events` | 我的活動（參加/開團） | — |
| `POST /event-get-upload-url` | 團局圖片 S3 預簽章 | `{ fileType }` |
| （`/event/:id`） | 團局資源（含取消團局等操作） | — |

> 團局資料含：主揪/代揪、團局種類（俱樂部團局/個人自主練習/即時對局…）、**底台底注**、場地名稱與特色、
> 場數、人數、時間、地點（含經緯度）、等級（初級/中級…）、手速（快手/中慢手）、
> 標籤（禁菸/冷氣強/電動桌/汽機車停車位/提供飲料/歡迎新手…）。

### 5.3 社群貼文
| 端點 | 用途 |
|---|---|
| `POST /community-create-post` | 發文（title/content/images/tags/location） |
| `POST /community-add-comment` | 留言 |
| `POST /community-like-post` | 貼文按讚 |
| `POST /community-like-comment` | 留言按讚 |
| `POST /community-get-upload-url` | 貼文圖片 S3 預簽章 |

### 5.4 評分 / 信譽
| 端點 | 用途 | 推斷欄位 🔶 |
|---|---|---|
| `POST /submit-rating` | 送出評分 | `{ gameId/userId, rating, comment, tags }` |
| `GET /rate-game/:id` | 取評分團局資料 | — |
| `POST /rate-user` | 評玩家（好評/差評 + 標籤 + 內容） | `{ userId, score, comment, tags }` |
| `GET /reviews/:id` 🔶 | 取某人/某場評論列表 | — |

> 信譽系統：好評率、待評分人次、優秀好評、差評、標籤分類、專屬回饋獎勵。

### 5.5 記帳 / 財務
| 端點 | 用途 | 推斷欄位 🔶 |
|---|---|---|
| `GET/POST /ledger` | 個人記帳（建立/查詢/修改/刪除紀錄） | `{ date, amount, ... }` |
| `POST /overdraw` 🔶 | 透支/超額相關 | — |

> 記帳含：紀錄日期、實際盈虧/金額、結算狀態、損益統計、盈虧分配、勝率統計、相片紀錄、下拉刷新。

### 5.6 聊天
| 端點 | 用途 |
|---|---|
| `POST /chat-mark-read` | 標記已讀 |
| `POST /chat/get-upload-url` | 聊天圖片 S3 預簽章 |

> 訊息即時傳輸機制（WebSocket / 輪詢）待原始碼確認 🔶。

### 5.7 推播 / 獎勵
| 端點 | 用途 |
|---|---|
| `GET /vapid-key` | 取 Web Push VAPID 公鑰 |
| `POST /subscribe-push` | 訂閱推播 |
| `POST /unsubscribe-push` | 取消訂閱 |
| `GET /subscription-status` | 查訂閱狀態 |
| `POST /claim-push-bonus` | 領推播獎勵 |

### 5.8 通用
| 端點 | 用途 |
|---|---|
| `POST /get-upload-url` | 通用 S3 預簽章上傳 |

---

## 6. 推斷資料模型 🔶（待原始碼校對）

```
User        { userId, email, nickname, avatar, level, inviteCode,
              reputation{ goodRate, goodCount, badCount, tags[] },
              stats{ winRate, games } }
Event/Game  { id, hostId(主揪), coHostId(代揪), type(團局種類),
              baseStake(底台底注), venue{ name, features[], lat, lng, address },
              rounds(場數), capacity(人數), startTime, level, pace(手速),
              tags[], status(open/cancelled) }
Ledger      { id, userId, date, amount(實際盈虧), status(結算狀態),
              photos[], note }
Post        { id, authorId, title, content, images[], tags[], location,
              likes, comments[] }
Rating      { id, fromUserId, targetId(user/game), score(好評/差評),
              comment, tags[] }
Message     { roomId, senderId, content, image?, readAt }
```

---

## 7. 待確認清單（拿到原始碼/測試帳號後補）

- [ ] 認證機制：login 回傳 token 型別、header 帶法、有效期
- [ ] 各 API 完整 request/response schema（需登入後實測抓）
- [ ] 聊天即時機制（WS vs 輪詢）
- [ ] 邀請碼發放/驗證流程
- [ ] 推播獎勵（claim-push-bonus）的規則
- [ ] 兌換與獎勵系統的貨幣/點數來源
- [ ] 後端實作（Lambda 函式清單、DynamoDB 表結構）

---

## 8. 如何補完本規格

1. **給測試帳號** → Claude 用 Playwright 登入，逐頁截圖 + 攔截每支 API 真實 req/res，把 🔶 全部升級成 ✅。
2. **工程師交原始碼** → 對照本文件校正，補上第 6、7 章。
3. 之後新功能設計，直接沿用第 4（路由）、第 5（API 命名慣例）擴充。
