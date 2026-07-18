# HANDOFF → Codex：實作「觀看時長獎 WatchTimeRewards」

**規格正典**：`tools/watchtime-rewards/DESIGN.md`（先完整讀，決策/機制/邊界都在裡面）。
**分工**：Claude 設計（本文＋DESIGN），Codex 實作＋自驗。**by**：Claude, 2026-07-18。
**目標 repo**：`/opt/sml/sweetbot-next`（後端，main）、`/opt/sml/sweetbot-site`（前台，master）。

## 一句話
直播觀眾「看多久領多少」：收看時間＝聊天在場**活躍區段加總**（相鄰訊息間隔 ≤ maxGapSec=600s 才計），每分鐘 1🦷+1⭐，**不封頂**；來源＝YT 聊天 ＋ Discord `934066682954129470` 合併（以 discordId）。不課稅、不發任何通知（隱藏機制）。

## 直接複用（別重造）
- **整體骨架照抄 `model/YtKeywordRewards.js`**：Firestore REST helper（httpsJson/fromFsValue/toFsValue）、pollTick(nonce 冪等 + updateTime≥啟動才處理)、preview/commit、runDaily(掃過去~26h distinct videoId)、settled 冪等鎖、`_setDoc/_getDoc/_writeResult`、`_recentVideoIds()`（ts 範圍 structuredQuery，ts 是 integerValue 毫秒）。→ 你只是換算法（活躍區段）＋多一個 Discord 來源＋多發 experience。
- **身分綁定**：`ViewerAuthorChannelIdDAO.selectOne({authorChannelId})` → discordId（未綁定略過），同 YtKeywordRewards `_bindRecipients`。
- **發放**：`ViewerDetailDAO.givePoint([id], teeth, 'point', reason)` ＋ `givePoint([id], exp, 'experience', reason)`。reason=`觀看時長獎:${videoId}`。
- **排程**：`discord.js` 已有 `schedule.scheduleJob({rule:'0 0 4 * * *', tz:Config.timeZone}, ...)`（就是 ytKeyword 的每日 job）；把 watch-time runDaily 接在同一處或並列一條。pollTick 用 `setInterval(...,5000)` 同 ytKeyword。
- **tax nontax patch**：照抄 `migration/patch_tax_class_yt_keyword.js`（本次剛做的），改成 `nontax-watch-time` / pattern `觀看時長獎` / priority 407。defaults.js 也加同一條。
- **前台**：照抄 `sweetbot-site/public/yt_keyword_rewards.html` 的結構（Firestore compat、onSnapshot、preview/commit cmd 寫法）改成 watch-time 版。

## 關鍵實作點
1. **前置工＝Discord 訊息擷取（DESIGN §4）**：`discord.js` messageCreate 內，`msg.channelId==='934066682954129470' && !msg.author.bot && msg.content` → Firestore REST 寫新 collection `sml_watch_chat_discord`，docId=`msg.id`（冪等 PATCH），欄位 `{discordId:msg.author.id, ts:<毫秒int>, text, guildChannelId}`。fire-and-forget、try/catch 吞錯不影響聊天。指令(`!`/`！`)照樣算在場，只排除 bot。
2. **活躍區段算法（DESIGN §1）**：合併某 discordId 的所有 ts（YT+Discord）排序 → `watchSec = Σ gap where gap≤maxGapSec` → `minutes=floor(watchSec/60)` → teeth/exp = minutes×perMin。1 則以下＝0。務必寫單元測涵蓋：多區段、>10分空檔剔除、單則=0、YT+Discord 交錯合併。
3. **視窗**：一場＝該 videoId 的 YT 訊息 ts 首~末（可被 cmd.startTs/endTs 覆寫）；Discord 撈 `sml_watch_chat_discord` 的 `ts∈[min,max]`（單欄 range，免建複合索引）。
4. **不發任何 Discord 訊息**；面板不放對外文案。
5. **經驗值不進稅帳**（只有 'point' 才 recordPointChanges），故只有牙齒靠 nontax-watch-time 歸類；務必跑 migration 才對線上生效（線上 sweetbot-tax-class 表非空走 DDB）。

## 上線紀律（這個 repo 的地雷）
- **sweetbot-next 併行快照雷**：改完立刻 commit 自己的檔、別留 dirty tree（別的 session 自動快照會吃走）。
- **commit 落 main**（照 puzzle-quest/ytKeyword 慣例，別走發布列車 staging）。
- **部署＝每天 16:00 台灣自動列車**（`daily-deploy` cron 08:00 UTC，擋髒樹、算 `deployed..main`、跑 deploy.sh push+restart+tag）。要上就 commit 乾淨等列車；migration 要**手動跑**（cron 不跑 migration）。
- 前台 `bash /opt/sml/sweetbot-site/deploy.sh` → sweetbot-games（會自動存版本快照）。
- **經濟煞車**：`teethPerMin`/`expPerMin`/`maxGapSec` 全走 `sml_config/watchTimeRewards` 後台可調，別寫死。

## 驗收（給回 Claude 覆核）
- 單元：活躍區段算法（含 maxGap 剔除）、YT+Discord 合併、未綁定略過、冪等、稅分類 `觀看時長獎`→nontax。
- 端到端：私頻真實小場 preview→小額 commit → 撈 `sweetbot-player-point-log` 比對 `point`＋`experience` 逐筆。
- 回報 findings 給 Claude，照慣例 Claude 覆核 / 你二驗雙簽再上列車。
