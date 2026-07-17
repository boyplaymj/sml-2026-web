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
| `M#BUILD` | 溫 | talent_nodes(bitmap)/talent_points/talent_unlockable、skill_slots/skill_bag、job_guild/tier、slots(23 URL) | ~1.2 KB | 中(升級/裝備/配點才動) |
| `M#PROGRESS` | 混 | quests map、群感印記、soul map(6軸+標籤)、garden(≤5畦)、achievements | ~3 KB | 中 |
| `PLAYER#PERMANENT` | 永久 | shards、career_history(per-guild)、祖傳天賦、靈魂深記、appAccountId | ~0.5 KB | 低(轉生/兌換) |

- **熱寫只背 CORE ~2KB WRU**,不背 23插槽URL/成就史。
- 讀狀態卡=`Query PK`(一次拿全部 4 顆,RCU 按總長算)或快速面板只 `GetItem M#CORE`。

### ③ 轉生重置邊界 → SK 前綴天然分區
- 轉生 = 刪 `SK begins_with "M#"` 的 3 顆,**保留 `PLAYER#PERMANENT`**。
- 一個 begins_with 條件搞定,零誤刪永久資產。生成新芽孢 = 寫新 M#CORE(stage=1)。

### ④ 跨平台 identity → 輕量,不另開表
- 前提:`userId` = Discord user id(sweetbot 慣例)→ Discord 查詢=PK 本身,免索引。
- 只需 **APP帳號→userId**:於 `PLAYER#PERMANENT` 存 `appAccountId` 屬性 + GSI `identity-index`(GSI1PK=appAccountId → 投影 userId)。

### ⑤ GSI → index overloading
| 表 | GSI | PK / SK | 用途 |
|---|---|---|---|
| monster | `identity-index` | appAccountId | APP↔player 解析 |
| ledger | (初期不建,需要再加 season-index) | | |
| 堡壘(已定) | level-index / guild-index / attacker-index / defender-index / season-index | | 配對/對帳/復仇/賽季榜 |
- 堡壘配對用泛型 GSI1PK/GSI1SK 欄承載多查詢型別,省 GSI 數。GSI 一律最終一致→正確性靠基表條件寫。

### ⑥ schema 缺欄 → 併階段3 補
設計冊 section-data schema 卡目前缺:`satiety`、`mood`、每日計數欄(摸頭/玩耍/整理/鼓勵)、`last_fed_at`、`khui_last_ts`、`zero_friendship_since`、`zero_reputation_since`、`talent_unlockable`、`career_history`、`appAccountId`。階段3 定 M#CORE/BUILD schema 時一併補齊。

---

## 🗺️ ERD(文字版)

```
sweetbot-yajunban-monster (PK=userId)
├─ SK M#CORE          熱·活狀態      ← 照顧/移動/被動/lazy衰退
├─ SK M#BUILD         溫·build       ← 天賦/技能/職業/23插槽
├─ SK M#PROGRESS      混·內容循環     ← 任務/群感/靈魂/菌圃/成就
└─ SK PLAYER#PERMANENT 永久·跨轉生    ← 碎片/職人資歷/祖傳天賦/appAccountId
      └─ GSI identity-index (appAccountId → userId)

sweetbot-yajunban-ledger (PK=userId, SK=<TYPE>#ts#ulid)   永久流水
sweetbot-yajunban-battle (PK=battleId, TTL=leaseExpireAt) 租約自癒

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

## ➡️ 交給階段3
以 `M#CORE` + `M#BUILD` 的完整欄位 schema(型別/預設/巢狀 map 結構)為主,補齊決策⑥缺欄,對齊 sweetbot-next DDB 型別慣例(Number/String/Map/StringSet)。
