# 牙菌斑怪獸 · DDB 資料模型 — 階段2:單表 vs 多表決策 + ERD

> 交接文件 · 產出日期 2026-07-17 · 承接 [STAGE1-access-patterns.md](./STAGE1-access-patterns.md)
> 狀態:**已拍板**(Claude 出提案 → 使用者 signoff 全採,2026-07-17)。可選 Codex 二驗待定。
> 用途:階段3(怪獸聚合 item 主 schema)起的實作藍圖。

## 📏 前置:怪獸聚合 item 大小估算(解 400KB 疑慮)

| 欄位群 | 內容 | 估算 |
|---|---|---|
| 基本+核心數值 | id/race/stage/seed/~20數值/時間戳 | ~0.8 KB |
| 天賦 | 145節點 bitmap/set + 點數 | ~0.3 KB |
| 技能 | skill_bag(~20招)+ slots | ~0.8 KB |
| 23插槽渲染 | 23×{url~70字, generated_at} | ~2.5 KB |
| 靈魂 | 6軸+個性標籤+(管理員劇情記憶) | ~0.5–2 KB |
| 任務+群感印記 | 進行中+各主題計數 | ~1 KB |
| 菌圃 | ≤5畦×狀態 | ~0.5 KB |
| 成就 | 解鎖集合+進度(累積) | ~1.3 KB |
| 位置/菌氣/雜項 | | ~0.2 KB |
| **合計** | | **典型 ~8–10 KB / 極端 ~15–20 KB** |

**結論**:400KB 上限**非風險**(只用 2–5%)。真正成本驅動力=**DynamoDB 寫入 WRU 按 item 全長計費**(UpdateItem 改 1 欄也算整包)→ 高頻熱寫若背整包,浪費 WRU。這是決策②「拆熱冷」的唯一理由,不是大小上限。

---

## ✅ 6 項拍板決策

### ① 單表 vs 多表 → 混合 single-table
| 表 | PK | SK / 說明 | 理由 |
|---|---|---|---|
| `sweetbot-yajunban-monster` | userId | 實體型別(見③) | 怪獸資料高度耦合,PK overloading 省跨實體讀 |
| `sweetbot-yajunban-ledger` | userId | `<TYPE>#<ts>#<ulid>`(EXP/QUEST/FRAGMENT) | 流水永久可 backfill |
| `sweetbot-yajunban-battle` | battleId(ULID) | 租約+TTL | 生命週期/churn 與怪獸不同,獨立 |
| 堡壘 5 表(已定案 5f6e62b) | — | fortress/raid/sugar-pulse/guild-pool/ledger | 跨服 GSI/存取形狀不同 |

全部 PAY_PER_REQUEST · ap-southeast-1。

### ② 單一大 item vs 拆熱冷 → 同 PK 拆 3 個 item(WRU 治本)
`sweetbot-yajunban-monster` 表 · PK=userId · 用 SK 分 item:

| SK | 別名 | 內容 | 大小 | 寫頻率 |
|---|---|---|---|---|
| `M#CORE` | 熱 | race/stage/seed/born_at、6戰鬥數值、charm/friendship/reputation/survival_hours/xp、obesity/satiety/mood/battle_deaths、位置/khui_last_ts、全時間戳、每日計數、zero_*_since | ~1.5–2 KB | **高**(照顧/移動/被動/衰退) |
| `M#BUILD` | 溫 | talent_nodes(**StringSet**,見二驗收口)/talent_points/talent_unlockable、skill_slots/skill_bag、job_guild/tier、slots(23 URL) | ~1.2 KB | 中(升級/裝備/配點才動) |
| `M#PROGRESS` | 混 | quests map、群感印記、soul map(6軸+標籤)、garden(≤5畦)、achievements | ~3 KB | 中 |
| `PLAYER#PERMANENT` | 永久 | shards、career_history(per-guild)、祖傳天賦、靈魂深記、appAccountId | ~0.5 KB | 低(轉生/兌換) |

- **熱寫只背 CORE ~2KB WRU**,不背 23插槽URL/成就史。
- 讀狀態卡=`Query PK`(一次拿全部 4 顆,RCU 按總長算)或快速面板只 `GetItem M#CORE`。

### ③ 轉生重置邊界 → 固定 3 顆 exact-key TransactWrite 覆寫（⚠️ Codex P0-2 修正）
- ~~原案「刪 `SK begins_with "M#"` 一個條件搞定」不成立~~:DDB 可 Query begins_with 但**無 atomic delete-many**。
- **改**:怪獸 item 集合固定為 `M#CORE`/`M#BUILD`/`M#PROGRESS` 三顆(已知有限)→ 轉生 = 單一 `TransactWrite`{ Put M#CORE(fresh stage=1)+Put M#BUILD(fresh)+Put M#PROGRESS(fresh)+Update PLAYER#PERMANENT(+繼承碎片/祖傳天賦/職人資歷/靈魂深記) },全 exact-key、原子、遠低於 100 item/4MB。覆寫即重置,不需 delete-many。
- 未來若 PROGRESS 需溢成多顆(現 ~3KB 不會)→ 才改 generationId/lifeId 模型(切 active generation 指標+非同步清舊)。現階段不需要。

### ④ 跨平台 identity → claim item 唯一鎖（⚠️ Codex P0-1 修正）
- 前提:`userId` = Discord user id → Discord 查詢=PK 本身免索引。✅ 不變。
- ~~原案「`PLAYER#PERMANENT.appAccountId` + GSI `identity-index`」~~:**GSI 不保證唯一、非強一致** → 兩個 Discord user 可能同綁一個 APP 帳號。
- **改**:加 identity claim item **`PK=APP#<appAccountId>, SK=IDENTITY`**(monster 表內,PK overloading)、屬性 `userId`。綁定 = 單一 `TransactWrite`{ Put `APP#<id>` with `ConditionExpression attribute_not_exists(userId)`(唯一鎖;用表實際 PK 屬性名 `userId`,非字面 `PK`)+Update `PLAYER#PERMANENT.appAccountId` }。APP→userId 直接 `GetItem APP#<id>`(免 GSI)。換綁走 Delete+Put 同交易。

### ⑤ GSI → index overloading
| 表 | GSI | PK / SK | 用途 |
|---|---|---|---|
| monster | ~~identity-index~~(移除) | — | 改用 claim item `APP#<id>` 直查,見④ |
| ledger | (初期不建,需要再加 season-index) | | |
| 堡壘(已定) | level-index / guild-index / attacker-index / defender-index / season-index | | 配對/對帳/復仇/賽季榜 |
- 堡壘配對用泛型 GSI1PK/GSI1SK 欄承載多查詢型別,省 GSI 數。GSI 一律最終一致→正確性靠基表條件寫。

### ⑥ schema 缺欄 → 併階段3 補
設計冊 section-data schema 卡目前缺:`satiety`、`mood`、每日計數欄(摸頭/玩耍/整理/鼓勵)、`last_fed_at`、`khui_last_ts`、`zero_friendship_since`、`zero_reputation_since`、`talent_unlockable`、`career_history`、`appAccountId`。階段3 定 M#CORE/BUILD schema 時一併補齊。

---

## 🗺️ ERD(文字版)

```
sweetbot-yajunban-monster (single-table, PK overloading)
  PK=userId:
    ├─ SK M#CORE / M#BUILD / M#PROGRESS   怪獸三顆(轉生 exact-key 覆寫重置)
    ├─ SK INV#<itemId>                     背包道具(qty,原子扣)        [⑦ 新增]
    └─ SK PLAYER#PERMANENT                 永久(碎片/職人資歷/祖傳天賦/appAccountId)
  PK=APP#<appAccountId>:
    └─ SK IDENTITY → userId                綁定唯一鎖 attribute_not_exists [④ 修正]

sweetbot-yajunban-ledger (PK=userId, SK=<TYPE>#ts#ulid)      永久流水
sweetbot-yajunban-battle (PK=battleId, TTL=leaseExpireAt)    租約自癒
sweetbot-yajunban-world  (PK=zone#gridBucket, SK=cell/entityId, 殘渣帶TTL) [⑧ 新增]

堡壘 5 表(已定 5f6e62b):fortress / fortress-raid / sugar-pulse /
  fortress-guild-pool / fortress-ledger
```

## 寫入路徑對照(WRU 最佳化驗證)
| 操作 | 寫哪顆 | WRU |
|---|---|---|
| 摸頭/餵食/移動/被動吸收/lazy衰退 | M#CORE | ~2 |
| 配點/學技能/裝備/轉職 | M#BUILD | ~2 |
| 任務進度/靈魂6軸/收成/成就 | M#PROGRESS | ~3 |
| 碎片兌換/職人資歷/轉生繼承 | PLAYER#PERMANENT | ~1 |
| 餵食(扣背包)、偷菜、raid、糖潮 | TransactWrite 跨顆/跨表 | 各顆 size |

→ 高頻熱寫((摸頭/移動/被動))穩定 ~2 WRU,不受插槽/成就膨脹拖累 ✅

## 🔍 Codex 二驗 findings + Claude vet 處置(2026-07-17)

Codex(Neku)對階段2 做對抗式二驗,7 findings。Claude 逐條 vet:**全部採納**(2 個 P0 是階段2 決策的真錯,已在上方 ③④ 修正)。

| # | Codex finding | Claude vet | 處置 |
|---|---|---|---|
| P0-1 | appAccountId 只靠 GSI 無法唯一綁定(非唯一非強一致,兩 Discord user 可綁同 APP) | ✅ 成立·真錯 | 已改④=claim item `APP#<id>` `attribute_not_exists` 唯一鎖+TransactWrite |
| P0-2 | 轉生 delete begins_with 非原子 | ✅ 成立·真錯 | 已改③=固定3顆 exact-key TransactWrite 覆寫 |
| P1-3 | 讀路徑要分層;ProjectionExpression 不省 RCU | ✅ 成立 | DAO 定 `getStatusCore`/`getFullMonster`,見下 |
| P1-4 | TransactWrite 需 builder 合併同 item mutation(防同交易重複操作同 key) | ✅ 成立 | DAO 層 transaction builder,見下 |
| P1-5 | 背包/道具 schema 未接;EssenceBagDAO scan/filter 不適高頻原子扣 | ✅ 成立·真缺口 | 新增決策⑦ |
| P1-6 | 棋盤世界查詢(相鄰格/殘渣)無法靠 PK=userId | ✅ 成立·真缺口 | 新增決策⑧ |
| P1-7 | 熱點在全域(糖潮 META 單item/level-index 低基數)非 monster PK | ✅ 成立·小規模可接受 | 記 scale 待辦,見下 |

### ⑦ 背包/道具 schema(補 P1-5)
- monster 表加 `INV#<itemId>` SK item(隨玩家 PK),`qty:N`+道具 metadata。
- 高頻原子扣:`SET qty = qty - :n` + `ConditionExpression qty >= :n`;可與 M#CORE(餵食)同 `TransactWrite`(同表跨 SK)。
- **不沿用 EssenceBagDAO**(scan/filter compat,不適高頻原子)。

### ⑧ 棋盤世界 spatial schema(補 P1-6)
- 新增 `sweetbot-yajunban-world`:`PK=zone#gridBucket`(空間分桶)、`SK=cell/entityId`,存格子佔用(誰在此)+動態元素(殘渣/糖晶,帶 TTL 自動消失)。
- 「相鄰格敵人」=Query 玩家 gridBucket(+鄰桶);移動時舊桶刪/新桶寫(可跟 M#CORE.pos 同 Transact)。
- 對齊 STAGE1 1-3「世界狀態別塞玩家大 item」。屬新工序,**排入階段7(GSI/spatial)一併做**。

### 🔴 DAO 層注意(給階段9,併 STAGE3 已記的 4 地雷)
- **讀分層**(P1-3):`getStatusCore`=GetItem M#CORE;`getFullMonster`=Query PK;禁高頻面板每次全讀。ProjectionExpression 不省 RCU(按投影前 item size 計)。
- **transaction builder**(P1-4):送 TransactWrite 前合併「同一 item 的多個 mutation」成一個 Update,避免同交易重複操作同 key 被拒。
- **scale**(P1-7):糖潮 pool 大規模 shard(多 META 分片加總)、level-index 用 matchableBucket 打散(堡壘已埋)。小規模先不做,記待辦。

### 存疑點收口
- **存疑① talent 編碼** → 確定 **StringSet**(Codex 未反對+Claude 背書單節點原子 ADD),已回改決策②。
- **存疑⑤ stats 歸 CORE/BUILD** → Codex 未提異議+讀路徑已分層 → **stats 留 M#CORE**,關閉。

---

## ➡️ 交給階段3
以 `M#CORE` + `M#BUILD` 的完整欄位 schema(型別/預設/巢狀 map 結構)為主,補齊決策⑥缺欄,對齊 sweetbot-next DDB 型別慣例(Number/String/Map/StringSet)。**階段3 草稿已完成**(`STAGE3-schema-DRAFT.md`),二驗已合流(talent SS/stats 留 CORE 確認),可定稿去 DRAFT。背包⑦/世界⑧ schema 排階段4/7。
