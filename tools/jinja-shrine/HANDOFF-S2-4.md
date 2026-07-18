# 🛠️ S2-4 施工單（給 Fable 5）：御祈禱受付所 — 厄年除厄（綁生日）

> **任務**：玩家在御祈禱受付所提供性別、系統依其生日算「数え年厄年」，若逢厄年 → 花牙齒除厄 → 記錄「本台北年已除厄」。S1 引擎 B 讀 `fortune.yakuHaraiYear`，當年即減免厄年 penalty。
> **只做這格**：`ShrineFortuneDAO.setYakuHarai`（原子寫 gender+年）+ `ShrineHaraiService.harai` + 單測 + `ShrineLuck.js` 匯出 `taipeiYear`（1 行 exports）。
> **不要做**：discord.js/UI、開放時間閘（S3）、不改引擎 B 邏輯（只加 taipeiYear 到 exports）、不碰御守/回收。
> 權威樹＝`/opt/sml/sweetbot-next`。做完 `node --test` 全綠 → 交 Opus 覆核 → 同步 `impl-s2/`。**先不要 commit。**

---

## 0. ⚠️ 最關鍵：除厄年份必須與引擎 B 同源

引擎 B（`computeLuck`）用 **`taipeiYear(nowEpoch)`**（= `(nowEpoch+8h)` 的西元年）判「本年是否已除厄」。
本 service 記錄的 `yakuHaraiYear` **必須用同一個 `taipeiYear`**，否則跨年/時區邊界會「除了厄卻沒生效」的 silent bug。
→ **不要自己另算年份**。步驟：在 `model/shrine/ShrineLuck.js` 的 `module.exports` **加入 `taipeiYear`**（函式已存在，只加匯出這一行），service `require` 它。

---

## 1. `ShrineLuck.js` — 匯出 taipeiYear（唯一對引擎檔的改動）
```js
module.exports = {
  AXES, baseAxes, computeYaku, computeLuck,
  revenueMultiplier, probWeight, resistFactor, clamp,
  taipeiYear   // ← 新增這一行(函式已存在,勿改其邏輯)
};
```
> 這是對已簽核 S1 引擎的**唯一**改動,且只加匯出、不動任何邏輯。既有 20 個 luck 測試須仍全綠。

---

## 2. `ShrineFortuneDAO.setYakuHarai`（原子寫）
import 已有 `UpdateCommand`（S2-3 補過）。
```js
// 記錄除厄:一次 UpdateCommand 原子寫 yakuHaraiYear(+可選 gender)。
// gender 傳入(male/female)才寫;否則只寫年。
async setYakuHarai (discordId, year, gender) {
  const values = { ':y': year };
  let expr = 'SET yakuHaraiYear = :y';
  const names = {};
  if (gender === 'male' || gender === 'female') {
    expr += ', #g = :g';
    names['#g'] = 'gender';
    values[':g'] = gender;
  }
  await this.ddb.send(new UpdateCommand({
    TableName: this.tableName,
    Key: { discordId: String(discordId) },
    UpdateExpression: expr,
    ...(Object.keys(names).length ? { ExpressionAttributeNames: names } : {}),
    ExpressionAttributeValues: values
  }));
  return true;
}
```
> `gender` 是 DynamoDB 保留字 → 用 `#g` alias（上面已處理）。Key `{discordId}`，非 base.get(id)。

---

## 3. `ShrineHaraiService.harai`（新檔 `model/shrine/ShrineHaraiService.js`）

建構子可注入 deps={ fortuneDAO, viewerDAO, viewerDetailDAO, configDAO }（比照 ShrineLuckService/ShrineOmamoriService 的 `_daos()` lazy require）。
import：`const { computeYaku, taipeiYear } = require('./ShrineLuck');`、`const { DEFAULT_SHRINE_CONFIG } = require('./defaults');`。

```js
// harai(discordId, gender, nowEpoch?) → { ok:true, yakuLevel, year, fee } | { ok:false, reason }
// 御祈禱除厄:驗 gender+生日→算厄年→在厄年才收費除厄→記 yakuHaraiYear(接引擎 B)。
async harai (discordId, gender, nowEpoch = Math.floor(Date.now() / 1000)) {
  try {
    const { fortuneDAO, viewerDAO, viewerDetailDAO, configDAO } = this._daos();

    // 1) gender 必填且合法
    if (gender !== 'male' && gender !== 'female') return { ok: false, reason: 'gender_required' };

    // 2) config(缺→DEFAULT):fee=fees.gokitou、rechargeable=yakuHaraiRechargeable
    let cfg = null;
    try { cfg = await configDAO.getMain(); } catch (_) { cfg = null; }
    cfg = cfg || {};
    const fee = (cfg.fees && cfg.fees.gokitou != null) ? cfg.fees.gokitou : DEFAULT_SHRINE_CONFIG.fees.gokitou;
    const rechargeable = (cfg.yakuHaraiRechargeable != null) ? cfg.yakuHaraiRechargeable : DEFAULT_SHRINE_CONFIG.yakuHaraiRechargeable;

    // 3) 生日(ViewerDAO；YYYY-MM-DD → yyyymmdd),缺/非 8 碼 → birthday_required
    const viewer = await viewerDAO.getByDcID(String(discordId));
    const birthday = (viewer && viewer.birthday) ? String(viewer.birthday).replace(/-/g, '') : null;
    if (!birthday || !/^\d{8}$/.test(birthday)) return { ok: false, reason: 'birthday_required' };

    // 4) 算厄年(用引擎同源 taipeiYear + computeYaku);非厄年 → 不收費
    const year = taipeiYear(nowEpoch);
    const kazoe = year - parseInt(birthday.slice(0, 4), 10) + 1;
    const yk = computeYaku(kazoe, gender);
    if (yk.level === 'none') return { ok: false, reason: 'not_in_yakudoshi' };

    // 5) 同年冪等:本年已除厄且不可重複 → already_haraied(不收費)
    const fortune = await fortuneDAO.getByPlayer(discordId);
    if (fortune && fortune.yakuHaraiYear === year && !rechargeable) return { ok: false, reason: 'already_haraied' };

    // 6) 先查餘額(不足不扣不寫)
    const detail = await viewerDetailDAO.selectOne({ discordId: String(discordId) });
    const balance = (detail && typeof detail.point === 'number') ? detail.point : 0;
    if (balance < fee) return { ok: false, reason: 'insufficient', need: fee, have: balance };

    // 7) 扣款
    await viewerDetailDAO.givePoint([String(discordId)], -fee, 'point', '御祈禱除厄');

    // 8) 寫 yakuHaraiYear(+gender);失敗退款
    try {
      await fortuneDAO.setYakuHarai(discordId, year, gender);
    } catch (err) {
      console.warn(`[ShrineHarai] setYakuHarai failed for ${discordId}, refunding:`, err && err.message);
      try { await viewerDetailDAO.givePoint([String(discordId)], fee, 'point', '御祈禱除厄退款'); }
      catch (re) { console.warn(`[ShrineHarai] REFUND FAILED ${discordId} fee=${fee}:`, re && re.message); }
      return { ok: false, reason: 'write_failed' };
    }

    return { ok: true, yakuLevel: yk.level, year, fee };
  } catch (err) {
    console.warn(`[ShrineHarai] harai error for ${discordId}:`, err && err.message);
    return { ok: false, reason: 'error' };
  }
}
```

**鐵律**
- 順序：gender/生日/厄年/冪等/餘額 全部先驗，**通過才扣款**；扣款後寫失敗 → 退款（同 grant 模式）。
- **非厄年不收費**（`not_in_yakudoshi`）。
- **同年冪等**：`yakuHaraiYear===本年 && !rechargeable` → 不重複收費。
- `year` 一律用 `taipeiYear(nowEpoch)`（引擎同源），**不得自算**。
- 絕不 throw；未預期錯 → `{ok:false, reason:'error'}`。

---

## 4. 檔案清單
| 檔 | 動作 |
|---|---|
| `model/shrine/ShrineLuck.js` | exports 加 `taipeiYear`（僅此一行,勿改邏輯） |
| `DAO/DDB/ShrineFortuneDAO.js` | 加 `setYakuHarai(discordId, year, gender?)` |
| `model/shrine/ShrineHaraiService.js` | **新**，`harai`（§3） |
| `test/shrineHarai.test.js` | **新**，node:test（§5） |

---

## 5. 單元測試矩陣（node:test，stub 注入）

厄年 fixture 對齊 `shrineLuck.test.js`：`NOW = Math.floor(Date.UTC(2026,6,1)/1000)`（台北年 2026）；男 42 大厄 birthday `1985-01-01`（kazoe 42）；男 30 非厄 birthday `1997-01-01`。
stub：`viewerDAO.getByDcID→{birthday}`、`fortuneDAO.getByPlayer→{yakuHaraiYear?}`+`setYakuHarai` 記錄、`viewerDetailDAO.selectOne→{point}`+`givePoint` 記錄、`configDAO.getMain→cfg`。

1. **正常除厄**（男42、足額、未除過）→ givePoint 一次(-gokitou)、setYakuHarai(2026,'male') 被呼叫、回 `{ok:true, yakuLevel:'honyaku', year:2026, fee}`。
2. **gender 缺/非法** → `gender_required`，不扣不寫。
3. **birthday 缺/非 8 碼**（viewer 無 birthday）→ `birthday_required`，不扣不寫。
4. **非厄年**（男30）→ `not_in_yakudoshi`，不扣不寫。
5. **同年已除厄 + rechargeable=false** → `already_haraied`，不扣不寫。
6. **同年已除厄 + rechargeable=true** → 允許再除（再扣、再 setYakuHarai）。
7. **餘額不足** → `insufficient`，不扣不寫。
8. **setYakuHarai 失敗退款** → givePoint 兩次(-fee 後 +fee)、`write_failed`。
9. **config 缺**（getMain null）→ fee fallback DEFAULT 800、rechargeable fallback false。
10. **DAO setYakuHarai**（另用 stub ddb.send）：帶 gender → `SET yakuHaraiYear = :y, #g = :g`、`#g`→'gender'、Key `{discordId}`；不帶 gender → 只 `SET yakuHaraiYear = :y`、無 ExpressionAttributeNames。

> 全用注入 stub、不打真 AWS。

---

## 6. 規範
- 只 commit shrine 相關檔；**先不 commit**（Opus 覆核後提交）。
- 六軸英文 key、node:test 全綠才交（新測 + 既有 grant7/recycle7/luck20 都不能破）。
- **特別回報**：`taipeiYear` 匯出後既有 luck 20 測仍綠（證明沒動到引擎邏輯）。
- 完成回報：改/新增檔案 + `harai` 與 `setYakuHarai` 全文 + `node --test` 結果 + 偏離處。
