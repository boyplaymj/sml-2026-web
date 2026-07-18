# 火車大亨 V1-c 施工單 — 客運上線（首次碰 live）

> 依 DESIGN §15.12 + V1_HANDOFF。V1-c = **目的地從 NPC 改成別的玩家站、客運全套(來回+票收+客流點)上線、wire+restart**。貨運收貨閘留 V2。
> 前兩階段已完成(V1-a world 層 e55b85f+guard 4203448 / V1-b 客運票收引擎 aa90114),本階段把它們接進 live。
> 安全:仍照「先寫+驗、最後才 wire+restart」;wire 時機要使用者定(restart 清所有頻道 session)。

## 🔑 關鍵簡化(探子確認)
- transit SK = `<arriveAt 補零>#<dispatchId>`,結算靠 `sk <= now#~` 範圍查;item 已有 `kind` 欄。
- → **客運把 transit.arriveAt 設成「回到寄件站的時間」returnAt = departAt + 2×單程 travel**,即可**沿用既有 batchSettle/commitSettle 的 arriveAt 範圍查機制,不改結算排程**。settle 只需按 `kind` 分流「算什麼收入 + 給不給客流點」。
- travelDuration 既有函式回單程分鐘 → 客運 dispatch 時 `arriveAt = now + 2×單程`(來回);貨運(V2)才要 awaiting_collect 中間態。

## 需要使用者拍板的決策
1. **V1-c 期間貨運怎麼辦?**(貨運收貨閘=V2,但 NPC 目的地要廢)
   - **建議 A(推薦)**:V1-c 期間**貨運暫時停用**(派車面板只出客運),等 V2 收貨閘做好再一起開玩家貨運。最乾淨、不留半套怪狀態。
   - 選項 B:貨運沿用「一次性抵達即結給寄件人」的舊引擎、但目的地改成玩家站(無收貨閘)→ 過渡期能玩貨運,但語意跟 v0.3 不符、V2 要再改。
2. **客流點取得量公式**(§15.12.6-1):建議 `每趟客流點 = round( 座位收 × flowRate )`,`flowRate` 入 config(暫定 0.15);離線也算。
3. **backfill migration 何時跑**:V1-c wire 前要對現有 live 站補 world 座標(`node backfill_world.js`,冪等)。建議 wire 當天一起跑。
4. **wire + restart 時機**(清 session)。

## config 改動清單(seed + DDB published/draft + FALLBACK 同步)
- `balance.worldMap.bounds = { w: 1000, h: 1000 }`(world.js 現走內建預設,正式入 config 供後台可調)。
- `balance.antiAbuse.shortTripFatigue.thresholdUnits`(全玩家世界短程門檻,暫定 ~距離量級的 25%,例 250?待校準)。
- `balance.passenger = { flowRate: 0.15 }`(客流點取得率,新)。
- **FALLBACK(TrainTycoonConfigDAO.js)補客車廂 px_normal/px_green/px_tour**(現只 DDB/seed 有、fallback 缺 → drift;見 [[project_train_tycoon]] fallback≠seed 雷)。
- `destinations`:廢 NPC 城(或保留欄位但派車不再讀它,改讀 WorldDAO)。

## 子階段(每階段驗;前三階段不碰 live,只第四階段 wire）
### V1-c-1：config + 站資料層（不碰 live）
- config seed 加上四項(bounds/thresholdUnits/passenger.flowRate)+ FALLBACK 補客車廂;灌 DDB published+draft。
- `stations` 加 `flowPoints` 欄;**開站 createOrReopen 初始化 `flowPoints:0`** + 開站時 `WorldDAO.putNode(spawnCoord)` 落座(新站上座標)。
- 驗:config 讀回四項、開站寫 flowPoints:0 + world node(先在私頻或 dry-run 驗,不動既有玩家)。

### V1-c-2：目的地改玩家站（純資料 + 面板資料源，先不 wire 行為）
- `dispatchableDests(cfg, station)` 改成讀 `WorldDAO.listNodes()` 去掉自己 → 每個候選 recipient 帶 `{userId, coord, tier}`(**tier 讀 stations 權威值、非 node.tier hint**,批量 getStation 或 listNodes 附 tier 僅供排序);距離 = `world.pairDistance(myCoord, theirCoord)`。
- 面板目的地 select 改列玩家站(顯示暱稱走 [[reference_embed_mention_nickname]] 純文字、按距離排序、cap 25)。
- 驗:純函式/DAO 層測試(給假 nodes → 正確候選+距離+排除自己)。

### V1-c-3：客運派車 + 來回結算 + 客流點（引擎接線，仍不 wire）
- `planDispatch` 加**客運分支**:放行 loco kind∈{passenger,both}、cars 為 passenger 車廂、收入用 `passengerRevenue`、`arriveAt = now + 2×單程 travel`、**不檢查收件人月台**(§15.12.8 客運豁免)、只佔寄件人一格、`kind:'passenger'`、記 `recipientId=destId`(玩家 userId)。短程疲勞照乘。
- `settle.js settleDispatch` 按 `kind` 分流:passenger → `passengerRevenue − 來回燃料(2×單程 fuel)`、`releasedSlot:1`、無 loss/collect;附帶算 `flowPointsToRecipient = round(座位收 × flowRate)`。
- `commitSettle.js` 客運那筆 TransactWrite **加第三方 item**:`Update recipient station ADD flowPoints`(跨玩家),與既有 `SET sender treasury`/`Delete transit` 同筆原子;收件人不存在(退站?)時 fail-safe 略過客流點但仍結給寄件人。
- 驗:dispatch/settle 新測試(客運票收入帳寄件人、flowPoints 入帳收件人、來回時長、跨玩家交易形狀);既有 freight 測試不破。

### V1-c-4：面板顯示 + wire + restart（碰 live）
- 面板顯示金庫牙齒 + **客流點**兩數字;派車面板依決策1(建議只出客運)。
- 跑 `backfill_world.js` 補現有站座標。
- 客流點花用(設施改吃客流點)= **不在 V1-c**,留 V2/P6 設施改造(V1-c 先只累積+顯示)。
- wire(TrainTycoon.js 已在 discord.js,無需新 wire,只需 restart 讓新碼生效)+ restart(先問時機)+ 私頻 903327108451950692 實測(開站→落座→對另一測試站派客運→等來回→結算入票收+對方得客流點)。

## 里程碑
V1-c-1 config/站層 → 驗 → V1-c-2 目的地玩家化 → 驗 → V1-c-3 客運引擎接線 → 驗 → V1-c-4 面板+backfill+restart+私頻實測 → Codex 全驗 → V2 貨運收貨閘。
