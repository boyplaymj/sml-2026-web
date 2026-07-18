# ⛩️ 甜甜神社 — STAGE 1：運氣引擎（Codex 查驗基準）

> S1 = 主架構命門。把「運氣」算成六軸有效值,供跨遊戲讀取。**核心是純函式 `computeLuck`**（不碰 DDB、可離線單測，對齊報稅 `calculateTaxBill` 模式）；DAO + `getLuck` 快取/fail-safe 另包一層。
> 本階段**只算數值、可查詢,不接任何遊戲、不改 discord.js**（wiring 是 S4）。

---

## 1. 檔案佈局（sweetbot-next）

| 檔 | 角色 | 純度 |
|---|---|---|
| `model/shrine/ShrineLuck.js` | 純函式:`computeLuck` + 公式 helper + 厄年/穢れ 計算 | **純**（可離線單測） |
| `model/shrine/defaults.js` | `DEFAULT_SHRINE_CONFIG`（鏡射 seed config，測試/fallback 用） | 純 |
| `DAO/DDB/ShrineFortuneDAO.js` | fortune 表 get/put/update | I/O |
| `DAO/DDB/ShrineOmamoriDAO.js` | omamori 表 by-player query（分頁） | I/O |
| `DAO/DDB/ShrineConfigDAO.js` | config `key=main` 讀取（快取） | I/O |
| `model/shrine/ShrineLuckService.js` | `getLuck(discordId, axis)`:DAO→computeLuck→快取 60s→fail-safe 50 | I/O 薄包 |
| `test/shrineLuck.test.js` | 純引擎單測（node:test） | — |

> 六軸英文 key 固定：`zaiun / shengun / zhiun / body / renyuan / xingyun`。

---

## 2. `computeLuck(input)` — 純函式（命門）

### 輸入
```jsonc
{
  "fortune": { base:{6軸}, buffs:[{axis,delta,expireAt}], ... } | null,
  "omamori": [ { axis, delta, acquiredAt, expireAt, recycled } ] | [],
  "nowEpoch": 1721260000,        // 注入,方便測試(不在純函式內取現在時間)
  "config": DEFAULT_SHRINE_CONFIG | 後台 config,
  "birthday": "19940807" | null, // yyyymmdd
  "gender": "male" | "female" | null
}
```

### 演算法（順序）
1. **base**：`axes = fortune?.base ?? {六軸皆 50}`。
2. **有效 buff**：對 `fortune.buffs` 中 `expireAt > nowEpoch` 者，`axes[buff.axis] += buff.delta`（過期的忽略）。未知 axis 的 buff 跳過（防髒資料）。
3. **穢れ（御守到期未回收）**：對每張 `omamori` 中 `!recycled && expireAt <= nowEpoch` 者：
   `daysExpired = floor((nowEpoch - expireAt) / 86400)`；`axes.body -= daysExpired * config.kegareDailyDecay`。
   （未到期、或已回收 → 不扣。穢れ只扣 `body`；`綜合運` 為衍生值會連帶下降。）
4. **厄年**：`kazoe = nowYear - birthYear + 1`（`nowYear` 由 `nowEpoch` 換算）。依 `gender` 查厄年表（見 §4）決定 `yakuLevel`（`none/maeyaku/honyaku/atoyaku`，大厄額外加重），`axes.body += config.yakuPenalty[level]`（penalty 為負值）。
   **⚠️ 缺 `gender` → 一律 `yakuLevel='none'`、不扣厄年**（保守；不因缺資料誤罰。gender 由 S2 御祈禱流程補收）。缺 `birthday` 同理不扣。
5. **clamp**：每軸有效值夾到 **[0, 100]**（honor §1.2 的 ±10%/±20% 保證上限；buff 可把軸拉高但封頂 100，不無限疊）。
6. **綜合運** `sougou = mean(六軸)`（等權平均，四捨五入或保留小數皆可，測試對整數）。

### 輸出
```jsonc
{
  "axes": { zaiun, shengun, zhiun, body, renyuan, xingyun },  // 夾 [0,100] 後
  "sougou": 50,
  "breakdown": { base, buffDelta:{軸→Σ}, kegarePenalty:number, yakuLevel:string, yakuPenalty:number }
}
```
`breakdown` 供後台/除錯透明化（玻璃箱），非必要欄可精簡。

---

## 3. 公式 helper（純，export 供 S4 各遊戲）

以 config.luckCoef 為除數（後台可調緊煞車）：
```
revenueMultiplier(v, div=500)  = 1 + (v-50)/div        // 收益:v0→0.9, v50→1.0, v100→1.1
probWeight(w, v, div=250)      = max(0, w*(1+(v-50)/div)) // 機率權重:v0→0.8w, v100→1.2w
resistFactor(v, div=200)       = 1 - (v-50)/div          // 穢れ/衰減速率乘子:v100→0.75(抗)
```
> **🛡️ PvP 不動勝率鐵律**：這些 helper 只給 PvE/經濟/抽獎用。S4 wiring 時 PvP 對戰路徑不得呼叫 `probWeight` 改判定,只可用於彩蛋/風味。此鐵律在 S4 逐遊戲檢查。

---

## 4. 厄年表（数え年，§DESIGN 4.2）

```
男 本厄: 25, 42(大厄), 61     女 本厄: 19, 33(大厄), 37, 61
前厄 = 本厄-1   後厄 = 本厄+1   大厄(42男/33女)命中本厄時 penalty 疊加 taiyakuExtra
```
`computeYaku(kazoe, gender)` → `{ level:'none'|'maeyaku'|'honyaku'|'atoyaku', isTaiyaku:bool }`。純函式,單測。

---

## 5. `getLuck(discordId, axis)` — 薄包（I/O）

- **快取**：模組級 `Map`，key=discordId，TTL 60s（存整包 computeLuck 結果,取用時挑 axis）。
- 流程：cache 命中且未過期 → 回 `axes[axis]`；否則 DAO 讀 fortune + omamori + config(+ ViewerDAO 取 birthday/gender) → `computeLuck` → 存快取 → 回。
- **fail-safe**：任何 DAO 錯 / 查無資料 / `axis` 非六軸之一 → **回 50**（baseline，不影響原玩法），並 `console.warn`。**絕不 throw 給呼叫端遊戲**。
- 另提供 `getLuckAll(discordId)` 回整包（後台/多軸一次取用）。

---

## 6. 單元測試矩陣（`test/shrineLuck.test.js`，Codex 驗收）

1. `fortune=null` → 六軸皆 50、sougou=50。
2. 過期 buff 被忽略；有效 buff 正確加成到對應軸；未知 axis buff 被跳過。
3. buff 疊加超過 100 → 夾到 100。
4. 穢れ：一張過期 N 天未回收 → `body -= N*decay`；已回收/未到期 → 不扣；多張累加。
5. 厄年:給 gender+birthday 且命中本厄/大厄 → body 扣對；前後厄扣對;**缺 gender 或 birthday → 不扣**。
6. clamp:大量負面 → 軸不低於 0;大量正面 → 不高於 100。
7. 公式 helper:`revenueMultiplier` v=0/50/100 → 0.9/1.0/1.1;`probWeight` 邊界不為負;`resistFactor` 正確。
8. `computeYaku` 男 42=大厄本厄、女 33=大厄本厄、前/後厄、非厄年=none。
9. `getLuck` fail-safe:DAO 拋錯 → 回 50;未知 axis → 回 50（此項可用 stub/注入 DAO 測，或標為整合測試）。

---

## 7. 分工 & 交付

- **我(Claude/Opus)主導**純引擎 `ShrineLuck.js` + `computeLuck` + 公式 + 厄年 + 測試（命門,親寫）。
- DAO 三支(extend `DDBCompatibleBaseDAO`,薄)可由 **Fable 5** 產樣板、我覆核。
- 完成 → `node --test` 綠 → commit(邊界:只 shrine 相關檔,不碰 unrelated)→ 交 **Codex 驗**:純度、演算法對規格、fail-safe 50、clamp、穢れ/厄年、PvP 鐵律註記、測試覆蓋。
- **S1 不接遊戲、不改 discord.js**(S3/S4 才做)。

## 8. 已知待補（往後階段）
- `gender` 來源:S2 御祈禱流程收集(或生日之外另存);S1 缺 gender 就不扣厄年。
- `生肖本命年` fallback(無出生年時):S2。
- buff 的 `source`（哪張籤/御守給的）僅記錄用,S1 不依賴。
