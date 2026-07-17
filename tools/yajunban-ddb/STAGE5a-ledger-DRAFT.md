# 牙菌斑怪獸 · DDB 資料模型 — 階段5a:`sweetbot-yajunban-ledger` 流水帳表 schema

> **定稿 · Claude 覆核 + Codex 二驗已合流(2026-07-17)**:3 P1 併入(`entryClass` 防雙計、gen transaction condition、per-event 冪等閘)。雙軌帳無硬傷。
> 交接文件 · 產出日期 2026-07-17 · 承接 [STAGE2-schema-decision.md](./STAGE2-schema-decision.md)(決策①:ledger 獨立表 PK=userId·SK=`<TYPE>#ts#ulid` 權威)+ [STAGE4-schema-DRAFT.md](./STAGE4-schema-DRAFT.md)(M#PROGRESS/PERMANENT 定稿·寫入路徑)+ [STAGE1-access-patterns.md](./STAGE1-access-patterns.md)(1-4 任務發獎/碎片、1-5 fortress-ledger 分界)
> 語義來源:設計冊 `score-repo/yajunban_design.html`(section-quest「完成/歷史→ledger 加 QUEST# 流水」、section-growth 礦物碎片來源、section-data 資料層拍板;canonical)。型別慣例:`sweetbot-next/DAO/DDB/PlayerPointLogDAO.js`(牙齒流水欄位風格)+ STAGE3 共通慣例(epoch ms、createdAt/updatedAt、玻璃箱)。

---

## ⚠️ 待確認/存疑點(設計時不確定,交覆核/二驗拍板)

1. **QUEST# 事件列 vs 資源列的雙軌**(最大設計題):草稿採「**一資產一列**(EXP#/FRAGMENT#)+ QUEST# 為事件稽核列(含獎勵包快照,不參與重放)」——任務發獎的 EXP/碎片會在**同一 TransactWrite** 另發 EXP#/FRAGMENT# 資源列(refId 串回 QUEST# 的 ulid)。優點:重放重建邏輯單一型別(只掃資源列加總)、對帳清楚。代價:一次任務繳交多 1–3 個 Put(~各 1 WRU,中頻可接受)。**替代案 B**:QUEST# 列內嵌 rewards 就是唯一紀錄、重放要解析兩種列 → 省寫但重放/對帳兩套 code path。待二驗選邊。
2. **戰鬥結算 xp 記不記 EXP#**:STAGE1 1-3 戰鬥結算=「單筆 UpdateItem 塞全部」(PvE≈1–2 寫)。若要記 EXP# 就得升級成 TransactWrite(2 item,寫成本×2)。草稿立場:**v1 不記**(戰鬥 xp 屬中頻微量,非「有份量事件」),與 A 層被動同歸「不記名單」;若日後戰鬥經濟要對帳再開。待拍板。
3. **EXP# 是否擴及 charm/reputation**:任務可給 EXP/魅力/聲望/友好度(section-quest 可給清單)。這些全是**當代欄**(轉生即清,重建價值低)。草稿:EXP# 的 `asset` 欄 v1 只用 `"xp"`;charm/reputation 變動不獨立記列(QUEST# 事件列的 rewards 快照已含,供稽核)。若要開,用 `asset` 值擴充即可、**不加新 TYPE**。待確認。
4. **反哺兌換的雙表雙帳**:碎片素→礦物碎片的兌換,fortress-ledger 已定 `S#season#EX#ts#ulid` 記「碎片素支出」(STAGE1 1-5/設計冊 3906)。但 yajunban-ledger 的 FRAGMENT# 若不記「碎片入帳」,重放就無法重建 `PERMANENT.shards` 完整值。草稿:**兌換 TransactWrite 同時 Put 兩表各一列**(fortress EX#=支出、yajunban FRAGMENT#=入帳,refId 互指)——重放只認 FRAGMENT#,EX# 供堡壘經濟對帳。跨表同交易 DDB 允許(TransactWrite 跨表 OK)。待二驗確認不算雙重記帳。
5. **balanceAfter 不存**:TransactWrite 的 Update 無法在交易內取「更新後值」→ 存 balanceAfter 需改 read-modify-write(多一次強讀+樂觀鎖,違反高頻寫預算)。草稿:**一律不存**(對齊 sweetbot-player-point-log 只存 variation 的慣例);餘額對帳=重放加總 vs 主 item 現值。若某流程本就強讀快照(如轉生)也**不**例外開欄,免半殘語義。待背書。
6. **season / gen 維度欄**:怪獸域流水的自然維度是**世代 gen**(轉生正交於賽季;`M#CORE.xp` 是當代值,重放重建必須按 gen 切段)。草稿:每列必帶 `gen`(寫入當下 `PERMANENT.generation`);`season` 選帶(寫入當下 seasonId,供未來 season-index GSI 免 backfill)。存疑:seasonId 的取值來源(全域 config?)本階段未定,若 v1 拿不到就先不寫該欄(**屬性不存在,不存 null**——STAGE4 P0-1 慣例)。
7. **ts 字典序與位數**:SK 中 `ts`=epoch ms 的 `String(Date.now())`,現為 13 位、到 2286 年前字典序=時間序,**不補零**(對齊 fortress-ledger 設計冊寫法 `"S#"+seasonId+"#EX#"+ts+"#"+ulid`)。若二驗要求防呆可改補零至 14 位,但兩邊要一致。待確認。
8. **ULID 依賴**:sweetbot-next 目前**無 ulid 套件**(已 grep 確認 package.json/原始碼皆無)。實作需加 `ulid` npm 依賴,或退而用 `crypto.randomUUID()` 當尾綴(唯一性同樣成立,只失去 ulid 自含時間戳的可讀性;排序已由 SK 的 ts 段承擔)。屬階段9 DAO 實作決定,schema 不受影響。
9. **候選型別不納 v1**:菌圃收成(STAGE1 1-4「產出入背包/ledger」措辭含糊)、轉生事件稽核(REBIRTH#)、成就換獎——正典來源(STAGE1 實體清單/STAGE2 決策①/設計冊 3149)只點名 EXP/FRAGMENT/QUEST 三型。草稿**不編造新型別**;收成產出=道具入 `INV#`(STAGE4 已定),要不要留流水待產品拍板(若要,建議走 QUEST#同款事件列思路另立 TYPE,別塞爆 FRAGMENT#)。

---

## 🚧 界線(務必先讀):牙齒🦷 不進這張表

| 資源 | 走哪本帳 | 依據 |
|---|---|---|
| **牙齒🦷**(跨產品共用貨幣,甜甜/両雀共用) | **既有 `sweetbot-player-point-log`**(givePoint 埋點,PK=discordId、SK=ISO createdAt、欄位 pointType/variation/reason) | 牙齒=跨產品共用遊戲幣正典;yajunban 任何收/付牙齒(如孵化投入牙齒加成)一律走 givePoint 既有管線,**絕不在 yajunban-ledger 記牙齒** |
| **堡壘經濟**(🍬糖蜜/🧱材料/兵/掠奪 loot/碎片素支出/季末歸檔) | **`sweetbot-yajunban-fortress-ledger`**(已定案:PK playerId、SK `S#season#EX/LOOT/ARCHIVE#...`、season-index) | STAGE1 1-5 + 設計冊 3834/3903–3907 |
| **yajunban 遊戲內資源**(EXP、礦物碎片、任務完成/發獎歷史) | **本表 `sweetbot-yajunban-ledger`** | STAGE2 決策① + 設計冊 3149 |

- **碎片素**(fortress 慢產資源)的產出/支出=堡壘域 → fortress-ledger;碎片素兌換**成礦物碎片**的「碎片入帳」才落本表 FRAGMENT#(見存疑④)。
- 本表只記 **yajunban 內部資源流水**,是牙菌斑自己的帳;與牙齒流水、堡壘流水三本帳**各自獨立、refId 可互串**。

---

## 📌 表與主鍵(對齊 STAGE2 決策①⑤)

- **表**:`sweetbot-yajunban-ledger` · PAY_PER_REQUEST · ap-southeast-1
- **PK** = `userId`(S,= Discord user id,`String()`,對齊 monster 表)
- **SK** = `sk`(S)= **`<TYPE>#<ts>#<ulid>`**
  - `TYPE` ∈ `EXP` / `FRAGMENT` / `QUEST`(v1 全集,實際歸納自 STAGE1 實體清單、STAGE2 決策①、設計冊 3149;**不多不少**,候選見存疑⑨)
  - `ts` = epoch **毫秒** `String(Date.now())`(13 位,字典序=時間序至 2286;見存疑⑦)
  - `ulid` = ULID(唯一性尾綴,同毫秒多列不撞;排序主責在 ts 段;依賴見存疑⑧)
  - 例:`FRAGMENT#1752720000000#01J2ZK8Q3WXYZ...`
- **GSI**:**初期不建**(STAGE2 決策⑤明文「ledger 初期不建,需要再加 season-index」)。列帶 `season`/`gen` 屬性=未來加 GSI 免 backfill。
- **append-only**:列一經寫入**永不 Update/Delete**(流水鐵律);`updatedAt` 恆等於 `createdAt`(留欄純為對齊 STAGE3 共通稽核欄慣例)。
- **保留策略:永久**。不設 TTL、不隨轉生/換季清(轉生清的是 M# 三顆,本表跨世代累積);定位=可 backfill 重建 `PLAYER#PERMANENT.shards` 等永久資產(類比報稅系統 point-log 永久保留可隨時 backfill 的先例)。
- **玻璃箱**:流水裸值(delta/累計)**禁直出 API**;玩家可見的「取得紀錄」走 DTO 帶名化(「獲得 🔴紅碎片 ×3」),EXP 裸數字不出面板(STAGE3 慣例)。

## 🏷️ SK 型別前綴列舉(v1 正典)

| TYPE | 記什麼 | 觸發來源(實際歸納) | 依據 |
|---|---|---|---|
| `EXP#` | EXP 有份量入帳(asset=`xp`) | 主線任務大塊 EXP、進化/里程碑;**不含** A 層被動微量與摸頭/餵食零星 xp(高頻寫爆,見「不記名單」)、戰鬥結算 v1 不記(存疑②) | STAGE1 實體清單「EXP# 前綴」+ section-quest 主線「大塊 EXP」 |
| `FRAGMENT#` | 礦物碎片增減(asset=六色 `red/blue/green/purple/yellow/white`) | 入帳:BOSS 掉落、PvP、賽季獎勵、腐蝕特定地形、成就(極少)、堡壘掠奪/內政、反哺兌換(碎片素→碎片,存疑④)、任務關鍵里程碑、轉生繼承結轉;扣除:碎片兌換數值(**負 delta**) | section-growth 碎片取得清單 + STAGE1 1-2「碎片投入/跨轉生保留」+ 1-4「任務完成獎勵…碎片素」 |
| `QUEST#` | 任務完成/發獎**事件稽核列**(含獎勵包快照;不參與資源重放,存疑①) | 繳交任務(主線/日常/週常/挑戰)、群感特殊支線完成 | 設計冊 3149「完成/歷史→既有 ledger 加 QUEST# 流水」(canonical)+ STAGE1 1-4 任務完成獎勵發放 |

**不記名單(防寫爆,一樣是拍板)**:A 層被動吸收(高頻微量)、摸頭/玩耍/整理/鼓勵、餵食零星 xp、靈魂 6 軸滑動、群感印記累積、菌氣/移動——這些高頻低額變動**只動主 item,不落流水**。ledger 只收「有份量事件」。

---

## 📄 entry 欄位表(每列)

| 屬性名 | 型別 | 語義 | 說明 |
|---|---|---|---|
| `userId` | S | PK,Discord user id | `String()`,對齊 monster 表/point-log 的 discordId 角色 |
| `sk` | S | SK,`<TYPE>#<ts>#<ulid>` | 見上;唯一性靠 ulid 尾綴 |
| `type` | S | 型別冗欄:`EXP`/`FRAGMENT`/`QUEST` | 與 SK 前綴同值,免字串切割、供 FilterExpression;對齊 point-log `pointType` 風格 |
| `entryClass` | S | **重放分類**(Codex P1-3):`RESOURCE`(EXP#/FRAGMENT#,參與重放加總)/`EVENT`(QUEST#,純稽核不重放) | DAO 只提供 `replayResources()` 掃 `entryClass=RESOURCE`,杜絕後人誤掃 `QUEST#.rewards` 雙計 |
| `asset` | S | 資源標的 | EXP#=`"xp"`(存疑③可擴);FRAGMENT#=`"red"/"blue"/"green"/"purple"/"yellow"/"white"`(六色,section-growth);QUEST# **不帶此欄**(事件列) |
| `delta` | N | 增減量,**正=入帳、負=扣除** | 對齊 point-log `variation`;FRAGMENT# 兌換數值=負;QUEST# 不帶此欄 |
| `reason` | S | 來源事由(機器可讀 slug) | 如 `quest_claim` / `boss_drop` / `pvp_win` / `season_reward` / `terrain_corrode` / `achievement` / `fortress_raid` / `fortress_exchange` / `rebirth_inherit` / `stat_exchange`;對齊 point-log `reason`,供聚合統計 |
| `refId` | S | 關聯 id(可選,無關聯**不寫屬性**) | questId / battleId / raidId / fortress-ledger EX 列 ulid / achId;任務發獎的資源列指回同交易 QUEST# 列 ulid(存疑①) |
| `questId` | S | (僅 QUEST# 列)任務靜態 id | 事件列主體;搭 `questType`(`main/daily/weekly/challenge/emergent`) |
| `rewards` | M | (僅 QUEST# 列)獎勵包快照 | 如 `{ xp:N, shards:M{red:N,...}, items:M{<itemId>:N}, charm:N, reputation:N }`——**稽核用,不參與重放**(存疑①);缺項不寫 |
| `season` | S | 賽季 id(可選) | 寫入當下賽季;拿不到就不寫屬性(存疑⑥);未來 season-index GSI 的鍵材料 |
| `gen` | N | 世代數 | 寫入當下 `PERMANENT.generation`;**重放重建當代欄(xp)必須按 gen 切段**的依據 |
| `createdAt` | N | 建立時間 epoch ms | 與 SK 的 ts 同值(N 型,查詢/顯示免解析 SK);STAGE3 慣例 epoch ms,**不用 ISO**(point-log 的 ISO SK 是舊表歷史包袱,不沿用) |
| `updatedAt` | N | = createdAt | append-only 列不可變;留欄純為 STAGE3/4 共通稽核欄一致 |

- **balanceAfter:不存**(存疑⑤:TransactWrite 內取不到更新後值,存了就要 RMW,不值)。
- 單列 ~200–400 bytes,寫 1 WRU;永久保留吃存儲(前 25GB 免費,量級無虞)。

---

## 🔗 寫入慣例(與主 item 同 TransactWrite)

流水**永遠與主 item 變更同一筆 `TransactWrite`**(帳實相符鐵律;DDB 支援跨表交易):

| 操作 | TransactWrite 內容 | 冪等閘 |
|---|---|---|
| 任務繳交發獎 | Update `M#PROGRESS.quests`(標完成,**條件:完成且未領**,STAGE4 P1-5)+ Update `INV#<reward>` / `PERMANENT.shards` / `M#CORE.xp` + **Put QUEST# 事件列 + Put EXP#/FRAGMENT# 資源列**(存疑①) | 主 item 條件失敗→整筆 rollback,流水不落 |
| 碎片入帳(BOSS/PvP/地形/成就/掠奪) | Update `PERMANENT.shards.<color>`(`SET =if_not_exists+:n`,巢狀禁 ADD)+ Put `FRAGMENT#`(正 delta) | 來源事件自身冪等閘(如 raid `state=RESOLVED→LOOTED` 條件) |
| 碎片兌換數值 | Update `PERMANENT.shards`(條件 ≥ 成本,負)+ Update `M#CORE.stats.<k>` + Put `FRAGMENT#`(負 delta,reason=`stat_exchange`) | 條件扣款失敗→rollback |
| 反哺兌換(碎片素→碎片) | Update fortress `res`(條件 ≥)+ Put **fortress-ledger** `EX#` + Update `PERMANENT.shards` + Put **本表** `FRAGMENT#`(refId=EX ulid;存疑④) | fortress res 條件 |
| 轉生碎片繼承結轉 | 併入轉生 5 顆 TransactWrite(+ Put FRAGMENT# reason=`rebirth_inherit`,若轉生有碎片加成才發列) | `generation=:readGen` 條件(STAGE4 P1-3) |

**冪等三層**(對齊 STAGE1 冪等機制節):
1. **主 item 條件寫是第一防線**——流水列與主 item 同交易,主 item 的狀態閘(未領/state/餘額條件)擋掉重複,流水自然不會雙寫。
2. **`ClientRequestToken`**:跨 item 轉資源的 TransactWrite 一律帶(STAGE1 1-3 明文),擋 10 分鐘內網路重送。
3. **SK 唯一性**:每列 Put 帶 `ConditionExpression attribute_not_exists(userId)`(防 ulid 撞列,理論上不會,防呆);**注意**:ulid 每次重試會變,SK 唯一性**不能**當業務冪等閘,業務冪等只能靠第 1、2 層。

## 🔍 查詢模式

| 查詢 | 作法 | 頻率 |
|---|---|---|
| 某玩家某型別全史 | Query PK=userId + `begins_with(sk, "FRAGMENT#")` | 低(後台/對帳) |
| 某玩家某型別時間範圍 | Query PK + `sk BETWEEN "FRAGMENT#<t1>" AND "FRAGMENT#<t2>#~"`(13 位 ms 字典序可比,同 point-log queryByDateRange 手法) | 低 |
| 某玩家全型別近況 | 三次 Query(各型別倒序 `ScanIndexForward=false` + Limit)——SK 型別前綴使單次 Query 無法跨型別按時間混排,**接受**(讀=低頻稽核,非熱路徑) | 低 |
| 重建 `PERMANENT.shards`(backfill) | Query PK + begins_with `FRAGMENT#` 全頁加總 delta(**分頁 loop `ExclusiveStartKey` 必做**,point-log 1MB 截斷教訓) | 極低(救災) |
| 重建當代 xp | Query `EXP#` + filter `gen=當前世代` 加總(gen 欄的存在理由) | 極低 |
| 賽季/全服統計 | v1 = 後台低頻 Scan;量大再加 season-index GSI(欄位已備,免 backfill) | 極低 |

**讀路徑鐵律**:本表**不進任何玩家熱路徑**(面板/戰鬥/任務刷新全走 monster 表 + lazy compute);ledger 讀=稽核/後台/救災專用。

---

## 🔴 DAO 層注意(給階段9)

1. **append-only**:DAO 只給 `putEntry`(含在 transaction builder 內)與 Query 讀;**不提供 Update/Delete 方法**。
2. **transaction builder 合流**(STAGE2 P1-4):任務發獎一次交易含多顆 monster item + 多列 ledger Put——builder 要合併同 key mutation,ledger 列本身各自獨立 key 無此問題。
3. **分頁 loop 必做**:所有 Query 照 PlayerPointLogDAO.queryByDateRange 的 `ExclusiveStartKey` loop 寫法,防 1MB 截斷低估。
4. **屬性不存在 ≠ null**:`refId`/`season`/`asset`(QUEST# 列)等可選欄,不適用時**不寫屬性**,絕不存 DDB NULL(STAGE4 P0-1 慣例)。
5. **ulid 依賴**:實作前確認加 `ulid` 套件或替代尾綴方案(存疑⑧)。

## ✅ Claude(Opus)覆核 — 2026-07-17

整體:紮實,型別前綴有正典出處不編造、界線寫死、冪等三層 +「SK 唯一性不當業務閘」正確。**無 bug**。
- **背書存疑①雙軌**(EXP#/FRAGMENT# 資源列 + QUEST# 事件列):重放只掃資源列加總、QUEST# 純稽核 = 單一 code path,勝過單軌解析兩種列。⚠️ 鐵律:重放**必須忽略 `QUEST#.rewards`** 避免雙計(檔內已註)。多 1–3 WRU/繳交可接受。交 Codex 二驗確認非雙重記帳。
- **背書界線**(牙齒→point-log / 堡壘→fortress-ledger / yajunban 內部→本表)+ **balanceAfter 不存** + **gen 切段重放**。
- 存疑⑧ ulid:退 `crypto.randomUUID()` 當尾綴完全可行(排序主責在 ts 段),不必為此加 npm 依賴——階段9 DAO 自決。
- 存疑②戰鬥 xp v1 不記 = 對(免把單筆 Update 升級成交易)。

## 🔍 Codex 階段5 二驗 findings(5a)+ Claude vet 處置(2026-07-17)

5a **無 P0**(雙軌大方向 Codex 認可)。3 P1 全採納:

| # | finding | 處置 |
|---|---|---|
| P1-3 | QUEST# 要標不可重放,防後人掃 rewards 雙計 | 已加 `entryClass=EVENT/RESOURCE` 欄;DAO 只 `replayResources()` 掃 RESOURCE |
| P1-4 | gen 寫入要補 transaction condition 防跨代錯寫 | 見下 gen 寫入規則 |
| P1-5 | 冪等不能只靠任務主 item,各資源事件要 stable event gate | 見下冪等強化 |

### gen 寫入規則(P1-4)
- 一般事件:讀當前 `PERMANENT.generation` 當 `gen`,**同交易 `ConditionExpression PERMANENT.generation = :readGen`**(防任務發獎與轉生 race 寫錯代)。
- 轉生交易:若產生新世代初始列,用 `newGen = oldGen + 1`。

### 冪等強化(P1-5)
- **各資源事件各自要 stable event gate**,不能只靠任務主 item:BOSS 掉落=戰鬥結算 state、PvP=同對 24hr 首戰閘、地形/成就=事件唯一 id、碎片兌換=餘額條件、raid=`state=RESOLVED→LOOTED`。
- `ClientRequestToken` 只短期(~10 分)防網路重送,**不當長期業務冪等**。長期冪等靠主 item 狀態轉換條件。

## ➡️ 交給下一步

1. 存疑①(事件列+資源列雙軌 vs QUEST# 單軌)、②(戰鬥 xp)、④(反哺雙表雙帳)= 需 Claude 覆核 + Codex 二驗拍板的三個主題。
2. 定稿後回頭把 STAGE2 決策①表格的 ledger SK 描述補上 v1 型別全集與「牙齒/堡壘不進本表」界線一句。
3. 建表指令(PAY_PER_REQUEST、無 GSI)排實作階段;階段5b(若有,如 battle 租約表 schema)另檔。
