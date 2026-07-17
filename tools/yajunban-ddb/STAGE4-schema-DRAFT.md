# 牙菌斑怪獸 · DDB 資料模型 — 階段4:`M#PROGRESS` / `PLAYER#PERMANENT` / `INV#<itemId>` / `APP#<appAccountId>` 欄位 schema

> **草稿 · 先不定稿(Codex #6:碰轉生保留邊界 / appAccountId,待再一輪二驗)**
> 交接文件 · 產出日期 2026-07-17 · 承接 [STAGE3-schema-DRAFT.md](./STAGE3-schema-DRAFT.md)(M#CORE/M#BUILD 定稿 + 慣例)+ [STAGE2-schema-decision.md](./STAGE2-schema-decision.md)(決策③④⑦⑧ 權威)+ [STAGE1-access-patterns.md](./STAGE1-access-patterns.md)(1-4/1-5 存取模式)
> 語義來源:設計冊 `score-repo/yajunban_design.html`(section-quest / -soul / -garden / -achievement / -items / -growth,canonical)。型別慣例:`sweetbot-next/DAO/DDB/*`(TrainTycoonStationDAO / PuzzleRoundDAO / DDBBaseDAO)。
> **本檔僅為草稿**:轉生保留邊界的顆粒度、繼承通道落哪顆、群感閾值是否進 item 尚未拍板;Stage3 的 Codex #6 明言 Stage4 可草稿但先不定稿,待二驗確認 `PERMANENT.appAccountId` / 轉生保留邊界後才去 DRAFT。

---

## ⚠️ 待確認/存疑點(設計時不確定,交 Codex/使用者拍板)

1. **轉生保留邊界的顆粒度(最大不確定)**:STAGE2 決策③已定「轉生 = 固定 `M#CORE`/`M#BUILD`/`M#PROGRESS` 三顆 Put 覆寫重置 + `PLAYER#PERMANENT` Update 保留累加」。但 `M#PROGRESS` 內部並非全部該重置:成就(achievements)、圖鑑、稱號在設計冊語義偏「跨世代保留」(section-achievement「首次芽孢輪迴/傳承祖傳天賦/第10世」等成就本質是跨代里程碑)。**存疑:成就到底算「當代進度(隨轉生清)」還是「永久檔案(進 PLAYER#PERMANENT)」?** 草稿暫把 achievements 放 M#PROGRESS(=轉生會清),並在待確認標紅——若使用者要成就永久,得把 achievements 整塊搬到 PLAYER#PERMANENT,或再拆一顆 `PLAYER#ACHIEVE`。**這顆邊界一定要拍板才可定稿。**
2. **繼承通道(section-quest「特殊支線 → 繼承通道」)寫哪顆**:群感湧現的特殊支線完成 → 寫「祖傳天賦節點 / 世代印記 / 芽孢機率傾向 / 靈魂深記」(STAGE1 1-4「繼承通道寫入」)。這四項全是**跨世代永久遺產** → 語義上屬 `PLAYER#PERMANENT`。但觸發點在任務(M#PROGRESS 的 quests)。草稿把「觸發判定讀 M#PROGRESS.quests、實際落庫寫 PLAYER#PERMANENT」→ 特殊支線完成 = **TransactWrite(Update M#PROGRESS 標記支線已領 + Update PLAYER#PERMANENT 寫遺產)**。存疑:芽孢機率傾向(下一代性狀軟傾向)要不要獨立欄 `bud_bias`,還是併入 soul_legacy。
3. **群感隱藏印記的閾值是否進 item**:印記**計數**(各主題累積)必進 M#PROGRESS(暗中累積、軟上限);但「隱藏閾值/組合表」是**靜態設定**(section-quest「閾值不明示」)→ 草稿主張閾值**不落怪獸 item**,放設定表(對齊 STAGE1「靜態定義不落 item」慣例),讀時 lazy 比對。若 Codex 認為閾值要 per-player 個化(活動/難度調參)再議。
4. **soul 6軸的儲存形狀**:草稿用單一 `soul.axes` Map(6 個 Number,近期加權滑動 lazy)。存疑:滑動加權需不需要存「近期樣本/半衰時間戳」才能算 lazy?若只存當前加權值 + `soul.updatedAt`,滑動衰減無法精確重算(缺歷史)。草稿採「存當前值 + 每次互動即時加權更新(EWMA 指數移動平均,只需舊值+新事件+時間差)」→ 免存歷史樣本。待 Codex 確認 EWMA 對「近期加權」語義夠不夠。
5. **個性標籤(personality tag)存 vs lazy 結晶**:section-soul「讀 soul 時 lazy 結晶」→ 標籤可純 lazy 算(免存)。但設計冊也要「漂移慣性/老靈魂難改 + 管理員可蓋章傳奇人格」→ 需存「當前結晶標籤 + 慣性錨 + 管理員覆寫旗標」。草稿存 `soul.tag`(當前結晶)+ `soul.tag_locked`(管理員蓋章)+ 慣性靠 `soul.axes` 本身的滑動慣性表達。待確認顆粒度。
6. **garden 畦位上限**:section-garden = Stage4 2畦 → S5 3畦 → S6 4畦(傳說體預留 5)。task 講「≤5畦」。草稿用 `garden.plots` Map(key=畦位 index `"0"`–`"4"`),畦數由 stage 派生(不另存 max)。存疑:pH 微環境是畦位固有屬性(開「畦位改良」升級才賦予)→ 存每畦 `ph` 欄。
7. **appAccountId 綁定方向**:STAGE2 決策④ = 綁定寫 `PLAYER#PERMANENT.appAccountId` + Put `APP#<id>` claim item(`attribute_not_exists(PK)` 唯一鎖)同 TransactWrite。存疑:換綁(改綁另一 APP 帳號)= Delete 舊 `APP#` + Put 新 `APP#` + Update PERMANENT 同交易;是否允許換綁、換綁冷卻,屬產品決策未定。
8. **INV 道具的 metadata 深度**:道具靜態屬性(稀有度/科學依據/施加狀態/教哪招/插槽)是**設定表**(section-items 60 道具目錄),**不冗存進每個 INV# item**;INV# 只存動態態(qty + 來源 + 取得時間 + 換季旗標)。存疑:唯一性道具(堆疊上限 1,如信物)是否該進 `INV#` 還是獨立 `RELIC#`(section-items「🏵️信物欄」與菌囊分離)→ 草稿標記信物走獨立 SK 待階段5 細化,本檔 INV# 先涵蓋消耗品/材料/裝備/技能書/特殊道具。
9. **每畦防禦(毒孢陷阱/EPS 護盾)限時態**:section-garden 防禦①②③ 帶限時。草稿存每畦 `defense` Map(`type` + `expireAt` epoch ms)。lazy 判過期。待確認毒孢陷阱啟動率(10–40%)是否進 item(草稿:率走設定表/天賦,item 只存「有無布防 + 到期」)。

---

## 📌 表與主鍵(對齊 STAGE2 決策①②③④⑦)

- **表**:`sweetbot-yajunban-monster` · PAY_PER_REQUEST · ap-southeast-1(四類 item 全在此表,PK overloading)
- **型別代碼**:S=String / N=Number / M=Map / L=List / SS=StringSet / BOOL=Boolean / B=Binary
- **時間戳**:一律 **epoch 毫秒 Number**(`Date.now()` / `Number(now)`,對齊 TrainTycoon/PuzzleRound;不用 ISO)——沿用 STAGE3 慣例
- **共通稽核欄**:每顆帶 `createdAt`(N,建立)、`updatedAt`(N,每次寫 SET)
- **累計型 vs 狀態型**:累計型(印記/軸/career_history/shards/generation)只增 → 可最終一致原子累加;狀態型(garden 成熟/畦位佔用)有邊界 → 條件寫。逐欄標注
- **🔍 玻璃箱**:群感印記計數、soul 6軸數字 = **🔒裸值·禁直出**,只出帶名個性標籤 / 模糊暗示。逐欄標 `🔒`
- **DDB 空集合陷阱(STAGE3 合流 #2)**:凡 **StringSet 一律「預設不寫、缺省視空、首次 `ADD` 建立」**;**Map 可用 `{}` 空預設**(DDB 允許空 Map)。逐欄標「用哪種」
- **巢狀 Map 計數地雷(STAGE3 Claude 覆核 #1)**:巢狀路徑計數**不可** `ADD map.key`(`ADD` 只作用頂層屬性)→ 必須 `SET map.key = if_not_exists(map.key, :0) + :inc`(item 層仍原子)。逐處標注

---

## 🧩 M#PROGRESS(混 · 內容循環) — PK=userId · SK=`M#PROGRESS`

任務進行中 + 群感隱藏印記 + 靈魂6軸 + 菌圃 + 成就。中寫頻率,目標 ~3 KB。lazy-create(首次接任務/成就時建,或納入孵化交易——見 STAGE3 待決)。**⚠️ 轉生 Put 覆寫重置(除非把 achievements 拆出,見存疑①)。**

| 屬性名 | 型別 | 預設值 | 語義說明 | 巢狀結構 |
|---|---|---|---|---|
| `userId` | S | (必填) | PK,Discord user id,`String()` | — |
| `sk` | S | `"M#PROGRESS"` | SK 固定值 | — |
| `quests` | M | `{}` | **進行中任務**(少量並行,像 breedQueue;section-quest「掛怪獸 item 的 quests map」)。key=questId,value=進度態。完成/歷史**不落此顆**→走 ledger `QUEST#` 前綴。日常/週常刷新 = lazy(讀時比 `acceptedAt`/`resetTag` 判跨日跨週)。進度計數用 `SET quests.<qid>.progress = if_not_exists(...,:0)+:n` | `{ <questId>: { type:S(main/daily/challenge), progress:N, target:N, acceptedAt:N, resetTag:S(日常週常週期標記) } }` |
| `qs_marks` | M | `{}` | **群感隱藏印記計數**(section-quest quorum sensing)。各主題暗中累積:採集系/戰鬥系/社交系/探索系…。**🔒裸值·絕不出面板**(閾值不明示,只給模糊暗示「菌落開始躁動…」)。**累計型 + 軟上限**(即時代謝飽和,防肝爆刷);計數 `SET qs_marks.<theme> = if_not_exists(...,:0)+:n`。閾值/組合表 = 靜態設定不落此顆(存疑③) | `{ collect:N, combat:N, social:N, explore:N, ... }`(主題 key,缺鍵視 0) |
| `qs_triggered` | SS | **(不寫·缺省=空集)** | 已浮現的特殊支線 id 集合(印記跨閾值 → 支線浮現後記錄,防重複觸發)。⚠️ 空 SS 不寫、缺省視空、首次 `ADD` 建立 | 元素=支線 id 字串,如 `"harvest_festival"` |
| `soul` | M | (見下) | **靈魂文件**(section-soul):6行為軸 + 個性標籤 + 繼承起始。互動時 lazy 更新(近期加權滑動 EWMA)。**軸數字全 🔒裸值禁直出**,只露帶名標籤 | 見下方拆解 |
| `soul.axes` | M(內嵌) | `{}` | **6 行為軸**(長期滑動累積、近期加權):`aggression`(⚔️侵略)/`attachment`(🤗依附)/`social`(🗣️社交)/`caution`(🛡️謹慎)/`exploration`(🧪探索)/`greed`(🍬貪婪)。🔒裸值。EWMA 更新:`SET soul.axes.<k> = if_not_exists(...,:0)*:decay + :event`(存疑④,巢狀路徑用 SET 非 ADD) | `{ aggression:N, attachment:N, social:N, caution:N, exploration:N, greed:N }` |
| `soul.tag` | S(內嵌) | `null` | **當前結晶個性標籤**(玩家可見風味,如「莽夫菌/暖心菌/孤僻菌/饕客探險家/苦行僧菌」)。lazy 結晶自 axes,漂移有慣性(老靈魂難改)。存當前值供快取/展示 | — |
| `soul.tag_locked` | BOOL(內嵌) | `false` | 管理員蓋章「傳奇人格」旗標(true=鎖定不隨漂移;後台覆寫/劇情/客訴用)。存疑⑤ | — |
| `soul.lore` | S(內嵌) | `null` | 管理員注入的劇情記憶/傳奇人格文本(後台覆寫,低頻)。可選 | — |
| `garden` | M | `{}` | **背部菌圃**(section-garden;back 插槽 Stage4 解鎖)。key=畦位 index(`"0"`–`"4"`)。畦數由 stage 派生(S4=2/S5=3/S6=4/傳說5,不另存 max)。離線生長 = lazy(讀時比 `plantedAt`+成熟時間+pH)。收成清畦位。**畦位計數/狀態型**,收成/偷菜條件寫 | `{ <plotIdx>: { crop:S(礦物/材料/孢子/糖蜜/橋者菌 或 null), plantedAt:N, ph:S(acid/neutral/alkaline), level:N, defense:M{ type:S, expireAt:N } } }`(存疑⑥⑨) |
| `achievements` | M | `{}` | **成就**(section-achievement;第二個半透明系統)。已解鎖集合 + 進度累積。解鎖 `SET achievements.<aid>.done=:true`;進度 `SET achievements.<aid>.progress = if_not_exists(...,:0)+:n`。里程碑點數換獎。⚠️ **成就跨世代保留 vs 當代清 = 存疑①未定**(草稿放此顆=轉生清,若要永久搬 PERMANENT) | `{ <achId>: { done:BOOL, progress:N, unlockedAt:N }, _points:N(成就點累積) }` |
| `createdAt` | N | `Date.now()` | item 建立時間(epoch ms) | — |
| `updatedAt` | N | `Date.now()` | 最後寫入(epoch ms),每次 SET | — |

**lazy compute 標注**(STAGE1 1-4「lazy 大量」鐵律):日常/週常刷新、群感閾值比對、菌圃成熟、靈魂6軸滑動 = **全讀時算、零背景 job**。
**走 ledger `QUEST#` 前綴(不落此顆)**:任務完成歷史、任務發獎流水(section-quest「完成/歷史→既有 ledger 加 QUEST#」)。
**集合欄用法**:`qs_triggered`=**StringSet**(空不寫、`ADD` 建立);`quests`/`qs_marks`/`garden`/`achievements`=**Map**(`{}` 空預設 OK)。

---

## 🗄️ PLAYER#PERMANENT(永久 · 轉生不重置) — PK=userId · SK=`PLAYER#PERMANENT`

礦物碎片 + 職人資歷 + 祖傳天賦 + 靈魂深記 + appAccountId。低寫頻率,目標 ~0.5 KB。
**⚠️ 這顆是轉生 exact-key TransactWrite 時唯一走 `Update`(非 Put 覆寫)的 item**(STAGE2 決策③)——**保留累加,絕不重置**。

| 屬性名 | 型別 | 預設值 | 語義說明 | 巢狀結構 |
|---|---|---|---|---|
| `userId` | S | (必填) | PK,同上 | — |
| `sk` | S | `"PLAYER#PERMANENT"` | SK 固定值 | — |
| `shards` | M | `{}` | **各色礦物碎片**(section-growth「唯一戰鬥數值來源」)。6 色:`red`(鐵→ATK)/`blue`(鈣→DEF)/`green`(磷→HP)/`purple`(鎂鋅→magic)/`yellow`(硫→spd)/`white`(礦化結晶核→luck,稀有)。**累計型·跨轉生保留累加**(「老玩家越來越強」載體)。入帳 `SET shards.<color> = if_not_exists(...,:0)+:n`;兌換數值時原子扣(條件 ≥ 成本)同 TransactWrite 加 stats(遞增成本邊際遞減) | `{ red:N, blue:N, green:N, purple:N, yellow:N, white:N }`(缺鍵視 0) |
| `career_history` | M | `{}` | **職人資歷 per-guild**(section-jobs/1-2「跨世代永久」)。6 公會:`acid_smith`/`matrix_builder`/`pioneer`/`bridger`/`toxin_chemist`/`schemer`。每次轉生「當世所屬公會」ADD +1(轉職失敗率/加速/起始階算)。**累計型·跨世代不重置**;計數 `SET career_history.<guild> = if_not_exists(...,:0)+:1`(巢狀路徑用 SET) | `{ <guild>: N }`(當世該公會的轉生次數) |
| `ancestral_talents` | SS | **(不寫·缺省=空集)** | **祖傳天賦**(section-growth「每次芽孢輪迴挑 1 個已習得天賦帶到下世」+繼承通道點亮的轉生流隱藏節點)。轉生 +1(累積受控、一次只帶 1)。⚠️ 空 SS 不寫、缺省視空、首次 `ADD ancestral_talents :nodeSet` 建立(冪等原子單節點) | 元素=天賦節點 id 字串,如 `"acid_A_5"`, `"center_reborn_3"` |
| `soul_legacy` | M | `{}` | **靈魂深記**(section-soul「越輪迴越深=老靈魂」+繼承通道「世代印記/塑造下代個性親和」)。存下一代個性起始傾向 + 分支軟親和 + 世代印記(精通式微加成、邊際遞減)。**累計型·跨世代加深**;世代印記計數 `SET soul_legacy.marks.<theme> = if_not_exists(...,:0)+:1` | `{ start_bias:M{<axis>:N 個性起始傾向}, affinity:M{<branch>:N 分支親和}, marks:M{<theme>:N 世代印記}, bud_bias:M(存疑②,下代芽孢性狀軟傾向) }` |
| `generation` | N | `0` | **世代數**(section-growth「每代小幅永久加成、遞減」)。完成轉生 +1(純養老拿不到,平衡鎖②)。累計型;`ADD generation :1`(頂層屬性,可用 ADD) | — |
| `appAccountId` | S | `null` | **綁定的 APP 帳號 id**(STAGE2 決策④)。綁定後填。配合 `APP#<appAccountId>` claim item 唯一鎖。未綁=null。**綁定 = TransactWrite(Put `APP#<id>` attribute_not_exists + Update 此欄)**(見下 APP# item + 寫入路徑) | — |
| `codex_titles` | M | `{}` | (可選)圖鑑/稱號永久檔案(section-achievement「圖鑑/稱號」跨世代保留)。存疑①若成就整塊搬永久,此欄可能吸收成就檔案。草稿先留位、待拍板 | `{ titles:SS(不寫·缺省空), dex:SS(不寫·缺省空) }` |
| `createdAt` | N | `Date.now()` | 首次建立(玩家首孵化,永不重置) | — |
| `updatedAt` | N | `Date.now()` | 最後寫入(轉生/兌換/綁定) | — |

**集合欄用法**:`ancestral_talents`/(`codex_titles.titles`/`.dex`)=**StringSet**(空不寫、`ADD` 建立);`shards`/`career_history`/`soul_legacy`=**Map**(`{}` 空預設 OK)。
**轉生保留累加欄**(TransactWrite Update,非 Put):`shards`(+繼承碎片)、`career_history`(+1 當世公會)、`ancestral_talents`(+1 祖傳)、`soul_legacy`(加深)、`generation`(+1)。`appAccountId` 綁定後恆定(轉生不動)。

---

## 🎒 INV#<itemId>(背包道具) — PK=userId · SK=`INV#<itemId>`

菌囊道具(STAGE2 決策⑦補 P1-5;section-items 菌囊)。隨玩家 PK,每種道具一顆 item。**不沿用 EssenceBagDAO**(scan/filter 不適高頻原子扣)。

| 屬性名 | 型別 | 預設值 | 語義說明 | 巢狀結構 |
|---|---|---|---|---|
| `userId` | S | (必填) | PK,同上 | — |
| `sk` | S | `INV#<itemId>` | SK,`itemId` = 道具靜態 id(如 `INV#saliva_nourish`) | — |
| `qty` | N | `0`(不存則視 0) | **持有數量**。原子扣:`SET qty = qty - :n` + `ConditionExpression qty >= :n`(section-items 堆疊上限預設 999、唯一性道具 1);原子加(拾取/獎勵)`SET qty = if_not_exists(qty,:0) + :n` | — |
| `category` | S | (必填) | 大分類(section-items):`consumable`(消耗品)/`equipment`(裝備)/`material`(材料)/`skillbook`(技能道具)/`special`(特殊)。⚠️ 道具**靜態屬性**(稀有度/科學/施加狀態/教哪招/插槽)= **設定表不冗存**(存疑⑧) | — |
| `source` | S | `null` | 取得來源(採集/商店/BOSS/公會任務/菌圃/成就/PvP/賽季…),稽核用 | — |
| `season_bound` | BOOL | `false` | 換季旗標(section-items):`false`=保留;`true`=賽季擴充/一般道具換季轉食物資源。DTO/換季 worker 依此清算 | — |
| `acquiredAt` | N | `Date.now()` | 首次取得時間(epoch ms) | — |
| `updatedAt` | N | `Date.now()` | 最後動 qty 時間(epoch ms) | — |

**原子動 qty 的三大場景(可與 M#CORE / M#PROGRESS 同 TransactWrite,同表跨 SK)**:
- **餵食**(section 1-1):`TransactWrite`{ Update `M#CORE`(satiety/hp/xp/obesity 結算)+ Update `INV#<food>`(`qty -= 1` 條件 `qty>=1`)} → 結算與扣道具原子,防重複結算。
- **偷菜/收成**(1-4):收成產出入背包 = Update `M#PROGRESS.garden`(清畦)+ Update/Put `INV#<crop>`(`qty += 產量`)同交易;偷菜 = TransactWrite 雙方 item(偷者 `INV# += `、被偷 garden 減)。
- **任務獎勵發道具**(1-4):繳交任務 = TransactWrite{ Update `M#PROGRESS.quests`(標完成)+ Update `INV#<reward>`(`qty +=`)+ ledger `QUEST#` Put }。
- **學技能/升級/轉生消耗**:TransactWrite{ Update `M#BUILD.skill_bag` + Update `INV#<skillbook/material>`(`qty -= 1` 條件)}。

> ⚠️ **信物**(section-items「🏵️信物欄」)與菌囊分離、堆疊上限 1、永久不占渲染插槽 → 草稿標記走**獨立 SK(如 `RELIC#<id>`)待階段5 細化**,本檔 INV# 先不含信物(存疑⑧)。

---

## 🔐 APP#<appAccountId>(identity claim 唯一鎖) — PK=`APP#<appAccountId>` · SK=`IDENTITY`

跨平台身分唯一鎖(STAGE2 決策④修正 P0-1;PK overloading 於同表)。**GSI 不保證唯一/非強一致 → 改 claim item + `attribute_not_exists` 條件寫**。

| 屬性名 | 型別 | 預設值 | 語義說明 | 巢狀結構 |
|---|---|---|---|---|
| `userId` (= PK 欄名) | S | `APP#<appAccountId>` | **PK**,`APP#` 前綴 + APP 帳號 id。此表 PK 欄統一叫 `userId`(overloading),值為 `"APP#..."` | — |
| `sk` | S | `"IDENTITY"` | SK 固定值 | — |
| `boundUserId` | S | (必填) | **綁定的 Discord user id**。APP→Discord 反查 = 直接 `GetItem PK=APP#<id>`(免 GSI)。⚠️ 欄名用 `boundUserId` 避免與 PK 欄 `userId` 混淆(PK 欄裝的是 `APP#...` 值) | — |
| `boundAt` | N | `Date.now()` | 綁定時間(epoch ms) | — |
| `createdAt` | N | `Date.now()` | 建立時間(epoch ms) | — |
| `updatedAt` | N | `Date.now()` | 最後寫入(換綁時) | — |

**綁定寫入路徑(唯一鎖,STAGE2 決策④)**:
```
TransactWrite {
  Put  { PK=APP#<appAccountId>, SK=IDENTITY, boundUserId=<discordId>, boundAt=now }
        ConditionExpression: attribute_not_exists(userId)   // ← APP 帳號未被別人綁 = 唯一鎖
  Update { PK=<discordId>, SK=PLAYER#PERMANENT }
        SET appAccountId = :appId
        ConditionExpression: attribute_not_exists(appAccountId) OR appAccountId = :appId  // ← Discord 端未綁別的 APP
}
```
- APP→userId 解析(每次 API 登入,1-5「高頻」):`GetItem PK=APP#<id>` 拿 `boundUserId`(強一致 `ConsistentRead`)。
- **換綁**(存疑⑦,產品未定):`Delete 舊 APP#` + `Put 新 APP#`(attribute_not_exists)+ `Update PERMANENT.appAccountId` 同 TransactWrite。

---

## 🔄 轉生保留邊界(小表 · 對齊 STAGE2 決策③)

轉生 = 單一 exact-key `TransactWrite`(固定顆數,無 delete-many)。

| item | 轉生動作 | 保留/重置 | 保留累加哪些欄 |
|---|---|---|---|
| `M#CORE` | **Put 覆寫** | 🔴 重置(stage=1、友好/裝備歸零、數值須用碎片重建) | — |
| `M#BUILD` | **Put 覆寫** | 🔴 重置(talent_nodes/skill/job 清,祖傳天賦另從 PERMANENT 回填點亮) | — |
| `M#PROGRESS` | **Put 覆寫** | 🔴 重置(quests/qs_marks/soul 當代態/garden 清)⚠️ achievements 存疑① | — |
| `PLAYER#PERMANENT` | **Update(唯一保留)** | 🟢 保留累加 | `shards`(+繼承碎片)、`career_history`(+1 當世公會)、`ancestral_talents`(+1 祖傳)、`soul_legacy`(加深:start_bias/affinity/marks/bud_bias)、`generation`(+1);`appAccountId` 恆定 |
| `APP#<id>` | 不動 | 🟢 保留(身分綁定與轉生正交) | — |
| `INV#<id>` | 依 section-items | 裝備/道具轉食物資源(比照換季);永久擴充格保留 | — |

> ⚠️ soul 的處理有雙面:當代 `M#PROGRESS.soul.axes`(當世行為)重置,但「老靈魂/下代起始傾向」透過 `PLAYER#PERMANENT.soul_legacy` 保留並回填新世代 `soul.axes` 的起始值(繼承通道)。**這條 soul 當代 vs 深記的落點是待確認②的一部分。**

---

## 🧊 玻璃箱(DTO 轉換)清單 — 這些欄**絕不直出 API**

| 裸欄 | DTO 輸出 |
|---|---|
| `qs_marks.*`(群感印記計數) | **絕不出面板**;閾值不明示,只給模糊暗示(「菌落開始躁動…」/NPC 來訪/環境異變) |
| `soul.axes.*`(6行為軸數字) | 只露帶名個性標籤(`soul.tag`)+ 風味描述(「這隻最近有點孤僻…」),**永不出裸數字** |
| `shards.*` | 可給碎片數量提示(section 面板),但兌換門檻/遞增成本走 DTO |
| `soul_legacy.*`(繼承起始/世代印記) | 只給「老靈魂/傳承厚度」風味,不給裸數字 |
| `achievements.*` 隱藏成就 | 未解鎖前不現形(半透明系統),解鎖才帶名顯示 |
| `garden` 成熟時間 | 不對玩家顯示數字(section-garden「後端成熟時間·不對玩家顯示」),只給「快熟了/過熟流失」提示 |

---

## 🔗 寫入路徑(對齊 STAGE1 1-4 / STAGE2 WRU)

| 操作 | 寫哪顆 | 型別/原子性 |
|---|---|---|
| 接任務/進度更新 | M#PROGRESS.quests | UpdateItem(進度 SET+if_not_exists 加,巢狀) |
| 群感印記累積 | M#PROGRESS.qs_marks | UpdateItem(SET+if_not_exists,巢狀,軟上限) |
| 群感支線浮現 | M#PROGRESS.qs_triggered | UpdateItem(`ADD` 建立 SS) |
| 任務完成發獎 | M#PROGRESS + INV# + ledger QUEST# | **TransactWrite** |
| 繼承通道(特殊支線完成) | M#PROGRESS(標領) + PLAYER#PERMANENT(祖傳/世代印記/soul_legacy/bud_bias) | **TransactWrite**(存疑②) |
| 靈魂6軸滑動 | M#PROGRESS.soul.axes | UpdateItem(EWMA,巢狀 SET,多為互動時併寫) |
| 個性標籤結晶 | M#PROGRESS.soul.tag | 讀時 lazy 算,必要才寫快取 |
| 菌圃種植/收成 | M#PROGRESS.garden(+INV# 產出) | UpdateItem / 收成 TransactWrite |
| 偷菜 | M#PROGRESS.garden(雙方) + INV# | **TransactWrite**(雙方 item) |
| 成就解鎖/進度 | M#PROGRESS.achievements | UpdateItem(SET+if_not_exists,巢狀)⚠️存疑① |
| 碎片入帳 | PLAYER#PERMANENT.shards | UpdateItem(SET+if_not_exists,巢狀) |
| 碎片兌換數值 | PLAYER#PERMANENT.shards + M#CORE.stats | **TransactWrite**(扣碎片條件 + 加 stats) |
| 職人資歷 +1 | PLAYER#PERMANENT.career_history | 併入轉生 TransactWrite(巢狀 SET+1) |
| 轉生 | Put M#CORE/BUILD/PROGRESS + Update PERMANENT | **TransactWrite**(固定4顆 exact-key,決策③) |
| 綁定 APP 帳號 | Put APP#<id>(唯一鎖) + Update PERMANENT.appAccountId | **TransactWrite**(決策④) |
| 餵食/學技能扣道具 | INV#<id>(+M#CORE/M#BUILD) | **TransactWrite**(qty 條件扣) |

---

## 🔴 DAO 層注意(給階段9,沿用 STAGE3 4 地雷)

1. **巢狀 Map 計數禁 `ADD map.key`**:`qs_marks.*`、`soul.axes.*`、`career_history.*`、`shards.*`、`garden.<idx>.*`、`achievements.*` 全是 Map → 一律 `SET x = if_not_exists(x,:0) + :inc`(頂層 `generation` 才可用 `ADD`)。
2. **空 StringSet 禁存**:`qs_triggered`、`ancestral_talents`、`codex_titles.*` 預設不寫、缺省視空、首次 `ADD` 建立。
3. **夾限無原生**:garden 畦數(≤stage 派生上限)、qty(堆疊上限)、印記軟上限 → 條件寫拒溢出或 DTO 夾。
4. **transaction builder 合併同 item mutation**(STAGE2 P1-4):同一 TransactWrite 內對同 key(如餵食同時動 M#CORE 多欄)合併成一個 Update,避免同交易重複操作同 key 被拒。
5. **claim item 欄名別撞**:`APP#` item 的 PK 欄叫 `userId`(表統一 PK 欄名)但值是 `"APP#..."`,綁定的 Discord id 存 `boundUserId`——DAO 層別把兩者搞混。

---

## ✅ Claude(Opus)覆核 — 2026-07-17

整體:草稿紮實(空SS/巢狀SET/玻璃箱/轉生保留邊界都落實)。覆核抓到 1 個真 bug + 1 個要使用者拍板的設計題:

**🔴 1 個 DDB 真 bug(Fable5 沒抓到)**:
- **soul.axes EWMA 不能用 DDB update expression 算**:草稿 `soul.axes` 列寫 `SET soul.axes.<k> = if_not_exists(...,:0)*:decay + :event` —— **DynamoDB SET 算術只支援 `+`/`-`,不支援 `*`(乘法)**,`舊值×衰減` 無法原子。→ 改 **read-modify-write**(讀舊值→app 端算 EWMA→寫回;soul 是玩家自己怪獸、低競爭可接受,要防並發加 version 樂觀鎖)。**存疑④ 一併解決**:EWMA 語義 OK,落地是 RMW 非原子表達式。同理任何需要乘/除/max/min 的欄都不能靠 update expression。

**🟡 1 個要拍板的設計題(存疑①·阻斷定稿)**:
- **成就轉生保留邊界**:草稿暫放 `M#PROGRESS`=轉生清。但成就/圖鑑/稱號本質是 meta 進度(「第10世」「首次輪迴」跨代里程碑),permadeath+輪迴是核心循環 → **成就幾乎必然該永久保留**。**Claude 推薦:成就搬出 M#PROGRESS → 獨立 `PLAYER#ACHIEVE` item**(不塞 PERMANENT 免那顆膨脹、成就寫頻中);轉生時同 PERMANENT 走 Update 保留,轉生 TransactWrite 變 5 顆(仍遠低於上限)。**待使用者確認。**

**其餘背書**:APP# claim 唯一鎖邏輯正確、INV# 原子扣正確、轉生保留邊界表清楚、繼承通道 TransactWrite 跨兩顆合理、巢狀計數 SET+if_not_exists 全對。

**驗收方式**:逐欄對照設計冊 section-quest/soul/garden/achievement/items 語義 + DynamoDB update expression 規則(揪出 EWMA 乘法)+ 轉生保留邊界一致性。

## ➡️ 交給下一輪(定稿條件)

**本檔為草稿,定稿前須 Codex 二驗 + 使用者拍板下列:**
1. **存疑① achievements 轉生保留邊界**(當代清 vs 搬 PLAYER#PERMANENT / 拆 `PLAYER#ACHIEVE`)——**阻斷定稿**。
2. **存疑② 繼承通道落點 + soul 當代 vs soul_legacy 邊界**(bud_bias 是否獨立欄)。
3. **存疑④⑤ soul EWMA 是否夠表達「近期加權滑動」+ 個性標籤存/lazy 顆粒度**。
4. **存疑⑦ appAccountId 換綁策略**(是否允許/冷卻)。
5. **存疑⑧ 信物是否獨立 `RELIC#` SK**(vs 併 INV#)。
- 靜態表(群感閾值/組合表、道具 60 目錄靜態屬性、天賦/技能/公會平衡表)= **設定表不落怪獸 item**,另立設定表 schema(階段後段)。
- 世界 spatial `sweetbot-yajunban-world`(決策⑧)+ GSI = 排階段7。
