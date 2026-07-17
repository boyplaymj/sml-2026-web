# 牙菌斑怪獸 · DDB 資料模型 — 階段9a:核心 4 表建表 IaC

> 交接文件 · 產出日期 2026-07-17 · 承接 STAGE1–8(全定稿)+ [STAGE8 §表清單](./STAGE8-dao-engineering.md)
> 狀態:**草稿**(Claude 出腳本,待 signoff / Codex 二驗)。
> **範圍**:只建**完全定稿**的牙菌斑核心 4 表(monster/ledger/battle/world)。**堡壘 5 表不在此塊**(見文末「⏸ 堡壘 5 表前置」)。
> **產物**:`create_yajunban_core_tables.js`(本資料夾;定稿+驗後複製進 `sweetbot-next/migration/` 再 `node` 執行)。
> **性質**:純建表 IaC,**不碰 bot 邏輯**——沿用 repo 既有 migration 慣例(`create_livevote_tables.js` 冪等 CreateTable + `create_earthquake_tables.js` 的 `UpdateTimeToLive`)。

---

## 🧭 為什麼先只做核心 4 表(範圍決策)
- monster/ledger/battle/world 的**實體 key schema 已在 STAGE2–8 釘死到屬性名層級**(見下表),可直接建、零猜測。
- **堡壘 5 表**雖標「已定案」,但**實體 GSI 鍵名未定稿**:commit `5f6e62b` 在本 repo 找不到、無既有 migration、STAGE1 對 `level-index` 還在 `level` vs `matchableBucket` 兩說。**GSI 鍵名瞎猜 = 建錯要刪表重建**,故堡壘另立前置任務先釘 schema 再建(見文末)。
- 這塊也是**風險最低的起點**:inert 腳本、不動運行中的 bot、可獨立 `node` 跑。

---

## 📋 核心 4 表實體 schema(建表用)

| 表 | PK(attr:type) | SK(attr:type) | TTL | GSI | 來源 |
|---|---|---|---|---|---|
| `sweetbot-yajunban-monster` | `userId` : S | `sk` : S | ❌ 永不開 | ❌ 零 | S2/3/4/7a/8 |
| `sweetbot-yajunban-ledger` | `userId` : S | `sk` : S | ❌ | ⏸ 不建(season-index 延後) | S5a/7a |
| `sweetbot-yajunban-battle` | `battleId` : S | —(無 SK) | ✅ `leaseExpireAt`(秒) | ❌ | S6 |
| `sweetbot-yajunban-world` | `pk` : S | `sk` : S | ✅ `ttl`(秒) | ❌ | S7b |

**共通**:`BillingMode = PAY_PER_REQUEST`、`REGION = ap-southeast-1`。

### 逐表說明(對齊各定稿階段)
- **monster**:PK `userId` overloading——值為 Discord id(怪獸 6 顆:M#CORE/BUILD/PROGRESS/PLAYER#PERMANENT/PLAYER#ACHIEVE/INV#/PVP#)**或** `"APP#<appAccountId>"`(claim 唯一鎖,SK=IDENTITY)。同一 `userId`/`sk` 兩屬性即可承載全部(S4)。**永不開 native TTL**(裝永久資料,S8 §2 foot-gun)。
- **ledger**:PK `userId` + SK `sk`=`<TYPE>#<ts>#<ulid>`。**season-index GSI 延後不建**(S7a ⑪:`season` 欄 v1 就必帶→未來加 GSI 免 backfill,建表現在不含)。
- **battle**:PK `battleId`(ULID),**無 SK**。**TTL=`leaseExpireAt`**(秒級 10 位;S6 唯一真 TTL 生命週期)。
- **world**:PK `pk`=`<season>#<gridBucket>`(overloaded 空間分桶)+ SK `sk`=`OCC#<userId>`/`LOOT#<ulid>`。**TTL=`ttl`**(OCC=season-end、LOOT=壽命;S7b)。
  - ⚠️ **本階段新釘的實體屬性名**:world 的 PK 用泛型 `pk`(值為複合 `season#bucket`、overloaded)、SK 用 `sk`。STAGE7b 只寫概念 PK/SK,此處落地成 `pk`/`sk`(對齊 earthquake-log 泛型鍵慣例)。**待 Codex 確認命名**。

---

## ⚙️ 腳本設計要點(比既有樣板更嚴,落實 S8 P2-a)
1. **冪等 CreateTable**:`DescribeTableCommand` 先探,存在則跳過(不重建)。沿用 livevote 樣板。
2. **TTL 冪等且可修**:**不照 earthquake 樣板「表存在就整個 return」**——那會漏掉「表已建但 TTL 沒開/開錯 attr」。改為:建表後開 TTL;**且每次跑都 `DescribeTimeToLiveCommand` 驗現況**,未啟用/attr 不符才 `UpdateTimeToLive` 補正。落實 S8 §2「建表腳本驗證 TTL 已啟用且 attr 名正確」(TTL attr 打錯 = 靜默不清殭屍)。
3. **TTL attr 不同名硬編在表定義**:battle→`leaseExpireAt`、world→`ttl`(S8 P2-a 提醒兩表不同名)。
4. **建完 summary**:列每表狀態 + TTL 啟用結果,人可一眼核。
5. **只建不刪**:腳本不含 DeleteTable(避免誤刪)。

---

## 🚚 部署路徑(定稿+Codex 驗後才做,需協調時機)
1. 複製 `create_yajunban_core_tables.js` → `sweetbot-next/migration/`。
2. ⚠️ **併行快照雷**([[feedback_sweetbot_parallel_snapshot_hazard]]):挑沒有其他 session 在動 sweetbot-next 的時機,進 sweetbot-next 後**立即 commit** 該新檔(走 check-conflict.sh/AGENTS 治理),別留未提交。
3. `node migration/create_yajunban_core_tables.js`(冪等,可重跑)。
4. 驗:AWS console / `aws dynamodb describe-time-to-live` 確認 battle/world TTL 已 Enabled 且 attr 名對。

---

## ⏸ 堡壘 5 表前置(獨立小任務,不在本塊)
建堡壘 5 表 migration 前**必須先釘死實體 schema**(現只有概念級):
- 各表 PK/SK 實體屬性名(fortress=playerId?/raid=raidId?/sugar-pulse=?/guild-pool=guildId/ledger=playerId+S#season#…)。
- **5 條 GSI 的實體鍵**:`level-index`(**`level` 還是 `matchableBucket` 當 PK?** S1 兩說要拍板)、`guild-index`(guildId·channelId)、`attacker-index`(attackerId·departAt)、`defender-index`(defenderId·arriveAt)、`season-index`(seasonId·ts)。
- GSI 投影型別(ALL / KEYS_ONLY / INCLUDE)逐條定。
→ 建議做成 **STAGE9b**(先補堡壘實體 schema 卡 → 再出堡壘 migration)。

---

## ➡️ 交給 Codex 二驗的收口點
1. **核心 4 表 key schema** 與 STAGE2–8 定稿逐欄對齊(尤其 world 新釘的 `pk`/`sk` 命名、battle 無 SK)。
2. **TTL 冪等強化**:`DescribeTimeToLive` 驗證流程正確(existing 表也會補 TTL),且不會誤動已正確的表。
3. **season-index 延後不建**是否影響 v1(S7a 已判不影響、`season` 欄照寫)。
4. 腳本語法/SDK v3 用法(`@aws-sdk/client-dynamodb`)對齊 repo 現有 migration。
5. 堡壘 5 表切成 STAGE9b 前置是否合理(vs 硬湊進本塊)。
