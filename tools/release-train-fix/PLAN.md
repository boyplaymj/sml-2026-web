# 甜甜發布列車修復計畫（2026-07-14）— 交 Codex 執行+複驗

Claude 設計+已架保命網。Codex 做逐筆內容驗證 + 重建 + 裝排程 + guarded dry-run，回報後 Claude/使用者複驗。

## 背景
「每日 15:30 預告 / 16:00(台灣=08:00 UTC)release train 自動上線」是使用者 2026-07-06 定案的制度，腳本都在 `/opt/sml/sweetbot-release/`，但**從沒真正運作**：
1. **沒排程**：`systemctl list-timers` 無、`crontab -l` 空 → 16:00 沒東西自動跑。
2. **staging 壞**：`origin/main..origin/staging` = 16 筆 staging 獨有；`origin/staging..origin/main` = 57(staging 落後 main 57)。`release-train.sh` 的 `merge-base --is-ancestor main staging` gate 會擋下中止。
3. 根因：staging 是「歷史重寫(force-push 洗 SHA)前的舊 main」長出來的，SHA 全變 → 內容縱使已在 main、SHA/patch-id 也對不上。

## ⚠️ 關鍵風險（本次新發現，勿照舊記憶硬幹）
`git cherry origin/main origin/staging` 顯示 **16 筆全部 `+`(patch-id 在 main 找不到等價)、冗餘 0**。這**不代表**它們是真獨有——歷史重寫會讓 patch-id 對不上。但也**不能**因此就假設全冗餘去 force。**必須逐筆做內容層驗證。**

抽驗範例：`79ae3d5`(老人電動車)SHA 不在 main，但 main 有 `model/miniGame/CrossingRoad.js` 且該功能記憶記為 2026-07-05 已上線 → 判定「內容已在 main、屬冗餘」。要對 16 筆全做這種判定。

## ✅ 已完成的保命網
`git tag -f staging-archive-20260714 origin/staging` 已 push origin。**無論後續怎麼 rebuild，舊 staging 的 16 筆都能從這個 tag 救回**。

## 16 筆待驗清單（`origin/main..origin/staging`）
crossroad 物流貨車 c4b855a、market 系列(3fcbb42/e22672a/19c4854/edb6a13/3b21b2c/f899ea3)、stock(7145edd/9a05dab/bfe1648)、crossroad 老人電動車 79ae3d5、birthday 98ed586、bingo 90c036c、dragonboat f3f915f、interaction gate(af40834/ef7a1c9)。
> 記憶線索：79ae3d5(路權老人)、f3f915f+af40834+ef7a1c9(2026-07-09 已 cherry-pick 上 main)、9a05dab(曾作 staging backport) → 這幾筆大機率冗餘；market/stock 幾筆要實查 main 有無該功能。

## Codex 任務
1. **逐筆內容驗證**：對 16 筆每一筆，找出它動到的檔/功能，去 `origin/main` 查該內容是否已存在(grep 功能關鍵字、比對檔案關鍵區塊；**不要只信 patch-id**)。輸出表格：`sha | 主題 | 動到的檔 | main是否已有 | 判定(冗餘/獨有/部分)`。
2. **若有『獨有(main 缺)』**：**停手、別 rebuild**，列出來回報，等決定是否先 cherry-pick 上 main。
3. **若 16 筆全冗餘**：重建 staging = `origin/main`：
   - 在 staging worktree(`/opt/sml/sweetbot-staging`)`git fetch` → `git reset --hard origin/main` → `git push origin staging --force-with-lease`。
   - 驗 `git merge-base --is-ancestor origin/main origin/staging` 現在為真(gate 會過)。
4. **裝排程(crontab)**：`30 7 * * *` 跑 notify-maintenance.sh、`0 8 * * *` 跑 release-train.sh(帶正確 PATH/HOME/log、UTC)。
   - ⚠️ **今天(2026-07-14)別讓兩路對撞**：main 已有 `at` job #7 於 08:00 UTC 手動 deploy 試煉之門。**cron 從明天(2026-07-15)起生效**，今天照舊走 at job。(或若要今天就交給 train：先 `atrm 7` 再讓 train 跑，但需先驗 staging 已含 b643e6c。)
5. **guarded dry-run**：release-train 的通知先發到**測試頻道 903327108451950692**(非公告頻道 1023792388822536232),確認整條 測→合→deploy→healthcheck→tag→backport 流程綠燈,再切正式通知頻道。
6. **回報**給 Claude/使用者複驗(逐筆判定表 + rebuild 結果 + cron 內容 + dry-run log)。**不省略任何『獨有』commit 的揭露。**

## 收尾鐵律（沿用）
- hotfix 上 main 後要 `hotfix-backport.sh` 回補 staging，否則下一班 train 洗掉 hotfix。
- 別在 main 目錄留未提交 WIP(現在就有別 session 的 discord.js/VotePoolBuilder.js，會擋 deploy)。
- 相關：archive tag = `staging-archive-20260714`。
