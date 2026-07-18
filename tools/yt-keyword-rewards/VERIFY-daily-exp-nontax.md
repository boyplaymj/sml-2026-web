# VERIFY — YT 關鍵字獎改造（Codex 查驗單）

**送查對象**：Codex　**by**：Claude　**日期**：2026-07-18　**上線**：跟 16:00 列車（`deploy.sh`）
**repo**：`/opt/sml/sweetbot-next`（main）　**commit**：`aea5317`（程式）＋`2d39d4c`（DEPLOY_QUEUE 登記）

## 需求（使用者）
1. YT 關鍵字獎改成**每日固定時間自動發放**（定 04:00 台灣，跟隨每日任務時段）。
2. **不列入 `!報稅`**。
3. **不發任何通知給用戶**。
4. 獎勵欄現有「牙齒🦷 + 最多牙齒量」，**加「經驗值⭐ + 最多經驗值量」兩欄**。

## 改了什麼（4 檔）
- `model/YtKeywordRewards.js`
  - `normalizeRule` 加 `exp` / `maxExpPerUser`（Math.max(0,…)）。
  - `calculateRewards` 白名單過濾放行 `exp>0`（原本只 `reward>0`）→ 允許「只給經驗、不給牙齒」的規則。
  - `whiteHits` 每筆帶 `exp`。
  - `applyCap` 重寫：牙齒(`maxPerUser`) 與 經驗(`maxExpPerUser`) **各自獨立封頂**，一種到頂另一種仍可續給；兩者皆 0 才 drop 該 hit。上限=0 代表無上限。
  - `_bindRecipients` 累積 `total`(牙齒) + `totalExp`；hits 帶 exp；排序 total→totalExp。
  - `run()` commit：`if(r.total>0) givePoint(...,'point',reason)`；**新增** `if(r.totalExp>0) givePoint(...,'experience',reason)`。
  - stats + settled doc + `_emptyStats` 加 `totalExp`。
  - **新增 `runDaily()`**：讀 config，未 enabled 就跳過；`cutoffMs = now - 26h`；`_recentVideoIds()` 用 ts 範圍 structuredQuery（`ts` 由 sml-chat-capture 寫成 `integerValue` 毫秒）撈 distinct videoId；逐一 `_getDoc(ytKeywordSettled/{videoId})`，已結算跳過，否則 `run({action:'commit',videoId,nonce:'daily_'+videoId})`；結果寫 `sml_config/ytKeywordDaily`。全程無 Discord 訊息。
- `discord.js`：`schedule.scheduleJob({ rule:'0 0 4 * * *', tz: Config.timeZone }, ()=>ytKeywordRewards.runDaily().catch(...))`。原 `pollTick` 5s 手動備援不動。
- `model/tax/defaults.js`：`YT關鍵字獎` 從 `other-general-rewards`(other) 的 reasonPattern **移除**；新增 `nontax-yt-keyword`(pattern=`YT關鍵字獎`, includes, category=`nontax`, priority=**406** < 500)。
- `migration/patch_tax_class_yt_keyword.js`（新）：仿 `patch_tax_class_redenvelope.js`。Put 新規則(不存在才寫) + Update `other-general-rewards` reasonPattern(存在才改)。**上線時要手動跑一次**。

## 請重點查驗的不變式 / 邊界
1. **稅**：`classifyReason('YT關鍵字獎:xxx')` → `nontax`（priority 406 壓過 500，且已從 other 移除）。確認沒誤傷 `隨機事件獎勵|偽文件解謎破關|擁有精華獎勵|精華`（仍應 other）。migration idempotent、只動這兩條、不覆寫 tax-config。
2. **經驗獨立封頂**：同人同規則洗版時，牙齒到 `maxPerUser` 後仍持續給經驗到 `maxExpPerUser`；反之亦然。封頂=0 無上限。最後一筆截到剛好、單筆超過 cap 也截。
3. **經驗不進稅帳**：`givePoint(...,'experience',...)` 不呼叫 `TaxLedgerDAO.recordPointChanges`（只有 columnName==='point' 才會）。確認 run() 沒把 exp 也走 point。
4. **runDaily 冪等/安全**：
   - `_recentVideoIds` 的 ts 範圍查詢：`ts` 型別確認為 integerValue（來源 `score-repo/tools/lambda/sml-chat-capture/index.js:61`）；範圍查是否需 Firestore 複合索引？（單欄 range 應走預設單欄索引，請確認不會 400 requires-index。）
   - 直播**跨 04:00 仍在進行**時：會結算到當下、剩餘因冪等鎖不補發——這是已知取捨（時間挑深夜無台），確認不會 double-pay、不會 crash。
   - config 未 enabled / 無有效規則 / 撈訊息失敗 → graceful（不丟未捕捉例外、不影響其他排程）。
   - `run()` 內部 settled 二次檢查 vs runDaily 前置檢查：非 force，不會重發。
5. **不發通知**：全流程（pollTick / run / runDaily）確認零 Discord 送訊息。
6. **回歸**：舊規則（無 exp 欄）normalizeRule 後 exp=0、maxExpPerUser=0，行為與改前一致（只發牙齒）；手動面板 preview/commit 不受影響。

## 已自驗
- `node -c` 四檔全綠。
- inline 煙霧：稅分類 nontax ✅ / 牙齒6止·經驗5止 獨立封頂 ✅ / exp-only 規則(牙齒0·經驗12) ✅。

## 前端（另 repo，不在此 commit）
`/opt/sml/sweetbot-site/public/yt_keyword_rewards.html`：規則表+新增表單+試算名單加經驗欄、橫幅改「每日04:00自動」。firebase deploy 到 sweetbot-games，部署後請使用者強制重整（舊版面板 `save()` 會洗掉 exp 欄）。

## 上線步驟（16:00）
1. Codex 查驗 OK（有 finding 我先修再重 commit）。
2. `node migration/patch_tax_class_yt_keyword.js`（跑一次）。
3. `bash deploy.sh`（帶 main 所有 queued commit 上線 + 清 session）。
4. firebase deploy 前端 → sweetbot-games。
5. 私頻 903327108451950692 E2E + 撈 point-log 比對。
