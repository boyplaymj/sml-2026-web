# 甜甜「每日直接部署 main」— 取代 release train（Option B，2026-07-14 使用者定案）

Claude 設計,交 Codex 實作+自驗。**不自行破壞今天 16:00 的 at job #7**;新機制 2026-07-15 起生效、先走測試頻道。

## 為什麼換掉 release train
release train 模型 = 把 `staging` 的東西 promote 到 main;判 pending 看 `main..staging`。但實務是**直接 commit 到 main**,導致:main 一領先 staging → 前置 gate abort;就算回補 staging=main → `main..staging=0` 空班車跳過。**結論:train 在 commit-to-main 實務下永遠不會部署 main 改動。** 改成「每日直接部署 main 上還沒部署的 commit」。

## 核心:給部署一個錨 `deployed` tag
單一事實來源 = git tag `deployed` 指向「目前線上跑的 commit」。**由 deploy.sh 在成功部署後自己更新**,任何部署路徑(手動/at job/每日 cron)都一致。

### 改 `deploy.sh`
在既有 flow(commit→push→restart→healthcheck)**成功之後**加:
```bash
git tag -f deployed HEAD
git push -f origin deployed
```
(放在 healthcheck 通過後;失敗則不打 tag。)

## 新腳本 `/opt/sml/sweetbot-release/daily-deploy.sh`(取代 release-train-cron 的實體)
沿用 `lib.sh`(notify/healthcheck/log)與 flock。流程:
1. 取 deploy 鎖(與手動 deploy.sh 互斥,取不到=有人在部署,今天跳過)。
2. `git fetch origin`。
3. **前置 guard**:main 工作樹若有未提交改動 → **abort + notify、不硬上、不碰別人 WIP**(同 release-train 現行 guard)。
4. 確保 local main = origin/main(`git pull --ff-only`;若分岔=部署面異常,abort+notify)。
5. **算 pending** = `deployed..origin/main`(main 上還沒部署的 commit)。
   - 若 `deployed` tag 不存在(首跑)→ 視為「直接部署當前 main」。
   - 若 pending=0 → skip、notify「今日無新更新,不重啟」、exit 0。
6. pending>0 → 跑 `bash deploy.sh`(它會 push+restart+healthcheck+打 deployed tag)。成功後 notify「已上線 N 筆」+清單;失敗 notify + 不動 tag。

## crontab(替換現有兩行)
- `30 7 * * *` → `notify-maintenance-daily.sh`(改用 `deployed..origin/main` 抓待上線清單發預告;0 筆就說今天沒更新)。
- `0 8 * * *` → `daily-deploy.sh`。
- 保留 wrapper 的 `START_DATE=2026-07-15`(今天 skip、不撞 at job #7)+ `SWEETBOT_NOTIFY_CHANNEL=903327108451950692`(測試頻道 dry-run)。log 續用 cron.log。

## 退場 release train(不刪、只停用)
- 從 crontab 移除 `release-train-cron.sh`。
- `release-train.sh`/staging worktree/archive tag `staging-archive-20260714` **保留**(不刪,備查/可回滾)。README 或註解標記「已由 daily-deploy 取代,勿用」。

## 初始化 `deployed` tag（關鍵時序）
- **今天 16:00 前**:Codex 先把 deploy.sh 的打 tag 改上去(commit)。這樣**今天 16:00 的 at job #7 跑 deploy.sh 時就會順手建立 `deployed` tag** = 今天部署的 commit。
- 若今天 at job 因髒樹 abort(沒部署)→ `deployed` tag 不存在 → 明天 daily-deploy 首跑走「無 tag=直接部署當前 main」路徑,照樣把 b643e6c 上線。**兩種情況都收斂正確。**
- ⚠️ Codex 改 deploy.sh 這個 commit 本身也會進 main;若在今天 at job 前沒被別的部署帶上,就等 at job 一起上(它就是跑 deploy.sh)。注意別讓改 deploy.sh 的 commit 造成今天工作樹髒(改完立刻 commit)。

## 驗收(Codex 自驗 + 回報)
1. deploy.sh 改動:模擬成功路徑會 `git tag -f deployed` + push;失敗不打。node/bash -n 過。
2. daily-deploy.sh:造 `deployed`=某舊 commit + origin/main 領先 → 應偵測 pending>0;`deployed`=origin/main → 應 skip;main 工作樹髒 → 應 abort 不部署。**用 dry-run 旗標或指到測試環境驗,別真重啟線上 bot。**
3. crontab 已換、release-train-cron 已移除、START_DATE/測試頻道 guard 在。
4. 回報 diff + 三條路徑(有pending/無pending/髒樹)的驗證輸出。**不自行部署線上**。

## 之後(使用者)
明天 16:00 首班在測試頻道看綠燈 → 再把通知頻道切正式 1023792388822536232。
