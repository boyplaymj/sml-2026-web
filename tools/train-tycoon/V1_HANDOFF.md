# 火車大亨 V1 施工單 — 全玩家世界 + 客運最小可玩

> 依 DESIGN.md §15.12 v0.3。V1 目標 = **廢 NPC、world 座標上線、玩家可對「別的玩家站」派客運、來回後給票收、收件人被動賺客流點**。貨運收貨閘留 V2、逾時+疲勞全套留 V3。
> 安全原則(照 Phase0):**先做不碰 live 的純函式引擎 / DAO / migration,單元測試 + Codex 驗過,最後才一次 wire + restart**。目前 live 仍是舊單程 NPC 模型,V1 未 wire 前完全不影響線上。
> 分工:Fable5 實作(精確自足規格)→ Opus 主線獨立驗(讀碼+跑測試+非測試值手算)→ 兩 repo commit(引擎 sweetbot-next 本地不 push / 記要進 repo DESIGN)→ Codex 驗本地。**實作 agent 一律不 commit,只寫檔+回報路徑**(避併行快照吃 WIP,見 [[feedback_sweetbot_parallel_snapshot_hazard]])。

## 現況盤點(2026-07-18 探子)
- `train-tycoon-world` 表**已建**(nodeId HASH),**但無 WorldDAO**。
- 客運 catalog **已齊**:車頭 n700s/e5/l0(kind:passenger)、客車廂 px_normal(cap60)/px_green(cap32,special.fareMult 1.8)/px_tour(cap40,special.sceneryBonus 1.5)。座位 = `capacity`。
- 引擎 `dispatch.js` **目前擋客運車頭**(`loco.kind!=='freight'&&!=='both'→fail`)→ V1 要放行客運分支。
- `profit.js` **只有貨運 freightRevenue**,無客運票收。
- `destinations` config 仍是 NPC 城(npc_minato…)→ V1 距離改由 **world 座標 pairwise** 算,不再讀 NPC 距離。
- `fatigue.js` 的 `shortTripThreshold` 目前吃 `config.destinations` 距離百分位 → 全玩家後 destinations 無距離,需改吃 **config 固定門檻或世界距離參考**(見 V1-b)。

---

## V1-a：World 空間層（純函式 + DAO + migration，不碰 live）
**檔案(sweetbot-next):**
- `model/miniGame/trainTycoon/world.js`(純函式,rng/config 注入,不碰 IO/Date.now):
  - `spawnCoord(rng, config)` → `{x,y}`,在 `config.balance.worldMap.bounds{w,h}`(新增,預設 {w:1000,h:1000})內均勻隨機;決定性(給定 rng 序列可重現)。
  - `pairDistance(a, b)` → 歐氏距離 `round(hypot(dx,dy))`(對稱、同點=0)。
  - `distanceUnits(a, b, config)` → 把 pairDistance 正規化成遊戲「距離」尺標(讓既有 `distanceRefUnit`/`distanceToMinutes`/freight distanceFactor 公式原封不動沿用);預設 = pairDistance 直接當距離(bounds 選 1000 使距離量級對齊既有 NPC 30~160)。
- `DAO/DDB/TrainTycoonWorldDAO.js`(extends DDBBaseDAO,表名讀實例):
  - `putNode(nodeId, coord, meta)` / `getNode(nodeId)` / `listNodes()`(**Scan 必分頁**,見 [[project_sweetbot_yt_bind_migration]])/ 選配 `nearest(coord, n)`。
  - nodeId = 玩家站 userId;item = `{nodeId, x, y, tier, updatedAt}`。
- `seed/backfill_world.js`(idempotent migration):掃 `train-tycoon-stations` 每個 active 站,若 world 無其 node → `spawnCoord` 落座寫入;已有則跳過。**先對現有 live 站補座標**。
- `world.test.js`:spawn 在 bounds 內 / 決定性 / 距離對稱 / 已知座標→已知距離 / listNodes 分頁。

**config 追加**:`balance.worldMap.bounds{w,h}`(現有 worldMap 已有 relocateCostTeeth/distanceMinutesPerUnit)。

## V1-b：客運票收引擎（純函式 + catalog 確認）
- `profit.js` 追加 `passengerRevenue(cars, distance, recipientTier, opts, config)`:
  ```
  票收 = Σ客車廂( 座位 capacity × 車廂 fareMult(預設1) ) × fareBase
         × 距離係數( distance / distanceRefUnit )        ［沿用 freight 同款距離係數］
         × 對方 tier 需求係數 tierRecipientMult(recipientTier, pop)  ［復用 recipientMultiplier〕
         × 短程疲勞倍率                                    ［客運吃短程疲勞;pair 疲勞待 §15.12.6-4 決定〕
  ```
  観光車 sceneryBonus 當上緣(景點線加成,Phase 先簡化為乘上或忽略,flag 待校準)。
- 客運 `travelDuration` = **來回 = 2 × 單程**(單程沿用 `profit.js` travelDuration,V1-c settle 用 returnAt=departAt+2×單程)。
- `fatigue.js shortTripThreshold` 改吃 config 固定門檻(新增 `balance.antiAbuse.shortTripFatigue.thresholdUnits`)取代讀 destinations 百分位(全玩家後無 NPC 距離樣本)。
- 客運**只吃短程疲勞**(V1 先不對客運上 pair 疲勞,§15.12.6-4);**不吃收件人月台**(§15.12.8)。
- `passenger.test.js`:票收各因子 / 綠廂 fareMult / 距離係數 / tier 係數 / 短程疲勞 / 來回時長 = 2×。

## V1-c：客運派車 + 來回結算 + 客流點 + 面板 + wire
- **選收件人**:面板列「其他玩家站」(WorldDAO.listNodes 去掉自己,可按距離排序),取代 NPC 目的地。
- **客運 dispatch**:放行客運車頭分支;planDispatch 客運變體(距離來自 world pairDistance、時長來回、無收件人月台檢查、只寄件人月台)。
- **來回結算**:transit 加 `kind='passenger'` + `returnAt`;`batchSettle` 客運筆游標綁 `returnAt`;returnAt 到 → 寄件人票收入金庫 + **收件人 flowPoints** 同一筆跨玩家 `TransactWrite`(`SET sender treasury`/`Delete transit`/`ADD recipient.flowPoints`)。
- `stations` 加 `flowPoints` 欄(建站初始 0);面板顯示金庫牙齒 + 客流點兩數字。
- **wire**:客運那條走通後,連同既有骨架一次 wire + restart(先問時機、確認 discord.js 無他 session WIP)。
- 客流點花用(設施改吃客流點)= **V1 先只累積+顯示,花用接在 V2/既有 P6 設施改造**(§15.12.6-7/8 待定),避免 V1 過肥。

---

## 待定子決策(實作時定,非阻斷;彙整自 §15.12.6)
1. 客流點取得量公式(每趟 / 每座位 × 距離 × 自己 tier)+ 校準。
2. 客運票收常數(fareBase 現 12)校準。
3. 客運要不要也上 pair 疲勞(防狂送同一大站刷票)——V1 先不上、只短程疲勞。
4. 設施改吃客流點 or 牙齒或客流皆可(傾向皆可、客流為主)+ 新站起始客流點補助——留 V2。
5. world bounds 尺標 vs 既有距離量級對齊(建議 bounds 使距離落 20~200)。
6. 遷站成本沿用 `worldMap.relocateCostTeeth`。

## 里程碑
- V1-a 純函式/DAO/migration → Codex 驗 → V1-b 客運引擎 → Codex 驗 → V1-c 派車/結算/客流點/面板 → Codex 驗 → wire + restart + 私頻 903327108451950692 實測。
