# ⛩️ 甜甜神社 — STAGE 2：御守 / 回收 / 御祈禱厄年（綁生日）· Codex 查驗基準

> S2 = 神社「活起來」的留存核心：請御守（持有→加運）、御守 365 天效期→到期穢れ→古札納所回收（消穢れ+功德值）、御祈禱依生日厄年除厄。
> **產出 S1 引擎讀取的資料寫入端 + 兩個引擎小擴充**（活御守正向加成、除厄減免；STAGE1 §8 已預告屬 S2）。
> **不在範圍**：不接其他遊戲（S4）、不做全境設施 UI（S3）、不動 discord.js 大架構（只加本 3 設施指令）。
> 基準：`DESIGN.md §3（御守）/§4（御祈禱厄年）`＋ `STAGE0.md（表 schema）`＋ 已上線 `model/shrine/ShrineLuck.js`（S1 引擎）。

---

## 1. 檔案佈局（sweetbot-next）

| 檔 | 角色 | 狀態 |
|---|---|---|
| `model/shrine/ShrineLuck.js` | **擴充**：活御守正向加成 + 除厄減免（見 §3、§5） | 既有，加 2 段 |
| `model/shrine/defaults.js` | **擴充**：御守 boost 表、除厄設定 | 既有，加欄 |
| `DAO/DDB/ShrineOmamoriDAO.js` | 加 `grant`（請御守 Put）、`recycle`（標記回收）、`getBySk` | 既有 `listByPlayer`/`put` |
| `DAO/DDB/ShrineFortuneDAO.js` | 加 `addMerit`（功德值累加）、`setGender`、`setYakuHarai`（記除厄年） | 既有 `getByPlayer`/`put` |
| `model/shrine/ShrineOmamoriService.js` | 請御守 / 回收（扣牙齒×寫表的順序與退款、冪等） | 新 |
| `model/shrine/ShrineHaraiService.js` | 御祈禱：收 gender + 收費 + 記除厄年 | 新 |
| `test/shrineOmamori.test.js` / `test/shrineHarai.test.js` / 擴充 `test/shrineLuck.test.js` | 單測 | 新/擴充 |

> 牙齒收費一律走既有 point 系統（givePoint/扣點），**不在 shrine 表內記牙齒**。御守/功德值/gender/除厄年存 shrine 表。

---

## 2. 御守請領（授與所買御守）

**御守 item（存 `sweetbot-shrine-omamori`，PK=discordId, SK=sk）**
```jsonc
{
  "discordId": "123",
  "sk": "omamori#<uuid>",     // 唯一實例
  "type": "kinunmori",         // 金運守/勝守/…（config 定義）
  "axis": "zaiun",             // 對應六軸之一
  "boost": 6,                  // 持有中加成（config 依 type 定，見 §7）
  "acquiredAt": 1721000000,    // epoch 秒
  "expireAt": 1752536000,      // = acquiredAt + omamoriTtlDays*86400（預設 +365d）
  "recycled": false,
  "source": "juyosho"          // juyosho(授與所) / okumiya(奧社限定) …
}
```

**流程（`ShrineOmamoriService.grant`）**
1. 檢查開放時間（§DESIGN 5.3，授與所預設全日；config `hours`）。
2. 查 config 取該 type 的 `axis`/`boost`/`fee`。
3. **收費**：扣 `fee` 牙齒（餘額不足 → 明確錯誤、不寫表）。
4. **寫 omamori**：`grant` Put 一筆（`expireAt=now+ttl`）。
5. ⚠️ **原子性**：牙齒系統與 shrine 表跨系統無法單一 TransactWrite → 定序「**先扣牙齒、後 Put**；Put 失敗則退款（refund `fee`）並回錯」。退款走既有 givePoint 正向。
6. 回玩家：御守卡（type/效期/加成軸）。

> 御守加成**只來自 omamori 陣列**（單一真理），**不寫進 `fortune.buffs`**（那是籤 buff 的來源，兩者分離，避免雙記）。

---

## 3. 引擎擴充 A — 持有中御守正向加成（`computeLuck`）

S1 目前只算過期穢れ、**跳過活御守**。S2 新增：**未回收且未到期**的御守 → 對應軸 `+= boost`。

```
對每張 omamori：
  recycled           → 略過
  expireAt <= now    → 穢れ（既有：body -= daysExpired*decay）
  expireAt >  now    → 活御守：axes[o.axis] += (o.boost || 0)   ← 新增
```
- 未知 axis / boost 非 number → 略過（防髒資料，比照 buff）。
- 疊加後仍受最終 `clamp[0,100]`。
- `breakdown` 增 `omamoriBoost:{軸→Σ}` 透明化。

---

## 4. 古札納所回收

**流程（`ShrineOmamoriService.recycle(discordId, sk)`）**
1. `getBySk` 取該御守；不存在/非本人/已回收 → 冪等回「已回收/查無」不重複給獎。
2. `recycle`：ConditionExpression `recycled = false` 的 Update SET `recycled=true`（條件寫，**擋並發重複領功德**）。
3. 成功 → `fortune.addMerit(config.meritOnRecycle)`（預設 +50）。
4. 回收後該御守不再計穢れ（引擎 `recycled` 即略過），負成長止血。

> **功德值 `fortune.merit`** = 折價券（§DESIGN 9.2 決策），S2 只**累加**；折抵用於請御守/御朱印可 S2 尾或延後，先確保累加正確。

---

## 5. 御祈禱厄年（除厄）+ 引擎擴充 B

### 5.1 gender 收集
- S1 起 `fortune.gender` 恆缺 → 厄年不觸發。御祈禱受付所首次流程**收集 gender**（male/female 按鈕）寫 `fortune.setGender`。
- 生日取自既有 ViewerDAO（`YYYY-MM-DD`，service 已 `replace(/-/g,'')`→yyyymmdd）。無生日 → 引導補生日或用生肖本命年 fallback（fallback 延後）。

### 5.2 除厄機制（引擎擴充 B）
- 御祈禱除厄：檢查開放時間（09–17）；收 `fees.gokitou`（預設 800）；寫 `fortune.setYakuHarai(taipeiYear)`（記「本台北年已除厄」）。
- **`computeLuck` 擴充**：算厄年 penalty 時，若 `fortune.yakuHaraiYear === taipeiYear(now)` → 依 `config.yakuHaraiMode` 減免：
  - `'clear'`（預設）：penalty 歸零（發護符、當年全免）。
  - `'half'`：penalty ×0.5（四捨五入）。
- `breakdown.yakuLevel` 保留原判定、另加 `yakuHaraied:true/false` 供透明化。
- **冪等**：同台北年重複除厄 → 已除厄則提示、可選擇不重複收費（config `yakuHaraiRechargeable` 預設 false）。

### 5.3 生日聯動鉤子
- 既有生日祝賀流程（`getByBirthday`→祝賀）觸發時，一併算 `数え年`＋厄年，若逢厄年 → 祝賀訊息附鉤子「今年是你的○厄，要不要到神社除厄？」。
- 純附加文字，不改既有祝賀主流程；gender 缺則不附（保守）。

---

## 6. 數值 / config（`sweetbot-shrine-config`，key=main）

S2 用到既有欄 + 新增：
```jsonc
{
  "omamoriTtlDays": 365,
  "kegareDailyDecay": 1,
  "meritOnRecycle": 50,
  "yakuPenalty": { "maeyaku": -3, "honyaku": -6, "atoyaku": -3, "taiyakuExtra": -4 },
  "fees": { "omamori": 300, "gokitou": 800, ... },
  // ── S2 新增 ──
  "omamoriTypes": {                         // 御守型別 → 軸 + 加成 + 費（覆蓋 fees.omamori）
    "kinunmori":  { "axis": "zaiun",   "boost": 6, "fee": 300 },
    "shoumori":   { "axis": "shengun", "boost": 6, "fee": 300 },
    "gakugyomori":{ "axis": "zhiun",   "boost": 6, "fee": 300 },
    "kenkoumori": { "axis": "body",    "boost": 6, "fee": 300 },
    "enmusubi":   { "axis": "renyuan", "boost": 6, "fee": 300 },
    "koutsuu":    { "axis": "xingyun", "boost": 6, "fee": 300 }
  },
  "yakuHaraiMode": "clear",                 // clear | half
  "yakuHaraiRechargeable": false            // 同年可否重複除厄收費
}
```
> config 缺欄 → 引擎/service fallback DEFAULT（比照 S1 鐵律，config 掛掉不阻斷）。

### 6.1 config 上線契約（Codex S2-1 preflight）
線上 `config#main` 於 S0 已建，`seed_shrine_config.js` 用 `attribute_not_exists(key)` → **重跑會整列跳過、不會補 S2 新欄**。故：
- **① patch migration**：`migration/patch_shrine_config_s2.js`（冪等）—— 用 `UpdateExpression SET #f = if_not_exists(#f, :f)` 逐欄補 `omamoriTypes`/`yakuHaraiMode`/`yakuHaraiRechargeable`，**只補缺欄、不覆蓋後台已調值**，`ConditionExpression attribute_exists(key)` 防對空列寫，跑完 GetItem 讀回驗證（6 型別 + 六軸合法）。**S2-2 上線前需對 live 跑一次。**
- **② service 第二層防護**：S2-2/S2-4 讀 config 時，對 `omamoriTypes` 等 S2 區塊 **deep-merge `DEFAULT_SHRINE_CONFIG`**（缺區塊→用 DEFAULT），即使 live 漏欄也不炸。兩層並存＝live 有值可供後台編輯 + 程式永不因缺欄失敗。

---

## 7. DAO 契約（比照 S1）

- 全用**正確 key** GetItem/Query/Update（base DAO 寫死 PK=id 不可用）。
- `recycle` 用 **ConditionExpression `recycled=false`** 的 UpdateCommand（原子擋並發重領）。
- `addMerit` 用 `UpdateExpression ADD merit :n`（原子累加，免 read-modify-write 競態）。
- `listByPlayer` 已分頁；回收/查詢皆 by-player，無需 GSI。

---

## 8. 防護 / fail-safe

- 請御守：先扣後寫、寫失敗退款；餘額不足不寫表。
- 回收：條件寫冪等，重複點只給一次功德。
- 除厄：同年冪等（預設不重複收費）。
- 引擎擴充全走既有 `computeLuck` 的 clamp / fail-safe；getLuck 仍任何錯回 50。

---

## 9. 單元測試矩陣（Codex 驗收）

**引擎擴充 A（活御守加成）**
1. 一張活御守（未到期未回收）→ 對應軸 +boost；`breakdown.omamoriBoost` 正確。
2. 已回收 → 不加；已到期未回收 → 不加正向、走穢れ。
3. 未知 axis / boost 非數字 → 略過。
4. 活御守 + clamp：boost 疊高不超過 100。

**引擎擴充 B（除厄）**
5. 厄年 + `yakuHaraiYear==今年` → penalty 歸零（clear）；`half` → 半。
6. 厄年 + 除厄年為去年 → 照扣（除厄只當年有效）。
7. 非厄年 → 除厄與否皆不影響。

**Service**
8. grant：扣費正確、omamori expireAt=now+ttl、餘額不足不寫。
9. grant 寫失敗 → 退款路徑（stub DAO 拋錯，驗 givePoint 回補）。
10. recycle：條件寫、重複回收只給一次 merit（第二次冪等）。
11. harai：寫 gender + yakuHaraiYear；同年重複依 rechargeable 冪等。

---

## 10. 分工 & 交付

- **我（Opus）主導**引擎擴充 A/B（命門、動到已簽核的 S1 引擎，親寫 + 測試）。
- Service/DAO 樣板 Fable 5 產、Claude 覆核。
- 完成 → `node --test` 全綠 → commit（只 shrine 相關）→ 同步 review 副本到 `tools/jinja-shrine/impl-s2/` → 交 **Codex 驗**（重點：引擎 delta 不破壞 S1、原子/冪等、退款路徑、除厄當年語義）。
- **S2 不接其他遊戲、不做全設施 UI**（S3/S4）。

## 12. 執行切分（小任務 · 每階段 Codex 查驗）

> 原則：每個子任務**小到能一次做完 + 一次 Codex 驗**，避免單次過長。做完 → 同步 review 副本到 `tools/jinja-shrine/impl-s2/` → 交 Codex 驗 → **過了才進下一個**（不平行推疊）。依賴順序如下。

| 子任務 | 內容 | 主手 | Codex 驗點 |
|---|---|---|---|
| **S2-1 引擎擴充 A+B** | `computeLuck` 加「活御守 boost」+「除厄減免」；`defaults.js` + `seed_shrine_config` 加 `omamoriTypes`/`yakuHaraiMode`；`shrineLuck.test` +7 測 | **Opus**（動已簽核 S1 引擎） | delta 不破壞 S1（原 12 測仍綠）、boost/clamp、除厄當年 clear/half、去年不減 |
| **S2-2 御守 DAO + 請御守** | `ShrineOmamoriDAO.grant`/`getBySk`；`ShrineOmamoriService.grant`（先扣牙齒後 Put、失敗退款）；`shrineOmamori.test` | **Fable 5** → Opus 覆核 | 先扣後寫/退款路徑、correct-key、`expireAt=now+ttl`、餘額不足不寫 |
| **S2-3 回收 + 功德值** | `ShrineOmamoriDAO.recycle`（Cond `recycled=false`）；`ShrineFortuneDAO.addMerit`（`ADD`）；`service.recycle`；test | **Fable 5** → Opus 覆核 | 條件寫冪等、重複回收只給一次 merit |
| **S2-4 御祈禱除厄** | `ShrineFortuneDAO.setGender`/`setYakuHarai`；`ShrineHaraiService`（收 gender+收費+記除厄年+同年冪等）；test | **Fable 5** → Opus 覆核 | 同年冪等、寫 gender/yakuHaraiYear、接引擎 B 當年語義 |
| **S2-5 生日厄年鉤子** | 既有生日祝賀流程附「今年○厄，要不要除厄」提示 | **Opus**（動既有生日流程） | 不破壞既有生日祝賀、gender 缺不附、數え年算對 |

**需要 Fable 5 的**：S2-2、S2-3、S2-4（DAO/service 樣板，Opus 覆核）。
**Opus 親做的**：S2-1（引擎命門、動 S1）、S2-5（動既有生日流程，風險控管）。

**依賴**：S2-1 先（引擎+config，其餘讀 config）→ S2-2 → S2-3 → S2-4（除厄需引擎 B）→ S2-5。每格皆獨立可驗、可分次做。

---

## 11. 待補（往後階段）
- 生肖本命年 fallback（無出生年時）。
- 功德值折抵消費（可 S2 尾或 S3）。
- 御守/御朱印的 Discord 卡片美術（emoji/圖）。
- 奧社限定御守（§5.2.2）走同 grant 流程、`source:'okumiya'`，S3 奧社時接。
