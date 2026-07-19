# 觀看時長獎 — YT 自動偵測 + 額度安全 施工計畫

**目標**：直播免貼網址（RSS 0 額度自動抓 videoId）＋ 官方 v3 API 抓聊天發獎（不受 IP 封鎖）＋ 每日用量帳本 + kill switch，確保「一天 3 場 × 3 小時」也絕不把 10,000/天 配額燒完。
**分工**：Claude 設計/整合/部署/驗收；🟣**Fable5** 生成純邏輯模組與偵測 Lambda handler；**每階段交 Codex 獨立查驗**才進下一階段。
**動到的 repo**：`/opt/sml/score-repo`（production Lambda，有部署護欄地雷 → 先 commit 乾淨、防並行 session 快照）。
**by**：Claude, 2026-07-18。

## 鐵律（Codex 每階段都要檢查）
1. **絕不呼叫 `search.list`（100 單位）** — 找直播一律走 RSS(0) + `videos.list`(1)。
2. **每一次 v3 呼叫前必須走「單一原子預扣」helper `reserveUnits(cost)`**：僅當 `units + cost <= 9000` 才回 `allowed` 才可呼叫 v3；deny 時寫 `stoppedAt`（冪等，只寫一次）且**不**呼叫 v3。禁止任何 read-modify-write 或繞過路徑。（修 Codex finding 3、4）
3. 抓聊天維持 **1 次/分**（`liveChatMessages.list` maxResults=2000 + pageToken 接續）。
4. **Field-level writer 分界（updateMask 逐欄 merge，禁止整 doc 覆蓋）**：偵測器只 merge 寫 `chatCapture`/`chatBridge` 的 `{videoId, enabled}`；抓取器只寫 `{liveChatId, pageToken, lastPoll, lastCount}`；兩者互不覆蓋對方欄位。（修 Codex finding 2）
5. **停止抓取（清空/enabled=false）只能由「目前 active 的 videoId 被確認結束」觸發**，絕不因「RSS 最新片不是 live」而清掉 active capture。（修 Codex finding 1）

## 偵測器狀態機（IDLE / ACTIVE 兩態）
- **IDLE**（無 active capture：`chatCapture.enabled=false` 或無 videoId）：抓 RSS(0) → 取**前 N 筆候選**（`RSS_CANDIDATES=5`，非只最新片）→ **若候選集 ≠ 上次 OR 距 `lastIdleProbe` ≥ `idleProbeInterval`** → `reserveUnits(1)`+**單一 `videos.list(id=逗號串多筆)`**（多 id 仍 **1 單位**）→ 取**第一個帶 `activeLiveChatId` 的候選**（不必是最新片）→ 有才 merge 寫 `chatCapture{videoId,enabled:true}`(+`chatBridge{videoId,enabled:true}`) 轉 ACTIVE；全非 live 則記候選集+`lastIdleProbe`、維持 IDLE。（二驗 finding 1：重啟後漏抓；三驗 finding 1：**同一支候選從待機頁變 live、候選集不變也要靠 `idleProbeInterval` 週期性重探**）
- **ACTIVE**（已在抓某 videoId）：**完全忽略 RSS**（避免直播中發新片誤關）。結束判定**以抓取器 terminal 信號為主**（capture 連續 400 = 聊天永久結束 → 寫 `chatCapture.ended=true`），偵測器見 terminal 才 `reserveUnits(1)`+`videos.list(active-id)` 確認、連 2 次無 `activeLiveChatId` 才 merge 寫 `enabled:false` 轉 IDLE。另設**低頻 backstop**：每 `activeProbeInterval=15 分` 主動 probe 一次 active-id（防抓取器卡死漏掉 terminal），非每輪都 probe。（修二驗 finding 2：ACTIVE liveness 不再每 2 分燒 1 單位）

## 資料契約（Firestore `sml_config`）
- `ytLiveDetect` { mode: auto|off, channelId, lastCandidates[], lastCheck, missCount, lastActiveProbe, lastIdleProbe } — 偵測器狀態（`missCount`=ACTIVE 連續無 activeLiveChatId 次數；`lastActiveProbe`/`lastIdleProbe`=上次 ACTIVE backstop / IDLE 週期重探時間）。**只有偵測器寫**。
- `ytApiBudget` { quotaDatePt: "YYYY-MM-DD"(**太平洋時間 America/Los_Angeles**), reportDateTw: "YYYY-MM-DD"(台灣,僅營運報表), units: int, stoppedAt: int|null } — 每日用量帳本。**日切鍵用 `quotaDatePt`**，因 YouTube 官方 quota 於**午夜 PT 歸零**（非台灣午夜）；`reportDateTw` 只給後台看，不參與保護判斷。（三驗 finding 2）**只透過 `reserveUnits` 原子更新**（Firestore transaction 或 `currentDocument.updateTime` CAS + 有限重試），禁止裸 read-modify-write；跨 PT 日期在同一原子交易內歸零。PT 日期由呼叫端用 `Intl.DateTimeFormat('en-CA',{timeZone:'America/Los_Angeles'})` 算（DST-aware）。（修 finding 4）
- `chatCapture`（沿用）{ enabled, videoId, liveChatId, pageToken, lastPoll, lastCount, ended } — **偵測器只 merge 寫 `{videoId, enabled}`；抓取器只 merge 寫 `{liveChatId, pageToken, lastPoll, lastCount, ended}`**（`ended`=抓取器連續 400 判定聊天永久結束的 terminal 信號，偵測器只讀不寫）。
- `chatBridge`（納入契約）{ enabled, videoId, liveChatId, pageToken } — **偵測器只 merge 寫 `{videoId, enabled}`**；overlay 各層只寫自己的 `{liveChatId, pageToken, 心跳}`。
- 常數/門檻：`RSS_CANDIDATES=5`（IDLE 一次查前 5 候選，共 1 單位）；`detectInterval=2 分`（IDLE RSS 掃描，RSS 本身 0 額度）；`idleProbeInterval=5 分`（IDLE 即使候選集不變也週期性重探，抓「待機頁變 live」）；`activeProbeInterval=15 分`（ACTIVE backstop probe）；kill switch = **原子預扣後 `units + cost > 9000` 即 deny**（非事後判斷）；bridge 輪詢由 5s 放寬到 10s。

---

## STAGE 0 — 契約凍結（Claude，無 Fable5）
- 本文即交付物：資料契約、Lambda 邊界、門檻、狀態機定稿。
- **Codex 查驗**：無 search.list、無 writer race、**PT quota 日切 + TW report 分離**、kill switch 語意清楚。✅**四驗放行(2026-07-18)**。

## STAGE 1 — RSS 偵測純函式 🟣Fable5
- `parseCandidatesFromRss(xml, limit=RSS_CANDIDATES)` → 前 N 筆 { videoId, title } 陣列（malformed → 安全回 []）。
- `pickActiveCandidate(candidates, livenessMap)` → 第一個 `activeLiveChatId` 存在的候選（不必是最新片）。
- `shouldProbe(state, nowMs)` → bool 純函式（Codex 四驗提醒）：IDLE 回「候選集變 OR `now - lastIdleProbe ≥ idleProbeInterval`」；ACTIVE 回「見 `chatCapture.ended` OR `now - lastActiveProbe ≥ activeProbeInterval`」。把「要不要打 videos.list」抽成可單測的閘，handler 只依它決定是否 `reserveUnits`。
- `decideDetectAction(state, candidates, activeLiveness)` → `activate|deactivate|noop` **雙態狀態機**：
  - IDLE + 候選中有 live → `activate` 該支；IDLE + 候選全非 live → `noop`（記候選集）。
  - ACTIVE → **忽略 RSS**；terminal 或 backstop 判 active-id：連續 missCount≥2 → `deactivate`，否則 `noop`。
- 單元測試：解析候選、壞 XML 安全回 []、**IDLE + 最新片非 live + 第二筆是 live → activate 第二筆**（二驗 finding 1 迴歸）、**同候選集：首探全非 live → 過 `idleProbeInterval` 後同候選集第二筆變 live → activate**（三驗 finding 1 迴歸）、**直播中頻道發新片時 ACTIVE 不得 deactivate**（一驗 finding 1 迴歸）、active-id 連 1 次 miss 不清、連 2 次才清、同候選集未到 interval 不重探。
- **無網路**（純函式）。**Codex 查驗**：finding 1 迴歸測試存在且過、雙態邏輯正確。

## STAGE 2 — 用量帳本 + kill switch 🟣Fable5
- **2a 純函式** `budgetCompute(doc, nowQuotaDatePt, cost)` → `{ nextDoc, allowed }`：跨 **PT 日期**先歸零再**預扣**，`allowed = (units_after_rollover + cost) <= 9000`；deny 時 nextDoc 標 `stoppedAt`；同時更新 `reportDateTw`（傳入或算）。
- **2b 原子套用** `reserveUnits(cost)`：以 Firestore transaction 或 `currentDocument.updateTime` CAS + 有限重試套用 2a，回 `allowed`。**所有 v3 呼叫者唯一入口**。PT 日期字串由 helper 用 `Intl.DateTimeFormat('en-CA',{timeZone:'America/Los_Angeles'})` 產（DST-aware）。
- **cost 硬驗證（STAGE 2 Codex finding）**：`cost` 必為 `Number.isSafeInteger(cost) && cost>0`，否則 **fail-closed**（`allowed:false, error:'invalid-cost'`、不動帳本、不做 Firestore I/O）。擋掉 `0`(免費打 v3)、負值(退額度)、字串(污染 units)。因這是唯一保護入口，caller 傳錯 cost 也不能破防。補測 `0/-1/'1'/1.5/NaN/Infinity/null/undefined`。
- 單元測試（2a）：**PT 日切歸零**、累計不重複、**off-by-one：`8999+1`→allowed(=9000)、`8999+2`→deny、`9000+1`→deny**、**PT 邊界（同一 UTC 時刻在 PT 是 23:59 vs 00:01 → 換日/不換日；含 PST↔PDT DST 位移）**。（修 finding 3 + 三驗 finding 2）
- **測試指令**：`node --test test/*.test.js`（Node 22 下 `node --test test/` 會失敗）。
- **Codex 查驗**：預扣語意（非事後判斷）、CAS/transaction 併發不漏計、門檻精準、**日切鍵確為 PT 非台灣**。

## STAGE 3 — 偵測 Lambda `sml-yt-live-detect` 🟣Fable5
- handler：讀 `ytLiveDetect`(含 IDLE/ACTIVE 態) → 抓 RSS(0 額度) → 交 STAGE1 狀態機決策 → 需要 `videos.list` 時**先 `reserveUnits(1)`**、deny 就跳過 → **IDLE 用 `videos.list(id=候選逗號串)` 一次查 N 筆**取第一個 live；**ACTIVE 只在見 `chatCapture.ended` 或距 `lastActiveProbe`≥15 分才 probe active-id** → 依決策 **field-level merge** 寫 `chatCapture`/`chatBridge` 的 `{videoId, enabled}`（絕不碰 liveChatId/pageToken/telemetry）。更新 `lastCandidates/lastCheck/missCount/lastActiveProbe`。
- **只用 RSS + videos.list**；ACTIVE 不因 RSS 清空（一驗 finding 1）；IDLE 多候選找 live（二驗 finding 1）。
- ⚠️**接線鐵則（Claude STAGE 1 覆核發現）**：`decideDetectAction` 的 ACTIVE 分支把「livenessMap 無此片」當 miss；因此 handler **只有在 `videos.list` 呼叫成功**時才可把結果丟給 `decideDetectAction`。若 probe 因 API error/deny/逾時失敗 → **不得**當成一次 miss（否則兩次 API 故障會誤判直播結束）→ 該輪跳過決策、不動 missCount。
- **Codex 查驗**：無 search.list、v3 全走 `reserveUnits`、updateMask 只含允許欄位、多候選 videos.list 仍 1 單位、ACTIVE probe 頻率符 `activeProbeInterval`、結束走 active-id 連 2 次確認。

## STAGE 4 — 既有 Lambda 接帳本 + kill switch（Claude，小改）
- `sml-chat-capture`：每次 `yt()` 前呼叫 STAGE 2b 的 `reserveUnits(1)`；`!allowed` 則跳過該次呼叫。維持 1 次/分。抓取器寫入沿用既有 `capWrite`（已是 updateMask 逐欄，符合 finding 2）。
- `sml-yt-chat-bridge`：同上 + 頂上供應時把 `MIN_POLL` 5s→10s（最壞用量砍半）。
- **共用 `reserveUnits` 由單一模組匯出**，三個 Lambda（detect/capture/bridge）都 import 同一份，杜絕各自實作漏計。
- **Codex 查驗**：無任何 v3 路徑繞過 `reserveUnits`；capture 仍 1/分；bridge 間隔已放寬；writer 只碰自己欄位。

## STAGE 5 — 部署 / IAM / 排程（Claude，機械）
- 建 Lambda `sml-yt-live-detect`（Node），env：`YT_API_KEY`/`FS_API_KEY`/`FS_PROJECT`/`CHANNEL_ID`；EventBridge `rate(2 minutes)` ENABLED。
- 重佈 `sml-chat-capture` + `sml-yt-chat-bridge`。
- score-repo 部署護欄：先 commit 乾淨、確認無並行 session 佔用。
- **Codex 查驗**：排程/env/manifest 正確、未直播時 disabled 安全（RSS 抓不到 live 就不開抓取）。

## STAGE 6 — 端到端 + 演練（Claude + 真資料）
- 真 RSS 拉取驗證（今天已驗 200、含當日直播）。
- 模擬一輪偵測循環（閒置日）→ 確認不誤開；下一場真直播 → 確認自動設 videoId、帳本累加。
- **強制 kill switch 測試**：把 `ytApiBudget.units` 設到 8999 → 下一個 cost=1 呼叫剛好到 9000 允許、再一個 cost=1 被 deny 並寫 `stoppedAt`；確認 deny 後不再打 v3、只留 RSS。
- **finding 1 迴歸演練**：ACTIVE 中在頻道發一支新影片 → 確認偵測器不清掉正在抓的 live。
- **待機頁演練（三驗 finding 1）**：待機頁已在 RSS → 首探非 live →（不改候選）開播 → 確認 `idleProbeInterval` 內自動 activate。
- **PT 日切演練（三驗 finding 2）**：把 `ytApiBudget.quotaDatePt` 設成昨天 PT → 下次呼叫確認 units 歸零、`reportDateTw` 另計。
- **併發演練**：同時觸發 detect+capture+bridge → 確認 `ytApiBudget.units` 加總不漏計（原子預扣）。
- **Codex 終驗**：用真實遙測回推 3×3h 場景實際用量，確認 **< 900 單位**（表列 ≈762）、離 kill switch 9000 極遠。

---

## 用量預算核對（3 場 × 3 小時 = 9h/天，修二驗 finding 2 的算術）
| 項目 | 算式 | 單位 |
|---|---|---|
| 抓聊天 `liveChatMessages` | 540 分 × 1 | 540 |
| liveChatId 解析 | 3 場 × 1 | 3 |
| IDLE 週期重探（閒置 15h ÷ 5 分，多 id 共 1 單位/次） | 15h × 12 | 180 |
| ACTIVE backstop probe | 540 分 ÷ 15 = 36 | 36 |
| terminal 結束確認 | 3 場 × 1 | 3 |
| **合計** | | **≈ 762 / 10,000（7.6%）** |

**終驗門檻放寬到 `< 900`**（含忙碌日餘裕；離 kill switch 9000 仍極遠）。抓聊天 60 單位/小時 × 24h 上限 = 1440，物理上不可能燒完。
