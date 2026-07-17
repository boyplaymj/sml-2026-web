# 牙菌斑怪獸 · DDB 資料模型 — 階段5b:lazy compute 統一規範

> **定稿 · Claude 覆核 + Codex 二驗已合流(2026-07-17)**:2 P0 修正(khui 加 base 值欄、C 型改 virtual-state 權威判定)+ P1-6 rate_mods 快取進 CORE。（產出日期 2026-07-17）
> 承接 [STAGE1-access-patterns.md](./STAGE1-access-patterns.md)（「lazy compute 零背景 job」鐵律 + 各系統 lazy 欄）+ [STAGE2-schema-decision.md](./STAGE2-schema-decision.md)（resTickAt 樂觀鎖 / DAO 注意）+ [STAGE3-schema-DRAFT.md](./STAGE3-schema-DRAFT.md)（M#CORE/M#BUILD 定稿）+ [STAGE4-schema-DRAFT.md](./STAGE4-schema-DRAFT.md)（M#PROGRESS soul.version RMW）
> 語義來源:設計冊 `score-repo/yajunban_design.html`（canonical）。數值以設計冊為準;設計冊標「後端精確數值微調」者本檔標 ⏳待定。
> **性質:跨切面規範**。把散落各 item 的「讀時惰性計算」欄位統一成一套樣板,供階段9 DAO 實作對齊。本檔不新增 schema 欄,只規範「怎麼算、何時寫」。

---

## ⚠️ 待確認/存疑點

> 重點:**哪些 lazy 欄「純讀時算永不落庫」vs「消費時才落庫」的邊界**。這是本規範最需拍板處。

1. **mood(心情)是否永不落庫**:STAGE3 定義 mood 為「多為 lazy 算不落庫,但保留欄位供快取/覆寫」。草稿主張 **mood 走純讀時算(A 型),永不主動落庫**——由 satiety/last_interaction/戰鬥近況/成長感即時合成。存疑:是否有「管理員覆寫心情」或「心情事件快取」需求要落庫?若無,mood 欄可長期為空(只當覆寫用)。**待拍板**:mood 是否從 schema 移除純算,或保留為可選快取。
2. **satiety(飽食度)純讀時算 vs 消費時落庫的邊界**:satiety 隨時間 lazy 下降(基準 `last_fed_at`)。爭議:飽食度**唯一寫入點是餵食**(重置為新值 + 更新 `last_fed_at`),自然下降**永不落庫**(讀時算)。但「飽食見底 → 觸發飢餓生病 `sick_type=starve`」是**狀態轉換需落庫**。草稿主張:satiety 值本身純讀時算(A 型),但**跨越生病閾值時**才落庫寫 `sick_type`/`sick_since`(C 型消費落庫)。**待確認**:生病判定是否要「讀到就落庫」還是「只在互動時落庫」。
3. **friendship 每日 −1 的落庫時機**:friendship 是**狀態型有下限(0)**,不能純讀時算不落庫(否則裸值永遠停在上次寫入值,衰退看不見)。草稿主張 **C 型:讀時算應扣天數,但只在「有其他寫入(照顧/開面板結算)」或「跨越歸零邊界」時才把衰退落庫**,避免每次讀面板都寫一次。存疑:若玩家只讀不互動,衰退何時真正落庫?建議「開面板讀 = 觸發一次 lazy 結算落庫」(見樣板 §2 C 型),但要防高頻讀放大寫。**待拍板落庫觸發點**。
4. **khui(菌氣)確定純讀時算(A 型)**:STAGE1 1-3 明寫「零週期寫入」,存 `khui` 值+`khui_last_ts`(Codex 階段5 P0-1:只存 ts 不夠、公式需 base),回復永不落庫,只在**消費(移動 −1/戰鬥 −2)時**才寫 `khui=現值−n, khui_last_ts=now`。列此供對照 A vs C 邊界。
5. **soul 6軸 EWMA 的落庫**:STAGE4 已定 **RMW + soul.version 樂觀鎖**(非純讀時算)。EWMA 每次互動事件都要落庫(否則事件丟失)。這是 **B 型(需落庫的樂觀鎖寫回)**的範本,與 khui/satiety 的「純讀時算」正交。存疑:讀 soul 產生**個性標籤(soul.tag)結晶**是否落庫——草稿主張標籤純 lazy 算(A 型),只在管理員蓋章(tag_locked)時落庫。
6. **daily 計數重置的時區與落庫**:`daily_reset_date`(YYYYMMDD UTC)跨日 → 清 `daily_counts`。爭議:跨日「歸零」是純讀時算(讀到就當 0)還是要落庫清空?草稿主張 **C 型**:讀時比對 `daily_reset_date`,若跨日則**下次照顧寫入時**順帶 `SET daily_counts={}, daily_reset_date=今日`(照顧本來就要寫,搭便車零額外寫);純讀不落庫。
7. **各系統「間隔/rate」是存欄還是設定表常數**:khui 間隔(20分/新手10分)、satiety 下降率、菌圃成熟時間、群感軟上限——這些 rate **草稿主張全走設定表常數(不落 item)**,item 只存時間戳。存疑:是否有 per-player 個化 rate(活動加速/天賦改 rate)需求?若有(如天賦「菌氣回復加速」),則需在讀時把天賦 modifier 疊上設定表 base rate,**rate 仍不存 item,由 build 派生**。
8. **精確數值多處 ⏳待定**:設計冊 section-garden 明寫「作物成熟節奏…剩後端精確數值微調」、satiety 下降率/mood 合成權重未在設計冊給定死值。本規範定**形狀與落庫模式**,具體 rate 數值待後端調參,不編造。

---

## 📐 一、lazy 欄位總目錄表

> 欄位所在 item 對照:M#CORE(熱)/M#PROGRESS(混)/PLAYER#PERMANENT(永久)/fortress(堡壘表)。
> 「落庫模式」欄:**A**=純讀時算永不落庫 · **B**=需落庫的樂觀鎖寫回 · **C**=讀時算但只在有實質變動/消費/搭便車寫入時才落庫(見 §2)。

| 欄位 | 所在 item | 存什麼(時間戳/rate/lastComputedAt) | 讀時公式 | 寫回時機與條件 | 夾限(clamp) | 落庫模式 | DTO 關係 |
|---|---|---|---|---|---|---|---|
| **mood 心情** | M#CORE `mood` | 不存衰減值;由 `satiety`(算出值)+`last_interaction`+戰鬥近況+成長感即時合成。rate/權重=設定表 | `mood = f(satiety現值, now−last_interaction, 生病, 近期戰果)`;⏳權重待調 | **永不主動落庫**(欄位僅供管理員覆寫/快取);讀時算 | 0–100(DTO 層夾) | **A**(存疑①) | 🔒裸值→emoji+口吻提示,永不出數字 |
| **satiety 飽食** | M#CORE `satiety`,基準 `last_fed_at` | 存上次餵食後的飽食值 + `last_fed_at`(epoch ms);下降率=設定表⏳ | `satiety現 = clamp(satiety存 − rate×(now−last_fed_at), 0, 上限)` | **唯一寫入=餵食**(重置 satiety + last_fed_at);自然下降不落庫。**跨越見底→落庫寫 sick_type=starve**(存疑②) | 0–滿值(讀時 clamp) | **A**(值)/**C**(生病轉換) | 🔒裸值→需求提示💬 |
| **friendship 每日 −1** | M#CORE `friendship`,基準 `last_interaction` | 存 friendship 值 + `last_interaction`;−1/天=設計冊確認 | `days = floor((now−last_interaction)/86400000)`;`friendship現 = max(0, friendship存 − days)` | **狀態型有下限**→不可純讀不落。開面板/照顧時 lazy 結算落庫(`SET friendship=新值, last_interaction 進位`);跨越 0→寫 `zero_friendship_since` | 0–100(下限硬夾) | **C**(存疑③) | 🔒裸值→分帶😄80-100/😊50-79/😐20-49/😤0-19(設計冊確認) |
| **khui 菌氣** | M#CORE `khui`(值)+`khui_last_ts` | **存 base 值 + 時間戳**(Codex P0-1:只存 ts 不夠,公式需 base);間隔=設定表(20分/新手10分),上限5 | `khui現 = min(5, khui + floor((now−khui_last_ts)/間隔ms))` | **零週期寫**;僅消費(移動−1/戰鬥−2)時 `SET khui=現值−消費, khui_last_ts=now`(條件防超支) | 0–5(讀時 min 夾) | **A**(值)/消費時寫 | 🔒→菌氣格數,不給間隔內部數 |
| **每日計數重置** | M#CORE `daily_counts`,基準 `daily_reset_date` | Map `{headpat,play,groom,cheer}` + `daily_reset_date`(YYYYMMDD UTC) | 讀時:`daily_reset_date≠今日 → 視 counts 全 0` | 跨日**搭下次照顧寫入**時 `SET daily_counts={}, daily_reset_date=今日`;純讀不落(存疑⑥) | 各項 ≤上限(摸頭3/玩耍1/整理1/鼓勵3),條件寫拒超 | **C** | 灰化按鈕表達,不出數字 |
| **日常/週常任務刷新** | M#PROGRESS `quests.<qid>`,基準 `acceptedAt`/`resetTag` | 每任務 `resetTag`(週期標記字串,如日期/週序) + `acceptedAt` | 讀任務面板:`resetTag≠當前週期 → 該任務進度視 0/可重領` | 讀時比對→**下次領取/繳交寫入**時刷新 `resetTag`+清 progress;純讀不落 | progress ≤ target | **C** | 進度條相對值 |
| **群感閾值比對** | M#PROGRESS `qs_marks`(計數)+`qs_triggered` | 印記各主題計數(累計,軟上限);閾值/組合表=**靜態設定表不落 item** | 讀面板:`qs_marks vs 靜態閾值 → 支線是否浮現` | 印記累積本來就落庫(SET+if_not_exists+:n);**浮現支線→`ADD qs_triggered`**(消費落庫,防重觸發) | 印記軟上限(代謝飽和,條件寫) | **C**(浮現) | 🔒裸值·絕不出面板,只模糊暗示 |
| **靈魂 6 軸 EWMA** | M#PROGRESS `soul.axes`,樂觀鎖 `soul.version` | 6 軸當前加權值 + `soul.version`;衰減係數=設定表⏳ | RMW:讀舊值→app 端 `新 = 舊×decay + 事件×(1−decay)`(EWMA) | **每次互動事件落庫**(事件不可丟);`ConditionExpression soul.version=:old`,寫回 `+1`,衝突重讀重試 | 各軸 0–上限(app 端夾) | **B**(存疑⑤) | 🔒→只出 soul.tag 帶名標籤 |
| **個性標籤結晶** | M#PROGRESS `soul.tag`/`tag_locked` | tag(當前結晶)+ tag_locked(管理員鎖) | 讀 soul:`tag = crystallize(soul.axes)`;有慣性(老靈魂難改) | **純 lazy 算**;僅管理員蓋章時 `SET tag_locked=true`(落庫) | — | **A**(標籤)/管理員時 B | 帶名個性風味 |
| **菌圃成熟/過熟** | M#PROGRESS `garden.<idx>`,基準 `plantedAt` | 每畦 `crop`/`plantedAt`/`ph`/`level`;成熟時間節奏=設定表⏳(設計冊「後端精確數值微調」) | `age = now−plantedAt`;`成熟 = age ≥ matureMs(crop,ph,level)`;過熟 = `age ≥ overripeMs` | **收成時落庫**(清畦 `crop=null`+產出入 INV#,TransactWrite);成熟本身不落庫;過熟流失=讀時判定(存疑:流失是否要落庫罰) | 畦數 ≤ stage 派生上限 | **A**(成熟判定)/收成 C | 🔒後端成熟時間不顯示,只「快熟了/過熟流失」提示 |
| **堡壘離線產能** | fortress 表 `res`(map)+`resTickAt`(樂觀鎖) | `res`(各資源量)+ `resTickAt`(上次結算 ts)+ `upgradeDoneAt`(切段點) | 讀:離線產出按 `upgradeDoneAt` 切段累加,各段 rate 依當時等級,+12h/12h/24h 上限+扣兵糧 | **讀時發現可落定變動才寫**;樂觀鎖 `ConditionExpression resTickAt=舊值`,`SET res=新, resTickAt=now` | 產出上限(12/12/24h)+兵糧扣減夾底 | **B**(resTickAt 樂觀鎖) | 資源量可顯示,離線產出結算提示 |

---

## 🧩 二、統一 helper 樣板:`lazyResolve(欄位, now)`

抽象出「讀時惰性計算」的三種落庫模式。**核心分野=純讀 vs 需寫**。

```
lazyResolve(field, item, now):
    stored   = item[field.storeKey]           # 上次落庫的裸值(或缺省)
    baseTs   = item[field.tsKey]              # 該欄的時間戳基準
    rate     = settingsTable[field.rateKey]   # rate/間隔=設定表常數(§一 存疑⑦)
    computed = field.formula(stored, baseTs, rate, now)   # 讀時公式(見 §一 表)
    return clamp(computed, field.min, field.max)          # DTO/app 端夾限(§四)
```

### A 型 — 純讀時算,永不落庫
`khui`、`satiety`(值)、`mood`、菌圃成熟判定、個性標籤。
- **形狀**:`現值 = f(存值/時間戳, now)`,回傳給 DTO,**不寫 DDB**。
- **落庫只發生在「消費」那一刻**(khui 移動/戰鬥扣、satiety 餵食重置),消費時 `SET 值=消費後, tsKey=now`。
- **好處**:讀路徑(最高頻=開面板)零寫入,WRU 全省。
- **鐵律**:回復/衰退**永遠靠時間戳重算**,絕不背景 job 週期寫。

### B 型 — 需落庫的樂觀鎖寫回
`soul.axes` EWMA(`soul.version`)、堡壘離線產能(`resTickAt`)。
- **形狀**:讀舊值 → **app 端算**(EWMA 要乘法、產能要切段,DDB 表達式做不到,見 §四)→ 寫回帶樂觀鎖條件。
  ```
  old = read(item)                          # 建議 ConsistentRead(soul/轉生快照)
  new = compute(old, event, now)            # app 端乘法/切段
  writeCondition: item[lockKey] == old[lockKey]   # soul.version / resTickAt
  write: SET field=new, lockKey=new_lock (version+1 或 resTickAt=now)
  on conflict: 重讀重試
  ```
- **何時用 B**:計算需**乘/除/max/min**(DDB update expression 不支援),**且**結果必須落庫(事件不可丟 / 產出要入帳)。
- **樂觀鎖選型**:soul→`version` 遞增;堡壘→`resTickAt` 比時間戳。二者語義=「我讀的還是最新才寫」。

### C 型 — 讀時算,但只在有實質變動/消費/搭便車寫入時才落庫
`friendship` 每日−1、每日計數重置、日常週常刷新、群感支線浮現、satiety 生病轉換。
- **判準**:欄位是**狀態型有邊界**(不能純算不落,否則裸值停滯)**或**跨越了狀態邊界(歸零/生病/浮現)。
- **落庫觸發**(擇一,**不為 lazy 本身額外寫**):
  1. **搭便車**:本來就要寫的操作(照顧、繳任務、領獎)順帶把 lazy 結算 `SET` 進去(如照顧時一併寫 `friendship=衰退後值, last_interaction 進位`、`daily_counts` 重置)。
  2. **狀態跨界**:跨越歸零→寫 `zero_*_since`;跨生病閾值→寫 `sick_type`/`sick_since`;支線浮現→`ADD qs_triggered`。
  3. **開面板結算(需防放大)**:若「純讀面板」也要讓衰退落庫,限制為「每次開面板最多結算一次」,不可每次 GetItem 都寫(存疑③要拍板此觸發點)。
- **鐵律**:**讀取即算,但只在有實質變動或要消費時才寫**——避免高頻讀路徑退化成高頻寫。

### 決策樹(選 A/B/C)
```
這個 lazy 欄……
├─ 計算只需 +/− 且純展示、消費時才動 → A(純讀不落庫)
├─ 計算需 ×/÷/max/min 且結果必須落庫(事件不可丟/產出入帳) → B(樂觀鎖寫回)
└─ 狀態型有邊界、或跨越狀態界(歸零/生病/浮現/跨日) → C(搭便車/跨界才落庫)
```

---

## 🔒 三、鐵律重申

1. **零背景 job**:全站無任何週期性掃全表結算的 worker。所有回復/衰退/成熟/產能一律**讀時靠時間戳重算**(STAGE1 全站鐵律)。B 情境呼喚等「掃描」類走低頻 worker 讀不週期寫。
2. **高頻計數一律時間戳**:satiety/friendship 衰退/菌圃成熟/堡壘產能——存 `*_last_ts`/`plantedAt`/`resTickAt`,不存「當前值 + 定時遞增」;**khui 例外存 `khui` 值+`khui_last_ts`**(base 值非定時遞增,只消費時寫,Codex P0-1)。時間戳 lazy = 寫入預算最大省點(STAGE1 1-3)。
3. **讀路徑經 DTO(玻璃箱)**:所有 lazy 算出的裸值(mood/satiety/friendship/soul.axes/qs_marks/khui/成熟時間)**絕不直出 API**,一律 DTO 轉帶名狀態(emoji/分帶/體態名/模糊暗示)。lazy 計算在 DAO 讀層完成、DTO 層過濾。
4. **與樂觀鎖的關係**:
   - **A 型無鎖**(不寫,無競爭);消費寫用條件防超支(khui `khui≥消費量`)。
   - **B 型必鎖**:soul→`soul.version`(EWMA 事件不可覆蓋丟失,STAGE4 P0-2);堡壘→`resTickAt`(離線產能 last-write 會重複入帳,STAGE2)。
   - **C 型視情況**:跨界寫用條件(`attribute_not_exists(zero_*_since)` 防重寫時間戳);搭便車寫沿用該操作原本的條件。
5. **rate/間隔走設定表,item 只存時間戳**(§一 存疑⑦):per-player 個化(天賦加速)在讀時把 build modifier 疊上 base rate,rate 不落 item。

---

## ⚙️ 四、DDB 表達式限制提醒(給階段9 DAO)

> 這些是「為什麼有些 lazy 欄非走 B 型 RMW 不可」的根因。

1. **update expression 只支援 `+`/`−`,不支援 `×`/`÷`/`max`/`min`**:
   - **EWMA(soul.axes)**需 `舊值×decay` → **不能**原子 `SET`,必須 **RMW**(讀→app 算→寫回+version)。STAGE4 P0-2 已釘。
   - **堡壘離線產能**需按段 `rate×時長`、取 `min(上限)` → 同樣 app 端算 + resTickAt 樂觀鎖寫回。
   - 任何需要乘/除/夾頂的 lazy 欄一律 B 型。
2. **夾限(clamp)無原生**:friendship(0–100)/obesity(0–10)/mood(0–100)/khui(0–5)/satiety 上下限,DDB 無 clamp 運算。二選一:
   - **①條件寫拒溢出**:`ConditionExpression friendship < :max`(建議,保資料乾淨,STAGE3 覆核 #2);
   - **②允許溢出、DTO 層夾**:純讀時算(A 型)天然走這條——算出來就夾,根本不落庫。
   - **A 型 clamp 在讀層/DTO;C/B 型 clamp 在寫入條件或 app 端。**
3. **`ADD` 不作用於巢狀 Map 路徑**:`daily_counts.*`、`qs_marks.*`、`soul.axes.*`、`garden.<idx>.*`、`shards.*` 全是 Map → lazy 結算落庫用 `SET x = if_not_exists(x,:0) + :inc`,**不可** `ADD map.key`(頂層 `generation` 才可 `ADD`)。STAGE3/4 已釘。
4. **巢狀路徑用 `SET` + `if_not_exists`**:lazy 首次落庫(欄位原本缺省不寫,如空 SS/缺鍵 Map)要用 `if_not_exists` 建立基值;`qs_triggered`/`ancestral_talents` 等 **StringSet 空不存**,首次落庫用 `ADD` 建立集合。
5. **時間戳一律 epoch ms Number**(`Date.now()`),lazy 公式全用 `now − ts` 毫秒差 / 間隔ms;不用 ISO 字串(STAGE3 慣例)。時區(daily_reset_date)在 DTO 層轉,存 UTC。

---

## ✅ Claude(Opus)覆核 — 2026-07-17

整體:A/B/C 落庫模式分類清楚、決策樹好用、DDB 表達式限制根因對齊前四階段。**無 bug**。
- **解存疑③(friendship 讀放大)**:顯示一律讀時算(`max(0, stored−days)`,純讀面板永不寫)。⚠️ **此處「由互動/worker 落庫」為歷史舊解;後續 Codex P0-2 升級為 virtual-state 純推導判定、不依賴 persisted 欄**(見下「Codex 階段5 二驗處置」),以 P0-2 為準。
- **解存疑②(satiety 生病)**:satiety 值讀時算(A);生病判定同走 virtual-state(P0-2),persisted `sick_type` 僅快取。
- **mood(存疑①)**:保留欄位當「管理員覆寫/快取」可選、預設純算(A);不必從 schema 移除。
- 背書 soul=B(`soul.version`)、堡壘=B(`resTickAt`)、khui=A、daily/群感浮現/任務刷新=C 搭便車。
- 交 Codex 二驗:對抗式查 C 型跨界持久的觸發點(worker vs 互動)有無漏、`zero_*_since`/`sick_type` 由誰負責寫、C 型「開面板結算」的寫放大上限。

## 🔍 Codex 階段5 二驗 findings(5b)+ Claude vet 處置(2026-07-17)

2 P0 全採納(都是真問題):

| # | finding | 處置 |
|---|---|---|
| P0-1 | khui 只存 ts 不夠,公式需 base | 已改:M#CORE 加 `khui` 值欄,現值=`min(5, khui + floor((now−ts)/間隔))`,消費寫 `khui=現值−n, khui_last_ts=now`(STAGE3 已補欄+本檔 khui 列已修) |
| P0-2 | C 型跨界不能只靠互動/worker,否則逃跑/死亡有空窗 | **改 virtual-state 權威判定**(見下),persisted 欄降為快取 |
| P1-6 | rate 走設定表衝擊 CORE-only 快速面板(rate 受天賦/職業影響) | M#CORE 加 compact `rate_mods` 快取(從 BUILD 去正規化),`getStatusCore` 免讀 BUILD 即可算 lazy;天賦變更時同步(STAGE3 已補欄) |

### 🔑 P0-2:virtual-state 權威判定(取代原「worker 落庫」)
所有裁決(逃跑/生病致死)先跑 **`computeVirtualState(now)`**,用時間戳純推導、不依賴 persisted 欄:
- `virtualZeroAt = last_interaction + friendship值 × 86400000`(友好度歸零的虛擬時刻);**逃跑 = `now − virtualZeroAt ≥ 7天` 且期間無互動**。
- satiety→生病同理:`virtualSickAt = last_fed_at + satiety值/下降率`。
- **persisted `zero_*_since`/`sick_type` 只當快取/通知標記,不是唯一真相**;缺了也不影響正確性(可從時間戳重推)。
→ 徹底消除「worker 沒掃到的空窗」;純讀熱路徑仍零寫入(顯示照舊讀時算)。這比原存疑③解法嚴謹:不是「誰負責寫」而是「判定根本不靠寫」。

## ➡️ 交給下一輪

- **待 Claude 覆核**:逐條 vet §一落庫模式歸類(尤其 mood=A / friendship=C / satiety 生病邊界),對照設計冊語義 + DDB 表達式規則。
- **待 Codex 二驗**:對抗式檢查「純讀不落庫 vs 消費才落庫」邊界是否有漏(尤其 C 型「開面板讀是否落庫」的寫放大風險、friendship 只讀不互動時衰退可見性)。
- **拍板點**(存疑①②③⑥):mood 是否保留快取欄、satiety 生病落庫觸發、friendship 落庫觸發點、daily 重置搭便車 vs 讀時視 0。
- rate 精確數值(satiety 下降率/mood 權重/菌圃成熟節奏)= **後端調參 ⏳**,本規範只定形狀與落庫模式,不編造數值。
