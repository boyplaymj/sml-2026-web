# 牙菌斑怪獸 · DDB 資料模型 — 階段8:DAO 層工程注意事項總彙整

> 交接文件 · 產出日期 2026-07-17 · 承接 STAGE1–7(全定稿)
> 狀態:**已定稿**(Claude 彙整 → Codex 二驗 6 P1+2 P2 全採納 → 使用者 signoff,2026-07-17)。
> **性質**:本階段**不新增資料模型決策**,只把散在階段1–7 的 DDB 工程地雷/慣例/樂觀鎖/冪等收斂成**一份給階段9(DAO 實作)照做的 checklist**。每條標來源階段供回溯。
> 對齊 repo 慣例:`sweetbot-next/DAO/DDB/*`(`DDBBaseDAO`、`TransactWriteCommand`、PuzzleRoundDAO 的 epoch ms `createdAt`)。

---

## 🧭 表清單總覽(階段9 建表對象)
| 表 | PK / SK | TTL | GSI | 來源 |
|---|---|---|---|---|
| `sweetbot-yajunban-monster` | userId / `sk`(M#CORE·M#BUILD·M#PROGRESS·PLAYER#PERMANENT·PLAYER#ACHIEVE·INV#·PVP#·APP#IDENTITY) | ❌ 永不開 | ❌ 零 | S2/3/4/6/7a |
| `sweetbot-yajunban-ledger` | userId / `sk`=`<TYPE>#ts#ulid` | ❌ | ⏸ season-index 延後 | S5a/7a |
| `sweetbot-yajunban-battle` | battleId(ULID) / — | ✅ `leaseExpireAt`(秒) | ❌ | S6 |
| `sweetbot-yajunban-world` | `<season>#<bucket>` / `OCC#`·`LOOT#` | ✅ OCC=season-end·LOOT=壽命(秒) | ❌ | S7b |
| 堡壘 5 表 | (已定案 5f6e62b) | — | 5 條(level/guild/attacker/defender/season) | S1 |

全 **PAY_PER_REQUEST · ap-southeast-1**。**SK 物理屬性名一律 `sk`(小寫)**,DAO 禁寫概念名 `SK`(S7a P2-6b)。

---

## 1️⃣ DDB 表達式限制 & 型別雷(「DDB 不讓你這樣做」清單)
階段9 最容易踩、且**單元測試最該斷言**的一組:

| # | 限制 | 正解 | 來源 |
|---|---|---|---|
| 1.1 | **`SET` 不支援乘法**(EWMA/衰退算不了) | soul.axes 6 軸 EWMA、任何乘法衰退 → **RMW 讀出→JS 算→寫回 + version 樂觀鎖** | S4 |
| 1.2 | **`ADD` 不作用於巢狀 Map 路徑**(`stats.x`/`daily_counts.x` ADD 無效) | 用 `SET stats.x = if_not_exists(stats.x,:0) + :n` | S3 覆核 |
| 1.3 | **空 StringSet 不能存**(DDB 拒空 SS) | `talent_nodes`/`talent_unlockable`/`ancestral_talents` **預設不寫欄**、缺省視空、**首次 `ADD` 建立** | S3 Codex |
| 1.4 | **屬性不存在 ≠ NULL** | 可選欄(`refId`/`asset`/`appAccountId`)不適用時**不寫屬性**,**絕不存 DDB NULL**(否則 `attribute_not_exists` 判斷失效,如首綁 APP 被拒) | S4/S5a |
| 1.5 | **無原生夾限**(DDB 不會幫你 clamp 0–100) | 上下限欄(`friendship`≤100·`obesity_level`0–10·`satiety`)→ **條件寫**擋溢位 **或** DTO 層顯示夾;累計型(xp/charm/reputation/survival_hours)只增可原子 `ADD` | S1/S3 |
| 1.6 | **`ProjectionExpression` 不省 RCU**(按投影前 item size 計) | 省讀靠**拆 item**(getStatusCore 只 GetItem M#CORE),不靠投影 | S2 P1-3 |
| 1.7 | **TransactWrite 取不到更新後值** | ledger **不存 `balanceAfter`**(交易中拿不到 SET 後結果);餘額靠重放或另讀 | S5a |
| 1.8 | **同一 TransactWrite 禁對同 key 重複操作** | transaction builder **合併**同 item 的多個 mutation 成一個 Update(見 §3.2) | S2 P1-4 |

---

## 2️⃣ 秒/毫秒 & TTL 紀律(本 repo 首批真 TTL 表,無前例格外小心)
- **一表兩制**:`battle.leaseExpireAt` / `world.ttl(OCC/LOOT)` = **秒級 10 位**(`Math.floor(ms/1000)+窗口`);**其餘所有時間戳 = epoch ms 13 位**(`Date.now()`,對齊 sweetbot-next)。⚠️ **兩表 TTL 屬性名不同**:battle=`leaseExpireAt`、world=`ttl`。
- **IaC/建表要求**(Codex S8 P2):**CreateTable 不會開 TTL** → battle/world 建好後**必須各跑一次 `UpdateTimeToLive`** 指定對的屬性名(battle→`leaseExpireAt`、world→`ttl`);**建表腳本/單測驗證 TTL 已啟用且 attr 名正確**(名字打錯 = TTL 靜默不生效、殭屍永不清)。
- **DAO 封裝秒轉換**,呼叫端只碰 ms;**單測明確斷言**「寫進 TTL 欄的是秒級」(sweetbot-next 現有 DAO 全用 ms+旗標、無真 TTL 前例,無得抄)。
- **TTL 只做 GC、絕不當鎖 / 絕不當存活判定**:
  - battle 存活 = `state=ACTIVE && now ≤ leaseExpireAt*1000`(比時間戳,不看 TTL 有沒有刪)。
  - **world OCC = discovery index、`M#CORE.pos` 才是真相**(Codex S8 P2 措辭收斂):讀相鄰先靠 OCC 找候選 → 再比 `M#CORE.pos/posVersion` 複驗;**OCC 缺失 = false negative(找不到就漏掉),故禁 idle TTL**(見下)。複驗只除 false positive。
- **`monster` 表永不開 native TTL**(裝永久玩家資料,誤寫 `ttl` 會靜默刪 = foot-gun);**只 `battle`(全 ephemeral)+ `world`(佔用/殘渣)開 TTL**。
- **`world` OCC# 禁 idle TTL**(S7b P0-1):只 season-end TTL;刪線上/靜止玩家 OCC → spatial 反查不回 = 漏相遇/偷菜/重生。
- **PVP# 關係 item 不開 native TTL**(在 monster 表)→ 改 **lazy-prune**(讀時 `now−lastEndAt>24h+grace` 視同不存在、下次覆寫)。
> 來源 S6/S7b。

---

## 3️⃣ 原子性 & TransactWrite

### 3.1 何時必用 TransactWrite(「消耗+授予」兩鍵一律原子)
餵食(扣背包+結算)、配點(扣點數+加節點)、學/升技能(扣道具+寫招)、轉職(驗+改職階)、碎片投入(扣碎片+加數值)、任務發獎(怪獸+ledger)、偷菜(雙方 item)、raid、糖潮 claim、移動搬桶(CORE+world)、孵化、轉生。**來源 S1/S4/S7b**。

### 3.2 transaction builder 合併同 item mutation(**階段9 應先寫的共用基礎設施**)
- **獨立 `YajunbanTransactionBuilder` / shared helper,不塞進薄的 `DDBBaseDAO`**(Codex S8 P1-2:base DAO 只有簡單 CRUD,硬加會難維護)。職責:合併同 key Update、統一 `ClientRequestToken` 管理、條件表達式合併、秒/ms TTL helper(§2)。
- DDB 同一 TransactWrite **禁對同一 key 兩個操作** → builder 送出前把「同一 item 的多筆 mutation」**合併成一個 Update**。
- **範例(重生結算,S6/S7b P1-4)**:結算要動 M#CORE 的 `xp/reputation/battle_deaths/釋放 activeBattleId` **又要**寫重生落點 `pos/posVersion` → **不可**巢狀呼叫 world `moveTo()` 再生第二個 M#CORE Update,builder 合併成**單一 M#CORE Update**,再加 `Delete 舊 OCC`/`Put 新 OCC`/`Update battle state`。

### 3.3 冪等 & ClientRequestToken
- 跨 item 轉資源:`TransactWrite` + **`ClientRequestToken`**(冪等)。
- **但 ClientRequestToken 不夠當業務閘**:各業務事件要各自 **stable event gate**(見 §4.3)。

### 3.4 幾個固定形狀
- **孵化** = 單一 TransactWrite 原子建 **M#CORE + M#BUILD + PLAYER#PERMANENT + PLAYER#ACHIEVE**(4 顆;M#PROGRESS 走 lazy-create),防中途失敗留半隻怪。**來源 S3 Codex/S4**。
- **轉生** = 固定 5 顆 **exact-key** TransactWrite:Put M#CORE/BUILD/PROGRESS(fresh)+ Update PLAYER#PERMANENT(繼承)+ Update PLAYER#ACHIEVE(保留)。**非** `delete begins_with`(DDB 無 atomic delete-many)。**來源 S2③/S4**。
- **流水永遠與主 item 同 TransactWrite**(ledger 列不獨立寫)。**來源 S5a**。

---

## 4️⃣ 樂觀鎖 & 冪等分層

### 4.1 樂觀鎖清單(RMW:讀值→JS 算→條件寫比對讀值→版本+1)
| 對象 | 條件欄 | 為何 | 來源 |
|---|---|---|---|
| Khui 消費(移動-1/戰鬥-2) | `khui = :readBase AND khui_last_ts = :readTs` | virtual khui 不能用 condition 直接算,SET computedKhui-n | S5b/S6 P0-3 |
| soul.axes 6 軸 | `soul.version = :read`,SET version+1 | EWMA 需 JS 乘法(§1.1) | S4 |
| world 移動 pos | `M#CORE.posVersion = :read`,SET +1 | 併發改 pos 互覆蓋;重生/賽季不扣 Khui 無天然防護 | S7b P1-3 |
| 轉生繼承 | `PLAYER#PERMANENT.generation = :readGen`(ConsistentRead 快照) | 防 lost update/跨代 race | S4/S5a |
| 堡壘內政 | `resTickAt = 舊值` | 離線產出切段 | S1 |

### 4.2 冪等分層(戰鬥/資源)
- **戰鬥同 item 冪等 = `ConditionExpression state=ACTIVE`**(L1/L2/L3 三層終結:第一次翻 RESOLVED,其餘條件失敗 no-op)——**不靠 DDB version**(version/action_id 移出 DDB 留**記憶體**,因回合零 DDB 寫,S6 P0-2)。
- **開戰防雙開 = M#CORE 開戰鎖** `activeBattleId`+`activeBattleExpireAt`(TransactWrite 條件雙方鎖不存在或已過期;過期=自癒可重開)。battle 表 `Put attribute_not_exists(battleId)` **只防 ULID 重寫**(不當防雙開,每次新 ULID)。**來源 S6 P0-1**。
- **ledger 防重放雙計 = `entryClass`**:`RESOURCE`(EXP#/FRAGMENT#,參與餘額重放)/`EVENT`(QUEST#,純稽核不重放);DAO 只提供 `replayResources()` 掃 `entryClass=RESOURCE`,杜絕誤掃 `QUEST#.rewards` 雙計。**來源 S5a**。
- **SK 唯一性不當業務冪等閘**:ledger `sk` 的 ulid 尾綴每次重試會變,唯一性只防呆、不擋重複發獎;業務冪等靠 §4.1/§4.3。**來源 S5a**。

### 4.3 業務 event gate 範例(比 ClientRequestToken 更貼業務)
- 24hr 首戰獎勵:`attribute_not_exists(lastRewardAt) OR lastRewardAt <= :cutoff`。
- 繼承通道:`claimedAt`/`rewardId` 防重複加遺產。
- APP 綁定:claim item `PK=APP#<id>` `attribute_not_exists`(唯一鎖)。
- LOOT 拾取:`attribute_exists(sk) AND ttl > :nowSec`(恰好一次+排到期未刪)。
> 來源 S4/S5a/S6/S7b。

### 4.4 條件式原子扣減/加值(**≠ RMW 樂觀鎖**,Codex S8 P1-3)
與 §4.1 不同:這類**不需先讀**,單一條件寫天然原子。DAO 另立一組 `conditional guards`:
| 對象 | 扣減 | 加值/上限 | 來源 |
|---|---|---|---|
| INV# 道具 `qty` | `SET qty = qty - :n` + `ConditionExpression qty >= :n` | 拾取 `SET qty=if_not_exists(qty,:0)+:n`(含首綁補 metadata,§ S4);**堆疊上限** `qty + :n <= :cap`(一般 999、唯一性道具 1) | S4:117 |
| shards[color]、talent_points、資源 res.x | 各自 `x >= :cost` 條件扣 | `SET res.x = if_not_exists(res.x,:0) + :amt` | S1/S4 |
- 是餵食/學技能/升級/轉生消耗/碎片投入的核心 guard;失敗 = **業務拒絕**(數量不足),歸 §「ConditionalCheckFailed 處理分類」。

---

## ⚠️ 4.6 `ConditionalCheckFailed` 處理分類(Codex S8 P1-6:不是全往上炸)
條件寫失敗**不是**一律例外。階段9 DAO 要**統一錯誤分類**成三類,各自處置:
| 類別 | 觸發 | 處置 |
|---|---|---|
| **冪等 no-op**(成功語意) | 結算 `state != ACTIVE`(已被別層先結算) | **吞掉當成功**、read-back 現值回傳,不重試不報錯 |
| **樂觀鎖衝突→重試** | `khui`/`posVersion`/`generation`/`soul.version`/`resTickAt` 條件不符(有人先寫) | **重讀最新值→重算→重送**(有限次退避);超次才炸 |
| **業務拒絕**(給玩家看的正常結果) | INV `qty` 不足、LOOT `ttl` 過期、`activeBattleId` 被占用、資源 `res.x < cost` | 轉成**業務錯誤碼**(「材料不夠」「已被搶走」「戰鬥中」),**不是系統例外** |
- TransactWrite 失敗只回一個 `TransactionCanceledException` + `CancellationReasons` 陣列 → DAO 要**解析 reasons 定位是哪個 item/哪類**,別籠統重試(樂觀鎖可重試、業務拒絕重試無意義)。

## 5️⃣ lazy compute & virtual-state 權威(零背景 job 的核心)

### 5.1 三落庫模式(每個 lazy 欄先歸類)
- **A 純讀時算·永不落庫**:心情/飽食顯示/友好顯示/Khui 現值/菌圃成熟/個性標籤 → `GetItem` 後 JS 算,不寫回。
- **B 樂觀鎖寫回**(需乘法/切段):soul.axes EWMA(soul.version)、堡壘內政(resTickAt)。
- **C 搭便車跨界才落庫**:狀態**跨閾值**(友好跨 0/生病)才寫,且**由互動/事件觸發、非每次讀觸發**。

### 5.2 virtual-state 權威判定(S5b P0,消除 worker 空窗)
- 逃跑/生病等「跨界態」= **`computeVirtualState(now)` 純推導**為權威:`virtualZeroAt = last_interaction + friendship值 × 86400000`;persisted `zero_*_since`/`sick_type` **僅快取、非唯一真相**。
- 效果:**純讀熱路徑零寫**,又不依賴背景 worker 準時跑。
- **統一單一出口**(Codex S8 P1-4):`computeVirtualState(coreItem, now)` **回傳整包 computed state**——`friendship/satiety/mood/khui` 現值 + `zeroAt/sickAt` 等衍生態。**面板讀取、死亡判定、DTO 帶名化、互動前檢查全走同一套**,禁 DAO/DTO/戰鬥入口各算一次(否則出現「面板看沒病、死亡判定說病了」的分歧)。§5.3 的 khui 現值、§5.1-A 的顯示值都併進此出口。

### 5.3 Khui 現值(S5b P0:只存 ts 不夠)
- STAGE3 已加 **`khui` 值欄**;現值 = `min(5, khui + floor((now − khui_last_ts)/間隔))`(一般 20 分、新手 Stage1–2 10 分);消費寫 `khui = 現值 − n` 且更新 `khui_last_ts`。

### 5.4 rate_mods 快取(S5b P1-6)
- 影響衰退/回復速率的 mod **compact 快取進 M#CORE**(從 BUILD 去正規化)→ `getStatusCore` 免讀 BUILD 就能算 lazy。寫路徑改 build 時同步刷快取。

---

## 6️⃣ 讀分層 & glass-box(DTO)
- **`getStatusCore`** = `GetItem M#CORE`(+ rate_mods 快取,§5.4):高頻面板/移動/照顧走這條,**禁全讀**。
- **`getFullMonster`** = `Query PK=userId`(一次拿 CORE/BUILD/PROGRESS/…):狀態卡完整檢視才用。
- **glass-box 鐵律**:所有裸值(friendship/soul/talent/群感印記/EXP)**絕不直出 API**,一律經 **DTO 帶名化**(心情→emoji、肥胖→體態名、友好→分帶、talent→只給結構/方向不給數字);每欄標 `🔒裸值·禁直出`。
> 來源 S1/S2 P1-3/S3/S5a。

---

## 🏰 6.5 堡壘 5 表 DAO checklist(Codex S8 P1-5:不只指路)
堡壘子系統(fortress/raid/sugar-pulse/guild-pool/ledger)已定案(5f6e62b),但階段9 要照做的原子/順序形狀在此列明,別漏:
- **建堡壘四段式**:`state=CREATING` **先落 DDB**(`attribute_not_exists(playerId)` 條件 Put)→ **才做 Discord side-effect**(建頻道/邀請)→ 成功再 `SET state=ACTIVE`(條件 `state=CREATING`)。**DDB 佔位一定先於外部副作用**,防孤兒頻道;逾時 CREATING 可回收。
- **內政 lazy 結算**:`resTickAt = 舊值` 樂觀鎖(§4.1),離線產出按 `upgradeDoneAt` 切段 + 12h/12h/24h 上限 + 扣兵糧。
- **raid 恰好一次**:`RESOLVED → LOOTED` **兩段式**(先標 RESOLVED 才發 loot,`ConditionExpression` 擋重複掠奪);對齊 LOOT/PVP# 恰好一次族。
- **糖潮 claim**:`CLAIM + META + fortress` **三 item 單一 TransactWrite**(恰好一次語意);大規模才 shard META(§9)。
- **guild-pool 挑伺服器**:Scan 挑 ACTIVE 負載最低 → 條件 `ADD usedChannels` + `usedChannels < capacity`。
- **GSI pagination loop**:`level-index` 段位配對**必 pagination loop**(護盾/自己/activeRaid 濾光後可能整頁空,要續撈);沿用 §7 `queryAll()`。
> 來源 S1 §1-5(150–174 行)。本檔只列 DAO 形狀,數值/流程細節仍以堡壘既定案為準。

## 7️⃣ 鍵/屬性命名 · 掃描 · 排序
- **SK 物理屬性名 `sk`**(monster+ledger 一致);DAO 一律 `ExpressionAttributeNames {"#sk":"sk"}`,**不寫概念名 `SK`**(S7a P2-6b)。
- **Query 與 Scan 都必分頁 loop**(`LastEvaluatedKey`/`ExclusiveStartKey`);單次 1MB 會截斷(踩過的雷)。⚠️ **現有 `DDBBaseDAO.query()`/`scan()` 都只回第一頁**(`return res.Items`,無 loop,已核 `sweetbot-next/DAO/DDB/DDBBaseDAO.js:60/80`)→ 階段9 **必加 `queryAll()`/`scanAll()` helper** 做 `LastEvaluatedKey` loop,ledger 重放 / world bucket / fortress GSI / 背包 Query 全靠它,別直接用薄 base 的單頁版。**來源 Codex S8 P1-1**。
- 分析彙整(種族分佈/Stage 漏斗)`FilterExpression #sk = :core`(`:core="M#CORE"`,只數核心顆免一隻怪重複計)。**來源 S7a**。
- **ts 字典序**:ledger `sk` 的 `ts` = `String(Date.now())` 13 位,到 2286 年前字典序=時間序,**不補零**(對齊 fortress-ledger)。
- **世界桶**:`gridBucket = floor(x/B)","floor(y/B)`,`B=16`;相鄰 R=1/重生 R=8 皆最壞 2×2=4 桶(**前提整數棋格**,S7b P2-6a);`B` 改動只能在賽季邊界。
- **season 必帶**:ledger 每列 `season`=v1 全域 config seasonId,缺值退 `"S_UNKNOWN"` 佔位(不略過屬性),保 season-index 免 backfill。**來源 S5a/S7a P2-6c**。

---

## 8️⃣ 依賴 & repo 慣例
- **ulid 套件 sweetbot-next 沒有**(已 grep 確認)→ 階段9 加 `ulid` npm 依賴,或退 `crypto.randomUUID()` 當尾綴(唯一性同樣成立,排序已由 `sk` 的 ts 段承擔)。**來源 S5a**。
- 時間戳一律 **epoch ms Number**(`Date.now()`),**不用 ISO**(point-log 的 ISO SK 是舊表包袱,不沿用)。
- 共通稽核欄:`createdAt`(建立,`if_not_exists` 保險)、`updatedAt`(每次寫)。
- 牙齒🦷 收付**一律走既有 `givePoint`/`sweetbot-player-point-log`**,**絕不進 yajunban-ledger**(跨產品共用幣正典)。**來源 S5a**。

---

## 9️⃣ scale 待辦(小規模先不做,量大再開;**別靜默截斷,要 log 掉了什麼**)
- 糖潮 pool 多 META 分片加總;`level-index` 用 `matchableBucket` 打散(堡壘已埋)。
- 分析 Scan 加 `Segment/TotalSegments` 平行化。
- 玩家向排行榜/賽季榜:稀疏 GSI(只投影入榜資格)/ ledger `season-index`。
- per-day DAU/留存曲線:`ACT#<yyyymmdd>` 每人每日一筆 stable-gate(MVP 先 `M#CORE.last_interaction` 快照)。
> 來源 S2 P1-7/S7a ⑪。

---

## 🔟 改 schema 的流程鐵律(meta·給後續所有階段)
> Codex 已抓 3 次同類 stale:改一個欄位/決策,只改主要那列**不夠**。
- 改欄位/決策時,`rg` 該欄位/概念**全 doc 所有出現點**逐一更新:`存疑`段 / `鐵律`段 / `覆核`段 / `寫入路徑`表 / `交給下一步`狀態文字 / **跨檔引用**。
- 改完 **grep 驗證無殘留**。翻 DRAFT→定稿也要清「本檔為草稿/待二驗」狀態文字(頁首+內文兩處)。

---

## 🔍 Codex 二驗 findings + Claude vet 處置(2026-07-17)
Codex(Neku)二驗:**無 P0**,6 P1 全屬「補齊共用基礎設施」。Claude 逐條 vet(含核 `DDBBaseDAO.js:60/80`、`STAGE4:117`):**6 條全成立、全採納**。

| # | Codex P1 finding | vet | 處置 |
|---|---|---|---|
| P1-1 | 只寫 Scan 分頁不夠,**Query 也要**;現有 `DDBBaseDAO.query()/scan()` 只回第一頁 | ✅ 已核 code | §7 加 `queryAll()/scanAll()` helper 要求 |
| P1-2 | transaction builder 該獨立 helper,別塞薄 `DDBBaseDAO` | ✅ 合理 | §3.2 改「獨立 `YajunbanTransactionBuilder`」 |
| P1-3 | INV# 漏,且是**條件式原子扣減≠RMW 樂觀鎖** | ✅ 分類正確 | 新增 §4.4 conditional guards(qty≥n + 堆疊 cap) |
| P1-4 | `computeVirtualState()` 統一出口,回 friendship/satiety/mood/khui/zeroAt/sickAt | ✅ 防分歧 | §5.2 強化為單一出口、四處共用 |
| P1-5 | 堡壘 5 表只指路不夠,要 DAO checklist | ✅ 該展開 | 新增 §6.5 堡壘 checklist(四段式/RESOLVED→LOOTED/糖潮三item/guild-pool/GSI loop) |
| P1-6 | 補 `ConditionalCheckFailed` 處理策略(no-op/重試/業務拒絕) | ✅ 真缺 | 新增 §4.6 三類錯誤分類 + 解析 CancellationReasons |
| P2-a | TTL 段補 IaC 要求(CreateTable 不開 TTL,需 `UpdateTimeToLive`+驗 attr 名;battle=`leaseExpireAt`/world=`ttl` 不同名) | ✅ 真 gotcha | §2 加 IaC/建表要求列 |
| P2-b | 「不看 OCC 是否被 TTL 刪」措辭收斂為「OCC=discovery index、M#CORE=複驗真相、缺失=false negative」 | ✅ 更精準 | §2 對應列改寫 |

## ➡️ 定稿收口
- Codex 兩輪(6 P1 + 2 P2)**全採納全收斂**;本檔定位=**不新增決策只彙整**,無一與定稿階段衝突(未回改任何上游階段)。可去 DRAFT。
