# 🧬 遊戲關聯器 — 關聯查驗單（交 Codex）

## 這份文件要你做什麼

甜甜遊戲館後台新增了一個「遊戲關聯器」分頁（`game_relations.html`），把所有遊戲畫成藍圖方塊、彼此有關聯的部分用線連起來（例：賓果連線→送試煉大門鑰匙→可開試煉之門）。關聯資料是**人工維護**的，可能與實際程式脫節或過度宣稱。

**請你獨立比對「圖上宣稱的每一條關聯」與 sweetbot-next 實際程式碼**，產出三種結論：

1. **✅ 確認** — 關聯真實存在，`label`／`desc` 描述準確。
2. **⚠️ 需修正** — 關聯存在但描述不準（數值錯、方向錯、條件寫錯）→ 指出正確內容。
3. **❌ 不成立** — 程式裡查無此關聯，或已失效／未上線 → 建議刪除或改標註。

**另外**：回頭找**漏掉的關聯**（見 §4）。

> ⚠️ 只做**查驗與回報**，不要改 `game_relations.html`。回報後由 Claude 依你的結論改資料再 deploy。

---

## 1. 檔案位置

| 項目 | 路徑 |
|---|---|
| 關聯器頁面（含資料） | `/opt/sml/sweetbot-site/public/game_relations.html` |
| 資料模型 | 檔案頂端 `const GAMES = [...]`（節點）、`const LINKS = [...]`（關聯邊） |
| 甜甜 bot 程式碼（真相來源） | `/opt/sml/sweetbot-next/`（model / const / migration） |
| 後台頁（各遊戲設定） | `/opt/sml/sweetbot-site/public/*_admin.html` |

關聯邊格式：`{ from, to, label, type, desc }`。`type` ∈ `item`（道具/鑰匙）、`currency`（牙齒）、`identity`（身分/VIP/頭框）、`punish`（懲罰/監獄）、`progress`（經驗/等級）、`hook`（任務/成就追蹤）。

---

## 2. 節點清單（27 個，id → 名稱）

`teeth 牙齒(共用貨幣hub)` · `exp 經驗值(共用hub)` · `store 事件商店` · `frames 頭框系統` · `jail 監獄系統` · `bingo 賓果` · `randomev 隨機事件` · `votepool 競猜池` · `livevote 直播應援投票` · `ytkw YT抓取獎勵` · `quest 每日任務` · `trialgate 試煉之門` · `yajunban 牙菌斑怪獸` · `vip VIP名單` · `tax 報稅系統` · `minigame 甜甜審判所` · `mahjtyc 模擬麻將館` · `crossroad 捍衛路權` · `train 火車大亨` · `quake 地震速報` · `election 天王里選舉` · `puzzle 偽文件解謎` · `laoshiji 老司機` · `mapcode マップコード` · `trip 行程誌` · `video 影片製作` · `paradox 悖論引擎`

---

## 3. 待查驗的關聯（30 條）

「初查依據」是 Claude 這次挖到的程式位置，**僅供你起手，請自行確認行號與語意**（程式會變動）。標「🔍待你補」者 Claude 未定位到精確出處，請你找出並回報 file:line。

### A. 道具 / 鑰匙（item）
| # | 關聯 | 宣稱 | 初查依據（自行確認） |
|---|---|---|---|
| 1 | bingo → trialgate | 試煉大門鑰匙：連線 8 條送 3 把、12 條送 2 把 | `model/Bingo.js:45`（`keys:{8:3,12:2}`）、`model/Bingo.js:~931`（發放試煉大門鑰匙）|
| 2 | store → trialgate | 事件商店賣鑰匙柄＋鑰匙棒，湊齊合成鑰匙 | `model/EventStore.js:87,100`（鑰匙柄/棒）、`const/rpgPropsEnum.js:12,16`。**請確認是否真有「合成」邏輯**，或只是分開販售零件 |

### B. 身分 / 頭框 / 經驗（identity / progress）
| # | 關聯 | 宣稱 | 初查依據 |
|---|---|---|---|
| 3 | store → frames | 商店兌換限定頭框 | `model/EventStore.js:35`（限定頭框）|
| 4 | store → exp | 商店買 800 經驗 / 直升 1 等 | `model/EventStore.js:48`（800經驗值）、`:61`（1等）|
| 5 | randomev → exp | 隨機事件結果可發經驗（後台每結果選🦷或✨經驗）| `random_event_manager.html:142`（`CURRENCIES` 含 `experience`）；bot 端 `model/RandomEvent.js` 發放邏輯 🔍待你補行號 |
| 6 | ytkw → exp | YT 關鍵字結算同時發牙齒＋經驗，各自獨立封頂 | `model/YtKeywordRewards.js:137,162`（exp/maxExpPerUser）、`yt_keyword_rewards.html:124-129,198` |
| 7 | store → vip | 商店兌換 VVVIP 爽爽 3 日 | `model/EventStore.js:74`（VVVIP 爽爽3日）。**請確認是否真限時 3 日** |
| 10 | tax → vip | 報稅列報扶養親屬需 VVIP 身分 | 🔍待你補：`model/Dependent.js` 或 `model/tax/*` 扶養資格判定，確認是否綁 VVIP |
| 11 | election → tax | 當選里長助理/持前任榮譽徽章＝公職身分，報稅可主張「公職特別扣除」21800🦷 | `model/tax/TaxBill.js:7`（認定身分組＝里長助理/前任榮譽徽章）、`:126`（`publicService`）、`model/tax/defaults.js:15`（`publicServiceDeduction:21800`）|

### C. 懲罰 / 監獄（punish）
| # | 關聯 | 宣稱 | 初查依據 |
|---|---|---|---|
| 8 | tax → jail | 逃漏稅複刻 Jail 定罪流程入獄、逐級鎖權 | `model/Tax.js:665`（複刻 Jail.sentencing）、`model/tax/TaxBill.js:190` |
| 9 | minigame → jail | 小遊戲指令發錯頻道→甜甜審判所自動判刑入獄 | 🔍待你補：審判所錯頻→Jail 的接線程式（`minigame_admin.html` 定白名單；bot 端錯頻偵測→Jail）|

### D. 任務 hook（hook）— 代表性，宣稱「每日任務涵蓋 13 遊戲」
| # | 關聯 | 宣稱 | 初查依據 |
|---|---|---|---|
| 12 | quest → bingo | QuestTracker onGamePlay/onGameWin 追蹤達成 | `model/QuestTracker.js:183`（onGamePlay）、`:192`（onGameWin）|
| 13 | quest → crossroad | 同上 | 同上 |
| 14 | quest → livevote | 同上 | 同上 |

> **請你查證「涵蓋 13 遊戲」的真實數字**：實際有多少遊戲埋了 `QuestTracker` hook？列出清單。圖上只畫了 3 條代表線，若實際遊戲差很多，回報正確數量與清單。

### E. 牙齒貨幣流（currency）— 賺／花牙齒
| # | 關聯 | 宣稱 |
|---|---|---|
| 15 | mahjtyc → teeth | 麻將館經營賺牙齒 |
| 16 | crossroad → teeth | 過馬路距離/檢查點換牙齒 |
| 17 | train → teeth | 貨運在途結算賺牙齒 |
| 18 | quake → teeth | 有感地震限時領牙齒 |
| 19 | bingo → teeth | 建盤消耗 + 連線獎勵 |
| 20 | randomev → teeth | 事件結果發牙齒 |
| 21 | votepool → teeth | 付牙齒投票、猜對平分池 |
| 22 | livevote → teeth | 單票 50🦷、押中依賠率賠付 |
| 23 | ytkw → teeth | 關鍵字結算發牙齒 |
| 24 | quest → teeth | 完成每日任務給牙齒 |
| 25 | trialgate → teeth | 地城通關給牙齒 |
| 26 | yajunban → teeth | 牙菌斑/両雀與甜甜共用同一份牙齒餘額 |
| 27 | teeth → store | 商店以牙齒結帳 |
| 28 | tax → teeth | 整年牙齒收入結算課稅 |
| 29 | election → teeth | 候選人報名付牙齒保證金 |
| 30 | puzzle → teeth | 解謎推進/破案給牙齒 |

> 貨幣流查驗重點：**方向**（賺=`X→teeth`；純消耗如報名保證金/建盤費也記 `X→teeth` 表「與牙齒經濟有往來」）與**是否真的動到 point-log / givePoint**。特別注意：
> - **#26 yajunban → teeth**：牙菌斑目前是**設計階段未實作**，「共用同一份牙齒餘額」是規劃而非現況 → 若尚未上線，建議標註為「規劃中」或降級。
> - **#30 puzzle → teeth**：偽文件解謎宣稱免費制，**是否真的發牙齒獎勵**？若無，這條要刪（puzzle 應回歸孤島）。

---

## 4. 反向任務：找漏掉的關聯

除了驗證上面 30 條，請掃 `sweetbot-next` 找**圖上沒畫、但實際存在**的跨遊戲關聯，尤其：

1. **報稅扣抵的其他來源**：Claude 已知還有「認真里民特別扣除」（靠簽到/每日任務達成天數，`model/tax/TaxBill.js:72`）與「勳功抵減」（靠成就系統，`model/Tax.js:501`）。→ 這代表可能該新增節點 `checkin 每日簽到`、`achievement 成就系統`，並連到 `tax`。請確認並建議節點/關聯。
2. **VIP 特權的實際覆蓋面**：`model/VipControl.js` / VIP entitlements 是否對「報稅以外」的遊戲也給特權？若有，`vip→X` 應補線。
3. **經驗值 exp 的其他來源**：還有哪些遊戲會發經驗？（賓果？試煉之門？每日任務？簽到？）目前 exp 只連了 store/randomev/ytkw 三條，很可能低估。
4. **監獄 jail 的鎖權回饋**：入獄後會 block 哪些遊戲指令？若「在押→擋某些遊戲」是明確機制，可考慮 `jail→X`（阻斷型關聯，目前圖上無此類型，可先在回報中提出）。
5. **道具/鑰匙的其他流向**：`model/EventStore.js` 還賣什麼跨遊戲道具？`const/rpgPropsEnum.js` 的道具分別被哪些遊戲產出/消耗？

---

## 5. 回報格式

請輸出一份 markdown，含：

- **逐條結論表**：`#` | `關聯` | `✅/⚠️/❌` | `實際 file:line` | `修正建議（若⚠️/❌）`
- **漏掉的關聯清單**：`from → to` | `label` | `type` | `依據 file:line` | `建議新增節點?`
- **總結**：幾條確認、幾條需修、幾條不成立、找到幾條新關聯。

Claude 會據此改 `LINKS`（與必要的 `GAMES` 新節點）後重新 deploy。

---

## ✅ 查驗結果與處置紀錄（Codex 2026-07-18 查驗完畢）

原 30 條：**20 ✅ 確認、5 ⚠️ 需修正、5 ❌ 不成立**。已全部處置並 deploy（sweetbot-games）。最終＝29 節點、36 關聯。

**刪除（❌ 5 條 → 4 刪 1 改）**
- `minigame→jail`：bot 端無錯頻自動判刑接線 → 刪（審判所變孤島）
- `quest→livevote`：LiveVote 無 QuestTracker hook → 刪
- `yajunban→teeth`：牙菌斑仍設計/DAO 草稿未接餘額 → 刪（牙菌斑變孤島）
- `election→teeth`：程式無報名保證金扣款 → 刪
- `teeth→store`：EventStore 扣 `HPoint` 非 `point` → 不刪，改為釐清 teeth 節點含 point（稅基）與 HPoint（商店/賭場子錢包）

**修正描述（⚠️）**
- `store→trialgate`：無「合成」，兩玩家各消耗柄/棒各 1
- `quest→crossroad`：只 onGamePlay 無 onGameWin
- `mahjtyc→teeth`、`train→teeth`：收益進金庫、提款才入牙齒
- `puzzle→teeth`：非純免費，答題/提示扣牙進 pot、首破得 500+pot+50exp

**新增（§4 找漏）2 節點 + 多條**
- 🆕 `checkin 每日簽到`、🆕 `achievement 成就系統`
- `checkin→tax`（認真里民扣除）、`achievement→tax`（勳功抵減）、`checkin→teeth/exp`（簽到獎勵）
- `vip→quest`（drawCount=3+VIP等級）
- exp hub 補齊：`bingo/trialgate/quest/puzzle/crossroad→exp`（原本 exp 被低估）

**QuestTracker 實際覆蓋 = 13 game key**：bingo, sicbo, pusher, pokingfun, inbetween, upw, bjm, bj, flowertime, abcode, crossroad, pkpenalty, rps（livevote 未埋）。其中 10 個賭場小遊戲尚未進圖。

**待辦（下一輪，需使用者拍板）**
1. 是否把 10 個賭場小遊戲加成節點（皆 →teeth、→quest）
2. 是否新增「阻斷型」關聯型別 `block`，畫 `jail→遊戲指令`（在押鎖權）、`tax→高收益指令`（欠稅戶 gate）。依 `CommonUtil.js:236-275`、`discord.js:864-896`。
