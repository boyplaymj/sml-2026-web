---
name: deploy
description: 把 SML 官網 (sml-site) 部署／更新上線到 AWS S3 + CloudFront（正式網址 https://site.supermahjongleague.com）。當使用者說「更新」「更新網站」「佈版」「上線」「部署」「deploy」「push」等、要把目前的網頁推上線時使用。改完網頁內容後也會自動觸發。
---

# 部署 / 更新 SML 官網

使用者要把目前 `W:\SML\個人賽2026\sml-site` 的網頁推上正式網站時，執行以下動作：

## 步驟

1. 用 PowerShell 工具執行一鍵部署腳本：

   ```
   powershell -File "W:\SML\個人賽2026\sml-site\deploy.ps1"
   ```

   這支腳本會（三步）：
   - **[1/3]** `aws s3 sync` 整個 `sml-site` 到 `s3://boyplaymj-smlweb/sml-site/`（排除 .claude、*.psd、deploy.ps1、.git），資產帶 `Cache-Control max-age=86400`，並對 `index.html` / `style.css` / `app.js` 補正確 `Content-Type`（charset=utf-8）+ `max-age=300`
   - **[2/3]** `aws cloudfront create-invalidation --paths "/*"` 清除快取
   - **[3/3]** `git add -A` + `git commit` + `git push origin main` 自動存版本到 GitHub（repo: https://github.com/boyplaymj/sml-2026-web）。可加 `-msg "訊息"` 自訂 commit 訊息,不給則用時間戳
   - AWS CLI 完整路徑：`C:\Program Files\Amazon\AWSCLIV2\aws.exe`（不在 PATH）
   - CloudFront distribution：`E1J9S5W173HSDB`

2. 部署完成後，向使用者回報結果並附上網址：**https://site.supermahjongleague.com**

## 注意

- **只改 Firebase 資料**（選手、積分）**不需要跑這個**——那是官網即時讀取的，後台按「🌐 同步官網數據」就會自動更新。本 skill 只用於「網頁本身（版面／文字／程式）有改、要重新上線」。
- 部署是發布到正式網域，跑完務必回報成功與否。
- 若腳本因 AWS 憑證或網路失敗，把錯誤訊息回報給使用者，不要靜默重試。
