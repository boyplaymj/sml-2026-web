---
name: deploy
description: 統一部署 SML 各專案上線（官網／甜甜 bot／遊戲館／計分後台／Cloud Functions）。當使用者說「更新」「更新網站」「佈版」「上線」「部署」「deploy」「push」等要把東西推上線時使用。用法 /deploy <目標>；改完官網內容也會自動觸發（預設官網）。
---

# SML 統一部署 skill

一個入口、依目標路由到各自 canonical 流程，用機制保證跨專案部署一致性。
**環境：Linux（sml-claude-bot）。所有指令在本機執行。無獨立 CI 伺服器、GitHub push 不會自動部署**（見記憶 `project_deploy_architecture`）。

## 用法

```
/deploy site        官網 sml-site → S3 + CloudFront（預設；不帶參數也走這個）
/deploy sweetbot    甜甜 bot sweetbot-next → commit→push→systemd 重啟
/deploy games       甜甜遊戲館 → firebase（sweetbot-games.web.app）
/deploy broadcast   計分後台 broadcast → S3 + CloudFront
/deploy functions   score-repo Cloud Functions → firebase functions
```

不確定使用者要部署哪個時，先問清楚，不要猜著部署到正式環境。

## 各目標的動作

### site（官網 sml-site，正式 https://site.supermahjongleague.com）
1. **先跑 dry-run 給使用者確認**會發佈什麼：`bash /opt/sml/repo/deploy.sh --dryrun`
2. 確認無誤 → 正式部署：`bash /opt/sml/repo/deploy.sh`（可加 `-m "訊息"`）
3. 腳本只發佈「git 追蹤的根目錄 *.html/*.css/*.js ＋ assets/」→ 杜絕 `.claude`/`aws`/`*.pid` 等內部檔外洩（舊 Windows 腳本曾把這些誤發佈公開）。完成含 CloudFront 失效 + git push。
- 只改 Firebase 資料（選手/積分）不需跑這個——後台按「🌐 同步官網數據」即可。

### sweetbot（甜甜 bot sweetbot-next）
- `bash /opt/sml/sweetbot-next/deploy.sh`
- 治理：**未 commit 不准部署**、必須在 main；腳本會 commit→push origin main→systemd 重啟 `sweetbot-next.service`。
- 緊急拉起（程式當掉、無待上改動）：`FORCE_RESTART=1 bash /opt/sml/sweetbot-next/restart.sh`

### games（甜甜遊戲館 sweetbot-site → sweetbot-games.web.app）
- `bash /opt/sml/sweetbot-site/deploy.sh`
- 會同步設計檔→存 git 版本點→`firebase deploy --only hosting:sweetbot --project sml2026newscore`。多 AI 併行改，改檔前先 `bash check-conflict.sh`，絕不整檔覆蓋。

### broadcast（計分後台正式版 broadcast.boyplaymj.com）
- S3 `sml-frontend-prod` + CloudFront `E30NEB2CP9C6OM`（Cognito）。⚠️首次執行前先確認 build 產物與同步路徑，勿誤發佈內部檔（比照 site 的白名單原則）。

### functions（score-repo Firebase Cloud Functions）
- `cd /opt/sml/score-repo && firebase deploy --only functions`

## 通則（一致性護欄）
- 部署到正式一律**跑完回報成功與否 + 附網址**；失敗把錯誤原文回報，**不要靜默重試**。
- S3 類：**只發佈該公開的**（白名單/追蹤檔）、部署後**必做 CloudFront 失效**。
- bot 類：**未 commit 不上線**、必須在 main、push 讓 origin/main = 線上。
- 對外部署前先確認目標環境，避免推錯。
