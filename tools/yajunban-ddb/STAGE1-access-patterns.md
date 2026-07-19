# 牙菌斑怪獸 · DDB 資料模型 — 階段1:存取模式盤點

> 交接文件 · 產出日期 2026-07-17
> 用途:這是 DDB 資料模型 10 階段工程的**階段1 產出**,作為階段2「單表 vs 多表決策」與階段3+ schema 實作的輸入原料。
> 產法:Fable5 子代理並行讀設計冊 `score-repo/yajunban_design.html`(22分節)萃取,Claude 收斂。
> 設計冊為 canonical;本檔為衍生分析,若與設計冊衝突以設計冊為準。

## ⚠️ 前提
- 遊戲**尚未實作**(設計冊完整、零遊戲程式碼)。本階段是「首次實作用對 DB」,非既有資料遷移 → 多數低風險。
- 資料層已拍板:**全面 DynamoDB**、PAY_PER_REQUEST、ap-southeast-1、沿用 sweetbot-next 既有基礎設施。
- 玻璃箱原則:裸值存 DDB,但所有讀路徑經 API DTO 過濾成帶名狀態(心情→emoji、肥胖→體態名),裸數值永不出 API。

---

## 🧱 實體/表 清單初判(階段2 拍板用)

| 存放區 | 內容 | 生命週期 |
|---|---|---|
| **怪獸聚合 item**(`PLAYER#/MONSTER#ACTIVE`) | 數值/成長/照顧態/心情/飽食/肥胖/23插槽/天賦bitmap/技能/職階/靈魂6軸/任務map/群感印記/菌圃/成就 | 轉生重置 |
| **玩家永久區**(`PLAYER#` 或獨立 item) | 礦物碎片/祖傳天賦/職人資歷(per-guild)/靈魂深記 | **轉生不重置** ⚠️ |
| **ledger 流水表** | EXP#/FRAGMENT#/QUEST# 前綴 SK(既有表加前綴,非新表) | 永久(可 backfill) |
| **active_battle 租約** | 戰鬥暫態不落庫,只租約 + TTL | 場結束 / TTL 回收 |
| **堡壘 5 表**(已定案) | fortress / fortress-raid / sugar-pulse / fortress-guild-pool / fortress-ledger | 賽季歸檔 |
| **跨平台 identity**(未定案,另開工序) | Discord id ↔ APP 帳號雙向 | 綁定持久 |

## 兩條架構鐵律(階段2 前先鎖)
1. **轉生重置邊界**:會重置的(怪獸本體)與永久的(碎片/職人資歷/祖傳天賦/靈魂)**必須分 item/分區**,否則轉生會清掉永久資產。
2. **玻璃箱分層**:存取層要分「裸值層 vs DTO 層」,DTO 層負責帶名狀態轉換。

---

## 1-1 · 養成核心存取模式

| 存取模式 | 觸發時機 | 讀/寫 | 需要的資料(欄位) | 頻率 | 一致性 | 批次/單筆/Txn |
|---|---|---|---|---|---|---|
| 孵化建立怪獸(4因子種族判定) | 首次孵化,結算底數100+牙齒加成+施咒×0.5+心測後抽籤 | 寫(建立) | `user_id`(PK)、`race`、`stage=1`、`seed`、`born_at`、`xp=0`、`stats`、`charm/friendship/reputation/survival_hours=0`、`obesity_level=0`、`satiety`、`mood`、`battle_deaths=0` | 低 | 強一致 | 單筆 PutItem(condition 不存在,防重複孵化) |
| 讀怪獸狀態卡(面板) | `/牙菌斑`、`/狀態`、按鈕翻頁 | 讀 | 整個 `MONSTER#ACTIVE` item(API 過濾成帶名 DTO) | 高 | 最終一致 | 單筆 GetItem |
| 進化門檻檢查 | 開面板/照顧後判斷(天數/EXP/存活/魅力/友好/聲望全達標) | 讀 | `stage`、`xp`、`survival_hours`、`charm`、`friendship`、`reputation`、`born_at` | 高 | 最終一致 | 單筆 GetItem(與狀態卡共用) |
| 升階寫入(六階進化) | 全門檻達標且確認進化(選天賦、解鎖插槽/農場) | 寫 | `stage+1`、新 `slots`、天賦、(Stage4 開農場) | 低 | 強一致 | 單筆 UpdateItem(condition stage 未變+門檻達標) |
| 摸頭 | 面板按鈕(每日 3 次) | 寫 | `friendship`(+小)、`mood`、當日計數/時間戳、`last_interaction` | 高 | 強一致 | 單筆 UpdateItem(ADD+check 上限) |
| 餵食(結算) | 面板🍬下拉選背包食物(依飽食度) | 寫 | `satiety`、`friendship`(+中)、`mood`、`hp`、`xp`、`stats`、`obesity_level`(機率+)、pH、扣背包食物 | 高 | 強一致 | **TransactWrite**(怪獸結算+背包扣道具原子) |
| 玩耍 | 面板按鈕(每日 1 次) | 寫 | `friendship`(+中)、`charm`(+小)、`mood`、當日計數 | 中 | 強一致 | 單筆 UpdateItem(check 上限) |
| 整理 | 面板按鈕(每日 1 次) | 寫 | `charm`(+中)、`mood`、當日計數 | 中 | 強一致 | 單筆 UpdateItem(check 上限) |
| 鼓勵 | 面板按鈕(每日 3 次,特殊對話) | 寫 | `friendship`(+小)、`mood`、當日計數 | 高 | 強一致 | 單筆 UpdateItem(check 上限) |
| 心情計算 | 讀狀態卡時即時算(只回 emoji) | 讀(lazy) | `satiety`、`obesity_level`、生病旗標、`friendship`、`last_interaction`(不落庫) | 高 | 最終一致 | 單筆 GetItem(讀時算) |
| 友好度每日衰退(-1) | 綁「多久沒開面板」,讀時惰性結算 | 寫(或讀時算) | `friendship`、`last_interaction`(時間戳差) | 中 | 強一致 | 單筆 UpdateItem(lazy) |
| 飽食度自然下降 | 隨時間下降,讀時算 | 讀(lazy)/寫 | `satiety`、`last_fed_at` | 高 | 最終一致 | 讀時算 |
| 肥胖收支結算 | 餵糖(+)/走格子·發酵·清潔(-)/自然代謝 | 寫 | `obesity_level`(0–10)、來源事件、種族/性狀修正 | 中 | 強一致 | 單筆 UpdateItem(ADD) |
| 生病判定(飢餓型/臃腫型) | 飽食見底 或 肥胖 9–10,讀時檢查 | 讀+寫 | `satiety`、`obesity_level`、生病旗標、`hp`、卡進化門檻 | 中 | 強一致 | 單筆 UpdateItem |
| 死亡/逃跑判定 | 生病未處理、戰死3、友好=0持續7天、聲望=0持續7天、遺棄 | 讀+寫 | `battle_deaths`、`zero_friendship_since`、`zero_reputation_since`、生病旗標、`obesity_level` | 中 | 強一致 | Txn(刪 MONSTER#ACTIVE + 機率寫 NPC) |
| 友好/聲望歸零時間戳維護 | 友好或聲望降到 0 | 寫 | `zero_friendship_since`、`zero_reputation_since` | 中 | 強一致 | 單筆 UpdateItem |
| A 層被動吸收 | Discord 發言/reaction/PvE勝(遞減+每日軟上限) | 寫 | `survival_hours`、`xp`(+微)、菌氣、pH;**絕不寫 friendship** | 高 | 最終一致 | 單筆 UpdateItem(ADD,節流) |
| B 情境呼喚判定 | 久沒開面板/pH太酸/快生病低機率觸發 | 讀 | `last_interaction`、`satiety`、`obesity_level`、pH | 中 | 最終一致 | 單筆 GetItem(worker 掃) |

**設計影響**:餵食/升階/死亡轉NPC 需原子或條件寫防重複結算;心情/飽食/友好衰退全 lazy compute;每日次數靠時間戳/當日計數(餵食例外用飽食度當閥);累計型(EXP/魅力/存活/聲望)用原子 ADD 可最終一致,狀態型(友好/飽食/肥胖/battle_deaths)需強一致+條件檢查。
**⚠️ schema 缺口**:設計冊 schema 卡目前只列 `obesity_level`,`satiety`/`mood`/每日計數/`last_fed_at` 需在階段3 補欄。

---

## 1-2 · Build 系統(天賦/技能/職業/插槽/數值)

| 存取模式 | 觸發時機 | 讀/寫 | 需要的資料 | 頻率 | 一致性 | 批次/單筆/Txn |
|---|---|---|---|---|---|---|
| 讀天賦樹配置(已點+可點) | 開天賦樹介面/進化後 | 讀 | `talent_points_available`、`talent_nodes`(bitmap/set)、`stage`、`soul_behavior`、`career_history` | 中 | 最終一致 | 單筆 |
| 讀天賦樹結構定義(100格盤) | 渲染介面 | 讀 | 靜態天賦定義表(節點id/階層/雙閘門/前置/門檻) | 中 | 最終一致 | 設定表(快取) |
| 配點(消耗天賦點解鎖節點) | 玩家點天賦 | 寫 | `talent_points_available`(原子扣)、`talent_nodes`(加節點) | 中 | 強一致 | **單一 conditional UpdateItem**(兩鍵同 M#BUILD:ADD 節點+扣點,條件 點數≥cost+前置 contains+未持有;非跨顆故免 Transact,GROWTH-talent-DRAFT D1) |
| 雙閘門檢查(階段深度+靈魂軟親和) | 配點前驗證 | 讀 | `stage`、`soul_behavior`、目標節點階層/親和 | 中 | 強一致 | 單筆(隨配點條件) |
| 進化/菌核躍動給天賦點 | 進化 or 隱藏 EXP 達標 | 寫 | `talent_points_available`(ADD +1)、`stage` | 低 | 強一致 | 單筆(ADD) |
| 效果套用(戰鬥讀被動天賦) | 每場戰鬥結算 | 讀 | `talent_nodes`+靜態平衡表 | 高 | 最終一致 | 單筆+設定表 |
| 💎數值天賦解鎖檢查 | 碎片兌換數值後/戰鬥結算 | 讀 | `stats`(裸值)、數值天賦門檻 | 中 | 最終一致 | 單筆 |
| 💎數值天賦標記可習得 | 數值跨門檻瞬間 | 寫 | `talent_unlockable`、解鎖事件 | 低 | 最終一致 | 單筆 |
| 讀技能配置(槽+包包) | 開技能面板/戰鬥載入 | 讀 | `skill_slots`、`skill_bag`(技能+Lv) | 高 | 最終一致 | 單筆 |
| 學習新招 | 達條件/用技能書 | 寫 | `skill_bag`、道具消耗、遺忘替換 | 中 | 強一致 | **TransactWrite**(扣道具+寫技能) |
| 裝備/替換技能槽 | 玩家換技能 | 寫 | `skill_slots`、`skill_bag` | 中 | 強一致 | 單筆(條件式,槽數≤stage) |
| 技能升級 | 找 NPC 消耗道具 | 寫 | `skill_bag[skill].level`、道具消耗 | 中 | 強一致 | **TransactWrite** |
| 連招矩陣讀取(有向前置→引爆) | 戰鬥出招結算 | 讀 | 靜態連招加乘矩陣、當前敵人狀態印記 | 高 | 最終一致 | 設定表+戰鬥狀態 |
| 轉職 | 完成轉職任務 | 寫 | `job_guild`、`job_tier`、`stage`(二轉須S6)、禁忌種族檢查 | 低 | 強一致 | **TransactWrite**(驗種族/階段/任務+改職階) |
| 讀職業配置 | 面板/戰鬥/圖像 | 讀 | `job_guild`、`job_tier`、職業被動 | 中 | 最終一致 | 單筆 |
| 職人資歷跨世代讀 | 轉職失敗率/加速/起始階算 | 讀 | `career_history[guild]`(per-guild 永久) | 中 | 最終一致 | 單筆(永久 item) |
| 職人資歷跨世代寫(+1) | 芽孢輪迴轉生 | 寫 | `career_history[guild]`(ADD +1) | 低 | 強一致 | 單筆(ADD,**跨世代不重置**) |
| 讀 23 插槽(渲染疊圖) | 進化/面板/圖像 | 讀 | `slots`(每插槽 `{url, generated_at}`,疊圖1–23) | 高 | 最終一致 | 單筆 |
| 裝備/卸下插槽 | 解鎖插槽/外觀天賦/進化 | 寫 | `slots[slot_id]`、階段解鎖清單 | 中 | 最終一致 | 單筆(可 batch) |
| 數值黑箱讀 | 戰鬥/面板/門檻 | 讀 | `stats{hp,atk,def,magic,spd,luck}`、charm/friendship/reputation | 高 | 最終一致 | 單筆 |
| 礦物碎片投入(同色→數值+1) | 玩家兌換 | 寫 | `shards[color]`(原子扣)、`stats`(ADD +1)、遞增成本 | 中 | 強一致 | **TransactWrite**(扣碎片+加數值) |
| 碎片跨轉生保留累加 | 轉生結算 | 寫 | `shards`、數值基底(**永久不重置**) | 低 | 強一致 | **TransactWrite** |

**設計影響**:~145 天賦節點用 bitmap/整數位元/string set 壓進**單一 `talent_nodes` 欄**(已點集合稀疏,避免 145 sub-item 讀放大);配點/碎片/道具學習升級都是「消耗+授予」兩鍵→必須 TransactWrite+條件;**職人資歷/碎片/祖傳天賦放轉生不重置的永久區**(公會僅6,map 足夠);23 插槽只存 URL+時間戳,單 map 承載,進化多插槽一次寫。

---

## 1-3 · 戰鬥系統 + 棋盤地圖

> ⚠️ 設計冊實際:Khui 回復 一般每 20 分 +1、新手 Stage1–2 每 10 分 +1(×2);移動消耗 1、戰鬥消耗 2。(先前口頭「15分」為誤,以此為準)

| 存取模式 | 觸發時機 | 讀/寫 | 需要的資料 | 頻率 | 一致性 | 批次/單筆/Txn |
|---|---|---|---|---|---|---|
| 開戰寫 active_battle 租約 | 按攻擊/開始戰鬥 | 寫 | `battle_id`、`version`、`action_id`、`leaseExpireAt`(TTL)、雙方 `PLAYER#`、`state` | 中 | 強一致(`attribute_not_exists`/比時間戳) | 單筆 PutItem+Condition |
| 判斷「這場還活著嗎」 | 任何互動/重連/重觸發 | 讀 | `leaseExpireAt`、`arriveAt`、`state`(比時間戳,不靠 TTL 是否刪) | 中 | 強一致 | 單筆 GetItem |
| 讀怪獸戰鬥數值 | 開戰載入雙方 build | 讀 | `stats`、`race`、`stage`、技能/天賦、`battle_deaths` | 中 | 最終一致 | 單筆 GetItem |
| 戰鬥暫態(HP/pH/狀態/回合) | 每回合 8 步管線 | **不落庫** | 全放 bot 記憶體(asyncio/View),edit_message 翻頁 | 高 | — | 不落庫 |
| 戰鬥結束 1 次結算寫入 | KO/逃跑/AFK確定性/硬上限 | 寫 | 一次 UpdateItem 塞全部:`xp`、`reputation`、掉落、`last_interaction`、`battle_deaths`;同筆釋放租約 | 中 | 強一致(`version`/`action_id` 冪等) | 單筆 UpdateItem(PvE≈1–2寫、PvP≈2–3寫) |
| permadeath 計數 | 結算判戰死 | 寫 | `battle_deaths`(上限3→永久死亡) | 低 | 強一致 | 併入結算 |
| 冪等:同場不可重複結算 | AFK/超時/重連多觸發 | 寫 | `battle_id`+`version`+`action_id`;跨 item 轉資源用 `ClientRequestToken` | 中 | 強一致 | 單筆;跨item用 TransactWrite |
| 讀玩家位置/Khui | 移動、/地圖、PvP相遇 | 讀 | 座標、`khui_last_ts`(讀時算現值) | 高 | 強一致 | 單筆 GetItem |
| 移動(消耗菌氣) | 走一格/吃殘渣 | 寫 | 座標、`khui_last_ts`(扣1、記時間戳;戰鬥扣2) | 高 | 強一致(防超支) | 單筆 UpdateItem |
| 菌氣 Khui 回復 | 週期回復(20分/新手10分 +1) | **不寫庫** | 只存 `khui_last_ts`,讀時 `(now−ts)/間隔` 算,上限5 | 高 | — | 零週期寫入 |
| PvP 相遇觸發 | 相鄰格敵人按攻擊 | 讀+寫 | 雙方座標、PvP CD(1分)、同對24hr限制 | 中 | 強一致 | 讀+單筆(接開戰租約) |
| 剩菜殘渣/動態地圖元素 | 吃殘渣、殘渣沖刷消失 | 讀+寫 | 格子物件、消耗Khui取食材、地形快取 | 中 | 最終一致 | 單筆 |

**設計影響**:租約 TTL 只做垃圾回收(可延遲48h)、絕不當即時鎖,存活判斷一律比 `leaseExpireAt`/`arriveAt`+`state`;冪等雙層(戰鬥 `battle_id+version+action_id`,跨item轉資源 TransactWrite+ClientRequestToken);菌氣時間戳 lazy 算=寫入預算最大省點;戰鬥暫態全放記憶體只結束寫1次(合併單筆<1KB);世界主鍵 `PLAYER#/MONSTER#ACTIVE` 不帶 server_id,跨服才需 GSI,世界狀態別塞玩家大 item。

---

## 1-4 · 內容循環(任務/菌圃/成就/靈魂/賽季/轉生)

| 存取模式 | 觸發時機 | 讀/寫 | 需要的資料 | 頻率 | 一致性 | 批次/單筆/Txn |
|---|---|---|---|---|---|---|
| 任務:接任務 | 面板領取 | 寫 | 怪獸 `quests` map(新增進行中) | 中 | 強一致 | 單筆 |
| 任務進度更新 | 完成子目標 | 寫 | `quests` map progress | 高 | 最終一致 | 單筆(ADD) |
| 日常/週常刷新判定 | 讀任務面板時 | 讀→寫 | `quests` map+時間戳(跨日/週重置) lazy | 中 | 強一致 | 單筆 |
| 任務完成獎勵發放 | 繳交任務 | 寫 | 怪獸(EXP/魅力/聲望/碎片素/道具)+ledger `QUEST#` | 中 | 強一致 | **TransactWrite** |
| 群感隱藏印記累積 | 每解一小任務 | 寫 | `quests` map 各主題群感印記(暗中累積、軟上限) | 高 | 最終一致 | 單筆(ADD) |
| 群感閾值檢查→支線浮現 | 讀面板時 lazy 比對 | 讀→寫 | 印記 vs 隱藏閾值/組合→特殊支線旗標 | 中 | 最終一致 | 單筆 |
| 繼承通道寫入 | 群感特殊支線完成 | 寫 | 跨世代遺產(祖傳天賦/世代印記/芽孢機率/靈魂深記) | 低 | 強一致 | 單筆/Txn |
| 菌圃:離線生長成熟計算 | 上線讀菌圃 | 讀 | 各畦 `plantedAt`+成熟時間+pH lazy | 高 | 最終一致 | 單筆 |
| 收成 | `!收成` | 寫 | 畦位清空+產出入背包/ledger | 中 | 強一致 | 單筆/Txn |
| 偷菜(棋格經過) | 經過對方棋格 | 讀→寫 | 目標菌圃(僅成熟)、防禦、限偷1畦 | 中 | 強一致 | **TransactWrite**(雙方 item) |
| 偷菜(接吻·共食) | 接觸 | 讀→寫 | 同上低頻管道 | 低 | 強一致 | TransactWrite |
| 防禦布防/毒孢陷阱 | 離線前布防 | 寫 | 畦位防禦欄(限時)、毒孢DoT | 低 | 強一致 | 單筆 |
| 成就:解鎖檢查 | 偷菜/破秘寶/隨堂考觸發 | 讀→寫 | 成就進度+已解鎖集合 | 中 | 最終一致 | 單筆(ADD) |
| 成就里程碑換獎 | 累積到里程碑 | 寫 | 成就點→稱號/圖鑑/外觀,極少發碎片/天賦點 | 低 | 強一致 | 單筆/Txn |
| 成就寫入靈魂 | 解鎖成就 | 寫 | 怪獸 `soul` map | 低 | 最終一致 | 單筆 |
| 靈魂:6行為軸滑動更新 | 每次互動/戰鬥/照顧/任務 | 寫 | `soul` map 6軸(近期加權滑動 lazy) | 高 | 最終一致 | 單筆 |
| 個性標籤產生 | 讀 soul 時 lazy 結晶 | 讀→寫 | 6軸偏向→帶名個性+漂移慣性 | 中 | 最終一致 | 單筆 |
| 管理員覆寫 | 後台(活動/客訴/彩蛋) | 寫 | `soul` 標籤/劇情記憶/傳奇人格 | 低 | 強一致 | 單筆 |
| 賽季:換季歸檔軟重置 | 破台換季 | 寫 | 世界/地圖歸檔;怪獸本體完整保留;道具轉資源;位置重生 | 低 | 強一致 | 批次/TransactWrite |
| 轉生:permadeath 後輪迴 | 自主芽孢輪迴 | 寫 | 重置當代(友好歸零/裝備轉資源);生成3株候選芽孢 | 低 | 強一致 | **TransactWrite** |
| 礦物碎片/祖傳天賦繼承 | 完成轉生 | 讀→寫 | 碎片**跨轉生保留累加**;1祖傳天賦永久點亮;靈魂加深 | 低 | 強一致 | TransactWrite |

**設計影響**:任務/群感印記/靈魂6軸/菌圃/成就**全併進怪獸聚合 item 加欄位**(免新表、不吃成本四件套);任務歷史走 ledger 加 `QUEST#` 前綴;lazy compute 大量(刷新/群感閾值/菌圃成熟/靈魂滑動);群感裸數字不出面板(玻璃箱);**賽季歸檔(保留怪獸)vs 轉生(保留碎片/天賦/靈魂)是兩套正交生命週期**。

---

## 1-5 · 堡壘 5 表 + 跨平台 + 後台

> 堡壘 5 表已定案:`sweetbot-yajunban-fortress` / `-fortress-raid` / `-sugar-pulse` / `-fortress-guild-pool` / `-fortress-ledger`(全 PAY_PER_REQUEST / ap-southeast-1)

| 存取模式 | 觸發時機 | 讀/寫 | 需要的資料 | 頻率 | 一致性 | 批次/單筆/Txn |
|---|---|---|---|---|---|---|
| **fortress**(PK playerId 聚合) 開面板讀狀態 | 任何操作前 | 讀 | res map+resTickAt、buildings map、troops、breedQueue、level、shieldUntil、activeRaidId | 高 | 最終一致(樂觀鎖保護) | 單筆 GetItem |
| 建堡壘 step0 冪等檢查 | `!建堡壘` | 讀 | state(ACTIVE→回舊 inviteUrl;CREATING+createdAt 判逾時) | 低 | 強一致 | 單筆 GetItem |
| 建堡壘 step1 條件式佔位(先落庫) | step0 判無/逾時 | 寫 | Put `attribute_not_exists(playerId)`,state=CREATING+createdAt,fortressId="F#"+playerId | 低 | 強一致(條件寫) | 單筆條件 Put |
| 建堡壘 step5 落定 ACTIVE | 頻道+邀請建好 | 寫 | SET state=ACTIVE,guildId,channelId,inviteUrl,panelMessageId,condition state=CREATING | 低 | 強一致(條件寫) | 單筆條件 Update |
| 內政 lazy 結算落庫 | 讀時發現可落定變動 | 寫 | 新 res+新 resTickAt;樂觀鎖 `resTickAt=舊值`;離線產出按 upgradeDoneAt 切段+12h/12h/24h上限+扣兵糧 | 高 | 強一致(樂觀鎖) | 單筆條件 Update |
| 資源入帳(產出/掠奪/糖潮) | 各入帳事件 | 寫 | 原子 `SET res.x=if_not_exists(res.x,:0)+:amt` | 高 | 原子 ADD | 單筆 |
| 資源花費+升級開工 | 建築/堡壘升級 | 寫 | 條件 `res.x>=:cost`+`attribute_not_exists(upgradeDoneAt)` | 中 | 強一致(條件寫) | 單筆(天然原子) |
| 繁殖兵 | 繁殖按鈕 | 寫 | 扣🍬🧱+push breedQueue{type,qty,doneAt} | 中 | 強一致(條件寫) | 單筆 |
| 段位配對找目標 | 出征選目標 | 讀 | Query `level-index`(PK level·SK lastActiveAt),level∈[L−N,L+N] 各查+Filter 濾 shield/自己/activeRaid;**須 pagination loop 防護盾濾光**;sparse matchableBucket 旋鈕 | 中 | 最終一致(GSI) | Query ×(2N+1)+分頁 |
| 列某 guild 全部堡壘 | 對帳/回收/換季 | 讀 | Query `guild-index`(PK guildId·SK channelId) | 低 | 最終一致(GSI) | Query |
| **fortress-raid**(PK raidId=ULID) 出兵建場 | 出征 | 寫 | raid Put `attribute_not_exists`+fortress 條件 `attribute_not_exists(activeRaidId)` | 中 | 強一致(條件寫) | 兩筆條件寫 |
| 同目標冷卻檢查 | 出兵前 | 讀 | Query `attacker-index`(attackerId·departAt)+Filter defenderId | 中 | 最終一致(GSI) | Query |
| 守方預警/被打紀錄/復仇權 | 感應塔 ping/面板 | 讀 | Query `defender-index`(defenderId·arriveAt) | 中 | 最終一致(GSI) | Query |
| 結算① RESOLVED(純算·自足) | arriveAt 到點 | 寫 | condition `state=MARCHING`→只寫 raid result(🦴永不出 loot) | 中 | 強一致(冪等) | 單筆條件 Update |
| 結算② LOOTED(轉移·原子) | ① 完成後 | 寫 | **單筆 TransactWrite**(condition state=RESOLVED):raid→LOOTED+攻守 res+清 activeRaidId+shield/revenge+ledger,共3–5 item;**恰轉一次** | 中 | 交易原子 | TransactWrite |
| 殭屍場回收 | 崩潰未結算 | 讀+寫 | 比 leaseExpireAt/arriveAt+state(TTL 只回收) | 低 | 強一致(條件寫) | 單筆 |
| **sugar-pulse** 開潮/建池 | 定期+隨機爆發→role ping/APP push | 寫 | META item;活躍 pulseId 指標寫 `sweetbot-config` | 低 | — | 單筆 |
| 讀活躍 pulseId+池狀態 | 搶鈕前 | 讀 | config 指標+META | 潮中高 | 最終一致 | 單筆 |
| 糖潮 claim | 點`[🍬搶!]` | 寫 | **單筆 TransactWrite+ClientRequestToken 跨2表3item**:CLAIM ADD+Cap+去重、META poolRemaining−+防超賣、fortress res.sugar ADD;任一失敗 rollback 無補償 | 高(爆發) | 交易原子 | TransactWrite |
| **fortress-guild-pool**(PK guildId,<20筆) 挑伺服器 | 建堡壘 step2 | 讀+寫 | Scan 挑 ACTIVE 負載最低→條件 `ADD usedChannels`+`usedChannels<capacity` | 低 | 強一致(條件寫) | Scan+單筆 |
| 失敗回滾/回收頻道 | step2–5失敗/棄坑/換季 | 寫 | `ADD usedChannels :-1` | 低 | 原子 ADD | 單筆 |
| **fortress-ledger** 反哺兌換流水 | 碎片素→碎片等 | 寫 | Put SK `S#season#EX#ts#ulid` | 中 | — | 單筆 |
| 掠奪流水 | LOOTED 時 | 寫 | SK `S#season#LOOT#ts#raidId` | 中 | 同交易/best-effort | Transact/單筆 |
| 季末快照歸檔+重置 | 換季 | 讀+寫 | Put `S#season#ARCHIVE`(整包快照)→重置本體+釋放頻道(usedChannels−1) | 低 | — | 逐玩家批次 |
| 賽季榜/整季統計/對帳導出 | 經濟後台/季末 | 讀 | Query `season-index`(seasonId·ts) | 低 | 最終一致(GSI) | Query 分頁 |
| **跨平台 identity**(未定案) Discord↔APP 解析 | 每次 API 登入驗證 | 讀 | 統一 identity→playerId 雙向(table/PK/SK 待另開工序) | 高 | 強一致(綁定時) | 單筆 GetItem |
| **後台** 成本統計 dashboard | 管理頁 | 讀 | 月費試算+DAU/日成本/種族分佈/Stage漏斗/系統活躍/留存(接後端改讀實際) | 低 | 最終一致 | 聚合/批次 |
| 玩家管理/後台事件流 | 客訴補償/活動注入 | 寫+讀 | 後台→API→寫 DDB game event→bot/worker 讀(跳過 Firestore 中轉) | 低 | — | 單筆 |
| 對帳工具(P1/Codex #6) | 定期/手動 | 讀+寫 | 掃 `guild-index`+拉 Discord 現存頻道比對→修池 usedChannels/回收殭屍 CREATING/標孤兒頻道 | 低 | 最終一致讀+條件寫 | Query+逐筆修正 |

**設計影響**:GSI 共 5 條(`level-index`必須 pagination loop、`guild-index`、raid `attacker/defender-index`、ledger `season-index`),GSI 一律最終一致故正確性靠基表條件寫;高頻計數零背景 job(時間戳+lazy+resTickAt樂觀鎖+原子ADD,離線升級中途按 upgradeDoneAt 切段);四段式建堡「DDB 佔位一定先於 Discord side-effect」防孤兒;恰好一次語意兩處(raid LOOTED、糖潮 claim);TTL 只清理不鎖。

---

## 🔥 跨系統收斂(階段2 決策原料)

### 必須原子(TransactWrite / 條件寫)— 11+ 處
餵食(扣道具+怪獸)、天賦配點、碎片兌換數值、道具學習、技能升級、轉職、偷菜(雙方item)、任務發獎、轉生打包、死亡轉NPC、**raid 結算 LOOTED**(3–5 item)、**糖潮 claim**(跨2表3item+ClientRequestToken)、建堡壘四段式條件寫。

### Lazy compute 零背景 job(時間戳讀時算)
心情、飽食下降、友好每日-1、菌氣 Khui、菌圃成熟、日常/週常刷新、群感閾值、靈魂6軸滑動、堡壘離線產能(resTickAt 樂觀鎖)。**全站鐵律**。

### GSI 需求(5+1)
`level-index`(段位配對,pagination loop+matchableBucket)、`guild-index`(對帳)、raid `attacker-index`、raid `defender-index`、ledger `season-index`、+ 跨平台 identity 索引。

### 高頻熱點(要快取)
最高頻讀=**讀怪獸狀態卡**(開面板/翻頁);高頻寫=靈魂6軸、任務進度、A層被動吸收、糖潮claim(爆發)、堡壘資源入帳。

### 冪等機制
戰鬥=`battle_id+version+action_id`;跨 item 轉資源=TransactWrite+`ClientRequestToken`;建堡壘=`attribute_not_exists` 條件寫;raid=兩段式(RESOLVED 純算→LOOTED 轉移)。

---

## ➡️ 交給階段2 拍板的問題
1. **單表 vs 多表**:怪獸聚合走單一大 item?ledger/battle 租約/堡壘5表獨立(已定)?玩家永久區獨立 item 或塞玩家 item map?
2. **轉生重置邊界的物理切法**:`MONSTER#ACTIVE`(重置)vs `PLAYER#PERMANENT`(碎片/職人資歷/祖傳天賦/靈魂深記)如何分 SK/item。
3. **跨平台 identity 表**設計(目前「另開工序」待辦)。
4. 怪獸大 item 是否逼近 400KB item 上限(23插槽URL+145天賦+靈魂+任務+菌圃+成就)→ 需估算,可能要拆熱/冷欄位。
5. `satiety`/`mood`/每日計數/`last_fed_at` 等 schema 缺欄補齊(階段3 併)。

## 💰 成本控管待補
交 Fable5 前,設計冊 section-data 需補一段「## 💰 成本控管」連回 `tools/COST_CONTROL.md`:牙菌斑=多開 DDB 表(PAY_PER_REQUEST 邊際成本)、對話語氣走預寫模板庫**免 LLM**、無外部付費 API → 落成本控管綠區,但規則要求明文此段。
