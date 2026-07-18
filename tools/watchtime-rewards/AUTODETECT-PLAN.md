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

## 偵測器狀態機（IDLE / ACTIVE 兩態，修 finding 1）
- **IDLE**（無 active capture：`chatCapture.enabled=false` 或無 videoId）：抓 RSS(0) → 取最新 videoId → 若 ≠ lastVideoId → `reserveUnits(1)`+`videos.list` 確認 `activeLiveChatId` 存在 → **有才** merge 寫 `chatCapture{videoId,enabled:true}`(+`chatBridge{videoId,enabled:true}`) 轉 ACTIVE；無則僅記 lastVideoId、維持 IDLE。
- **ACTIVE**（已在抓某 videoId）：**完全忽略 RSS 最新片**（避免直播中發新片誤關）。只針對**目前 active 的那支 videoId** 做 `reserveUnits(1)`+`videos.list` 確認 `activeLiveChatId`；**連續 2 次**都沒有才判定結束 → merge 寫 `enabled:false`（清 videoId）轉 IDLE。單次沒有視為暫時性（不清）。
- ACTIVE 判定結束也可由抓取器 terminal 信號輔助（capture 連續 400 = 聊天永久結束），但**權威清空仍走上面 active-id 的 videos.list 確認**，單一判定來源。

## 資料契約（Firestore `sml_config`）
- `ytLiveDetect` { mode: auto|off, channelId, lastVideoId, lastCheck, missCount } — 偵測器狀態（`missCount`=ACTIVE 連續無 activeLiveChatId 次數）。**只有偵測器寫**。
- `ytApiBudget` { date: "YYYY-MM-DD"(台灣), units: int, stoppedAt: int|null } — 每日用量帳本。**只透過 `reserveUnits` 原子更新**（Firestore transaction 或 `currentDocument.updateTime` precondition compare-and-swap + 有限重試），禁止裸 read-modify-write。跨台灣日期在同一原子交易內歸零。（修 finding 4）
- `chatCapture`（沿用）{ enabled, videoId, liveChatId, pageToken, lastPoll, lastCount } — **偵測器只 merge 寫 `{videoId, enabled}`；抓取器只 merge 寫 `{liveChatId, pageToken, lastPoll, lastCount}`**。
- `chatBridge`（納入契約）{ enabled, videoId, liveChatId, pageToken } — **偵測器只 merge 寫 `{videoId, enabled}`**；overlay 各層只寫自己的 `{liveChatId, pageToken, 心跳}`。
- 門檻：kill switch = **原子預扣後 `units + cost > 9000` 即 deny**（非事後判斷）；偵測間隔 = 2 分；bridge 輪詢由 5s 放寬到 10s。

---

## STAGE 0 — 契約凍結（Claude，無 Fable5）
- 本文即交付物：資料契約、Lambda 邊界、門檻、狀態機定稿。
- **Codex 查驗**：無 search.list、無 writer race、台灣時區日切正確、kill switch 語意清楚。

## STAGE 1 — RSS 偵測純函式 🟣Fable5
- `parseNewestFromRss(xml)` → 最新 videoId + 標題（malformed → 安全回 null）。
- `decideDetectAction(state, newestVideoId, activeConfirmedLive)` → `activate|deactivate|noop` **雙態狀態機**（依上文 IDLE/ACTIVE）：
  - IDLE + 新片 + 確認 live → `activate`；IDLE + 新片但非 live → `noop`（記 lastVideoId）。
  - ACTIVE → **忽略 RSS 最新片**；只吃 active-id 的 liveness：連續 missCount≥2 → `deactivate`，否則 `noop`。
- 單元測試：解析最新、壞 XML 安全回 null、**直播中頻道發新片時 ACTIVE 不得 deactivate**（finding 1 迴歸測試）、active-id 連 1 次 miss 不清、連 2 次才清、同片冪等。
- **無網路**（純函式）。**Codex 查驗**：finding 1 迴歸測試存在且過、雙態邏輯正確。

## STAGE 2 — 用量帳本 + kill switch 🟣Fable5
- **2a 純函式** `budgetCompute(doc, nowTaiwanDateStr, cost)` → `{ nextDoc, allowed }`：跨台灣日期先歸零再**預扣**，`allowed = (units_after_rollover + cost) <= 9000`；deny 時 nextDoc 標 `stoppedAt`。
- **2b 原子套用** `reserveUnits(cost)`：以 Firestore transaction 或 `currentDocument.updateTime` precondition CAS + 有限重試套用 2a，回 `allowed`。**所有 v3 呼叫者唯一入口**。
- 單元測試（2a）：日切歸零、累計不重複、**off-by-one：`8999+1`→allowed(=9000)、`8999+2`→deny、`9000+1`→deny**、時區邊界（15:59Z vs 16:00Z 台灣換日）。（修 finding 3）
- **Codex 查驗**：預扣語意（非事後判斷）、CAS/transaction 併發不漏計、門檻精準。

## STAGE 3 — 偵測 Lambda `sml-yt-live-detect` 🟣Fable5
- handler：讀 `ytLiveDetect`(含 IDLE/ACTIVE 態) → 抓 RSS(0 額度) → 交 STAGE1 狀態機決策 → 需要 `videos.list` 時**先 `reserveUnits(1)`**、deny 就跳過 → 依決策 **field-level merge** 寫 `chatCapture`/`chatBridge` 的 `{videoId, enabled}`（絕不碰 liveChatId/pageToken/telemetry）。更新 `lastVideoId/lastCheck/missCount`。
- **只用 RSS + videos.list**；ACTIVE 時只查 active-id、不因 RSS 最新片清空（finding 1）。
- **Codex 查驗**：無 search.list、v3 全走 `reserveUnits`、updateMask 只含允許欄位（finding 2）、ACTIVE 直播中發新片不誤關（finding 1）、結束走 active-id 連 2 次確認。

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
- **併發演練**：同時觸發 detect+capture+bridge → 確認 `ytApiBudget.units` 加總不漏計（原子預扣）。
- **Codex 終驗**：用真實遙測回推 3×3h 場景實際用量，確認 < 600 單位、94% 餘裕。

---

## 用量預算核對（3 場 × 3 小時 = 9h/天）
| 項目 | 算式 | 單位 |
|---|---|---|
| 抓聊天 | 540 分 × 1 | 540 |
| liveChatId 解析 | 3 場 × 1 | 3 |
| 偵測確認 | 有換片才打 | ~30 |
| **合計** | | **≈ 573 / 10,000（5.7%）** |

kill switch 9000 = 永遠碰不到；抓聊天 60 單位/小時 × 24h 上限 = 1440，物理上不可能燒完。
