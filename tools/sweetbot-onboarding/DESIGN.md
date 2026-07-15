# 甜甜新人引導一條龍（Onboarding）— 設計冊 v0.1（骨架）

> 狀態：**討論中 / 骨架**。部分數值待使用者用分身帳號跑過現行流程後回填（見 §8 待定）。
> 目標：砍掉 MEE6 + Discord 原生雜湊流程，讓**甜甜自己**接管新人從入群到畢業的全流程；
> 把「綁定 YouTube」提前成**唯一解鎖關卡**，一步完成身分建立 + 反分身過濾 + 發獎資料鏈。

---

## 1. 目標與原則

- **甜甜一條龍**：入群偵測、歡迎、驗證、身分組、發禮、新手任務全由甜甜發，不依賴 MEE6。
- **綁定越早越好**：YouTube 綁定是第一個動作，也是唯一解鎖條件。理由：
  1. 身分建立（`sweetbot-viewer` 記錄）；
  2. **反分身**（要真實 YT 帳號 + 公開留言，且程式強制 1 YT ↔ 1 Discord）；
  3. 後續 VIP 偵測、關鍵字發獎、簽到牙齒的資料鏈從一開始就乾淨。
- **硬閘（已定案）**：綁定前新人**只看得到 `#新手村`**，其餘伺服器全鎖。過濾力最強、與「伯夷=YouTube 社群」主題一致。

---

## 2. 現況體檢（已讀程式確認，2026-07-15）

| 項目 | 現況 | 待辦 |
|---|---|---|
| 入群事件 `guildMemberAdd` | ❌ 無 handler（`discord.js`） | 要新增 |
| `GuildMembers` intent | ❌ 未開（只有 Guilds/GuildMessages/MessageContent/GuildMessageReactions，`discord.js:95`） | **要開**（privileged，Portal 也要開） |
| 身分組指派 | ✅ 現成（`CommonUtil.addRole/removeRole`、`VipRosterSync`、`LimitedTimeRole`，走 REST `members.fetch`，不需 intent） | 沿用 |
| 人類驗證 | ✅ `!link` YouTube 留言驗證（`Player.callLink`→`handleVerifyButton`→`_performBind`） | 改按鈕觸發、扶正成正式關卡 |
| 綁定唯一性 | ✅ `_performBind` 強制 1 YT 頻道 ↔ 1 Discord（`Player.js:236`） | 反分身主力，保留 |
| 綁定閘判定 | `player.checkBindStatus` = `sweetbot-viewer` 有無記錄（`discord.js:456/493/663`） | 沿用 |
| 新手牙齒 | ❌ 綁定不給初始牙齒（`_performBind` 不寫 point） | 加新手禮 |
| 新手村任務 | ❓ **程式/DDB/文件皆無**，研判在 Discord 端（MEE6 或原生 Onboarding），待使用者提供內容 | §8 待定 |

⚠️ **`model/DaVinciCode.js`（無 miniGame/）是舊死碼**；活的檔在 `model/miniGame/`。改引導別碰錯檔。

---

## 3. 甜甜一條龍流程

```
[加入伺服器]
   │ guildMemberAdd（需先開 GuildMembers intent）
   ▼
[Stage 0 落地：反機器人預檢]  ── 只看得到 #新手村
   │ · user.bot 被標記 → 自動踢
   │ · 帳號年齡 < N 天 → 隔離/婉拒（N 待定 §8）
   │ · raid 偵測：短時間大量加入 → 提高門檻/暫停放行（待定）
   │ · 甜甜貼歡迎 embed + 按鈕「🎬 綁定 YouTube 開始」
   ▼
[Stage 1 綁定 YouTube ★唯一解鎖關卡]
   │ · 點按鈕 → 甜甜私訊驗證碼 + 步驟（沿用 callLink，改按鈕觸發）
   │ · 到伯夷 YT 任一影片公開留言驗證碼 → 回來點「我留言了」
   │ · 甜甜掃留言比對（findCommentAuthor）→ 成功
   │   → 發「村民/已驗證」身分組 → 解鎖全伺服器
   │ · 失敗提示：DM 未開 / 找不到留言 / 驗證碼過期（沿用現有文案）
   ▼
[Stage 2 新手禮 + 新手村任務]
   │ · 立即發新手禮牙齒（金額待定 §8）
   │ · 任務清單（每項小獎，內容/獎勵待定 §8），候選：
   │     ✅ 綁定 YouTube（已完成）
   │     ⬜ !簽到 第一次
   │     ⬜ 玩一場小遊戲（!upw / 21點）
   │     ⬜ 到 #自我介紹 發文
   │     ⬜（可選）加 YouTube 頻道會員 → VIP
   ▼
[畢業：正式村民，全功能開放]
```

---

## 4. 反分身 / 反惡意機器人（縱深防禦）

| 層 | 機制 | 由誰 | 狀態 |
|---|---|---|---|
| L1 Discord 原生 | 驗證等級 High/Highest（需驗證手機）、Membership Screening 規則閘、AutoMod | 使用者（伺服器設定） | 待設 |
| L2 入群預檢 | `user.bot` 踢、帳號年齡閘、raid 偵測 | 甜甜程式（P3） | 待做 |
| L3 綁定閘 ★ | YT 留言驗證 + 1 YT ↔ 1 Discord | 甜甜程式（現成，改按鈕觸發） | 半現成 |
| L4 經濟層 | 牙齒須 `!簽到`/活動賺、綁定 1:1 → 養分身無利可圖 | 現有 | ✅ |

**已知漏洞（要修）**：`!綁定 <頻道ID>` 直接綁、**不驗證所有權**（只擋已被別人綁走）→ 有心人可冒認未綁頻道。
→ 對策：新手流程**只留 `!link`（留言證明）**；把 `!綁定` 收成**管理員專用**或停用。

---

## 5. 技術需求

- **開 `GatewayIntentBits.GuildMembers`**（`discord.js:95`）+ Portal → Bot → Server Members Intent（privileged；伯夷單一伺服器 <100 群免審核）。
- **新增 `guildMemberAdd` 事件** handler（放 `discord.js` client.on）。
- **身分組**：新增「未驗證」（預設落地）與「村民/已驗證」（解鎖）兩個 role；頻道權限設成「未驗證只見 #新手村」。role id 待建（§8）。
- **新手村任務進度**：新增 DDB 表（見 §6）或在 `sweetbot-viewer` 加欄位（傾向獨立表，避免污染核心記錄）。
- **新手禮發牙齒**：沿用 `ViewerDetailDAO.givePoint`。
- 綁定流程改「按鈕觸發」而非打 `!link`（沿用 `callLink`/`handleVerifyButton` 邏輯）。

---

## 6. 資料模型（草案）

**新表 `sweetbot-onboarding`（PAY_PER_REQUEST）**
- PK `pk` = discord_id
- 欄位：`stage`（landed/bound/graduated）、`joined_at`、`bound_at`、`tasks`（map：taskKey→done bool + rewardedAt）、`starter_given`（bool，冪等防重領）
- 用途：追蹤新人進度、防重複發禮、後台可看轉化漏斗。

---

## 7. 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：DDB 新表 `sweetbot-onboarding`（PAY_PER_REQUEST，量級極小，預估 < \$0.5/月）；新手禮/任務發牙齒（站內貨幣，非 AWS 成本）。
- 所有新表 PAY_PER_REQUEST；**無 LLM / 無付費 API**，故免帳本封頂四件套。
- **YouTube Data API**：綁定驗證掃留言用（`findCommentAuthor`），**免費但有每日配額**（10k units/日）。量大要留意，可加**冷卻/快取**避免濫刷配額（非金錢成本，但會撞配額上限致綁定失敗）。
- **牙齒通膨**：新手禮 + 任務獎勵是新的牙齒印鈔口，金額（§8）需對照牙齒經濟後台（`economy.html`）評估，別一次灌太多。
- 若日後加 LLM（如 AI 引導對話），回本規範補「四件套」。

---

## 8. 待定（等使用者分身跑完現行流程回填）

1. **現行新手村任務內容**：放哪（MEE6 / Discord Onboarding / 頻道）、有哪幾項、原本給什麼獎 → 對照後決定哪些搬進甜甜、哪些淘汰。
2. **新手禮牙齒金額**（對照經濟後台）。
3. **各任務項 + 個別獎勵**。
4. **帳號年齡閘門檻 N 天**（分身農場多新帳號；太嚴會誤傷真新人）。
5. **未驗證 / 村民 role id**、`#新手村` 頻道 id、伯夷 guild id。
6. raid 偵測是否要（看實際被攻擊頻率）。
7. `!綁定` 停用 or 管理員專用。

---

## 9. 分階段落地（每階段 <25 分、可單獨上線）

- **P1**：開 `GuildMembers` intent + `guildMemberAdd` 歡迎 embed + 綁定按鈕（先純引導，不鎖頻道）。低風險先讓甜甜「會打招呼 + 一鍵綁定」。
- **P2**：硬閘（未驗證 role 只見 #新手村 → 綁定成功發村民 role 解鎖）+ 新手禮牙齒。
- **P3**：反分身預檢（`user.bot` 踢 + 帳號年齡閘 +（可選）raid 偵測）+ 收 `!綁定` 權限。
- **P4**（選）：新手村任務清單 + 進度表 + 後台轉化漏斗卡。

---

## 10. 需要使用者在 Discord 端做的（我無法代勞）

- Portal → Bot → 開 **Server Members Intent**。
- 伺服器設定：建「未驗證 / 村民」role + 頻道權限、驗證等級調 High、開 Membership Screening + AutoMod。
- 提供 §8 的 id 與現行任務內容。
- 這些備妥後，甜甜程式那半才能接上。
