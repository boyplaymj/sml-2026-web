# ⛩️ 甜甜神社 — STAGE 0：資料層規格（Codex 查驗基準）

> 主架構分階段實作，每階段 Codex 查驗。本檔 = Stage 0 的**精確資料層規格**，是後續所有階段的地基與 Codex 驗收清單。
> 對齊 sweetbot-next 既有慣例（earthquake/livevote/yajunban migration）。全表 `PAY_PER_REQUEST` @ `ap-southeast-1`，**核心零 GSI**。

---

## 階段切分總覽（主架構路線圖）

| 階段 | 內容 | 我(Claude)的角色 | Fable5 | Codex 查驗重點 |
|---|---|---|---|---|
| **S0 資料層** | 7 表冪等 migration + 籤池/config 種子 | 主導規格(本檔) | 產 migration/種子樣板 | schema/keys/冪等/TTL、種子結構 |
| **S1 運氣引擎** | 六軸模型 + `computeLuck` lazy 統一出口 + `getLuck` 存取器 + 單元測試 | 主導設計+覆核 | 實作 | buff/穢れ/厄年結算正確、fail-safe 回 50、公式對 §1.2 |
| **S2 御守/回收/厄年** | 授與/365天效期/古札納所回收/穢れ負成長/消災解厄綁生日 | 主導設計+覆核 | 實作 | 到期→穢れ、回收消除、厄年数え年表對、生日聯動 |
| **S3 Discord 八設施** | 手水 gate→主殿抽籤→授與所→奧社→御祈禱→古札納所→御朱印帳→繪馬→石柱 | 覆核 | 實作 | 互動流、牙齒扣費原子、gate 邏輯 |
| **S4 跨遊戲 wiring** | `getLuck` 接麻將館/隨機事件/路權…逐一調係數 | 主導(防 pay-to-win) | 輔助 | PvP 不動勝率、係數保守、fail-safe |
| **S5 後台** | 遊戲館管理頁：籤池/費用/權重/效期/厄運率/繪馬審核/石柱榜/御朱印上架 | 覆核 | 生成+覆核 | 認證閘、schema 對齊、%÷100 |

> 每階段完成→commit(避併行快照雷)→交 Codex→收斂 findings→才進下一階段。

---

## S0 表定義（精確）

### 1. `sweetbot-shrine-fortune` — 玩家運氣狀態（核心）
- **PK** `discordId` (S) — 單鍵，無 SK。
- 屬性（item shape）：
  ```jsonc
  {
    "discordId": "123",
    "base": { "zaiun":50, "shengun":50, "zhiun":50, "body":50, "renyuan":50, "xingyun":50 },
    "buffs": [                      // 有效祝福 buff，lazy 讀取時濾掉過期
      { "axis":"zaiun", "delta":8, "source":"omikuji-0007", "grantedAt":1721260000, "expireAt":1721346400 }
    ],
    "lastHarai": "20260718",        // 手水洗手日(yyyymmdd)；當日==今天才算已淨手
    "yaku": { "year":2026, "kazoe":33, "level":"honyaku", "resolved":false }, // 厄年當年算一次
    "merit": 0,                     // 功德值(折價券性質)
    "updatedAt": 1721260000
  }
  ```
- 六軸 key 固定：`zaiun`(財)/`shengun`(勝)/`zhiun`(智)/`body`/`renyuan`(人緣)/`xingyun`(行)。**別用中文當 key**。
- 無 TTL（永久保留玩家狀態）。無 GSI。

### 2. `sweetbot-shrine-omamori` — 御守持有
- **PK** `discordId` (S)、**SK** `sk` (S) = `omamori#<instanceId>`（instanceId 用時間戳+亂數或既有 id 產生器）。
- 屬性：`type`(金運守/勝守/…)、`axis`(對應子軸)、`delta`(加成)、`acquiredAt`(epoch)、`expireAt`(=acquiredAt+365d)、`recycled`(bool)、`kegare`(bool，過期未回收=true)。
- 查詢：Query PK=discordId 取玩家全部御守（分頁）。無 GSI（到期提醒走 lazy per-player，非批次）。無 TTL（過期不刪，要留著算穢れ；回收才軟刪或標記）。

### 3. `sweetbot-shrine-goshuin` — 御朱印帳
- **PK** `discordId` (S)、**SK** `sk` (S) = `goshuin#<versionId>`。
- 屬性：`versionId`、`stampedAt`、`event`(哪個活動/季節版)、`imageKey`(圖床路徑，圖由使用者生成，先 placeholder)。

### 4. `sweetbot-shrine-ema` — 繪馬牆（公開）
- **PK** `bucket` (S) = `month#<yyyymm>`、**SK** `sk` (S) = `<createTimeEpoch>#<emaId>`。
- 屬性：`ownerId`、`ownerName`(純文字暱稱，embed mention 不穩故存純文字)、`wish`(願文)、`likes`、`createTime`。
- 查詢：Query PK=本月桶、`ScanIndexForward:false` 取最新；跨月查上一桶。無 GSI。

### 5. `sweetbot-shrine-pillar` — 石柱捐獻榮譽榜
- **PK** `discordId` (S) — 一人一柱，金額累加。
- 屬性：`donorName`(純文字)、`totalAmount`、`inscription`(刻字)、`firstAt`、`lastAt`。
- 榮譽榜：小表 `fullScan`+app 排序+分頁（低量，免 GSI）。

### 6. `sweetbot-shrine-omikuji-pool` — 籤詩池
- **PK** `omikujiId` (S)。
- 屬性：`rank`(大吉…大凶，11 常規階 + 大大吉彩蛋)、`waka`(和歌)、`sougou`(總合文)、`items`(見 DESIGN §2.2，分項 text+score→對應子軸)。
- 抽籤時 `fullScan` 載入池（數十張，快取），依 config 權重抽 rank→從該 rank 籤隨機。

### 7. `sweetbot-shrine-config` — 後台設定（單列 key='main'）
- **PK** `key` (S)。`key='main'` 存：各設施費用、籤階權重表、buff 時效(秒)、御守效期(365天)、穢れ每日扣率、厄運 penalty、市集活動開關。
- 仿 `sweetbot-earthquake-config`，後台可即時改、bot 讀取。

---

## S0 交付物（Codex 驗收清單）

1. **`migration/create_shrine_tables.js`** — 建上述 7 表，冪等(DescribeTable→不存在則建、**存在則驗 schema/TTL**：驗 KeySchema/AttributeDefinitions/`PAY_PER_REQUEST`/GSI=0 + `DescribeTimeToLive` 驗 TTL 未啟用，不符累積 fatal→exit 1)，region ap-southeast-1，本批無 TTL、無 GSI。跑法 `node migration/create_shrine_tables.js`。
2. **`migration/seed_shrine_config.js`** — 種 config 列（**PK `key = "main"`**，非 `config#main`）預設值（費用/權重/時效/效期/扣率）。冪等：`attribute_not_exists(key)` 條件式，已存在不覆蓋（`--force` 才強制），避免重跑洗掉後台改的值。
3. **`migration/seed_shrine_omikuji.js`** — 種初始籤詩池（S0 先種 11 常規階各 1 張 + 大大吉彩蛋佔位，正式文本 S1/獨立批次補；每張含六軸 items 範例）。
4. Codex 驗：表名/keys/型別、冪等可重跑、種子 item 結構符合本規格六軸 key（英文）、無多餘 GSI/TTL。

> ⚠️ S0 只建表+種子，**不接 bot、不改 discord.js**。跑 migration=建真實 DDB 表(有成本但極小，PAY_PER_REQUEST)，需使用者授權後執行。

---

## 💰 成本控管
見 `DESIGN.md`「💰 成本控管」段：7 表全 PAY_PER_REQUEST、無 LLM、無付費 API → 免帳本封頂四件套。
