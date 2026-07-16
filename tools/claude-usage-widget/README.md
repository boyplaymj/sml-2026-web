# Claude 用量桌面小工具(液體槽)

即時以「液體槽」動畫顯示兩個 Claude 帳號(main / backup1)的用量。液面 = 已用額度,
分三槽:**5 小時階段 / 每週・全模型 / 每週・Fable**,各帶重置倒數與分級變色(綠→黃→紅)。

## 架構(三層,零伺服器)

1. **採集器** `collector.py`(跑在 SML 主機的 systemd timer,每 60 秒)
   - 幫 main + backup1 各打一次 `GET /api/oauth/usage`(**純 GET,不燒 LLM token、不影響計費**)。
   - token 過期會自動用 refreshToken 刷新(端點/參數沿用 `aws/discord-bridge`);
     main 寫回 `~/.claude/.credentials.json`,backup1 寫回 SSM。
   - 產出精簡 `usage.json`(**只含百分比與重置時間,無任何 token/密鑰**)上傳圖床。
2. **公開 JSON**:`s3://boyplaymj-image/claude-usage/<slug>/usage.json` → CloudFront `image.boyplaymj.link`。
3. **桌面小工具** `index.html`:同源讀 `usage.json`,canvas 波浪動畫;每 30 秒輪詢。
   - 支援 `?src=` 覆寫資料來源;fetch 失敗自帶示範資料(本機 `file://` 也能開)。

## 部署位置

- systemd:`claude-usage.service` + `claude-usage.timer`(每 60 秒)。
- S3 路徑寫在 `.deploy-path`(不可猜 slug)。
- 更新 `index.html` 後要 `aws cloudfront create-invalidation --distribution-id E2IJWN6FWT2XYG --paths "/claude-usage/<slug>/*"`。
  `usage.json` 因帶 `?t=` 查詢字串,每次都回源、免 invalidation。

## 手動跑 / 除錯

```bash
python3 collector.py                 # 印 usage.json 到 stdout
python3 collector.py --out usage.json # 寫檔(供本機 http 預覽)
sudo systemctl start claude-usage.service   # 觸發一次上傳
journalctl -u claude-usage.service -n 20
```

## 已知狀態

- **backup1 目前「需重新登入」**:其 SSM 憑證的 refreshToken 已失效(`invalid_grant`),
  無法自我刷新。切一次帳號重新登入 backup1 後即自動恢復顯示。

## 💰 成本控管

本工具**不吃額外成本**:查用量是純 GET(無 LLM token、無推論)、無新 DynamoDB 表、
無付費 API;僅每 60 秒一次 S3 PUT(~4.3 萬次/月,<US$0.02)與既有 CloudFront 分發。
故依 `tools/COST_CONTROL.md` 規範屬「免成本控管段」等級,惟此段仍作紀錄。
