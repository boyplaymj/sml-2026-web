# 🛠️ S2-2 施工單（給 Fable 5）：御守 DAO + 請御守 service

> **任務**：神社「請御守」——玩家花牙齒請一枚御守，寫進 omamori 表（S1 引擎已會讀它加成）。
> **只做這格**：御守 DAO 的 `grant`/`getBySk` + `ShrineOmamoriService.grant`（先扣牙齒後寫、失敗退款）+ 單元測試。
> **不要做**：回收（S2-3）、御祈禱除厄（S2-4）、Discord 指令/UI（S3）、不動 discord.js、不碰引擎。
> 權威樹＝`/opt/sml/sweetbot-next`。做完 `node --test` 全綠 → 交 Opus 覆核 → 同步 `tools/jinja-shrine/impl-s2/` → Codex 驗。

---

## 1. 要用的既有接口（照抄，別自己另寫）

### 牙齒扣款/退款/查餘額 — `DAO/DDB/ViewerDetailDAO.js`
```js
// 加/扣點：teethCount 負數=扣、正數=給；columnName 用 'point'(=牙齒)
await viewerDetailDAO.givePoint([discordId], -fee, 'point', '請御守:kinunmori');
// ⚠️ givePoint 用 ADD、不擋負餘額、內部吞錯 → 一定要「先查餘額」再扣！
// 查餘額：
const v = await viewerDetailDAO.selectOne({ discordId });   // → { id, point, ... } | null
const balance = (v && typeof v.point === 'number') ? v.point : 0;
```

### 御守表 DAO — `DAO/DDB/ShrineOmamoriDAO.js`（已有 `listByPlayer`/`put`）
- 已有 `put(item)`（PutCommand）、`listByPlayer(discordId)`（Query 分頁）。
- **本格新增**：`getBySk(discordId, sk)`（GetItem，correct-key `{discordId, sk}`）。
- 表：`sweetbot-shrine-omamori`，PK=`discordId`(S)、SK=`sk`(S)。base DAO 寫死 PK=id 不可用 → 用 doc client 自寫（比照既有 `listByPlayer`）。

### config — `DAO/DDB/ShrineConfigDAO.js`（已有 `getMain()`）
- `getMain()` 可能回 null 或缺欄 → **deep-merge DEFAULT**（第二層防護，STAGE2 §6.1）：
```js
const { DEFAULT_SHRINE_CONFIG } = require('../shrine/defaults'); // 依實際路徑
const cfg = (await configDAO.getMain()) || {};
const omamoriTypes = cfg.omamoriTypes || DEFAULT_SHRINE_CONFIG.omamoriTypes;
const ttlDays = (cfg.omamoriTtlDays != null) ? cfg.omamoriTtlDays : DEFAULT_SHRINE_CONFIG.omamoriTtlDays;
```

---

## 2. 御守 item schema（寫進 omamori 表）

```jsonc
{
  "discordId": "123",
  "sk": "omamori#<uuid>",        // require('crypto').randomUUID()
  "type": "kinunmori",           // 來自 config.omamoriTypes 的 key
  "axis": "zaiun",               // = omamoriTypes[type].axis（六軸英文 key）
  "boost": 6,                    // = omamoriTypes[type].boost
  "acquiredAt": 1721000000,      // nowEpoch(秒)
  "expireAt": 1752536000,        // = acquiredAt + ttlDays*86400
  "recycled": false,
  "source": "juyosho"            // 授與所
}
```
> 六軸/boost 直接抄 config 的 `omamoriTypes[type]`；**別在 service 內硬寫數值**。

---

## 3. `ShrineOmamoriService.grant` 流程（命門：先扣後寫 + 退款）

新檔 `model/shrine/ShrineOmamoriService.js`，**建構子可注入 DAO**（比照 `ShrineLuckService`，供測試 stub）：
```js
class ShrineOmamoriService {
  constructor (deps = {}) { this._deps = deps; /* lazy require 真 DAO，同 ShrineLuckService._daos() 寫法 */ }

  // grant(discordId, type, nowEpoch?) → { ok, omamori?, reason? }
  async grant (discordId, type, nowEpoch = Math.floor(Date.now() / 1000)) {
    // 1) 取 config（deep-merge DEFAULT），驗 type 合法
    //    type 不在 omamoriTypes → { ok:false, reason:'unknown_type' }
    // 2) fee = omamoriTypes[type].fee（缺則 DEFAULT）
    // 3) 查餘額：balance < fee → { ok:false, reason:'insufficient', need:fee, have:balance } 不寫任何東西
    // 4) 扣款：givePoint([discordId], -fee, 'point', `請御守:${type}`)
    // 5) 建 item（§2，sk=omamori#randomUUID，expireAt=nowEpoch+ttlDays*86400）
    // 6) 寫表：omamoriDAO.put(item)
    //    try/catch：put 拋錯 → 退款 givePoint([discordId], +fee, 'point', `請御守退款:${type}`) → { ok:false, reason:'write_failed' }
    // 7) 回 { ok:true, omamori:item }
  }
}
module.exports = ShrineOmamoriService;
```

**鐵律**
- 先查餘額、餘額不足**不扣不寫**。
- 扣款成功後 put 失敗 → **一定退款**（金額相同、reason 標明退款）。
- 全程不 throw 給呼叫端（回 `{ok:false, reason}`）；未預期錯誤也包成 `{ok:false, reason:'error'}` 並 `console.warn`。
- 六軸/boost/fee 一律來自 config，不硬寫。

---

## 4. DAO 契約
- `getBySk`：`GetCommand` Key=`{discordId:String(id), sk}` → `res.Item || null`。**非 scan、非 base.get**。
- 沿用 `listByPlayer` 的 doc client 寫法（`this.ddb` / `this.tableName`）。

---

## 5. 檔案清單
| 檔 | 動作 |
|---|---|
| `DAO/DDB/ShrineOmamoriDAO.js` | 加 `getBySk`（grant 直接用既有 `put`，或加一層薄 `grant(item)=put(item)`） |
| `model/shrine/ShrineOmamoriService.js` | **新**，`grant`（§3） |
| `test/shrineOmamori.test.js` | **新**，node:test（§6） |

---

## 6. 單元測試矩陣（node:test，stub DAO 注入）

以 stub 注入 `viewerDetailDAO`/`omamoriDAO`/`configDAO`：
1. **正常請御守**：餘額足 → 扣 fee 正確（givePoint 被呼叫、amount=-fee、column='point'）、put item 的 `axis/boost` 對上 config、`expireAt=nowEpoch+ttlDays*86400`、`recycled=false`、回 `{ok:true}`。
2. **餘額不足**：balance < fee → `{ok:false, reason:'insufficient'}`，**givePoint 與 put 都沒被呼叫**。
3. **未知 type** → `{ok:false, reason:'unknown_type'}`，不扣不寫。
4. **put 失敗退款**：omamoriDAO.put stub 拋錯 → 驗證 givePoint 被呼叫兩次（-fee 後 +fee 退款）、回 `{ok:false, reason:'write_failed'}`。
5. **config 缺 omamoriTypes**：configDAO.getMain 回 `null` → deep-merge DEFAULT 後仍能請 6 種御守之一（不炸）。
6. **sk 唯一**：連請兩次 → 兩個不同 sk。
7. **getBySk**：put 後 getBySk 取得同一 item；不存在 → null（可用 stub 驗 Key 正確）。

> 測試用注入 stub，不打真 AWS。金額/呼叫次數用可記錄的 fake（例如 push 到陣列）驗。

---

## 7. 規範
- 只 commit shrine 相關檔（`sweetbot-next` 有其他 session 在製，別掃到）。commit 訊息前綴 `神社(shrine): S2-2 ...`。
- 六軸英文 key：`zaiun/shengun/zhiun/body/renyuan/xingyun`。
- node:test 全綠才交。
- 有疑問（尤其退款/餘額競態）標註，Opus 覆核時處理。
