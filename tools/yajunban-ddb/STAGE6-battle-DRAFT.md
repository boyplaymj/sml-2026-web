# 牙菌斑怪獸 · DDB 資料模型 — 階段6:戰鬥租約表 `sweetbot-yajunban-battle`

> **定稿 · Claude 覆核 + Codex 二驗已合流(2026-07-17)**:3 P0 修正(開戰鎖 activeBattleId 防雙開、version 移記憶體結算靠 state=ACTIVE、Khui 扣 RMW 樂觀鎖)+ 3 P1(PvP 雙方 CORE、24hr 業務閘、PVP# 回填)。（產出 2026-07-17）
> 承接 [STAGE2-schema-decision.md](./STAGE2-schema-decision.md) 決策①(battle 獨立表)、[STAGE1-access-patterns.md](./STAGE1-access-patterns.md) §1-3(戰鬥+棋盤存取模式)、[STAGE3-schema-DRAFT.md](./STAGE3-schema-DRAFT.md)(M#CORE 戰鬥數值/battle_deaths/hp 語義)。
> 語義來源:設計冊 `score-repo/yajunban_design.html` §section-battle(3×3/8步管線/19狀態/pH/三層終結/租約崩潰安全)、§section-board(菌氣 Khui 移動/賽季地圖/重生)。型別慣例:`sweetbot-next/DAO/DDB/*`(DDBBaseDAO / TrainTycoonTransitDAO 的 `TransactWriteCommand`、PuzzleRoundDAO 的 epoch ms createdAt)。

---

## ⚠️ 頭號鐵律:`leaseExpireAt` 是 epoch **秒**,不是毫秒!

- 本 repo 全表(monster / ledger / …)時間戳一律 **epoch 毫秒**(`Date.now()`,見 STAGE3 慣例③)。
- **唯獨** DynamoDB **原生 TTL 屬性**要求 epoch **秒**(Unix seconds)——DDB 只認秒;若誤寫 ms,item 會被當成「西元五萬年」永不過期,租約自癒與 GC 全失效。
- 故 `leaseExpireAt` **必須** `Math.floor(Date.now()/1000) + windowSec`。本表所有**其他**時間戳(createdAt/updatedAt/resolvedAt/pos 快照 ts…)仍是 **ms**。**一表兩制,DAO 層務必封裝、別讓呼叫端手算。**
- ⚠️ sweetbot-next 現有 DAO **無** epoch-秒 TTL 前例(MarketSession / TrainTycoonTransit 等都用 ms 欄 + `settled/isSettle` 旗標判生死,不靠原生 TTL)→ **本表是第一個真用 DynamoDB TTL 的表**,更要在 DAO 註解與單測明確標秒,並在建表時 `UpdateTimeToLive` 指定 `AttributeName=leaseExpireAt`。

---

## ## 待確認/存疑點

> 開頭先列不確定處,交 Claude 拍板 / Codex 二驗。

1. **【重點】PvP 1 分 CD + 同對 24hr 首戰獎勵 → 存哪顆?**
   - 這兩個是**跨場次、per-pair 的關係狀態**,而戰鬥租約(battleId)是**單次相遇即拋**的 ephemeral item → CD/24hr **不能**存租約(結算後租約就 GC 掉了,下一次相遇讀不到)。
   - 也**不宜**放 bot 記憶體(process 重啟就失憶 → CD/24hr 可被無限刷)。
   - **草案建議**:放 **monster 表**的關係 item `PK=userId, SK=PVP#<opponentId>`(PK overloading,同玩家 PK-local),屬性 `lastEndAt`(ms)、`lastRewardAt`(ms)。**不帶 ttl / 不開 native TTL**(見 Claude 覆核:monster 表永不開 TTL);過期靠 lazy-prune 覆寫。
     - CD 判定 = `now − lastEndAt < 60_000ms`(比時間戳,**不**靠 TTL 刪);
     - 24hr 首戰獎勵 = `now − lastRewardAt ≥ 24h` 才發資源。
     - 結算時在同一 `TransactWrite` 內**雙向各寫一顆**(A→B 與 B→A),讓反擊窗口/雙方查詢都命中。
   - **存疑**:(a) 這算 monster 表還是 battle 表職責?我傾向 monster(關係屬玩家域);(b) 用獨立 `PVP#<opponentId>` SK item vs 塞 M#CORE 一顆 map `pvp_recent{opponentId:{...}}`——前者可個別 TTL/無上限但多 item,後者省 item 但 map 會膨脹需剪枝。**請拍板。**

2. **【重點】敗北重生位置(距擊敗者≥8格/回出生區/偏🪨地形)存哪?**
   - 重生 = 改怪獸**座標**,座標是 M#CORE 屬性(STAGE1 §1-3「移動寫座標/khui_last_ts」)→ **重生落點寫 M#CORE.pos**,在結算 UpdateItem 內一併 SET,**不**留在戰鬥租約。
   - 但「距擊敗者≥8格」要**讀擊敗者座標**:草案從**開戰快照** `defenderRef.pos`/`attackerRef.pos`(見下)取,或結算當下 GetItem 對手 M#CORE。
   - **存疑**:重生落點的實際挑格演算法(掃出生區半徑內、篩≥8格且旁有🪨、Stage1–2 再加遠)屬**引擎邏輯非 schema**;schema 只需保證 M#CORE 有 `pos` 可寫、開戰快照有雙方起始 `pos`。確認這樣切分 OK?棋盤格佔用/🪨地形查詢屬**世界表**(STAGE2 決策⑧ `sweetbot-yajunban-world`,排階段7)→ 重生挑格需跨讀世界表,**依賴階段7**,此處先標依賴。

3. **【重點】開戰快照要存多少?(暫態在記憶體 → 租約只存「啟動資訊」)**
   - 戰鬥暫態(HP/pH/狀態層/回合)**全在 bot 記憶體**(STAGE1 §1-3、設計冊「暫態不落庫」)→ **若 bot 崩潰,記憶體暫態直接遺失**、無法從租約 resume;租約 TTL 過期後該場**視同可重開**(不 resume、不補償)。
   - 故快照**不需**足以還原整場,只需**啟動資訊 + 冪等/自癒/結算所需最小集**:雙方 `userId`(PvE 為 `NPC#<id>`)、`battleType`、雙方 `race/stage`(相剋/新手保護/聲望懲罰門檻判定)、雙方**起始 `pos`**(重生≥8格計算)。
   - **存疑**:是否也快照雙方 `stats/talent/skill` 以防戰中對手改 build(anti-cheat 定格)?我傾向**不快照 build**(戰中不可改 build,結算時對 M#CORE 重讀即可,省 item size),只快照 refs + 起始 pos。若要嚴防「戰中偷升級」再議。確認 build 不快照?

4. **AFK 確定性結算的「確定性」判定放哪?**
   - 設計冊 L2:連續 2–3 回合無動作 → 不判和,直接算「之後都不出手」的確定結局(該死就死、DoT 穩贏就贏)、計入 permadeath。此**計算在記憶體引擎**(需當前 HP/pH/狀態層,全在記憶體)→ **schema 無專屬欄**,只是結算路徑之一(resolvedReason=`AFK`)。
   - **存疑**:若 bot 在 AFK 尚未觸發時崩潰 → 暫態失,租約 TTL 到期被 GC,場次消失、**不**補算 AFK 結局(掛機者僥倖逃過該場,但下次相遇照打)。可接受?還是要在租約存「最後一次記憶體暫態摘要 checkpoint」讓重啟後能補算 AFK?**我傾向不 checkpoint**(違反「暫態不落庫」且增寫入),接受崩潰即棄場。請確認健康性可接受。

5. **租約結束是 Delete 還是標記 RESOLVED?**
   - **草案建議標 RESOLVED(不刪)**:結算 = UpdateItem 租約 `SET state=RESOLVED, resolvedReason, resolvedAt` + **縮短** `leaseExpireAt`(給短 TTL 例如 +5 分,交 DDB TTL 免費 GC)。
   - 理由:留 RESOLVED 尾巴當**短期冪等哨兵**——重送/多觸發的第二次結算讀到 `state=RESOLVED` 即 no-op 拒絕;若直接 Delete,過期租約=可重開(見自癒),反而讓「剛結算完的重送」誤判成新戰開場。
   - **存疑**:確認採「標記 + 短 TTL GC」而非「即時 Delete」?(即時 Delete 較省一點 storage 但冪等窗口消失。)

6. **`battleType` 秘寶/Boss 是否本階段納入?**
   - 設計冊 §section-battle 列:PvE/PvP(標準,共用規則)、Boss 戰(待設計)、最終 Boss(待設計)、任務戰鬥(待設計)。prompt 另提「秘寶」。
   - **草案**:`battleType` enum 先開 `PVE | PVP`(已定案規則),另**預留** `BOSS | RAID | QUEST | TREASURE` 值(欄位就緒、引擎待各模式定案再接)。確認預留即可、無需現在定 Boss/秘寶 schema?

7. **PvE 對手鍵怎麼表達 `defenderId`?**
   - PvP:`defenderId` = 對方 Discord `userId`。PvE:對手是 NPC/野怪 → 建議 `defenderId = NPC#<npcTemplateId>#<spawnUlid>`,`defenderRef` 存模板 race/stage/地形強度。確認前綴 `NPC#` 命名?

---

## 1. 表定義

| 項目 | 值 |
|---|---|
| 表名 | `sweetbot-yajunban-battle` |
| 分區鍵 PK | `battleId`(S,**ULID**——時間可排序、開戰即生成) |
| 排序鍵 SK | **無**(單一 item / battleId;租約是扁平單筆) |
| 計費 | PAY_PER_REQUEST |
| Region | ap-southeast-1 |
| **TTL 屬性** | **`leaseExpireAt`(epoch 秒!)** — 建表後 `UpdateTimeToLive AttributeName=leaseExpireAt Enabled=true` |
| GSI | **無**(依 battleId 直查 GetItem;PvP 關係查詢走 monster 表 `PVP#` item,見存疑1) |

> 為何獨立表(STAGE2 決策①):戰鬥生命週期(秒~分)與 churn(高開高關 + TTL GC)與怪獸長壽 item 完全不同,混表會污染 monster PK 的熱點與 TTL。

---

## 2. Item 欄位表

> 慣例:epoch **ms**(除 `leaseExpireAt` 為秒);玻璃箱裸值禁直出;屬性不存在 ≠ DDB NULL(未設就不寫);空 SS 不寫;巢狀計數 `SET + if_not_exists` 非 `ADD`。

| 屬性名 | 型別 | 語義 | 說明 |
|---|---|---|---|
| `battleId` | S | **PK**,單場戰鬥唯一鍵 | ULID(開戰生成,時間可排序);結算冪等靠 `state=ACTIVE`+ClientRequestToken(version 已移記憶體,P0-2) |
| `state` | S | 場次生命狀態 | enum `ACTIVE`(進行中)/`RESOLVED`(已結算)。**存活判斷靠此 + `leaseExpireAt` 比時間戳,絕不靠 TTL 是否已刪**(見鐵律①) |
| `battleType` | S | 戰鬥種類 | enum `PVE`/`PVP`(已定案);預留 `BOSS`/`RAID`/`QUEST`/`TREASURE`(存疑6) |
| ~~version~~(移出 DDB) | — | **回合版本留記憶體**(Codex 階段6 P0-2) | 每回合 +1 在 bot View 記憶體,**不落 DDB**(回合零 DDB 寫);若落 DDB version 會停在 0 使結算條件形同無效→ DDB 結算冪等改靠 `state=ACTIVE`,不靠 DDB version |
| ~~action_id~~(移出 DDB) | — | **互動去重留記憶體** | 按鈕 turn_id/action_id 在 View 記憶體去重;DDB 側結算冪等 = `state=ACTIVE` 條件 + 結算 ClientRequestToken |
| `attackerId` | S | 攻擊方(先按攻擊者)Discord userId | 對應 M#CORE 之 PK;結算寫回此人 M#CORE |
| `defenderId` | S | 防禦方 | PvP=對方 `userId`;PvE=`NPC#<templateId>#<spawnUlid>`(存疑7) |
| `attackerRef` | M | 攻擊方開戰快照(啟動資訊) | `{ userId:S, race:S, stage:N, pos:{ x:N, y:N }, snapAt:N(ms) }`——只存啟動/相剋/重生所需最小集,**不快照 build**(存疑3) |
| `defenderRef` | M | 防禦方開戰快照 | 同上結構;PvE 存 NPC 模板 `race/stage/地形強度` |
| `leaseExpireAt` | N | **⚠️ epoch 秒** · TTL 屬性 | 崩潰自癒租約:`Math.floor(Date.now()/1000)+windowSec`(開戰時 window≈整場硬上限+寬容,例如 10 分;結算後縮成 ~5 分交 GC)。**只做垃圾回收(可延遲 48h),絕不當即時鎖** |
| `resolvedReason` | S | 結算原因(僅 RESOLVED) | enum `KO`/`FLEE`/`AFK`/`TIMEOUT`/`DRAW`(對應設計冊 KO/逃跑/L2 AFK確定性/L3硬上限/3回合無互動平手) |
| `resolvedAt` | N | 結算時間(ms,僅 RESOLVED) | 稽核/冪等窗口 |
| `createdAt` | N | 開戰時間(ms) | 共通稽核欄(對齊 STAGE3);≈ ULID 內時戳,冗餘便於掃描 |
| `updatedAt` | N | 最後寫入(ms) | 每次 UpdateItem SET |

**不落此表的暫態(全放 bot 記憶體 asyncio/View,STAGE1 §1-3 + 設計冊):** 即時 `HP`、`pH`、狀態層(DoT/控場/buff 疊層與倒數)、當前回合數、8 步管線中間結果、15 秒回合計時、命中/傷害計算暫存。→ 崩潰即棄(不 resume)。

---

## 3. 寫入路徑

> 一場**只寫 1 次結算**(合併單筆 <1KB;PvE≈1–2 寫、PvP≈2–3 寫,STAGE1)。高頻回合互動**零 DDB 寫**(純記憶體 + `edit_message`)。

### 3.1 開戰(條件寫,防重複開戰 + 承接崩潰自癒)
```
開戰 = 單一 TransactWrite(原子:開戰鎖 + Khui RMW 扣 + 建租約)。
DAO 先讀雙方 M#CORE 拿 khui 快照(base+ts)+ activeBattleId,再:
TransactWrite (ClientRequestToken=<開戰冪等碼>) {
  ① Update M#CORE(attacker):
       SET activeBattleId=<新ULID>, activeBattleExpireAt=now+WINDOW_MS,
           khui=:computedKhui-2, khui_last_ts=now, updatedAt=now
       Condition: (attribute_not_exists(activeBattleId) OR activeBattleExpireAt < :nowMs)  // 開戰鎖:不在別場(P0-1)
                  AND khui=:readBase AND khui_last_ts=:readTs                              // khui RMW 樂觀鎖(P0-3)
  ② Update M#CORE(defender)（PvP 才有;PvE 無此顆）:
       SET activeBattleId=<同ULID>, activeBattleExpireAt=now+WINDOW_MS
       Condition: attribute_not_exists(activeBattleId) OR activeBattleExpireAt < :nowMs      // 防被重複拉入戰
  ③ Put battle:
       { battleId, state=ACTIVE, battleType, attackerId, defenderId, attackerRef, defenderRef,
         leaseExpireAt=floor(now/1000)+WINDOW_SEC, createdAt=now(ms), updatedAt=now(ms) }
       Condition: attribute_not_exists(battleId)
}
```
- **防重複開戰(P0-1)**:靠 ①② 的 `activeBattleId` 鎖(不存在或已過期才可開),**非** `attribute_not_exists(battleId)`(每次新 ULID 擋不住)。TOCTOU race 被鎖擋——兩個並發開戰只有一個過鎖條件、另一個整筆 rollback(Khui 也不扣)。
- **Khui 扣 RMW(P0-3)**:khui 是 virtual(lazy 算),Condition **不能**寫 `khui≥2`(算不了 `khui+regen`)→ DAO 先讀 base+ts 快照,交易條件 `khui=:readBase AND khui_last_ts=:readTs` 樂觀鎖,SET `computedKhui-2`;併發或自然回復使快照失效則 condition 失敗重讀重試。扣後不退還(棄賽亦然)。
- **崩潰自癒**:`activeBattleExpireAt`/`leaseExpireAt` 過期 = 鎖自動釋放、可重開。
- **崩潰自癒**:舊場若 bot 崩潰未結算 → 其租約 `leaseExpireAt`(秒)到期後 DDB 自動 GC(免費);**但**自癒判定**不等** DDB 真的刪(TTL 可延遲 48h),而是**開戰/互動時比** `now > leaseExpireAt*1000 || state=RESOLVED` → 過期租約視同不存在、可開新場。

### 3.2 結算(KO/逃跑/3回合平手 → 1 次寫,同交易釋放租約)
```
TransactWrite (ClientRequestToken = <場次結算冪等碼>) {
  ① Update M#CORE(attacker): SET xp += drop.xp(PvE), reputation ±= Δ, last_interaction=now,
        battle_deaths = if_not_exists(battle_deaths,0)+1(若戰死), pos=重生落點(若敗),
        REMOVE activeBattleId, activeBattleExpireAt,        // 釋放開戰鎖
        updatedAt=now(ms)
  ①b (PvP) Update M#CORE(defender): 同上結算雙方(reputation/pos/battle_deaths/last_interaction
        /釋放鎖)——**PvP 必須寫雙方 CORE**(Codex P1-4),PvE 只寫一顆;builder 合併同 key
  ② Update battle(此 battleId): SET state=RESOLVED, resolvedReason, resolvedAt=now(ms),
        leaseExpireAt=floor(now/1000)+GC_SEC(縮短交 GC), updatedAt=now(ms)
        ConditionExpression: state = ACTIVE                 // 冪等:第一次結算即翻 RESOLVED,其餘拒(P0-2,不靠 DDB version)
  ③ (PvP) Update PVP#<opponentId> ×2(雙向): SET lastEndAt=now
        (+ SET lastRewardAt=now 僅當 Condition attribute_not_exists(lastRewardAt) OR lastRewardAt<=cutoff)  // 24hr 首戰業務閘 P1-5
        // lazy-prune·不開 TTL(monster 表永不開 TTL)
  ④ (PvP 掉落/道具) Update INV#<itemId>: SET qty = if_not_exists(qty,0)+n     // monster 表 backpack, STAGE2 決策⑦
}
```
- **permadeath**:`battle_deaths+1` 達 3 → 引擎觸發永久死亡流程(轉生/封存,屬階段4/引擎),schema 面只保證 CORE 有 `battle_deaths` 狀態型欄(STAGE3)。
- **PvP 不給 EXP**:只 `reputation` + 掉落 + 地圖優勢(設計冊)。EXP 僅 PvE/日常互動。聲望懲罰(打低 2 階以上 → 聲望反降)在 Δ 計算內。
- **冪等雙層**:同 item 冪等靠 ②的 `state=ACTIVE` 條件(第一次結算翻 RESOLVED,其餘拒;**不靠 DDB version**,回合版本在記憶體,P0-2);**跨 item 轉資源**(碎片/道具/雙向 PVP)靠 `TransactWrite` + `ClientRequestToken`。

### 3.3 AFK 確定性結算(L2)
- 觸發:連續 2–3 回合無動作(引擎 asyncio 計時器,掛機方不需操作)。判 AFK 前給 **~30 秒重連寬容窗**(區隔真斷線 vs 惡意掛機)。
- 動作:**與 3.2 相同結算路徑**,`resolvedReason=AFK`;結局 = 記憶體引擎算「之後都不出手」的確定性結果(該死照死、DoT 穩贏照贏,**不**給較輕特殊結局 → 逃避誘因歸零)。
- 崩潰邊界見存疑4(暫態失即棄場、不補算)。

### 3.4 殭屍租約回收(自癒,零人工)
- 純靠 DDB 原生 TTL 掃 `leaseExpireAt`(秒)→ 過期 item 免費刪(可延遲最多 48h,可接受,因存活判斷不靠刪)。
- **無**需背景 job / cron(對齊 STAGE1「lazy 零背景 job」+設計冊崩潰安全方案B)。任何互動遇到過期租約當場當「可重開」處理。

---

## 4. PvP 特有狀態:存哪一顆(釐清)

| 狀態 | 語義 | 存哪 | 理由 |
|---|---|---|---|
| 1 分 CD | 同對象戰後 60s 冷卻(期間被打可反擊互換攻方) | **monster 表 `PVP#<opponentId>` 關係 item**(存疑1) | 跨場、per-pair;租約結算後即 GC,存不住;bot 記憶體重啟即失憶 → 必須落 DDB。比 `now−lastEndAt<60s` |
| 同對 24hr 首戰獎勵 | 同兩人 24h 內只有第一場給聲望+道具 | **同上 `PVP#<opponentId>`**,`lastRewardAt` | 比 `now−lastRewardAt≥24h`;**lazy-prune 不開 TTL**(monster 表永不開 TTL,見覆核) |
| 敗北重生位置(≥8格/回出生區/偏🪨/新手更遠) | 改怪獸座標 | **M#CORE.pos**(結算 UpdateItem 內 SET) | 座標屬玩家域(STAGE1 §1-3);挑格演算法讀擊敗者 pos(取自開戰快照 `*Ref.pos`)+ 世界表格佔用(階段7 依賴) |
| 反擊窗口 | CD 期間防方可立即反攻(角色互換) | 讀 `PVP#` 的 `lastEndAt`(在 CD 內)即允許新開戰、角色互換 | 純讀判定,無新持久狀態 |
| 戰鬥暫態(HP/pH/狀態層/回合) | 戰中即時 | **bot 記憶體**(不落庫) | 設計冊 + STAGE1 明定 |

**一句話**:租約 = **單次相遇的啟動 + 冪等 + 自癒**;**跨場關係**(CD/24hr)歸 monster 表 `PVP#` item;**位置/永久死亡/資源**歸 M#CORE / INV#;**戰中暫態**歸記憶體。

---

## 5. 鐵律落實對照(自檢)

| # | 鐵律 | 本 schema 如何落實 |
|---|---|---|
| ① | TTL 只做 GC、絕不當即時鎖 | 存活判斷一律比 `state=ACTIVE && now≤leaseExpireAt*1000`(§3.1);TTL 僅免費 GC 殭屍(§3.4);租約秒/ms 分離(鐵律①) |
| ② | 戰鬥暫態不落此表、放記憶體 | §2 明列 HP/pH/狀態層/回合全在 bot 記憶體;崩潰即棄不 resume |
| ③ | 結算 1 次 | §3.2 單一 TransactWrite:M#CORE 塞全部變動 + 標記租約 RESOLVED + permadeath +1;高頻回合零 DDB 寫 |
| ④ | 冪等雙層 | 同 item = `state=ACTIVE` 條件(§3.2②,不靠 DDB version,P0-2);跨 item 轉資源 = TransactWrite + ClientRequestToken(§3.2 header);回合去重 = 記憶體 turn_id/action_id(§2,不落 DDB) |
| ⑤ | 防重複開戰 + 崩潰自癒 | **防雙開靠 M#CORE 開戰鎖**`activeBattleId`+`activeBattleExpireAt`(開戰 TransactWrite 條件雙方鎖不存在或已過期,P0-1);battle 表 Put `attribute_not_exists(battleId)` **只防 ULID 重寫**(理論上不撞);開戰前置比 CD/座標;過期鎖/租約視同可重開=崩潰自癒(§3.1/§3.4) |
| — | 空 SS 不寫 / 巢狀 SET+if_not_exists 非 ADD / 未設不寫 | `battle_deaths`/`INV.qty` 用 `SET if_not_exists(x,0)+n`(§3.2,呼應 STAGE3 覆核「ADD 不作用於巢狀 Map」);快照 M 只塞有值欄 |

---

## 6. DAO 層注意(給階段9)

- **秒/毫秒封裝**:`leaseExpireAt` 讀寫一律在 DAO 內 `*1000`/`Math.floor(/1000)`,對外只暴露 ms;單測明確斷言「寫進去的是 10 位數秒級」。（本 repo 首個真 TTL 表,無前例可抄,格外小心。）
- **存活判定 helper**:`isBattleAlive(item) = item.state==='ACTIVE' && Date.now() <= item.leaseExpireAt*1000`——禁止任何地方靠「GetItem 拿不到 = 死」(TTL 刪可延遲 48h)。
- **transaction builder**(承 STAGE2 P1-4):結算跨 M#CORE/INV#/PVP# 多顆時,合併「同一 item 的多個 mutation」成一個 Update,避免同交易重複操作同 key 被 DDB 拒。
- **沿用** `TrainTycoonTransitDAO` 的泛用 `TransactWriteCommand` 提交樣式(見 `DAO/DDB/TrainTycoonTransitDAO.js`)。
- **PVP# 清潔策略**(Codex P2·非阻斷):讀到過期 `PVP#<opponentId>`(`now−lastEndAt > 24h+grace`)時**順手 Delete/覆寫**,避免長期累積殭屍列(monster 表不開 TTL 故靠此 lazy 清)。

---

## ✅ Claude(Opus)覆核 — 2026-07-17

整體:優秀。TTL 秒/毫秒處理到位(頭號鐵律+逐欄+DAO 封裝)、租約非即時鎖、暫態不落庫、結算 1 次。**發現 1 個安全隱患 + 存疑1/2/3 拍板**(註:結算冪等原寫「三元組」,經 Codex P0-2 修正為 `state=ACTIVE`+記憶體 version):

**🔴 安全隱患:別在 monster 表開原生 TTL**
- 草案 PVP# 關係 item 建議帶 `ttl`(秒)交 DDB GC。但 PVP# 放 monster 表(PK=userId),而 **monster 表裝的是永久玩家資料(M#CORE/BUILD/PROGRESS/PERMANENT/ACHIEVE)——在這張表開 native TTL 是 foot-gun**:任何 bug 誤寫 `ttl` 到永久 item 就被靜默刪除。
- **改**:PVP# CD/24hr **不開 native TTL**,改 **lazy-prune**(讀時 `now−lastEndAt > 24h+grace` 視同不存在、下次相遇覆寫)。累積量有界(每對手一顆)可接受;**monster 表永不開 TTL**保永久資料安全,**只有 battle 表(全 ephemeral)開 TTL**。

**存疑拍板**:
- **存疑1**:(a) PVP# 歸 monster 表 ✓(關係屬玩家域);(b) 獨立 `PVP#<opponentId>` SK item ✓(非 M#CORE map、免膨脹)——但**去掉 `ttl` 欄改 lazy-prune**(見上)。⚠️ PVP# 是**新 SK item family**,要補進 STAGE2/4 monster 表 item 清單(定稿時回填)。
- **存疑2**:pos 切分 OK(重生落點寫 M#CORE.pos、挑格演算法屬引擎、格佔用查詢依賴階段7 世界表)✓
- **存疑3**:不快照 build ✓(戰中不可改 build、結算重讀 M#CORE 即可省 item size;anti-cheat 靠「戰中禁改 build」規則非定格)
- **存疑4/5/6/7**:背書——AFK 崩潰即棄場、租約結束標 RESOLVED+短 TTL(冪等哨兵勝過即時 Delete)、battleType 預留 enum、PvE `NPC#` 前綴。

**回 Codex #2(三層終結重複結算)**:`ConditionExpression state=ACTIVE` 已擋——L1/L2/L3 任一先結算即設 RESOLVED,其餘結算條件失敗 no-op,不只靠 version。sound。

## 🔍 Codex 階段6 二驗 findings + Claude vet 處置(2026-07-17)

3 P0 + 3 P1 全採納(P0 都是真問題、互相關聯):

| # | finding | 處置 |
|---|---|---|
| P0-1 | 開戰防重複 race window(`attribute_not_exists(battleId)` 擋不住同時開兩場) | 加**開戰鎖** M#CORE `activeBattleId`+`activeBattleExpireAt`,開戰 TransactWrite 條件雙方鎖不存在或過期(STAGE3 補欄+§3.1 改) |
| P0-2 | `version` 每回合+1 與「回合零 DDB 寫」矛盾 | version/action_id **移出 DDB 留記憶體**;DDB 結算冪等只靠 `state=ACTIVE`(§2/§3.2/§5 改) |
| P0-3 | Khui 扣 2 condition 算不了 virtual khui | 改 **RMW 樂觀鎖** `khui=:readBase AND khui_last_ts=:readTs` SET computedKhui-2(§3.1 改) |
| P1-4 | PvP 結算不能只寫 attacker CORE | PvP 寫**雙方 CORE**、PvE 一顆(§3.2 ①b) |
| P1-5 | 24hr 首戰獎勵需業務閘非只 ClientRequestToken | PVP# 發獎帶 `attribute_not_exists(lastRewardAt) OR lastRewardAt<=cutoff` 條件(§3.2 ③) |
| P1-6 | PVP# 新 item family 需回填 STAGE2/4 | 已回填 STAGE2 ERD(順補上漏的 PLAYER#ACHIEVE) |

**開戰鎖 = 崩潰自癒二用**:`activeBattleId`/`activeBattleExpireAt` 既防雙開(P0-1),過期又=鎖釋放可重開(自癒),與 battle 表 `leaseExpireAt` 呼應;「玩家一次一戰」語義由此鎖保證。

## ➡️ 交回 / 下一步
- Claude 覆核上方**存疑1/2/3**(PvP CD/24hr/重生/快照粒度落點)拍板後,可去 DRAFT。
- ✅ **依賴階段7 已結案**(2026-07-17,STAGE7b 定稿):重生挑格 + 相鄰格佔用查詢由 `sweetbot-yajunban-world`(`PK=zone#bucket`,決策⑫–⑯)提供;重生落點/相鄰 PvP/偷菜的格佔用查詢接法見 [STAGE7b](./STAGE7b-world-spatial.md)。
  - ⚠️ **回饋:重生結算 M#CORE Update 要升級**(STAGE7b Codex P1-3/P1-4):
    - **不可**在結算交易裡巢狀呼叫 world `moveTo()` 再產生**第二個** M#CORE Update(DDB 同交易禁對同 key 重複操作)→ transaction builder 把「戰鬥結算(xp/reputation/battle_deaths/釋放 activeBattleId)**+** pos/posVersion 重生落點搬移 **+** 租約釋放」**合併成同一顆 M#CORE Update**,再加 `Delete 舊 OCC` / `Put 新 OCC`(world 表)。
    - 該 M#CORE Update 需帶 **`ConditionExpression posVersion=:read`** 樂觀鎖(重生不扣 Khui、無天然防護)、SET `posVersion+1`,OCC 寫同值。
    - 淨效果:PvE 重生結算 = 1 顆 M#CORE(合併) + 2 顆 world OCC(Delete/Put);PvP 再加敗方對稱處理。仍單一 TransactWrite,遠低於 100 item/4MB。
- Codex 二驗建議聚焦:①秒/毫秒是否真的到處分清、②結算 TransactWrite 的 `version` 條件是否足以擋所有重送路徑(L1/L2/L3 三層終結會不會多次觸發同場結算)、③PVP# 關係 item 雙向寫是否有孤兒/半寫風險。
