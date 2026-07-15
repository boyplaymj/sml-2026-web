# 甜甜每日任務系統（Daily Quest）— 設計冊 v0.1

> 狀態：**決策已定案，架構草案**。核心與 `!簽到`（`DailyCheckIn`）相鄰但關鍵不同：
> 簽到是「點按鈕就給」，每日任務要**先真的達成條件**才算完成 → 需要一套**事件追蹤器**。
> 關聯：[[新人引導 tools/sweetbot-onboarding/DESIGN.md]]（新手村任務可共用本套引擎）。

---

## 1. 玩法（使用者已定案）

1. **每日任務數**：基本 **3 個**；**每升一級 VIP 多 1 個**（VIP1=4、VIP2=5…）。多出來的是 bonus。
2. **每日重置**：台灣時間 **05:00**（用「日期 key + 重置時」判定，不沿用簽到的「當月第幾天」）。
3. **重抽**：允許，但**每天只有 1 個任務格可重抽**，**該格重抽次數不限**（一直轉到滿意為止）。其餘任務格不可重抽。**每次重抽花 80🦷**（= sink，whale 狂抽反而回收牙齒；金額後台可調）。
4. **連續（streak）**：當天**解完 3 個任務**才算「當日達成」，streak +1；沒解滿 3 個 → 當天不算、隔天 streak 歸零。（VIP 多出的任務不影響門檻，仍是解 3 個即達成。）
5. **連續獎勵**：沿用 `DailyCheckIn` 的連續天數曲線（見 §5），達里程碑發額外獎。
6. **領獎**：**打開 `!每日任務` 面板手動領**（不自動發）。達標的任務顯示可領鈕。
7. **任務池後台可編輯**：在**甜甜遊戲館新增管理頁**（見 §6），可增刪改任務模板、獎勵、權重。

---

## 2. 與 `DailyCheckIn` 的關係（沿用 vs 新做）

**沿用現成：**
- 連續天數 streak 計算模式（`continuousCount`）+ 里程碑/週獎概念。
- 獎勵設定表模式（可分等級、發**牙齒 or 道具**，`ViewerDetailDAO.givePoint` / `Props.giveLogic`）。
- 冪等防重領（`claimed` 標記，仿 `haveAwards`）。

**新做的核心 = 事件追蹤器 `QuestTracker`：**
```
各遊戲行動 ──track(discordID, 事件類型, 數量, meta)──▶ QuestTracker.track()
                                                        │ 抓該玩家今日任務中 event 相符者
                                                        │ progress += n；達 target → done=true
                                                        ▼
                                              玩家 !每日任務 面板 → 領獎鈕 → 發獎+claimed
```

---

## 3. 架構

### DDB 三張表（全 PAY_PER_REQUEST）
- **`sweetbot-quest-config`** — 任務模板池（後台可編輯）。每則：
  - `key`、`title`、`desc`、**`event`**（觸發事件字串，如 `game_win:upw`）、`target`（目標數）、`reward`（type=point/prop + amount/paramater）、`weight`（抽取權重）、`difficulty`、`enabled`。
- **`sweetbot-daily-quest`** — 玩家每日進度。`pk=discordID`、`sk=YYYY-MM-DD`（以 05:00 重置切日）：
  - `quests: [{key, target, progress, done, claimed, rerollable}]`、`rerollSlotUsed`、`streak`、`streakClaimed`、`assignedAt`。
  - 每天首次互動時**懶抽**（依 VIP 等級決定張數、依 weight 隨機且不重複）。
- **`sweetbot-quest-streak`**（或併入上表 meta 列）— 記每玩家連續達成天數 + 最後達成日期，跨月/跨日算 streak 用。

### QuestTracker.track(discordID, event, n=1, meta)
- 取/建今日 doc（不存在則懶抽）。
- 逐一比對 active 且未 done 的任務：`event` 相符（含 meta filter，如頻道白名單）→ `progress += n`；達標標 `done`。
- **不自動發獎**（決策 6）；只更新進度。玩家開面板才領。
- fire-and-forget、全 catch，**絕不影響遊戲主流程**（埋點失敗不能讓遊戲爆）。

### 埋點（各遊戲加一行呼叫）
- 工作量主體。分階段埋，P1 先高流量幾個（§4）。
- 💡 捷徑：部分事件已流過 `sweetbot-player-point-log`（帶 `reason`），可先靠它做部分事件源，減少埋點。

### UI
- `!每日任務` 一個指令開面板（embed：3+ 任務、進度條、streak 天數）+ 按鈕（每個達標任務一顆「領」鈕、1 顆「重抽」鈕作用在可重抽格、連續里程碑「領」鈕）。之後全按鈕，照「一指令開場」慣例、同訊息重繪不洗版。

---

## 4. 事件分類 taxonomy（＝後台管理頁分類正典）

每則任務 = **大分類（A~E）→ 事件 key → 參數（target 次數/數量 + meta 對象）**。
後台建任務用三層下拉：選大分類 → 選事件 key → 填參數。
可行性：🟢 現成/易埋　🟡 中等　🔴 較難（暫緩）。**P1** = 首發要埋的。

### A. 遊戲行為類 🎮
| 事件 key | 意思 | 參數 | 可行 | P1 |
|---|---|---|---|---|
| `game_play:any` | 玩任意小遊戲 N 次 | 次數 | 🟢 | ✅ |
| `game_play:<遊戲>` | 玩指定遊戲 N 次 | 次數 | 🟢 | |
| `game_win:any` | 贏任意遊戲 N 次 | 次數 | 🟢 | ✅ |
| `game_win:<遊戲>` | 贏指定遊戲 N 次 | 次數 | 🟢 | |
| `game_bet` | 遊戲下注累計 N 牙齒 | 牙齒量 | 🟢 | |
| `game_achieve:<成就>` | 遊戲內特定成就（upw 開局猜中 / 過馬路走 X 距離…） | 依成就 | 🟡 | |

**`<遊戲>` key**（現有 miniGame）：`upw`(達文西)、`sicbo`(骰寶)、`bjm`(21點)、`pokingfun`(戳戳樂)、`crossroad`(過馬路)、`abcode`(1A2B)、`inbetween`(隆巴)、`flowertime`(猜花)、`bingo`(賓果)、`rps`(剪刀石頭布)、`pkpenalty`(PK罰球)、`pusher`(推推樂)
**防farm**：只認**有下注的正式局**，排除 auto-casino 自動局。

### B. 社交互動類 💬
| 事件 key | 意思 | 參數 | 可行 | P1 |
|---|---|---|---|---|
| `post_message` | 指定頻道發言 N 則 | 次數 | 🟢 | ✅ |
| `mention_user` | @提及某人 N 次 | 次數 | 🟢 | |
| `get_mentioned` | 被別人 @ N 次 | 次數 | 🟢 | |
| `add_reaction` | 對訊息按表情 N 次 | 次數 | 🟢 | |
| `button_click:<key>` | 觸發某互動按鈕 | 次數 | 🟢 | |
| `reply_message` | 回覆別人訊息 | 次數 | 🟡 | |

**技術前提已具備**：發言/@ 靠 `MessageContent` intent ✓、表情靠 `GuildMessageReactions` intent ✓、按鈕全走 `discord.js` 派發器 ✓ → B 類全部可埋，不需加新 intent。
**防farm**：`post_message`/`add_reaction` **每日設計數上限** + 最短字數 + 頻道白名單，防洗頻。

### C. 經濟類 💰
| 事件 key | 意思 | 可行 | P1 |
|---|---|---|---|
| `checkin` | 每日簽到 | 🟢 | ✅ |
| `teeth_earned` / `teeth_spent` | 賺/花 N 牙齒 | 🟢 | |
| `redpacket_grab` | 搶紅包 N 次 | 🟢 | |
| `gift_send` | 送禮給別人 | 🟡 | |
| `item_use` / `item_buy` | 用/買道具 | 🟡 | |

### D. 養成/系統類 📈
| 事件 key | 意思 | 可行 | P1 |
|---|---|---|---|
| `exp_gain` | 獲得 N 經驗 | 🟢 | |
| `vote_join` | 參加競猜/投票 | 🟢 | |
| `bind_youtube` | 綁定 YT（與 onboarding 共用） | 🟢 | |
| `quest_complete` | 完成其他每日任務（meta 任務） | 🟢 | |

### E. 直播連動類 📺（選配）
| 事件 key | 意思 | 可行 | P1 |
|---|---|---|---|
| `yt_keyword` | 直播聊天觸發關鍵字（已有 `YtKeywordRewards`） | 🟡 | |
| `stock_bet` | 賽況應援盤下注 | 🟢 | |

### P1 首發（🟢 高流量、單點好埋、涵蓋日常主行為）
`checkin` + `game_play:any` + `game_win:any` + `post_message`。
B 類 `mention_user`/`button_click`/`add_reaction`（趣味任務）列 **P2 擴充**。

---

## 5. 獎勵數值（定案：**Tier C 大方**，後台可調）

> 使用者選 C 大方檔（2026-07-15）。因任務池後台可編輯，數值非不可逆——上線後盯 `economy.html`，通膨過頭即在後台下調。

**單題 / 每日：**
- 每完成 1 題：**150🦷 + 30 EXP**
- 當天**解滿 3 題** bonus：**+250🦷**（同時 streak +1）
- 每日基礎上限（解滿 3）：3×150 + 250 = **700🦷 / 人 / 天**

**連續里程碑（streak，厚曲線）：**
| 連續天數 | 獎勵 |
|---|---|
| 3 天 | +500🦷 |
| 7 天 | +1,500🦷 + 1 根牙刷 |
| 14 天 | +4,000🦷 + 稀有道具 |
| 30 天 | +10,000🦷 + 頂級稀有道具 |

- 攤平約 **+450🦷/人/天**；日基礎 700 + streak 450 ≈ **1,150🦷/人/天**。
- 斷連：任一天沒解滿 3 個 → 隔日 streak 歸零重算。
- streak 獎冪等（`streakClaimed` 記已領里程碑，防重領）。

（所有數值皆存後台 config，非寫死；VIP 多出的任務也是每題 150🦷。）

---

## 6. 後台管理頁（甜甜遊戲館，決策 7）

- **新頁面**：遊戲館加「📋 每日任務管理」頁，仿現有 admin 頁模式（隨機事件 `sml-random-events` / 競猜 `vote_manager.html`）：
  - **前端**：任務模板 CRUD 表格（event/target/reward/weight/enabled）、預覽玩家今日任務分佈。
  - **後端**：Lambda + APIGW action 端點，驗 Firebase token + `gameAdmins` 白名單，直連 `sweetbot-quest-config`。
- 沿用既有後台驗證/部署管線（`check-conflict.sh`→`deploy.sh`，別整檔覆蓋）。

---

## 7. 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：DDB 新表 ×3（`sweetbot-quest-config` / `sweetbot-daily-quest` / streak），PAY_PER_REQUEST，量級小（預估 < \$1/月）；後台 Lambda + APIGW（免費額度內）。
- 所有新表 PAY_PER_REQUEST；**無 LLM / 無付費 API**，故免帳本封頂四件套。
- **牙齒通膨（重點盯）**：每日任務 + 連續獎 是**新印鈔口**。

  **實測基線（point-log 近14天，2026-07-02~15）**：DAU ~45、每日印鈔 ~164,000🦷（人均 ~3,600）、印鈔≈回收（economy 大致平衡，淨值 −62k~+45k 擺盪）。

  **Tier C 投放預估**：人均 ~1,150🦷/天 × DAU 45 ≈ **+52,000🦷/天 ≈ 帳面 +32%**。抵銷因子：① 重抽 80🦷/次 = sink；② 任務驅動玩家下注（骰寶/upw）→ 額外 sink。實際淨通膨預期 < 帳面。

  **監控＋煞車（必做）**：上線後每日看 `economy.html`（Lambda `sml-teeth-economy`）的淨值曲線；若日均淨印鈔明顯翻正/失衡，**後台直接下調每題/bonus/streak 數值**（config 可調，不用改程式重部署）。建議上線首 2 週密集觀察。
- 反分身：靠新人引導硬閘 + 1:1 YT 綁定 + 任務「只認正式局」擋 auto-farm。
- 若日後加 LLM（如 AI 生成每日任務敘述），回本規範補「四件套」。

---

## 8. 待辦 / 待定

1. ✅ 獎勵數值已定（Tier C，§5）；獎勵金額後台可調。
2. 任務池**初始內容**（開幾則、涵蓋哪些遊戲）— 下一步。
3. `post_message` 的**頻道白名單** + 最短字數。
4. 重抽是否加 1~2 秒防連點（次數不限但每次扣 80🦷）。
5. 面板 UI 視覺（進度條用 emoji or 文字）。

---

## 9. 分階段落地（每階段 <25 分、可單獨上線）

- **P1**：`QuestTracker` 引擎 + `sweetbot-daily-quest` 表 + 懶抽 3 任務 + `!每日任務` 面板（讀進度/領獎/重抽）+ 埋 §4 四個事件（獎勵先寫死小值）。
- **P2**：連續 streak + 里程碑獎（沿用 DailyCheckIn 曲線）。
- **P3**：VIP 加任務數 + 後台管理頁（`sweetbot-quest-config` + Lambda + 遊戲館頁）。
- **P4**：擴事件 + 經濟數值對表微調 + 轉化/參與後台卡。

---

## 10. 初始任務池 seed（後台可再增刪改）

獎勵預設 **Tier C**：一般 `150🦷 + 30EXP`；挑戰級 `250🦷 + 50EXP`（後台可調）。
`weight` = 抽取權重（越高越常出現）；`難度` 供後台分組/篩選。
**埋點策略**：每個 miniGame 結算時同時發 `game_play:any` + `game_play:<key>`（一點兩用），首發即可支援指定遊戲任務。

### P1 可上線子集（只用已埋 🟢 事件）
| id | 名稱 | event | target | 難度 | weight | 獎勵 |
|---|---|---|---|---|---|---|
| q_checkin | 簽到小尖兵 | `checkin` | 1 | 簡單 | 10 | 150🦷+30 |
| q_play1 | 動動手指 | `game_play:any` | 1 | 簡單 | 10 | 150🦷+30 |
| q_play3 | 遊戲咖 | `game_play:any` | 3 | 普通 | 8 | 150🦷+30 |
| q_play5 | 遊戲狂人 | `game_play:any` | 5 | 挑戰 | 4 | 250🦷+50 |
| q_win1 | 旗開得勝 | `game_win:any` | 1 | 普通 | 8 | 150🦷+30 |
| q_win2 | 常勝軍 | `game_win:any` | 2 | 挑戰 | 4 | 250🦷+50 |
| q_msg1 | 打個招呼 | `post_message` | 1 | 簡單 | 10 | 150🦷+30 |
| q_msg3 | 話匣子 | `post_message` | 3 | 普通 | 6 | 150🦷+30 |
| q_upw | 密碼高手 | `game_play:upw` | 1 | 普通 | 6 | 150🦷+30 |
| q_sicbo | 骰運亨通 | `game_play:sicbo` | 3 | 普通 | 6 | 150🦷+30 |
| q_bjm | 21點賭神 | `game_win:bjm` | 1 | 挑戰 | 4 | 250🦷+50 |
| q_cross | 過馬路達人 | `game_play:crossroad` | 1 | 普通 | 6 | 150🦷+30 |
| q_poke | 戳戳樂 | `game_play:pokingfun` | 2 | 普通 | 6 | 150🦷+30 |

（P1 埋點：`checkin`＋各 miniGame 的 `game_play:any/<key>`＋`game_win:any/<key>`＋`post_message`；首發先埋 upw/sicbo/bjm/crossroad/pokingfun 五款高流量遊戲。）

### P2+ 擴充池（待對應事件埋點）
| id | 名稱 | event | target | 難度 | 獎勵 |
|---|---|---|---|---|---|
| q_mention | 呼朋引伴 | `mention_user` | 1 | 社交 | 150🦷+30 |
| q_famous | 人氣王 | `get_mentioned` | 3 | 社交 | 150🦷+30 |
| q_react | 情緒表達 | `add_reaction` | 3 | 社交 | 150🦷+30 |
| q_btn | 按鈕控 | `button_click:<key>` | 1 | 趣味 | 150🦷+30 |
| q_redpkt | 手氣紅包 | `redpacket_grab` | 1 | 經濟 | 150🦷+30 |
| q_vote | 競猜參一咖 | `vote_join` | 1 | 養成 | 150🦷+30 |
| q_exp | 經驗獵人 | `exp_gain` | 100 | 養成 | 150🦷+30 |
| q_spend | 血拼一波 | `teeth_spent` | 500 | 經濟 | 150🦷+30 |

**每日抽取**：從 enabled 池按 weight 隨機不重複抽 N 張（N = 3 + VIP等級）；建議每日至少含 1 張簡單、避免整組都挑戰級勸退。
