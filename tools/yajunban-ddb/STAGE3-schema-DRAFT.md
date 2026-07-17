# 牙菌斑怪獸 · DDB 資料模型 — 階段3:`M#CORE` / `M#BUILD` 完整欄位 schema

> **定稿 · Codex 階段2二驗已合流(2026-07-17)**:4-item 切法確認不變、存疑①talent=StringSet、存疑⑤stats 留 CORE;轉生改 exact-key 覆寫(見 STAGE2 決策③)。M#CORE/M#BUILD 欄位不受影響。背包⑦/世界⑧ schema 排階段4/7。
> 交接文件 · 產出日期 2026-07-17 · 承接 [STAGE2-schema-decision.md](./STAGE2-schema-decision.md)（4-item 切法權威）+ [STAGE1-access-patterns.md](./STAGE1-access-patterns.md)（存取模式）
> 語義來源:設計冊 `score-repo/yajunban_design.html`（section-stats / -growth / -race / -talent / -skills / -jobs / -slots / -data,canonical）。型別慣例:`sweetbot-next/DAO/DDB/*`（DDBBaseDAO / TrainTycoonStationDAO / PuzzleRoundDAO）。
> **狀態:定稿**(見上行)。歷史備註:本檔曾為草稿待二驗;Codex 二驗已確認 4-item 切法不變、M#CORE/M#BUILD 欄位定稿;背包⑦/世界⑧ 另排階段4/7。

---

## ⚠️ 待確認/存疑點(設計時不確定,交 Codex/使用者拍板)

1. **talent_nodes 編碼(最大不確定)**:草稿選 **StringSet(SS)** 存已點節點 id,理由見 M#BUILD talent_nodes 列。替代方案=145-bit **bitmap(Binary B)**。取捨:SS 支援「單節點 ADD 冪等原子寫」(配點正好是 TransactWrite 加 1 節點+扣 1 點,SS 的 `ADD :node` 天生對味)、可讀、稀疏(單一生命只點得到極少格);bitmap 省 ~15 bytes 但失去單節點原子 ADD、要 bit 運算、除錯難。因整包 item 才 ~10KB、400KB 上限非風險(STAGE2),**bytes 不是約束 → 選 SS**。若 Codex 認為要極致壓縮或要「一次讀就知整棵樹狀態」再改 bitmap。
2. **節點總數 145 vs 100**:設計冊 section-talent 明寫「100 格主盤」+「🥚 轉生流疊加層(中心 8 + 各色臂約 8×4 ≈ 40,不計入 100)」→ 實際 ≈ 140–145。task 講 145。SS 存 id 與節點總數無關(稀疏),故此不確定性不影響 schema,只影響靜態定義表。**靜態天賦定義表(節點 id/階層/雙閘門/前置/門檻)不落怪獸 item**,是設定表(見 STAGE1 1-2「讀天賦樹結構定義」),本 schema 不含。
3. **時間戳格式**:sweetbot-next 慣例=**epoch 毫秒 Number**(`Date.now()`,見 PuzzleRoundDAO.createdAt / TrainTycoon `Number(now)`)。設計冊舊 Firestore 草案用 ISO 字串(`"2026-01-01T00:00:00Z"`)→ **本 schema 一律改 epoch 毫秒 N**,不用 ISO。⚠️ 若後端有跨平台(APP)需求要人讀,再議;目前對齊 bot 慣例。
4. **`slots[].generated_at`**:設計冊 Firestore 草案寫成日期字串 `"2026-01-01"`。本 schema 統一 epoch 毫秒 N。存疑:插槽圖是否需保留「生成日」給後台稽核?若是,可另加 human-readable,但預設只存 ms。
5. **stats 該放 CORE 還是獨立**:6 戰鬥數值(hp/atk/def/magic/spd/luck)是「碎片兌換才變」的準永久值(STAGE1:數值只能靠碎片提升、跨轉生保留基底),寫頻率其實低,語義上更接近 BUILD。但戰鬥/面板/門檻**讀**極高頻,且 STAGE2 決策②表格明列 stats 在 CORE。**草稿遵從 STAGE2 放 CORE**,但標記為邊界爭議點——若 Codex 認為 stats 幾乎不熱寫、該跟 BUILD 走以縮小 CORE 熱寫 item,可移。(註:hp 當前值戰鬥中不落庫、只在結算寫,STAGE1 1-3;故 CORE.stats.hp 是「上限/基礎值」語義,非戰鬥中即時血量。)
6. **生病旗標形狀**:設計冊有兩病型(飢餓型/臃腫型),草稿用單一 `sick_type` 字串(`none`/`starve`/`obese`)+ `sick_since`,而非兩個 bool。若戰鬥/治療邏輯要同時帶兩型再改 Map。
7. **每日計數的重置基準**:草稿用 `daily_counts`(Map)+ `daily_reset_date`(當地日 YYYYMMDD 字串)。lazy 判斷「跨日就歸零」。存疑:時區(台灣 UTC+8)在何層決定;建議存 UTC 日字串、DTO 層轉。餵食不進 daily_counts(用 satiety 當閥,STAGE1 1-1)。
8. **`friendship` 上限**:section-stats 面板顯示 (30/80) 但 section-growth 明寫「當前狀態型,上限 100」。草稿採 **0–100**(growth 為準),面板的 80 是進化門檻顯示區間非硬上限。
9. **position 座標形狀**:設計冊 section-board 未在本次萃取範圍;草稿用 `pos`(Map `{x:N, y:N}`)+ 世界維度另議。若地圖有 server/zone 維度,座標可能要加 `zone`。標記待 section-board 補。
10. **job 未就職 / 未進化預設**:`job_guild`=`null`(未選公會)、`job_tier`=`0`(0=未就職,1=見習…4=二轉)。存疑:tier 用數字 1–4 還是字串 `apprentice/colonizer/...`;草稿用數字 + 說明對照,對齊 train `tier` 用法。

---

## 📌 表與主鍵(對齊 STAGE2 決策①②③)

- **表**:`sweetbot-yajunban-monster` · PAY_PER_REQUEST · ap-southeast-1
- **PK** = `userId`(S,= Discord user id,沿用 sweetbot 慣例;`String(userId)` 存)
- **SK** = 實體型別字串。本檔:`M#CORE`(熱)、`M#BUILD`(溫)
- 轉生 = 固定 3 顆 exact-key `TransactWrite`(Put M#CORE/BUILD/PROGRESS + Update PLAYER#PERMANENT),**非** `delete begins_with`(DDB 無 atomic delete-many);詳見 STAGE2 決策③
- 兩顆共通稽核欄:`createdAt`(N,epoch ms,建立時)、`updatedAt`(N,epoch ms,每次寫)——對齊 PuzzleRoundDAO / TrainTycoon 慣例
- **型別代碼**:S=String / N=Number / M=Map / L=List / SS=StringSet / BOOL=Boolean / B=Binary
- **累計型 vs 狀態型**:累計型(xp/charm/reputation/survival_hours)只增不減 → 可用原子 `ADD` + 最終一致;狀態型(friendship/satiety/obesity_level/mood/battle_deaths)有上下限 → 需強一致 + 條件檢查(STAGE1 1-1 設計影響)。每列在「語義說明」標注。
- 🔍 **玻璃箱**:standard=所有裸數值欄**絕不可直接出 API**,須經 DTO 轉帶名狀態(心情→emoji、肥胖→體態名、友好→分帶、talent→只給結構/方向不給數字)。逐欄標 `🔒裸值·禁直出`。

---

## 🔥 M#CORE(熱 · 活狀態) — PK=userId · SK=`M#CORE`

寫頻率最高(照顧/移動/被動吸收/lazy 衰退),目標 ~1.5–2 KB、熱寫 ~2 WRU。

| 屬性名 | 型別 | 預設值 | 語義說明 | 巢狀結構 |
|---|---|---|---|---|
| `userId` | S | (必填) | PK,Discord user id,`String()` | — |
| `sk` | S | `"M#CORE"` | SK 固定值 | — |
| `race` | S | (孵化時定) | 種族:`blue`(塑料)/`red`(血色)/`purple`(菌類)/`green`(菜渣)。天生不變(轉生重 roll) | — |
| `stage` | N | `1` | 成長階段 1–6(芽孢…蛀牙王)。🔒進化外觀由此驅動,數值隱藏 | — |
| `seed` | N | (孵化時定) | 怪獸外觀種子,固定不變(疊圖/生圖一致性) | — |
| `born_at` | N | `Date.now()` | 出生時間(epoch **ms**)。survival_hours / 進化目標天數的基準 | — |
| `stats` | M | (孵化基準) | 6 戰鬥數值。🔒裸值·禁直出(黑箱,只透過戰鬥/外觀感知)。**準永久**:只靠碎片兌換 +1(TransactWrite),等級不給;跨轉生保留基底。詳見存疑⑤ | `{ hp:N, atk:N, def:N, magic:N, spd:N, luck:N }` — hp=基礎/上限值(戰鬥即時血在記憶體,結算才寫);全 N |
| `charm` | N | `0` | 魅力值。**累計型**(只增)。技能/道具解鎖門檻+進化門檻+外觀提示。🔒裸值 | — |
| `friendship` | N | `0` | 友好度。**狀態型 0–100**(每天無互動 −1,lazy)。羈絆技功率/進化門檻/歸零逃跑。需強一致+上限檢查。🔒裸值(DTO→分帶😄😊😐😤) | — |
| `reputation` | N | `0` | 聲望。**累計型**(只增)。門檻+防閉關練功;=0 持續 7 天觸發逃跑(見 zero_reputation_since)。🔒裸值 | — |
| `survival_hours` | N | `0` | 存活時數。**累計型·活動/A層被動吸收累計**(離線亦累計)。⚠️ **非 `now−born_at`**;`born_at` 只作年齡/進化天數基準,不當 survival_hours 計算源(Codex Stage3 合流 #5)。🔒裸值 | — |
| `xp` | N | `0` | 累計 EXP。**累計型**。只解鎖(進化/技能/插槽/菌核躍動),不加裸戰鬥數值。🔒裸值 | — |
| `obesity_level` | N | `0` | 肥胖等級 **0–10**。**狀態型**(收支結算,ADD 但夾限)。7–9 生病風險、10 死亡;3/6/9 觸發重生圖。🔒裸值(DTO→體態名) | — |
| `satiety` | N | (孵化滿值) | 飽食度。**狀態型**(隨時間 lazy 下降,見 last_fed_at)。見底→飢餓生病。🔒裸值。**(決策⑥補欄)** | — |
| `mood` | N | (初值) | 心情分數 0–100。**狀態型·多為 lazy 算不落庫**(由互動新鮮度/戰鬥近況/飢餓/成長感即時算),但保留欄位供快取/覆寫。🔒裸值(DTO→emoji+提示)。**(決策⑥補欄)** | — |
| `battle_deaths` | N | `0` | 戰鬥死亡累計(上限 3→永久死亡)。**狀態型**,強一致+條件。🔒裸值 | — |
| `sick_type` | S | `"none"` | 生病旗標:`none`/`starve`(飢餓型)/`obese`(臃腫型)。卡進化門檻+HP 流失。見存疑⑥。**(決策⑥補欄,原僅 obesity_level)** | — |
| `sick_since` | N | `null` | 生病起始 epoch ms(未病=null),供 DoT/未處理則死判定 | — |
| `pos` | M | `{x:0,y:0}` | 棋盤座標。移動消耗菌氣寫入。見存疑⑨(zone 維度待 section-board) | `{ x:N, y:N }` |
| `khui` | N | (孵化滿 5) | **菌氣當前基準值**(Codex 階段5 P0-1:只存 ts 不夠,公式需 base)。讀時現值=`min(5, khui + floor((now−khui_last_ts)/間隔))`;消費(移動−1/戰鬥−2)時 `SET khui=現值−消費, khui_last_ts=now`(條件防超支) | — |
| `khui_last_ts` | N | `Date.now()` | 菌氣回復基準時間(epoch ms)。間隔=20 分/新手 Stage1–2 10 分;與 `khui` 配對算現值,零週期寫、僅消費時更新。**(決策⑥補欄)** | — |
| `last_interaction` | N | `Date.now()` | 最後開面板/照顧互動(epoch ms)。友好每日 −1 衰退 + 心情新鮮度 + B 情境呼喚判定的基準 | — |
| `last_fed_at` | N | `null` | 最後餵食(epoch ms)。satiety lazy 下降基準。**(決策⑥補欄)** | — |
| `daily_counts` | M | `{}` | 每日照顧次數計數(跨日 lazy 歸零)。摸頭≤3/玩耍≤1/整理≤1/鼓勵≤3(餵食不計,用 satiety 當閥)。**(決策⑥補欄)** | `{ headpat:N, play:N, groom:N, cheer:N }`(缺鍵視為 0) |
| `daily_reset_date` | S | (今日) | 每日計數重置基準日 `YYYYMMDD`(UTC,DTO 轉時區)。讀時比對→跨日清 daily_counts。見存疑⑦ | — |
| `zero_friendship_since` | N | `null` | 友好度降到 0 的時間(epoch ms);非 0 時清 null。=0 持續 7 天→逃跑判定。**(決策⑥點名)** | — |
| `zero_reputation_since` | N | (未歸零時不寫) | 聲望降到 0 的時間(epoch ms);**快取/通知用,非唯一真相**(可由 reputation 值+時間戳虛擬推導,見 5b P0-2 virtual-state)。=0 持續 7 天→逃跑。**(決策⑥點名)** | — |
| `rate_mods` | M | `{}` | **lazy rate 修正快取**(Codex 階段5 P1-6):從 M#BUILD 天賦/職業/道具去正規化的 compact 修正,讓 `getStatusCore`(只讀 CORE)能算 khui/satiety/菌圃 lazy 值免讀 BUILD。天賦/職業變更時同步(低頻);缺鍵=用設定表 base rate | `{ khui_regen:N, satiety_decay:N, garden_mature:N, ... }` |
| `createdAt` | N | `Date.now()` | item 建立時間(epoch ms) | — |
| `updatedAt` | N | `Date.now()` | 最後寫入時間(epoch ms),每次 UpdateItem SET | — |

**孵化 = 單一 `TransactWrite` 原子建立 M#CORE + M#BUILD**(Codex Stage3 合流 #3:不可只 Put M#CORE,否則中途失敗留半隻怪獸)。兩顆各帶 `ConditionExpression attribute_not_exists(userId)` 防重複孵化。M#CORE 初值:`stage=1, xp=0, charm/friendship/reputation/survival_hours=0, obesity_level=0, battle_deaths=0, satiety=滿, sick_type=none`;M#BUILD 初值:`job_guild=null, job_tier=0, talent_points_available=0, skill_slots=預設空槽`,而 `talent_nodes/talent_unlockable/skill_bag/slots` 屬性**不寫**(缺省視為空)。M#PROGRESS 走 lazy-create(首次接任務/成就時建),或 Stage4 決定納入孵化交易。

---

## 🌿 M#BUILD(溫 · build) — PK=userId · SK=`M#BUILD`

升級/裝備/配點/轉職才動,目標 ~1.2 KB。與 CORE 分顆 → 熱寫不背 23 插槽 URL。

| 屬性名 | 型別 | 預設值 | 語義說明 | 巢狀結構 |
|---|---|---|---|---|
| `userId` | S | (必填) | PK,同 CORE | — |
| `sk` | S | `"M#BUILD"` | SK 固定值 | — |
| `talent_nodes` | SS | **(不寫·缺省=空集)** | **已點天賦節點 id 集合**。⚠️ **DynamoDB 不能存空 SS**(Codex Stage3 合流 #2)→ 預設**不寫此屬性**、缺省視為空;第一次配點用 `ADD talent_nodes :nodeSet` 建立(冪等原子單節點)+扣點。稀疏可讀。🔒:只給結構/方向,經 DTO(戰鬥才配靜態平衡表) | 元素=節點 id 字串,如 `"biofilm_A_3"`, `"acid_B_5"`, `"center_reborn_2"` |
| `talent_points_available` | N | `0` | 可用天賦點(未花)。進化 +1 / 菌核躍動 +1。配點時原子扣(條件 ≥1)。🔒裸值(只揭「可以點了」事件,不給數字) | — |
| `talent_unlockable` | SS | **(不寫·缺省=空集)** | **數值天賦「已達門檻可習得」標記集合**(💎 數值天賦環,數值跨門檻時 `ADD` 寫入)。⚠️ 同 talent_nodes:空 SS 不寫、缺省視為空。與 nodes 分開:unlockable=可習得待點、nodes=已點。**(決策⑥點名補欄)**。🔒 | 元素=數值天賦節點 id,如 `"gem_atk_1"` |
| `skill_slots` | M | (見預設) | 已裝備技能槽(槽數受 stage 限:主動 1→4/被動 1→2/天賦欄固定 1)。裝備/替換寫。存裝備中技能 id | `{ active:L[skillId,...], passive:L[skillId,...], talent:L[skillId] }`;3 格技能佔多格由 DTO/戰鬥層驗 |
| `skill_bag` | M | `{}` | 技能包包:已學會技能→等級。學新招/升級寫(TransactWrite 扣道具)。基礎技替換不消失、一般技替換遺忘(從 bag 刪)。各技有 Lv 上限(後台平衡閥) | `{ <skillId>: { level:N } }`(key 即 skillId,不冗存 id;Codex Stage3 合流 #4) |
| `job_guild` | S | `null` | 所屬公會:`acid_smith`/`matrix_builder`/`pioneer`/`bridger`/`toxin_chemist`/`schemer`(六公會);未就職=null。轉職 TransactWrite 驗種族禁忌+階段+任務。見存疑⑩ | — |
| `job_tier` | N | `0` | 職階:0=未就職 / 1=見習(初萌菌) / 2=正職(定殖者) / 3=一轉(優勢種) / 4=二轉(關鍵種,須 Stage6)。🔒對玩家給稱號名 | — |
| `slots` | M | `{}` | **23 插槽外觀**(疊圖 1–23):每插槽存生成圖 URL + 生成時間。進化/裝備/外觀天賦寫(可 batch)。**只存 URL+ts,是 CORE 拆冷的主因**(不進熱寫)。key=插槽名(body/head_1/arm_l_1…item_r,共 23,見 section-slots) | `{ <slotName>: { url:S, generated_at:N } }`;generated_at=epoch ms(見存疑④) |
| `createdAt` | N | `Date.now()` | 建立時間(epoch ms) | — |
| `updatedAt` | N | `Date.now()` | 最後寫入(epoch ms) | — |

**23 插槽名(section-slots,疊圖順序 1–23)**:`body, tail_1, tail_2, tail_3, wing_1, wing_2, back, leg_l, leg_r, arm_l_1, arm_r_1, arm_l_2, arm_r_2, arm_l_3, arm_r_3, item_l, item_r, head_1, head_2, head_3, head_1_top, head_2_top, head_3_top`。各階段解鎖子集(Stage1=body;Stage2=+head_1;Stage3=+arm_l_1/arm_r_1/leg_l/leg_r/tail_1;Stage4=+back/wing_1/head_1_top;Stage5=+arm_l_2/arm_r_2/tail_2/wing_2;Stage6=+item_l/item_r;傳說/神話體=其餘,未來)。

---

## 🔗 寫入路徑(對齊 STAGE2 WRU 驗證)

| 操作 | 寫哪顆 | 型別/原子性 |
|---|---|---|
| 摸頭/玩耍/整理/鼓勵(每日計數+friendship/charm/mood) | M#CORE | UpdateItem,ADD+上限條件,~2 WRU |
| 餵食(satiety/hp/xp/obesity+扣背包) | M#CORE(+背包表) | **TransactWrite**(結算+扣道具原子) |
| 移動(pos/khui_last_ts) | M#CORE | UpdateItem,防菌氣超支條件 |
| A 層被動吸收(survival_hours/xp,絕不寫 friendship) | M#CORE | UpdateItem ADD,節流 |
| lazy 衰退(friendship −1 / satiety / mood / khui) | M#CORE(多為讀時算,必要才寫) | 時間戳差計算 |
| 配點(talent_points −1 + talent_nodes ADD 節點) | M#BUILD | **TransactWrite**(點數≥1+前置) |
| 學技能/升級(skill_bag + 扣道具) | M#BUILD(+背包表) | **TransactWrite** |
| 裝備/替換技能槽 | M#BUILD | UpdateItem,槽數≤stage 條件 |
| 轉職(job_guild/job_tier) | M#BUILD | **TransactWrite**(驗種族禁忌/階段/任務) |
| 碎片兌換數值(stats +1) | M#CORE.stats(+PERMANENT 碎片) | **TransactWrite**(扣碎片+加數值) |
| 進化(stage+1 + 新 slots + talent_points+1) | M#CORE + M#BUILD | 條件寫(stage 未變+門檻達標);跨顆用 Transact |
| 裝備/生成插槽(slots[x]) | M#BUILD | UpdateItem(可 batch) |

---

## 🧊 玻璃箱(DTO 轉換)清單 — 這些欄**絕不直出 API**

| 裸欄 | DTO 輸出 |
|---|---|
| `stats.{hp,atk,def,magic,spd,luck}` | 黑箱,只給戰鬥結果/外觀(HP 條可給相對格數,不給數字) |
| `charm/friendship/reputation/xp/survival_hours` | 進化提示/羈絆分帶,不給裸數字 |
| `friendship` | 分帶😄(80–100)/😊(50–79)/😐(20–49)/😤(0–19) |
| `mood` | emoji + 怪獸口吻提示文字 |
| `obesity_level` | 體態名(精實/圓潤/臃腫/病態臃腫),外觀圖變胖 |
| `satiety / sick_type` | 需求提示💬、生病狀態帶名 |
| `talent_nodes / talent_points_available / talent_unlockable` | 天賦樹「結構+方向」透明、數字不透明;只揭「可以點了」事件 |
| `khui`(由 khui_last_ts 算) | 菌氣格數(給格數可以,不給內部間隔數) |

---

## ✅ Claude(Opus)覆核結論 — 2026-07-17

**整體:通過**。Fable5 版對齊佳,並正確裁決 3 處設計冊↔sweetbot 慣例衝突(時間戳→epoch ms、friendship→0–100、hp=基礎值非戰鬥即時血)。以下為覆核補充,**不阻斷 schema,但階段9 DAO 必須遵守**:

**🔴 4 個 DynamoDB 實作地雷(Fable5 草稿未點出,補記)**:
1. **`ADD` 不能用在巢狀 Map 路徑**:`stats.*`、`daily_counts.*` 是 Map。碎片兌換數值、每日計數**不能**寫 `ADD stats.atk :1`(DynamoDB `ADD` 只作用頂層屬性)→ 必須 `SET stats.atk = if_not_exists(stats.atk,:0) + :inc`(item 層仍原子,OK)。階段9 DAO 注意。
2. **夾限(clamp)無原生**:friendship(≤100)/obesity_level(0–10)/mood(0–100)的上下限,DynamoDB 無 clamp 運算。策略二選一:①條件寫拒絕溢出(`ConditionExpression friendship < :max`)②允許溢出、DTO 層夾。階段9 明訂,建議①保資料乾淨。
3. **`skill_bag` 冗存 id**:`{<skillId>:{id:S,level:N}}` 的 value 內 `id` 與 map key 重複。可簡化為 `{<skillId>:{level:N}}`(除非未來有 per-skill metadata)。省 bytes+免不一致。
4. **`survival_hours` 語義要釘死**:若=純 wall-clock 存活,應 lazy from `born_at`(免存欄免寫);若=只在活動/A層被動時累計(非掛機白算),才需存計數欄。設計冊語義偏後者(A層被動加+離線累計)→ **保留欄位正確**,但 DAO 要明確「不是 now−born_at」。

**🟡 2 處與 Codex 二驗重疊(等 findings 合流)**:
- **存疑⑤ stats 歸 CORE vs BUILD**:我同意這是真爭議。stats 幾乎不熱寫(只碎片兌換)、卻放最熱的 CORE。若 Codex 也提,傾向移 BUILD 縮小 CORE 熱寫面(但 stats 讀極高頻、跟 CORE 一起讀反而好)→ 讀寫取捨,待 Codex #1/#5 合流拍板。
- **存疑① talent SS vs bitmap**:**我背書 Fable5 選 SS**(單節點原子 ADD 的價值 > 省 15 bytes),但這**推翻了 STAGE2 文件寫的「bitmap」**。定稿時要回頭把 STAGE2 決策②的 talent 存法改成 SS(一致性)。

**驗收方式**:對照設計冊 section-stats/growth/slots 逐欄語義、對照 sweetbot-next DAO 型別慣例、DynamoDB 表達式規則檢查——非只看「schema 長得對」。

### Codex Stage3 合流(2026-07-17,已套用到上表)
Codex 讀 `49d41a5` 草稿後 6 點,Claude vet 全採納:
1. **stats 留 CORE** ✅(與 Claude/二驗一致)
2. **talent SS + DDB 不能存空 SS** → talent_nodes/talent_unlockable 預設不寫、缺省=空、首配點 `ADD` 建立(已改)
3. **孵化改 TransactWrite 建 M#CORE+M#BUILD**(防半隻怪獸,已改孵化說明)
4. **skill_bag 簡化** `{<skillId>:{level:N}}`(已改)
5. **survival_hours 措辭釘死**=活動累計非 `now−born_at`(已改)
6. **Stage4 可草稿但先不定稿**(碰 `PERMANENT.appAccountId`/轉生保留邊界)
⚠️ 註:Codex 這輪讀的是 `49d41a5`(P0 修正**前**);**Stage2 兩個 P0 已在 `83008bd` 修好**(③exact-key TransactWrite 覆寫、④`APP#` claim item 唯一鎖),Stage4 拍板可據此。

## ➡️ 交給階段4+(定稿後)

- 本檔定稿(Codex 二驗確認 4-item 切法不變 + 上述地雷併入)後,接 `M#PROGRESS`(任務/群感/靈魂/菌圃/成就)與 `PLAYER#PERMANENT`(碎片/career_history/祖傳天賦/appAccountId)schema;identity 由 `APP#<appAccountId>` claim item 承載(非 GSI,見 STAGE2 決策④)。
- 靜態天賦定義表、技能平衡表、公會招牌技表=**設定表**(不落怪獸 item),另立設定表 schema。
