# 牙菌斑怪獸 · DDB 資料模型 — 階段7a:GSI 盤整 + 彙整/分析查詢策略

> 交接文件 · 產出日期 2026-07-17 · 承接 [STAGE2-schema-decision.md](./STAGE2-schema-decision.md)(決策⑤ GSI overloading、P1-7 熱點 scale 待辦)
> 狀態:**草稿**(Claude 出提案,待 signoff / Codex 二驗)。
> 用途:定案「monster/ledger 表要不要加 GSI」+ 後台彙整(種族分佈/Stage漏斗/DAU/留存)查哪裡。與 [STAGE7b](./STAGE7b-world-spatial-DRAFT.md)(世界 spatial)同屬階段7,拆開因存取形狀正交。

---

## 🎯 本階段要回答的三個問題
1. **monster 表**除了 `PK=userId` 直查,還有沒有查詢需要 GSI?
2. **後台分析**(種族分佈、Stage 漏斗、DAU、留存、系統活躍)資料從哪來——即時 GSI vs 週期彙整?
3. **全域 GSI 清單**最終有幾條、各在哪張表(給 Codex 建表時一次到位)。

---

## ✅ 決策 ⑨:monster 表維持「零玩家向 GSI」

盤 STAGE1 全 5 節,monster 表(怪獸聚合 + INV#/PVP#/PLAYER#/APP#)上**沒有任何玩家向(高頻、即時)存取需要非 PK 查詢**:

| 候選查詢 | 是否需要 GSI | 為何不需要 |
|---|---|---|
| 讀自己怪獸/狀態卡 | ❌ | `PK=userId` 直查(STAGE2 ①) |
| Discord→怪獸 | ❌ | `userId` = Discord id,PK 本身 |
| APP 帳號→怪獸 | ❌ | claim item `GetItem APP#<id>`(STAGE2 ④,取代原 identity-index) |
| 「誰在我旁邊」PvP/偷菜 | ❌(在 monster 表上) | 走 **world 表** spatial(STAGE7b),不是 monster GSI |
| 段位/堡壘配對 | ❌(在 monster 表上) | 走 **fortress** 表 `level-index`(STAGE1 §1-5,已定) |
| 排行榜(玩家向) | ❌ | 設計冊 §board/§battle **無玩家向全服排行**存取模式(存活/聲望只在自己面板顯示);不無中生有 |

**結論**:monster 表確定**不建 GSI**。維持 STAGE2 ④⑤ 的「移除 identity-index、PK overloading 直查」。這也讓熱寫 WRU 不背 GSI 投影成本(每條 GSI = 每次基表寫多一份 WRU)。

> ⚠️ 若日後設計冊新增「玩家向全服排行榜」(如生存時數榜),才回頭評估**稀疏 GSI**(見決策⑪旋鈕),不是現在。

---

## ✅ 決策 ⑩:後台分析 = 週期彙整 scan,不即時 GSI

後台 dashboard 需求(STAGE1 §1-5 第176行 + 牙齒經濟後台既有):**種族分佈 / Stage 漏斗 / DAU / 留存 / 系統活躍 / 日成本試算**。全部是**跨全體怪獸的聚合**,不是「查某一筆」。

**判斷**:聚合查詢用 GSI **划不來**——GSI 只是換 PK 排序,聚合仍要掃整個 GSI(RCU 不會比掃基表省),卻要付「每次基表寫 +1 WRU × 每條 GSI」的長期稅。聚合正解是**週期彙整**,不是索引。

### 採用 pattern:沿用「牙齒經濟後台」既有做法(reference [[project_teeth_economy_dashboard]])
- 該後台已在跑「掃流水帳 → 聚合 → 存快照」(gen_usage.py / economy Lambda)。牙菌斑分析**掛同一條管線**,不新建成本四件套。
- **來源分兩路**:
  - **存量指標**(種族分佈 / Stage 漏斗 / 總怪獸數 / 平均數值)→ 週期 **Scan monster 表**,`FilterExpression #sk = :core`(`ExpressionAttributeNames {"#sk":"sk"}`、`:core="M#CORE"`;**用實際 SK 屬性名 `sk`,非概念名 `SK`**——Codex P2-6;只數核心顆,避免一隻怪重複計 4 顆)→ 聚合。小規模(< 數千怪 × ~2KB)單次 scan < 1–2 MB,幾十 RCU,日跑一次可忽略。
    > 📌 STAGE3 只寫「SK = 實體型別字串」未明訂**物理屬性名**;此處與 ledger 對齊定為 **`sk`(小寫)**,請 STAGE3 定稿時把 monster 表 SK 屬性名一併釘死 `sk`,免 DAO 端各寫各的。
  - **活躍/留存指標**(DAU / WAU / 留存曲線 / 新增)→ ⚠️ **不可靠 ledger**(Codex P1-2 修正):STAGE5a「不記名單」明文把摸頭/玩耍/整理/鼓勵/餵食零星/菌氣/移動這些**高頻互動排除在 ledger 外**,故 ledger 不是完整「哪天有互動」時間軸,直接切窗會嚴重低估 DAU。改採二選一:
    - **MVP(快照型)**:掃 `M#CORE.last_interaction`(或 `updatedAt`)做「最近 N 日活躍」快照統計。夠算「近期活躍數」,但**單一 timestamp 無歷史 → 算不出 per-day DAU / cohort 留存曲線**。
    - **要真 DAU/留存**:加**每日活躍標記** `ACT#<yyyymmdd>`(每玩家每日**至多一筆**,當日首次任意互動時 `Put attribute_not_exists` stable-gate 防寫爆;放 ledger 表或獨立 `PK=ACT#<date>,SK=userId` 讓「某日活躍名單」= 一次 Query)。成本 = 每活躍玩家每日 1 筆微寫,可忽略。留存 = 註冊 cohort × `ACT#` 日期集合 join。
    - **本階段結論**:MVP 先快照型(`last_interaction`),`ACT#` 標記排入「要留存曲線時再開」(見決策⑪旋鈕表新增列)。
- **落點**:聚合結果寫**一顆 stats 快照 item**(可放既有 config/economy 表,或 monster 表 `PK=STATS#<yyyymmdd>` 系統列)供後台直接 `GetItem` 秒開,不讓後台每次現掃。

> 對齊 STAGE2 P1-7:「糖潮 pool / level-index 熱點小規模先不做 shard,記待辦」——分析同理,**小規模先 scan,不預建索引**。

### ⚠️ Scan 分頁鐵律(給階段9 DAO)
彙整 Scan **必分頁 loop**(`LastEvaluatedKey`),單次 1MB 上限會截斷。這是本 repo 踩過的雷(記憶 [[project_sweetbot_yt_bind_migration]] 「Scan必分頁」)。彙整器加 `Segment/TotalSegments` 平行掃可選,小規模不需要。

---

## ✅ 決策 ⑪:稀疏 GSI「旋鈕」預留(scale 才開,現不建)

留一個**明文觸發條件**,避免日後「要不要加索引」再吵一輪:

| 未來需求 | 觸發門檻 | 屆時加什麼 | 現在做什麼 |
|---|---|---|---|
| 玩家向全服排行榜(生存/聲望) | 設計冊真的要上榜 | monster 稀疏 GSI:只對「入榜資格」的怪填 `rankBucket#season` PK + 分數 SK(稀疏=沒資格不投影,省 WRU) | 不建;欄位預留 |
| 分析 scan 變貴(彙整 > 數百 MB / > 數秒) | 怪獸數 ~上萬級 | ① Scan `Segment` 平行化 先試;② 仍不夠再上分析 GSI 或 DDB→S3 export + Athena | 不建;記門檻 |
| per-day DAU / cohort 留存曲線 | 後台要看留存(非只「近期活躍數」) | 每日活躍標記 `ACT#<yyyymmdd>`(每人每日至多一筆,stable-gate),或獨立 `PK=ACT#<date>` | MVP 先用 `M#CORE.last_interaction` 快照(決策⑩) |
| ledger 賽季榜/整季導出 | 季末對帳要按 season 撈 | ledger `season-index`(PK seasonId · SK ts) | STAGE2 ⑤ 已標「初期不建,需要再加」,維持;**但「免 backfill」的前提是 `season` 欄 v1 就穩定寫入**(Codex P2-6c)→ 需 v1 就有 seasonId 來源。STAGE5a 存疑⑥「seasonId 取值來源未定、拿不到就不寫」是**破口**:漏寫的列日後仍要 backfill。**建議 v1 就把 seasonId 落成全域 config,讓 ledger 每列必帶 season**(回饋 STAGE5a) |

**稀疏 GSI 要點**:GSI 只投影「有 GSI-PK 屬性」的 item。排行榜只需 top 玩家 → 只有夠格的怪寫 `rankBucket` 屬性 → GSI 稀疏、又小又便宜。這是正解,不是「全體都投影再排序」。

---

## 📋 全域 GSI 最終清單(給 Codex 建表,一次到位)

盤整**全部 8 張表**的 GSI,定案如下。**除堡壘 5+1 既定外,牙菌斑核心三表(monster/ledger/battle)階段一律零 GSI。**

| 表 | GSI | PK / SK | 用途 | 狀態 |
|---|---|---|---|---|
| `sweetbot-yajunban-monster` | — | — | 無;PK overloading + APP# claim 直查(決策⑨) | ✅ 零 GSI |
| `sweetbot-yajunban-ledger` | ~~season-index~~ | (seasonId · ts) | 賽季榜/導出 | ⏸ **延後**(⑪,需要再加) |
| `sweetbot-yajunban-battle` | — | — | 租約 `PK=battleId` 直查 + TTL 自癒;無跨查詢 | ✅ 零 GSI |
| `sweetbot-yajunban-world` | — | — | spatial 靠 `PK=zone#bucket` 分桶直查(STAGE7b) | ✅ 零 GSI(見7b) |
| `-fortress` | `level-index` | (matchableBucket/level · lastActiveAt) | 段位配對(pagination loop) | ✅ 既定(STAGE1) |
| `-fortress` | `guild-index` | (guildId · channelId) | 對帳/回收/換季 | ✅ 既定 |
| `-fortress-raid` | `attacker-index` | (attackerId · departAt) | 同目標冷卻 | ✅ 既定 |
| `-fortress-raid` | `defender-index` | (defenderId · arriveAt) | 被打預警/復仇 | ✅ 既定 |
| `-fortress-ledger` | `season-index` | (seasonId · ts) | 賽季榜/對帳導出 | ✅ 既定 |

→ **當下要建的 GSI 共 5 條,全在堡壘子系統**(與 STAGE1 §1-5「GSI 共 5 條」一致)。牙菌斑主循環(照顧/戰鬥/棋盤/任務/菌圃)**零 GSI**。

---

## 💰 成本控管(連回正典 [tools/COST_CONTROL.md](../COST_CONTROL.md))
- 本階段**不新增**任何燒 LLM / 付費 API 路徑;分析彙整純 DDB scan + 既有 economy Lambda。
- **省成本的核心決策就是「不加 GSI」**:每條 GSI 對高頻熱寫都是長期 WRU 稅,分析改週期 scan 一次性付費。符合 §1 鐵律「PAY_PER_REQUEST、按用量」。
- world/battle 分析若未來要 export,優先 DDB→S3 PITR export(不吃線上讀),不掃線上表。

---

## ➡️ 交給 Codex 二驗的收口點
1. **決策⑨** monster 零 GSI:確認 STAGE1 全節真的沒有玩家向非 PK 即時查詢被我漏掉(尤其任務/成就/靈魂有沒有「跨玩家找」的隱藏需求)。
2. ~~決策⑩ DAU 從 ledger 切窗~~ → **Codex P1-2 已修正**:ledger 不記高頻互動(STAGE5a 不記名單),DAU 改 `M#CORE.last_interaction` 快照(MVP)/ `ACT#` 標記(要留存曲線)。已改。
3. **決策⑪** 稀疏 GSI 旋鈕:確認排行榜/賽季榜觸發門檻寫法,及 ledger season-index 延後不會卡到季末對帳 MVP。
4. GSI 清單 5 條:與堡壘既定案(STAGE1 §1-5 / 5f6e62b)逐條對齊,無新增無遺漏。
