# 甜甜 Bot 所有權遷移交接文件（方案 C：重建為自有身分）

> 建立於 2026-07-14。給「另開的新 session」用，**假設你沒有先前對話的上下文**，照此執行即可。
> 目標：把甜甜 bot 從前工程師 `justin_liao` 的個人 Discord 開發者帳號下，**遷移到使用者自有的全新 application**，切斷「他重置 token / 刪 app 就讓甜甜斷線」的單點風險。

---

## 0. 一句話現況

- 甜甜的**程式、伺服器、DynamoDB、token 檔、主戰場伺服器、725/833 顆 emoji 都已是使用者的**。
- 唯一被綁住的是 **Discord「開發者應用程式」本身的所有權**，掛在個人帳號 `justin_liao`（非 Team）名下。
- 因為個人 app 無法直接轉移，且使用者選擇**不依賴 justin**，故走「重建」：用使用者自己的帳號建**新 app**，換 token，重邀、重傳被綁住的 emoji。
- 這件事**該做但不緊急**（實際曝險小）；可挑玩家離峰、使用者有空登入 Discord 時做。

---

## 1. 關鍵事實與 ID（都已用線上 API 實查，非臆測）

### 現行 application（要被取代的）
| 項目 | 值 |
|---|---|
| 應用名稱 | 甜甜 |
| Application ID（= bot user id） | `909624656846286899` |
| 擁有者 | 個人帳號 `justin_liao`，user id `594915171001171978`（**非 Team**） |
| bot_public | true |
| 所在伺服器數 | 34 |
| 需要的 intents | Guilds、GuildMessages、**MessageContent（特權，要手動開）**、GuildMessageReactions；partials: MESSAGE, CHANNEL, REACTION（見 `discord.js:96-101`） |

### Bot 真身與啟停
- 程式：`/opt/sml/sweetbot-next`（Node，systemd unit = `sweetbot-next.service`）
- 登入：`discord.js:693` `client.login(Config.loginToken)`；token 由 `config.js` 讀環境變數
- Token 優先序（`config.js:27`）：`SWEETBOT_TOKEN_<NODE_ENV大寫>` || `SWEETBOT_TOKEN`
- Token 檔：`/opt/sml/sweetbot.env`（權限 600），key = `SWEETBOT_TOKEN`（正式）
  - systemd `EnvironmentFile=/opt/sml/sweetbot.env`，`WorkingDirectory=/opt/sml/sweetbot-next`，`ExecStart=/usr/bin/node discord.js`
- 重啟：`bash restart.sh`（**未 commit 的改動會擋重啟**；緊急用 `FORCE_RESTART=1 bash restart.sh`）。詳見 `sweetbot-next/AGENTS.md` 版控治理。

### 主伺服器 & 群主分布（重邀新 bot 要用）
- **主戰場「伯夷打麻將」`698760345660948530`，群主 = 使用者 `165872613757943808`**（config 內 `centerServerID`）。✅ 重邀零阻力。
- 34 群中：**27 群非 justin**（`165872613757943808` ×25、`1038701587503271977` ×2）→ 使用者自己能重邀；**7 群是 justin** 名下 → 新 bot 要重邀需 Manage Server 或請他點連結。
- justin 名下 7 群：
  - 社群類 3：`劍靈玩一波 710502311335690311`、`甜甜之友會 1029372804010885180`、`神的恩澤 1090232634111701083`
  - 金庫類 4：`嫻嫻紙娃娃G 1039541011392770110`、`鹹鹹紙娃娃H 1039541079881552024`、`嫻嫻紙娃娃J 1041060103245275288`、`嫻嫻紙娃娃K 1041060209784799402`

### Emoji 金庫現況（換 bot 身分後的存活性）
- emoji 拼圖管線：`sweetbot-next/tools/emoji/`（`upload.js` 上傳、`emoji.js` 的 `em()` 存取器、`registry.json` 記錄）。
- 金庫自動探索：`upload.js` `VAULT_RE = /紙娃娃/`（甜甜在、名稱含「紙娃娃」、有管理表情權限的 guild）→ **新 bot 只要被邀進你的金庫就自動認得，免改碼**。
- 兩種儲存：
  - **guild-emoji** `/guilds/{guildId}/emojis` → 屬於 guild，**換 bot 存活**（emoji id 不變、registry 不動），新 bot 只要是該 guild 成員就能用。共 **833 顆**。
  - **app-emoji** `/applications/{APP}/emojis` → 屬於**舊 application**，新 app **看不到也用不到** → **必須重傳**。共 **34 顆**。
- 833 顆 guild-emoji 中：**725 顆在使用者自有金庫（安全）**；**108 顆卡在 justin 的 4 台金庫**（G:25、H:32、J:24、K:27）→ 新 bot 進不去就用不到 → 要搬到使用者金庫。

---

## 2. 硬寫死 `909624656846286899` 的 15 處（換新 id 要改的）

**線上會影響行為的（必改）：**
- `sweetbot-next/config/config.json:5` → `botSelfDiscordID`（甜甜辨識自己、忽略自己訊息/偵測被 tag）
- `sweetbot-next/tools/emoji/upload.js:26` → `const APP`（app-emoji 上傳/刪除端點）
- `sweetbot-staging/config/config.json`、`sweetbot-staging/tools/emoji/upload.js`（切換上線後 staging 也要同步，否則下次從 staging 部署會蓋回舊 id）

**同時注意（justin 的個人 id `594915171001171978`）：**
- `sweetbot-next/config/config.json:4` → `fatherDiscordID = 594915171001171978`（= justin 個人帳號，疑似給管理員權限）。**已拍板（§7-1）：改成使用者 id `165872613757943808`**。

**掃尾即可、不影響運行（有空再改）：**
- `repo/aws/codex-bridge/commands.json`、`repo/aws/discord-bridge/commands.json`
- `score-repo/sweetbot_commands.html`（+ `score-repo-backup-20260628/`）
- `repo/tools/tianwang-election/DESIGN.md`

**忽略（只是 DB 匯出樣本，非線上）：**
- `sweetbot-next/migration/dump/RPG_Saying.json`、`GameCdTime.json`
- `discordbot-sweet/`（舊廢棄品）

---

## 3. 執行清單（分工）

### A. 只有使用者能做（要登入使用者自己的 Discord）
1. 到 https://discord.com/developers 用**使用者自己的帳號**建新 application → 加 Bot → 複製新 **Bot Token** 與新 **Application ID**。
2. Bot 設定頁開 **Message Content Intent**（特權，預設關；不開甜甜讀不到 `!` 指令）。Server Members 若無用到可不開（現行只用上述 4 個）。
3. 產生 OAuth2 邀請連結（scope: `bot` + `applications.commands`；權限沿用舊 bot，保守可先給 Administrator 再收斂）→ 邀新 bot 進：
   - 使用者自有的 27 群（秒解）
   - **justin 名下 7 群一律不邀（已拍板 §7-2、§7-3）**：社群 3 群不再進；金庫 4 台改搬 emoji（見下）
4. 在主伺服器「伯夷打麻將」把新 bot 的角色**位階拉到它要管理的身分組之上**（否則發身分組/選舉當選綁定/VIP 都會失敗）。
5. 把新 token 貼給新 session 的 Claude（或直接寫進 `/opt/sml/sweetbot.env`）。

### B. Claude 可全包（拿到新 token 與新 app id 後）
6. **搬/重傳 emoji**（見 §4 腳本策略）：
   - 34 顆 app-emoji → 重傳到新 app。
   - 108 顆卡在 justin 金庫的 guild-emoji → 重傳到使用者自有金庫（挑有空位的），回填 `registry.json`（新 id）。遊戲透過 `em()` 讀 registry，**免改遊戲碼**。
7. **換 token + 改 id**：
   - `/opt/sml/sweetbot.env` 的 `SWEETBOT_TOKEN` 換成新 token（**先把舊值註解保留**，方便回滾）。
   - `config/config.json` 的 `botSelfDiscordID` → 新 app id；`fatherDiscordID` → `165872613757943808`（已拍板 §7-1）。
   - `tools/emoji/upload.js` 的 `APP` → 新 app id。
   - staging 同步。
8. **重啟**：commit 改動 → `bash deploy.sh`（或 `FORCE_RESTART=1 bash restart.sh` 緊急）。確認 `systemctl is-active sweetbot-next` = active。
9. **掃尾**：改 §2 那批文件類引用。

---

## 4. Emoji 重傳/搬遷腳本策略（給 Claude）

**來源真相 = Discord CDN（公開、免 auth）**，不依賴舊 token/舊 app 也能取得目前的圖：
- 靜態：`https://cdn.discordapp.com/emojis/{id}.png`
- 動態：`https://cdn.discordapp.com/emojis/{id}.gif`（registry 若有 animated 旗標據此選；否則先試 .gif 失敗再 .png）

流程：
1. 讀 `registry.json`，篩出 (a) 全部 `app:true` 的 34 顆；(b) `guildId ∈ {G,H,J,K}` 的 108 顆。
2. 逐顆從 CDN 抓 bytes → base64 → 用**新 token** 上傳：
   - app-emoji：`POST /applications/{新APP}/emojis`（body: name, image）
   - 搬遷的 guild-emoji：挑使用者自有金庫（`upload.js` 的 caps 邏輯找有空位者）`POST /guilds/{目標guildId}/emojis`
3. 拿新回傳的 emoji id **回填 registry.json**（同 name 換 id / guildId / app 旗標），保留舊備份 `registry.json.bak`。
4. **驗證**：隨機抽幾顆，確認新 id 的 CDN 圖抓得到、且遊戲盤面（如過馬路/試煉之門/賓果）渲染正常。
- 沿用 `upload.js` 既有的 UA `DiscordBot (https://boyplaymj.com, 1.0)` 與每金庫 50 顆上限/空位偵測。
- ⚠️ Discord 對 emoji 建立有 rate limit，逐顆之間加 sleep；動態 gif 檔案大小上限 256KB。

---

## 5. 回滾（rollback）

只要 **justin 還沒重置舊 token / 刪舊 app**，回滾是即時的：
- 把 `/opt/sml/sweetbot.env` 的 `SWEETBOT_TOKEN` 換回舊值（保留的註解那行）→ `FORCE_RESTART=1 bash restart.sh`。
- 甜甜立刻以舊身分 `909624656846286899` 回歸。emoji registry 若已改寫，回滾前先還原 `registry.json.bak`。
- 建議切換前先 `cp registry.json registry.json.pre-migration` 與記下舊 token。

---

## 6. 驗收清單（切換後逐項確認）
- [ ] `systemctl is-active sweetbot-next` = active，`bot.log` 無登入錯誤
- [ ] 主伺服器打 `!` 指令（如 `!積分`）甜甜有回應（= MessageContent intent 有開）
- [ ] 甜甜以**新身分**在線（頭像/名稱正常；新 bot user id）
- [ ] 一個含 app-emoji 的功能顯示正常（34 顆已重傳）
- [ ] 一個用到原 justin 金庫那 108 顆的遊戲盤面顯示正常（已搬遷+registry 回填）
- [ ] 發身分組類功能正常（角色位階已拉高）
- [ ] staging 的 id 已同步（下次部署不會蓋回舊 id）

---

## 7. 決策（使用者已拍板 2026-07-14）✅
1. **`fatherDiscordID` → 換成使用者 `165872613757943808`**（不再保留 justin，徹底不依賴他）。
2. **justin 名下 3 個社群伺服器（劍靈玩一波/甜甜之友會/神的恩澤）不重邀**。→ A 類步驟 3 只邀使用者自有的 27 群；justin 名下的群一律不邀。
3. **108 顆卡 justin 金庫的 emoji → 搬到使用者自有金庫**（徹底斷開）。→ Claude 走 §4 腳本從 CDN 抓圖重傳到自有金庫、回填 registry；justin 4 台金庫（G/H/J/K）一律不邀新 bot。
