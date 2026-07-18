# 觀看時長獎 WatchTimeRewards — 設計冊 v0.1

> 直播觀眾「看多久就領多少」：偵測每位觀眾的收看時間，**每 1 分鐘 = 1🦷 + 1⭐**。
> 收看時間來源＝聊天在場訊號（第一則到最後一則訊息），**YT 直播聊天 ＋ Discord `934066682954129470`（🔴生放送直播聊天室）合併計算**。
> 分工：Claude 設計、Codex 實作/驗證。相關：[[project_yt_keyword_rewards]]（共用身分鏈與結算骨架）、聊天抓取 overlay（不碰）。

## 0. 決策定案（2026-07-18，使用者拍板）
1. **防作弊＝最大空檔 10 分**：收看時間＝各「活躍區段」加總，**不是**單純頭尾相減。連續兩則訊息間隔 ≤ 10 分才計入該段；> 10 分視為離開/掛機，該空檔不計。
2. **不設封頂**：看直播是核心的牙齒＋經驗獲得途徑，一場多長就能領多長（受活躍區段規則自然約束）。
3. **不寫入報稅**：reason=`觀看時長獎` 歸 `nontax`（同 [[project_yt_keyword_rewards]] 的處理，附 tax-class patch migration）。
4. **隱藏機制**：不對觀眾公佈規則、不發任何通知/DM/公告，讓觀眾自己發現。後台面板僅管理者可見。

## 1. 核心機制
對「一場直播（videoId）× 每位觀眾（discordId）」：
1. 蒐集該人本場所有訊息 ts（**YT 聊天 ＋ Discord 聊天室 合併**，見 §3 身分合併、§4 資料來源）。
2. 依 ts 排序，算**收看秒數**＝相鄰訊息間隔中「≤ MAX_GAP(預設 600s＝10 分)」者的總和：
   ```
   watchSeconds = Σ gap_i   (只累計 gap_i ≤ MAX_GAP 的間隔；gap_i > MAX_GAP 不計)
   minutes      = floor(watchSeconds / 60)
   ```
   範例：訊息在 0、2、5、20、22 分 → 間隔 2,3,15,2 →（15>10 剔除）→ watch＝2+3+2＝7 分。
3. 獎勵：`teeth = minutes × TEETH_PER_MIN(預設1)`、`exp = minutes × EXP_PER_MIN(預設1)`。**無封頂**。
4. 只有 1 則訊息（或 0 則）→ 0 分 → 不發。

## 2. 資料模型 / 存取
- **YT 聊天**：現成 Firestore `sml_chat_messages`（由 `sml-chat-capture` Lambda 寫，含 `channelId`＝YT頻道ID、`ts`＝integerValue 毫秒、`videoId`、`text`）。**不改**。
- **Discord 聊天室 `934066682954129470`**：🔴**目前完全沒存**（`discord_reader.py` 只廣播 overlay 不落庫；甜甜 messageCreate 只做任務埋點/指令）。→ **新增擷取**（§4）。
- **新結算冪等鎖**：Firestore collection `watchTimeSettled`，docId=videoId（同 ytKeywordSettled 模式）。
- **指令/結果**：`sml_config/watchTimeCmd`、`sml_config/watchTimeResult`、每日彙總 `sml_config/watchTimeDaily`（同 ytKeyword 系列）。
- **設定**：`sml_config/watchTimeRewards` = `{ enabled, maxGapSec(=600), teethPerMin(=1), expPerMin(=1), blockedChannels[](YT channelId), blockedDiscordIds[] }`。

## 3. 身分合併（以 discordId 為準）
- YT 訊息：`channelId`(YT) → `ViewerAuthorChannelIdDAO.selectOne({authorChannelId})` → `discordId`。**沒綁定 → 略過**（無法發牙，同關鍵字獎）。
- Discord 訊息：`authorId` 本身就是 discordId。
- 同一人在 YT＋Discord 都發言 → 兩串訊息**合併成同一條 discordId 時間軸**再算收看時間（這就是「整合聊天室」的核心價值：綁定的觀眾兩邊都算）。
- 發放：`ViewerDetailDAO.givePoint([discordId], teeth, 'point', reason)` ＋ `givePoint([discordId], exp, 'experience', reason)`。

## 4. Discord 訊息擷取（前置工，新增）
甜甜 `discord.js` 的 `messageCreate`：若 `msg.channelId === '934066682954129470'` 且 `!msg.author.bot` 且有內容 →
寫一筆到 Firestore **新 collection `sml_watch_chat_discord`**：
```
docId = msg.id                       // Discord 訊息 id，冪等去重
{ discordId: msg.author.id, ts: <毫秒 int>, text: <可選,截斷>, guildChannelId:'934066682954129470' }
```
- 走現成 Firestore REST（甜甜已有 ytKeyword 的寫入路徑可複用）；寫入 fire-and-forget、失敗不影響聊天。
- 指令訊息（`!`/`！` 開頭）**照樣算在場**（有打字＝在看）；只排除 bot。
- 為何獨立 collection：與 YT `sml_chat_messages` 分開 → 結算查 Discord 用**單欄 ts 範圍查詢**（Firestore 預設單欄索引，免建複合索引），不與 YT 混。

## 5. 結算（新模組 `model/WatchTimeRewards.js`）
結構仿 `YtKeywordRewards.js`：
- `pollTick()`：每 5s 讀 `sml_config/watchTimeCmd`（nonce 冪等、updateTime≥啟動才處理），preview / commit → 寫 `watchTimeResult`。手動備援。
- `runDaily()`：每日 04:00 台灣（可與 ytKeyword 同一 schedule 內接續呼叫，或獨立 scheduleJob）。掃過去 ~26h YT `sml_chat_messages` 取 distinct videoId → 未在 `watchTimeSettled` 者自動 commit。
- `run(cmd)`：
  1. `videoId` 必填。讀 config（未 enabled 拋錯）。
  2. **視窗**＝該 videoId 的 YT 訊息 `ts` 首~末（`[minTs, maxTs]`）；可被 cmd.startTs/endTs 覆寫。
  3. 抓 YT 訊息（by videoId）＋ Discord 訊息（`sml_watch_chat_discord` 的 `ts ∈ [minTs, maxTs]`，單欄 range 查詢）。
  4. 身分合併（§3）：YT channelId→discordId（略過未綁定、略過 blacklist）；Discord authorId 直用（略過 blockedDiscordIds、bot）。
  5. 每 discordId 合併時間軸 → 算 watchSeconds（§1，MAX_GAP 剔除）→ minutes → teeth/exp。
  6. `preview`：回名單 `[{discordId, displayName, minutes, teeth, exp, ytMsgs, dcMsgs}]` ＋ stats（人數/總分/總牙/總經驗/總分鐘）。
  7. `commit`：`watchTimeSettled/{videoId}` 冪等檢查（非 force 已結算就拋錯）→ 逐人 `givePoint('point')`＋`givePoint('experience')` → 寫 settled doc（記 totalTeeth/totalExp/recipientCount）。reason=`觀看時長獎:${videoId}`。
- **不發任何 Discord 訊息**（§0-4 隱藏機制）。

## 6. 報稅（不課稅）
- `model/tax/defaults.js`：新增 `nontax-watch-time`（pattern `觀看時長獎`, includes, category `nontax`, priority 407）。
- 附 `migration/patch_tax_class_watch_time.js`（仿 patch_tax_class_yt_keyword.js）：Put 新規則到線上 `sweetbot-tax-class`（表非空走 DDB）。經驗值天生不進稅帳（只有 'point' 才 recordPointChanges）→ 只有牙齒那份靠此規則歸 nontax。

## 7. 後台面板（`sweetbot-site/public/watchtime_rewards.html`，管理者可見）
- 全域：啟用開關、`maxGapSec`（空檔上限，預設 600）、`teethPerMin`/`expPerMin`（預設 1/1）、黑名單（YT channelId ＋ Discord id）。
- 手動結算：videoId ＋（選填 start/end ts）→ preview 名單（顯示每人分鐘/牙/經驗/YT訊息數/DC訊息數）→ commit。
- 每日彙總唯讀（讀 `watchTimeDaily`）。
- 遊戲館 NAV 加入口。**面板不對外**，也不放任何「公佈給觀眾」的文案（隱藏機制）。

## 8. 邊界 / 防濫用
- 開場+散場各一句相隔數小時 → 因 MAX_GAP 剔除中間空檔 → 只得 ~0 分（頭尾兩則若間隔>10分則該段不計）。✅ 治到主要漏洞。
- 一場多次進出（活躍→離開>10分→回來）→ 各活躍段分別累加、離開空檔不計。✅
- 未綁定 YT 觀眾：略過（無法發牙）。Discord 使用者本就有 discordId。
- 工作人員/自己/bot：blockedChannels(YT) ＋ blockedDiscordIds(Discord) ＋ 自動排除 bot。
- 冪等：`watchTimeSettled/{videoId}`；手動 commit 後 04:00 自動 job 會跳過同場（不重發）。
- 直播播過 04:00：自動 job 結到當下、剩餘因冪等不補 → 改手動補結（同關鍵字獎取捨）。
- 純 Discord 場（無 YT videoId anchor）：v1 不支援（需 videoId 當視窗錨點），日後可加「以時間窗開場」模式。

## 9. 💰 成本控管
連回正典 **`tools/COST_CONTROL.md`**。本功能成本評估：
- **無 LLM、無付費 API、無新 Lambda/APIGW、無 S3**。結算跑在甜甜（sweetbot-next）進程內。
- **複用既有**：`sml_chat_messages`(YT，既有)、`sweetbot-viewer`/`sweetbot-player-point-log`(既有)、`givePoint`(既有)。
- **唯一新增**：Firestore collection `sml_watch_chat_discord`（每則 Discord 直播聊天寫 1 doc）＋ 4 個 `sml_config` 控制 doc。Firestore 寫入量級＝一場直播數百~數千則、成本可忽略（$0.18/10萬寫）。→ 依 §1 判斷屬「複用既有＋極小新增」，不需 LLM 四件套。
- **經濟面（通膨）需盯**：這是**新的、無封頂**的牙齒＋經驗水龍頭，人均產出可能高（鐵粉一場 60~120🦷+同量 exp）。上線後在 `economy.html` 盯人均/日印鈔（基線：全服日印約 164k🦷、DAU~45，見 [[reference_teeth_economy_baseline]]）；若人均過高，用後台 `teethPerMin`/`expPerMin` 下調當煞車（不需改碼）。

## 10. 交付順序（給 Codex）
1. **前置**：甜甜 messageCreate 擷取 934066682954129470 → `sml_watch_chat_discord`（§4）。
2. `model/WatchTimeRewards.js`（§5）＋ discord.js 接 pollTick(5s) ＋ 04:00 runDaily。
3. tax：defaults.js `nontax-watch-time` ＋ `migration/patch_tax_class_watch_time.js`（§6）。
4. 前台 `watchtime_rewards.html`（§7）＋ 遊戲館 NAV。
5. 測試：活躍區段算法（含 MAX_GAP 剔除）、YT+Discord 合併、未綁定略過、冪等、稅分類 nontax、preview/commit。
6. E2E：私頻真實小場，撈 point-log(point) + experience-log 逐筆比對。
