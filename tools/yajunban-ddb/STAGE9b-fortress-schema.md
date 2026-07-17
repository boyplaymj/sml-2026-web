# 牙菌斑怪獸 · DDB 資料模型 — 階段9b:堡壘 5 表實體 schema 定案

> 交接文件 · 產出日期 2026-07-17 · 承接 [STAGE1 §1-5](./STAGE1-access-patterns.md)(堡壘存取模式)+ [STAGE9a](./STAGE9a-core-tables-ddl.md)(核心 4 表已建)
> 狀態:**已定稿**(Claude 提案 → Codex 二驗 4 P1+1 P2 全採納 + 尾段確認無第 6 GSI/identity 排除正確 → 使用者 signoff,2026-07-17)。migration(9b-ddl)另出。
> **為何先出 schema 不出 migration**:堡壘 5 表原標「已定案」但**實體 GSI 鍵名/投影/TTL attr 從未落到屬性層級**(commit `5f6e62b` 不在本 repo)。GSI 建錯要**刪表重建**,故先把實體 schema 釘死+Codex 驗,簽核後才寫 migration(9b-ddl)。
> **範圍**:5 表 = `fortress` / `fortress-raid` / `sugar-pulse` / `fortress-guild-pool` / `fortress-ledger`。全 PAY_PER_REQUEST · ap-southeast-1。

---

## 🎯 關鍵決策:`level-index` 的 PK 用 `matchableBucket`,不用裸 `level`
STAGE1 對 `level-index` 有兩處看似衝突:line 158「PK level·SK lastActiveAt」vs line 192「pagination loop + matchableBucket」。**拍板 = `matchableBucket`**,理由三:
1. **可稀疏化 + 格式可演進**:用泛型鍵 `matchableBucket` 而非裸 `level`,才有空間做稀疏化與 sharding。
2. **格式可演進、GSI 結構不變**:v1 `matchableBucket = "L#" + level`;未來單一 level 過熱要打散 → 改成 `"L#" + level + "#" + shard`(寫入端 re-derive),**GSI schema 不用改**(裸 `level` 當 PK 就沒這彈性)。
3. **配對查詢**:段位帶 [L−N, L+N] = 對每個 level 算出 `matchableBucket` 字串各 Query 一次(未來 sharding 再 ×(shard+1))。

### ⚠️ 稀疏條件只管「狀態型、伴隨寫入」的資格 —— 護盾不移出 GSI(Codex 9b P1-1 修正)
~~原案:合格 = ACTIVE 且無護盾 且不在 raid,失格就 REMOVE `matchableBucket`。~~ **錯**:護盾 `shieldUntil` 是**時間自然到期**,若護盾期間 REMOVE,到期那刻**沒有任何寫入**會把它 SET 回去 → 該堡壘永遠不在配對池,直到玩家下次互動。這是 **false negative**,且和 lazy/零背景 job 方向衝突(同 STAGE7b OCC idle TTL 那類陷阱)。
- **改**:`matchableBucket` 稀疏條件**只看會伴隨寫入的狀態型資格** = `state=ACTIVE` **且** `attribute_not_exists(activeRaidId)`(進/出 raid 本就有寫)。
- **護盾 = 留在 index projection、query 後用 `shieldUntil > now` 過濾**(時間態不進稀疏條件)。護盾自然到期不需任何寫入,配對方讀時即時判定。
> 代價:寫入端維護 `matchableBucket` 只在 **ACTIVE↔非ACTIVE、進↔出 raid** 這些必有寫入的轉換點 SET/REMOVE——不碰時間態,無 false negative。列入 DAO 注意。

---

## 📋 5 表實體 schema

### 1. `sweetbot-yajunban-fortress`(PK 聚合,單 item/玩家)
| 項目 | 值 |
|---|---|
| PK | `playerId` : S |
| SK | —(無;每玩家單 item,`GetItem` 讀狀態) |
| TTL | ❌(玩家持久狀態;換季走 ledger ARCHIVE + 重置,非 TTL) |
| GSI1 `level-index` | PK `matchableBucket` : S · SK `lastActiveAt` : N · **稀疏** |
| GSI2 `guild-index` | PK `guildId` : S · SK `channelId` : S |
| AttributeDefinitions | playerId(S) / matchableBucket(S) / lastActiveAt(N) / guildId(S) / channelId(S) |

### 2. `sweetbot-yajunban-fortress-raid`(PK raidId)
| 項目 | 值 |
|---|---|
| PK | `raidId` : S(ULID) |
| SK | —(無) |
| TTL | ✅ `ttl` : N(秒;**= `max(zombieLeaseEnd, cooldownUntil, revengeUntil, notifRetentionUntil)`**,Codex 9b P1-2)。**不能只設殭屍 GC**——同表還撐同目標冷卻(attacker-index)/守方預警/復仇(defender-index),太早 TTL 掉這些查詢會消失。TTL 仍只 GC、存活判定比 `arriveAt`+`state`(同 battle 律) |
| GSI1 `attacker-index` | PK `attackerId` : S · SK `departAt` : N(同目標冷卻;Filter defenderId) |
| GSI2 `defender-index` | PK `defenderId` : S · SK `arriveAt` : N(守方預警/復仇) |
| AttributeDefinitions | raidId(S) / attackerId(S) / departAt(N) / defenderId(S) / arriveAt(N) |

### 3. `sweetbot-yajunban-sugar-pulse`(PK pulseId + SK)
| 項目 | 值 |
|---|---|
| PK | `pulseId` : S |
| SK | `sk` : S(`META` / `CLAIM#<playerId>`) |
| TTL | ✅ `ttl` : N(秒;糖潮結束後 META/CLAIM 自清,零背景 job。**claim 去重/防超賣靠條件寫非 TTL**) |
| GSI | ❌(活躍 `pulseId` 指標存 `sweetbot-config`,直查 pulseId) |
| AttributeDefinitions | pulseId(S) / sk(S) |

### 4. `sweetbot-yajunban-fortress-guild-pool`(PK guildId,小表)
| 項目 | 值 |
|---|---|
| PK | `guildId` : S |
| SK | —(無;<20 筆,Scan 挑負載最低) |
| TTL | ❌ |
| GSI | ❌ |
| AttributeDefinitions | guildId(S) |

### 5. `sweetbot-yajunban-fortress-ledger`(PK playerId + SK)
| 項目 | 值 |
|---|---|
| PK | `playerId` : S |
| SK | `sk` : S(`S#<season>#EX/LOOT/ARCHIVE#<ts>#<ulid|raidId>`) |
| TTL | ❌(永久流水;可 backfill) |
| GSI1 `season-index` | PK `seasonId` : S · SK `ts` : N(賽季榜/對帳導出) |
| AttributeDefinitions | playerId(S) / sk(S) / seasonId(S) / ts(N) |

---

## 🔭 GSI 投影(Projection)提案
GSI 只投影查詢方要用的欄,省儲存/WCU(每寫基表 = 每 GSI 投影一份)。
⚠️ **`NonKeyAttributes` 只列非 key 欄**(Codex 9b P1-3):DDB 對每條 GSI **自動投影 table key + 該 index 的 key**,列進 `NonKeyAttributes` 會 ValidationException。下表把「自動可得」與「NonKeyAttributes」分開:

| GSI | Projection | 自動投影(table+index key) | NonKeyAttributes(手列) | 理由 |
|---|---|---|---|---|
| `level-index` | `INCLUDE` | playerId, matchableBucket, lastActiveAt | `level, shieldUntil, activeRaidId, state` | 配對後濾 shield(`shieldUntil>now`)/自己/activeRaid;**補 `state`**(Codex P1-4)供 GSI 最終一致/維護漏寫時防禦性過濾 |
| `guild-index` | `KEYS_ONLY` | playerId, guildId, channelId | —(無) | 對帳只需「此 guild 有哪些 playerId/channelId」比對 Discord |
| `attacker-index` | `INCLUDE` | raidId, attackerId, departAt | `defenderId, state` | 同目標冷卻 Filter defenderId、看 state 是否進行中 |
| `defender-index` | `INCLUDE` | raidId, defenderId, arriveAt | `attackerId, state` | 守方預警/復仇要知誰打、何時到(arriveAt 已是 index SK 自動投影)、狀態 |
| `season-index` | `INCLUDE`(改) | playerId, seasonId, ts | `type, delta, refId`(對帳摘要) | 見下 P2-5:改 INCLUDE 摘要,不用 ALL |

- **`season-index` 由 ALL 改 INCLUDE**(Codex 9b P2-5):`ARCHIVE` 列可能是整包季末快照,ALL 會把大 item 複製進 GSI。改投影對帳摘要欄;**完整 ARCHIVE 快照走基表 `Query PK=playerId + begins_with(sk,"S#<season>#ARCHIVE")` 讀**,不塞進 season-index。
> 全 GSI 最終一致 → 正確性靠基表條件寫(STAGE1 line 180)。投影不影響 query 正確性,只影響「查完要不要回基表補讀」。

---

## 🔴 DAO 注意(給 migration 後的 DAO 實作)
- **`matchableBucket` 維護**:只在 **state=ACTIVE↔非ACTIVE、進↔出 raid**(activeRaidId 變動)這些**必有寫入**的轉換點 SET/REMOVE(P1-1)。**不看 `shieldUntil`**(時間態,護盾在 index 內用 query 後 `shieldUntil>now` 過濾)。漏維護 = 配對池髒。
- **配對 pagination loop 仍需**(STAGE1):即使稀疏,同 bucket 內仍可能多筆 + 需濾自己/activeRaid/**護盾(`shieldUntil>now`)** → `queryAll()`(STAGE8 §7)。
- **raid TTL 秒/ms**:`ttl` 秒級 10 位 = `max(zombieLeaseEnd, cooldownUntil, revengeUntil, notifRetentionUntil)`(P1-2),其餘 ms(STAGE8 §2 一表兩制,DAO 封裝)。
- **恰好一次**:raid LOOTED(state=RESOLVED 條件)、糖潮 claim(跨2表3item TransactWrite+ClientRequestToken)——見 STAGE8 §4.3/§6.5。

---

## 🔍 Codex 二驗 findings + Claude vet 處置(2026-07-17)
Codex 二驗:順序/切分/多數 PK-SK-TTL 認可;**4 P1 + 1 P2 成立全採納**(P1-1 是我稀疏設計的真 false-negative)。

| # | Codex finding | vet | 處置 |
|---|---|---|---|
| **P1-1** | 護盾按時間到期,`matchableBucket` 因 shield REMOVE 後到期無寫入 SET 回 → false negative(與零背景 job 衝突) | ✅ 真錯(同 STAGE7b OCC 陷阱) | 稀疏條件改只看 `state=ACTIVE AND attribute_not_exists(activeRaidId)`;護盾改 index 內 query 後 `shieldUntil>now` 過濾 |
| **P1-2** | raid TTL 不能只殭屍 GC(同表撐冷卻/預警/復仇查詢,太早刪就消失) | ✅ | TTL attr 改 `ttl` = `max(zombieLeaseEnd, cooldownUntil, revengeUntil, notifRetentionUntil)` |
| **P1-3** | GSI `NonKeyAttributes` 不可列 table/index key(會 ValidationException) | ✅ | 投影表拆「自動投影 key」vs「NonKeyAttributes」,移除 playerId/arriveAt 等 key |
| **P1-4** | level-index 補 `state` 供 GSI 最終一致/漏寫時防禦性過濾 | ✅ | NonKeyAttributes 加 `state` |
| P2-5 | season-index 用 ALL,ARCHIVE 整包快照會複製進 GSI | ✅ | 改 INCLUDE 對帳摘要;完整 ARCHIVE 走基表 Query 讀 |
| P2-6 | sugar-pulse `ttl` 合理、claim 靠條件寫非 TTL 寫得對 | ✅ 背書 | 無需改 |

## ➡️ 定稿後 · 交給 9b-ddl(migration)
- Codex 尾段已補確認:`fortress`/`guild-pool` 無 SK、`raid` 單 PK raidId、`ledger` playerId/sk+season-index 皆對齊 STAGE1;**無需第 6 條 GSI**;跨平台 identity 不屬堡壘 5 表(排除正確)。
- 全 P1+P2 已改、無阻斷點 → 出 `create_yajunban_fortress_tables.js`(5 表 + 5 GSI,沿用 9a 腳本骨架 + GSI 驗證)。
