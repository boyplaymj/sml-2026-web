# 觀看時長獎 — YT 自動偵測 + 額度安全 施工計畫

**目標**：直播免貼網址（RSS 0 額度自動抓 videoId）＋ 官方 v3 API 抓聊天發獎（不受 IP 封鎖）＋ 每日用量帳本 + kill switch，確保「一天 3 場 × 3 小時」也絕不把 10,000/天 配額燒完。
**分工**：Claude 設計/整合/部署/驗收；🟣**Fable5** 生成純邏輯模組與偵測 Lambda handler；**每階段交 Codex 獨立查驗**才進下一階段。
**動到的 repo**：`/opt/sml/score-repo`（production Lambda，有部署護欄地雷 → 先 commit 乾淨、防並行 session 快照）。
**by**：Claude, 2026-07-18。

## 鐵律（Codex 每階段都要檢查）
1. **絕不呼叫 `search.list`（100 單位）** — 找直播一律走 RSS(0) + `videos.list`(1)。
2. **每一次 v3 呼叫都要先過帳本 + kill switch**，沒有任何路徑可繞過計數。
3. 抓聊天維持 **1 次/分**（`liveChatMessages.list` maxResults=2000 + pageToken 接續）。
4. 偵測與抓取的 videoId 寫入不可 race（單一 writer 原則：偵測器只寫 videoId/enabled，抓取器只寫 pageToken/liveChatId/telemetry）。

## 資料契約（Firestore `sml_config`）
- `ytLiveDetect` { mode: auto|off, channelId, lastVideoId, lastCheck } — 偵測器狀態。
- `ytApiBudget` { date: "YYYY-MM-DD"(台灣), units: int, stoppedAt: int|null } — 每日用量帳本。
- `chatCapture`（沿用）{ enabled, videoId, liveChatId, pageToken, ... } — 偵測器寫 videoId+enabled；抓取器寫其餘。
- 門檻：kill switch = units ≥ 9000；偵測間隔 = 2 分；bridge 輪詢由 5s 放寬到 10s。

---

## STAGE 0 — 契約凍結（Claude，無 Fable5）
- 本文即交付物：資料契約、Lambda 邊界、門檻、狀態機定稿。
- **Codex 查驗**：無 search.list、無 writer race、台灣時區日切正確、kill switch 語意清楚。

## STAGE 1 — RSS 偵測純函式 🟣Fable5
- `parseNewestFromRss(xml)` → 最新 videoId + 標題（malformed → 安全回 null）。
- `decideDetectAction(state, newestVideoId, confirmedLive)` → `set|clear|noop` 狀態機。
- 單元測試：解析最新、壞 XML 安全、videoId 變更、直播結束→clear、同片冪等。
- **無網路**（純函式）。**Codex 查驗**：邏輯 + 邊界測試齊全。

## STAGE 2 — 用量帳本 + kill switch 純函式 🟣Fable5
- `budgetTick(doc, nowTaiwanDateStr, cost)` → `{ nextDoc, allowed }`：跨台灣日期自動歸零、累加 cost、`allowed = units < 9000`。
- 單元測試：日切歸零、逼近門檻擋下、累計不重複計、時區邊界（15:59Z vs 16:00Z = 台灣換日）。
- **Codex 查驗**：計數不重不漏、歸零正確、門檻精準。

## STAGE 3 — 偵測 Lambda `sml-yt-live-detect` 🟣Fable5
- handler：讀 `ytLiveDetect`+`ytApiBudget` → 若未 stopped：抓 RSS(0 額度) → 最新片≠lastVideoId 或目前無 active 抓取 → `videos.list`(1 單位，經帳本) 確認 `activeLiveChatId` → 有=寫 `chatCapture{videoId,enabled:true}`(+chatBridge) → 無=清空。更新 lastVideoId/lastCheck。
- **只用 RSS + videos.list**；每個 v3 呼叫都經 `budgetTick`。
- **Codex 查驗**：確認無 search.list、帳本路徑完整、冪等、直播結束會 clear。

## STAGE 4 — 既有 Lambda 接帳本 + kill switch（Claude，小改）
- `sml-chat-capture`：每次 `yt()` 前 `budgetTick`；`!allowed` 則跳過。維持 1 次/分。
- `sml-yt-chat-bridge`：同上 + 頂上供應時把 `MIN_POLL` 5s→10s（最壞用量砍半）。
- **Codex 查驗**：無任何 v3 路徑繞過帳本；capture 仍 1/分；bridge 間隔已放寬。

## STAGE 5 — 部署 / IAM / 排程（Claude，機械）
- 建 Lambda `sml-yt-live-detect`（Node），env：`YT_API_KEY`/`FS_API_KEY`/`FS_PROJECT`/`CHANNEL_ID`；EventBridge `rate(2 minutes)` ENABLED。
- 重佈 `sml-chat-capture` + `sml-yt-chat-bridge`。
- score-repo 部署護欄：先 commit 乾淨、確認無並行 session 佔用。
- **Codex 查驗**：排程/env/manifest 正確、未直播時 disabled 安全（RSS 抓不到 live 就不開抓取）。

## STAGE 6 — 端到端 + 演練（Claude + 真資料）
- 真 RSS 拉取驗證（今天已驗 200、含當日直播）。
- 模擬一輪偵測循環（閒置日）→ 確認不誤開；下一場真直播 → 確認自動設 videoId、帳本累加。
- **強制 kill switch 測試**：把 `ytApiBudget.units` 設到 8990 → 確認逼近 9000 就停 v3、只留 RSS。
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
