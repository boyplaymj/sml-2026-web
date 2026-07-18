# 両雀 — 服務接手交接需求（給工程師）

嗨 👋

我們要把両雀後端服務接手、搬到我們自己的 AWS 帳號。做法是**平行架一套 staging 影子環境**先跑起來、確認資料與功能都對之後，才做正式切換，**全程可回滾、對你現在線上的服務零影響**。目前 staging 已經架好、程式也跑通了，接下來需要麻煩你協助幾件事才能把真實資料與網域接過來。

已按「最省你力氣」的方式整理，每項都附了具體做法。有任何一步不確定，跟我說一聲就好 🙏

---

## 📋 一眼清單（你要準備的東西）

| # | 項目 | 必要性 | 大概要做什麼 |
|---|------|--------|--------------|
| ① | DynamoDB 資料匯出 | **必要** | 對表做 Export to S3，開唯讀給我們拉 |
| ② | `ENCRYPTION_KEY` 原值 | **必要** | 走安全管道給我們（LINE 綁定解密要用） |
| ③ | 輪換 2 把外洩的 AWS IAM key | **建議盡快** | 到 IAM 停用/換掉（安全） |
| ④ | jiomj.com 網域移交 | 切換前 | 給授權碼轉移，或改 nameserver |
| ⑤ | LINE channel 移交 | 切換前 | channel 擁有權 / secret / access token |

> ①② 先給我們就能開始做遷移演練；③ 越早越好；④⑤ 到正式切換前準備即可。

---

## ① DynamoDB 資料匯出（最主要）

**目的**：把正式環境資料完整拷一份，讓我們灌進 staging 做遷移演練（比對筆數、點數餘額加總、抽樣驗證）。
**你的環境**：AWS 帳號 `228304098112`、region `ap-southeast-1`。

### 建議做法：DynamoDB「Export to S3」（對線上零影響、不用寫程式）
這是**時間點快照匯出**，不吃讀取容量、不影響服務：

1. 對每張表啟用 **PITR（Point-in-time recovery）**（若還沒開）。
2. Console → DynamoDB → **Exports to S3**，或 CLI：
   ```bash
   aws dynamodb export-table-to-point-in-time \
     --table-arn arn:aws:dynamodb:ap-southeast-1:228304098112:table/<表名> \
     --s3-bucket <你的匯出桶> --s3-prefix ryojaku-export/<表名> \
     --export-format DYNAMODB_JSON --region ap-southeast-1
   ```
3. 匯出檔（DynamoDB JSON、gzip）落在你的 S3 後，**交付方式二選一**：
   - **(A 最省事)** 在該桶加一條 policy，允許我們帳號 `380931373365` 唯讀那個 prefix，把桶名 + prefix 給我們，我們自己拉。
   - **(B)** 直接把檔案給我們（大表可能上 GB，建議走 S3 連結而非附件）。

> 嫌逐表麻煩，直接**整批匯出所有 `MahjongClub_*` 開頭的表** + 下面兩張 `LineBot-*` 就好，我們不怕多、只怕漏。

**要匯出的表（共 27 張）**：
```
MahjongClub_Users                 MahjongClub_Games              MahjongClub_Registrations
MahjongClub_Ratings               MahjongClub_RatingComments     MahjongClub_PointTransactions
MahjongClub_Ledger                MahjongClub_Community          MahjongClub_Notifications
MahjongClub_DailyClaims           MahjongClub_EventCommands      MahjongClub_EventRedemptions
MahjongClub_RedeemCodes           MahjongClub_CodeBatches        MahjongClub_ActivityVouchers
MahjongClub_ChatMessages          MahjongClub_ChatRooms          MahjongClub_ChatConnections
MahjongClub_ChatUserMemberships   MahjongClub_PushSubscriptions_MultiDevice
MahjongClub_AdminUsers            MahjongClub_AdminConfigs       MahjongClub_AdminAuditLogs
MahjongClub_APITokenStats         MahjongClub_TrafficStats
LineBot-User-Profiles             LineBot-User-Profile-Sessions
```
（若你那邊實際表名/前綴不同，以你的為準；我們只要完整、不遺漏即可。）

---

## ② `ENCRYPTION_KEY` 原值（必要）

Users 表裡 LINE 綁定帳號的 `encryptedLineId` 是用 `ENCRYPTION_KEY`（AES）加密的。**一定要拿到原本那把 key**，否則所有 LINE 綁定的帳號在新環境會解不開＝壞掉。

- 請走**安全管道**提供 `ENCRYPTION_KEY` 原值（別貼公開對話；用私訊或密碼管理器分享連結）。
- 其他機密**可選、之後再說**：`JWT_SECRET`（換掉＝全用戶被登出，可接受但挑時機）、`VAPID_PUBLIC/PRIVATE_KEY`（換掉推播訂閱要重訂）、`Gemini` / `OpenAI` API key（決定用你的還是我們自己開帳單）。先給 `ENCRYPTION_KEY` 最關鍵。

---

## ③ 請輪換兩把外洩的 AWS IAM 金鑰（安全提醒）

我們在你交付的原始碼裡發現**硬編了 2 把 AWS IAM access key**（在前端/後端的 `.ps1` / `.md` 部署腳本內），GitHub 的 push protection 也擋過。這等於憑證外流風險：

- 麻煩盡快到 IAM **停用 / 輪換這兩把 key**。
- 我們這邊已把值遮蔽、隔離保存、不會外流；但源頭那兩把還是建議你換掉。

---

## ④ 網域 `jiomj.com` 接手（我們要繼續沿用這個網域）

`jiomj.com` 的 DNS 在你的 AWS Route53、指向你的 CloudFront。我們想**保留這個網域繼續用**，需要把它接過來。兩條路擇一（建議最終走「完整移轉」）：

### 路線 A（建議）：把網域「註冊」整個轉給我們 — 真正擁有
1. 告訴我們 **jiomj.com 註冊在哪家註冊商**（GoDaddy / お名前.com / Gandi / Namecheap…）。
2. 到該註冊商後台：**解鎖網域**（關掉 transfer lock）＋ **暫時關閉 WHOIS 隱私**（授權信要收得到）＋ 給我們 **授權碼（Auth Code / EPP code）**。
3. 確認網域**註冊已滿 60 天**、近 60 天沒轉移過（註冊商規定）。
4. 我們在自己的註冊商發起轉入、輸入授權碼，雙方 email 確認，約 **5–7 天**完成。之後 DNS / 憑證 / CloudFront 全部我們自己重建。

### 路線 B（較快，但註冊仍在你名下）：只把 DNS 委派給我們
1. 我們先在自己的 Route53 建 `jiomj.com` hosted zone，產出 **4 個 nameserver** 給你。
2. 你到註冊商把 `jiomj.com` 的 **nameserver 改成我們給的那 4 個**。
3. 之後 DNS 全我們掌控（自簽 ACM、指向我們的 CloudFront）。
   ⚠️ 缺點：續約 / 所有權還是你，你若忘記續約我們會連帶失去 → 建議之後仍補做路線 A。

*（ACM 憑證我們拿到 DNS 控制權後自己重簽，不用你處理。）*

---

## ⑤ LINE 官方帳號 / LINE Login channel 移交（跟網域一起）

這個 App 靠 LINE 綁定運作（LINE Login、`encryptedLineId`、推播），callback / webhook URL 都綁在 jiomj.com。**光轉網域不夠**，LINE Developers console 那邊也要移交，否則 LINE 登入 / 推播會斷：

- **LINE Login channel** 和 **Messaging API channel** 的 **channel ID / channel secret / channel access token**。
- 決定移交方式：把 console 的 **admin 權限加給我們**，或把 channel 轉到我們的 LINE Developers provider。
- 之後 callback / webhook URL 我們會改指到新後端。

---

## 其他 / 時程

- 資料匯出可以你方便時做，我們先拿一份**近期快照**做演練即可。
- 正式切換前，我們會再跟你約一次「**最終增量同步 + 短暫凍結寫入**」的窗口，把切換當下的新資料補齊，確保零遺失。
- 全程你現在的線上服務不受影響；真的切換也保留舊站可回滾 N 天。

再次感謝協助，有任何一項需要我補 CLI 指令 / policy 範本，我馬上給 🙏
