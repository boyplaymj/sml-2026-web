# 牙菌斑怪獸 · DDB 資料模型 — 階段9b:堡壘 5 表實體 schema 定案

> 交接文件 · 產出日期 2026-07-17 · 承接 [STAGE1 §1-5](./STAGE1-access-patterns.md)(堡壘存取模式)+ [STAGE9a](./STAGE9a-core-tables-ddl.md)(核心 4 表已建)
> 狀態:**草稿**(Claude 出 schema 提案,待 signoff / Codex 二驗)。
> **為何先出 schema 不出 migration**:堡壘 5 表原標「已定案」但**實體 GSI 鍵名/投影/TTL attr 從未落到屬性層級**(commit `5f6e62b` 不在本 repo)。GSI 建錯要**刪表重建**,故先把實體 schema 釘死+Codex 驗,簽核後才寫 migration(9b-ddl)。
> **範圍**:5 表 = `fortress` / `fortress-raid` / `sugar-pulse` / `fortress-guild-pool` / `fortress-ledger`。全 PAY_PER_REQUEST · ap-southeast-1。

---

## 🎯 關鍵決策:`level-index` 的 PK 用 `matchableBucket`,不用裸 `level`
STAGE1 對 `level-index` 有兩處看似衝突:line 158「PK level·SK lastActiveAt」vs line 192「pagination loop + matchableBucket」。**拍板 = `matchableBucket`**,理由三:
1. **稀疏化過濾護盾**:`matchableBucket` **只對「可被配對」的堡壘寫**(state=ACTIVE **且** 無護盾 **且** 不在 activeRaid);不合格就**不寫此屬性 → 不進 GSI**。直接解掉 STAGE1 line 158「須 pagination loop 防護盾濾光」的痛(護盾者根本不在索引裡)。
2. **格式可演進、GSI 結構不變**:v1 `matchableBucket = "L#" + level`;未來單一 level 過熱要打散 → 改成 `"L#" + level + "#" + shard`(寫入端 re-derive),**GSI schema 不用改**(裸 `level` 當 PK 就沒這彈性)。
3. **配對查詢照舊**:段位帶 [L−N, L+N] = 對每個 level 算出 `matchableBucket` 字串各 Query 一次(未來 sharding 再 ×(shard+1))。
> 代價:寫入端要維護 `matchableBucket`(合格時 SET、失格時 REMOVE)——這是**稀疏 GSI 的固有成本**,換來索引乾淨。列入 DAO 注意。

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
| TTL | ✅ `leaseExpireAt` : N(秒;殭屍場 GC,STAGE1 line 165。**存活判定比 `arriveAt`+`state`,TTL 只回收**,同 battle 律) |
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
GSI 只投影查詢方要用的欄,省儲存/WCU(每寫基表 = 每 GSI 投影一份):

| GSI | Projection | 投影欄 | 理由 |
|---|---|---|---|
| `level-index` | `INCLUDE` | `playerId, level, shieldUntil, activeRaidId`(+key `matchableBucket/lastActiveAt`) | 配對後要濾 shield/自己/activeRaid + 拿 playerId 出兵;稀疏已擋大部分護盾 |
| `guild-index` | `KEYS_ONLY` | —(key 已含 guildId/channelId + 基表 playerId) | 對帳只需「此 guild 有哪些 playerId/channelId」比對 Discord |
| `attacker-index` | `INCLUDE` | `defenderId, state`(+key) | 同目標冷卻要 Filter defenderId、看 state 是否進行中 |
| `defender-index` | `INCLUDE` | `attackerId, state, arriveAt`(+key) | 守方預警/復仇要知誰打、何時到、狀態 |
| `season-index` | `ALL` | 全欄 | 對帳導出要完整流水列(ledger 列小,ALL 可接受) |

> 全 GSI 最終一致 → 正確性靠基表條件寫(STAGE1 line 180)。稀疏投影不影響 query 正確性,只影響「查完要不要回基表補讀」。

---

## 🔴 DAO 注意(給 migration 後的 DAO 實作)
- **`matchableBucket` 維護**:堡壘任何改動 state/shield/activeRaid 的寫路徑,都要**同步 SET/REMOVE `matchableBucket`**(合格才有值)。漏維護 = 配對池髒(該進沒進/該出沒出)。
- **配對 pagination loop 仍需**(STAGE1):即使稀疏,同 bucket 內仍可能多筆 + 需濾自己/activeRaid → `queryAll()`(STAGE8 §7)。
- **raid TTL 秒/ms**:`leaseExpireAt` 秒級 10 位,其餘 ms(STAGE8 §2 一表兩制,DAO 封裝)。
- **恰好一次**:raid LOOTED(state=RESOLVED 條件)、糖潮 claim(跨2表3item TransactWrite+ClientRequestToken)——見 STAGE8 §4.3/§6.5。

---

## ➡️ 交給 Codex 二驗的收口點
1. **`level-index` = `matchableBucket`**(非裸 level)這個拍板:稀疏化+可演進的理由是否成立;`"L#"+level` 格式 + 「合格才寫」的維護成本可接受嗎。
2. **各表 PK/SK/TTL attr**:raid TTL 用 `leaseExpireAt`(對齊 STAGE1 line 165)、sugar-pulse 加 `ttl`(STAGE1 沒明寫、我補的 GC)是否合理;fortress/guild-pool 無 SK 對不對。
3. **GSI 投影**:`level-index` 的 INCLUDE 欄集是否漏(配對真正要讀的);`season-index` 用 ALL 會不會太重。
4. **AttributeDefinitions 完整性**:每個當 GSI 鍵的屬性都列進去了(DDB 建表會驗)。
5. 有沒有**第 6 條 GSI / 漏的存取模式**(跨平台 identity 未定案不在此塊,對嗎)。
6. schema 簽核後才寫 `create_yajunban_fortress_tables.js`(9b-ddl)——這順序 OK 嗎。
