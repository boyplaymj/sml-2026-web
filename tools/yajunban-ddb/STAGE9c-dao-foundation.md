# 牙菌斑怪獸 · DDB 資料模型 — 階段9c:DAO 層基礎設施 + 逐表 DAO 計畫

> 交接文件 · 產出日期 2026-07-17 · 承接 [STAGE8](./STAGE8-dao-engineering.md)(DAO checklist)+ 9a/9b(9 表已建)
> 狀態:**✅ 全 DAO(A–E)完成上線**(sweetbot-next `b1878e6`→…→`46332ac`→`79a7df1`,均多輪 Codex 二驗收斂;共 446 測試不打 AWS)。逐表 DAO 交付完畢;剩 rebirth 5 顆組裝(A/C/D 交會點)+ 階段10 賽季歸檔。
> **程式位置**:`sweetbot-next/DAO/DDB/yajunban/`(獨立資料夾,不動共用薄 `DDBBaseDAO`)。

---

## ✅ 已完成:兩件共用基礎設施(STAGE8 §3.2/§7 指名先寫)

### 1. `YajunbanTransactionBuilder.js`
跨表原子交易建構器。核心 = **合併同 `(table,key)` 的多筆 update 成單一 Update**(DDB 禁同交易對同 key 兩操作)。API:
- `.update(table, key)` → 回 UpdateOp;**同 key 再 `.update()` 回同一顆**(merge)。鏈式:`.set(path,v)` / `.setArith(path,'+'|'-',by)`(巢狀計數 `if_not_exists`,避 ADD 不作用 Map)/ `.add(attr,v)`(頂層,拒巢狀)/ `.remove(path)` / `.conditionEquals|Gte|Exists|NotExists(...)`。
- `.put(table, item, key)` / `.delete(table, key)`(帶條件);**同 key 混用 put/delete/update → throw 衝突**。
- 結構化條件**自產 placeholder**,呼叫端不手拼 expression(免撞名)。
- `.clientRequestToken` / `static ttlFromNow(windowSec, nowMs?)` / `static ttlSeconds(ms)`(STAGE8 §2 秒級 10 位)。
- `.build()` → TransactWriteCommand input(≤100 item 上限檢查);`.commit(ddb)` 直送。
- **測試**:`_test_txn_builder.js` 19 斷言全綠(合併同 key/巢狀路徑/條件 AND/衝突 throw/TTL 10 位/跨表 3 item/空交易 throw)。

### 2. `pagination.js`(Codex S8 P1-1)
`queryAll(ddb, params)` / `scanAll(ddb, params)` 跑 `LastEvaluatedKey` loop。現有 `DDBBaseDAO.query()/scan()` 只回第一頁 → ledger 重放 / world bucket / fortress GSI / 背包 Query 一律走這個防 1MB 截斷。

> 慣例對齊:`@aws-sdk/lib-dynamodb` DocumentClient(純物件免手 marshal)、`String(userId)` 鍵強制、`TransactWriteCommand` 由呼叫端組 input(同 TrainTycoonTransitDAO)。

---

## 🗺️ 逐表 DAO 計畫(建議順序,每塊 Fable5 生成 + Opus 覆核 + Codex 二驗)

| # | DAO | 重點(對應 STAGE) | 依賴 |
|---|---|---|---|
| A | ✅ **MonsterDAO**(`caee569`) | 已做:讀分層 getStatusCore/getStatus(帶 virtual)/getFullMonster;`computeVirtualState()` 統一出口(virtualState.js,24 測試);孵化 4 顆 TransactWrite;bindAppAccount claim 唯一鎖(首綁 `conditionNotExists(appAccountId)`)/resolveAppAccount(ConsistentRead);INV# 條件扣減 consumeItem/addItem(guard n/cap)。**待補**:rebirth 5 顆(橫跨 C/D)、rebindAppAccount(Delete 舊 claim)、PVP# lazy-prune、talent SS ADD、soul EWMA RMW | builder |
| B | ✅ **LedgerDAO**(`9a2e129`) | 已做:`buildEntry` SK=`<TYPE>#ts13#uuid`(randomUUID,ulid 未裝)+ 型別分軌硬驗(RESOURCE 強制 asset+finite delta、gen 需整數、EVENT 禁 asset/delta)、`season` 必帶退 S_UNKNOWN、updatedAt=createdAt;`append`/`putTxnItem` 帶 `attribute_not_exists(userId)` 防呆;查詢 queryByType/queryByDateRange(驗 type/finite/t1≤t2)/recentByType 全走 queryAll 分頁;**`replayResources()`/`aggregateResources()`**=只認 `entryClass=RESOURCE`、EXP# 依 gen 切段、FRAGMENT# 跨代累計、忽略 QUEST#.rewards 免雙計(39 測試)。**待補**:跨表反哺 refId 互指的 fortress EX# 由 FortressDAO 發、season config 單一來源接線 | queryAll |
| C | ✅ **BattleDAO**(`b215667`) | 已做:秒/ms TTL 封裝(leaseFromNow/isBattleAlive=state==ACTIVE && now≤leaseExpireAt*1000,首個真 TTL 表)、buildBattleItem(不快照 build)、**startBattle**(單一 TransactWrite=開戰鎖+Khui RMW 扣+Put 租約;開戰鎖 OR/< 條件推應用層 pin 觀測值避 builder 限制)、**resolveBattle**(state=ACTIVE 冪等+釋放鎖 pin activeBattleId 防 stale resolve 誤刪新場+過期 expired 不結算+PvP 雙方 CORE)、**PVP# 關係**(CD 60s/24hr 首戰閘/lazy-prune/雙向寫,getPvpRelation ConsistentRead)。**Codex 兩輪二驗收斂**(4 P1:強讀/CD 反擊/過期檢查/pin expireAt;二輪背書「強讀+序列化+CD 已足不需硬條件閘」)。檔頭釘死三不變式(PvP 必走 startBattle/PVP# 強讀/PVP# 與解鎖同交易)。**待補**:敗方 pos 重生+world OCC 搬桶、INV# 掉落 cap-in-txn、isConditionalOnlyCancellation 抽共用 —— 皆依賴 D WorldDAO | builder |
| D | ✅ **WorldDAO**(`46332ac`) | 已做:B=16 分桶數學(pkFor/bucketPksForRange 笛卡兒積 + Chebyshev 過濾,R=1/R=8 邊界)、秒/ms TTL 封裝、buildOcc(驗整數 cell + **ttlSec>nowSec** 防在線玩家被 TTL 抹掉)/buildLoot、**moveTo**(跨表原子搬桶,同桶覆寫/跨桶 Delete舊+Put新,**posVersion 樂觀鎖**=重生/賽季不扣 Khui 路徑唯一防超寫閘,khui 扣沿用 RMW pin)、**verifyOccupant**(強讀 M#CORE 複驗 pos+posVersion,**只除 false positive**:prune Delete 條件 pin posVersion=occ 值不刪並發新 OCC,非阻斷)、**LOOT**(spawnLoot attribute_not_exists / pickLoot 恰好一次:條件 Delete `attribute_exists AND ttl>nowSec`[conditionGte nowSec+1]+ 同交易 INV# 獎勵,兩人搶只一人成功)、**appendOccMove**(OCC 搬桶疊進已含 M#CORE Update 的複合交易,不巢狀 moveTo,STAGE7b P1-4;moveTo 自己也走這條 DRY)。**Codex 兩輪二驗收斂**(1輪 2 P1[ttl 過期/itemN 正整數]+1 P2[R 驗證];2輪無新 finding)。builder 補 `DeleteOp.conditionGte`(19 測試無回歸)。**待補**:接回 C 敗方 pos 重生(helper 就緒待 rebirth 組裝)、INV#/LOOT reward cap-in-txn | builder, queryAll |
| E | ✅ **堡壘 5 表 DAO**(`c5ce509`→`7b947eb`→`79a7df1`) | **FortressDAO**(建堡四段式 step0/1/5 + createToken fencing 防孤兒頻道 + reclaimCreating 殭屍接手;matchableBucket 稀疏維護只狀態/raid 轉換點不看 shield;addResources 原子 ADD/spendForUpgrade 條件扣;findMatches level-index 配對護盾 query 後濾;guild-index;玩家入口全 pin state=ACTIVE)+ **RaidDAO**(launchRaid 兩筆條件寫上鎖離池;resolveRaid state=MARCHING AND arriveAt≤now;lootRaid 讀 raid 拿權威攻守身分 + state=RESOLVED 恰好一次 + 守方 res≥loss 條件扣 + LOOT 流水併同交易 5 item + 攻方重進池 state=ACTIVE;raid ttl=max 各窗口秒;attacker/defender GSI)+ **SugarPulseDAO**(claim 跨 2 表 3 item 恰好一次:CLAIM# 去重/META poolRemaining≥amount 防超賣 + endAt>now 擋過期/fortress 入帳 state=ACTIVE)+ **GuildPoolDAO**(Scan 挑負載最低 + 條件 usedChannels<capacity 屬性對屬性)+ **FortressLedgerDAO**(S#season#EX/LOOT/ARCHIVE SK + season-index + 缺 season 退 S_UNKNOWN + ARCHIVE 走基表)。**Codex 三輪二驗收斂 9 findings**(P1-3 lootRaid 身分權威/P1-7 pulse 過期 hole/P1-8 玩家入口 state=ACTIVE 皆真 bug)。194 測試 | builder, queryAll, scanAll |

> 每個 DAO 一塊小交付(<25 分),各自 test + Codex 二驗。**重生結算**橫跨 A+C+D(結算合併同 M#CORE Update + world 搬桶)是最需要 builder 的地方。

---

## ➡️ 下一步
建議從 **A. MonsterDAO** 起(最核心、其他多半依賴怪獸讀寫);`computeVirtualState()` 統一出口是關鍵(STAGE8 §5.2 P1-4)。⚠️ 寫 sweetbot-next 一律 path-scoped commit(併行快照雷 [[feedback_sweetbot_parallel_snapshot_hazard]])。
