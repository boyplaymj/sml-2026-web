# 🛠️ S2-3 施工單（給 Fable 5）：古札納所回收 + 功德值

> **任務**：玩家把御守拿去「古札納所」回收 → 該御守標記 `recycled=true`（引擎即不再算穢れ）→ 給玩家功德值 `merit`。
> **只做這格**：`ShrineOmamoriDAO.recycle`（條件寫）+ `ShrineFortuneDAO.addMerit`（原子累加）+ `ShrineOmamoriService.recycle`（冪等、只給一次功德）+ 單測。
> **不要做**：御祈禱除厄（S2-4）、Discord 指令/UI（S3）、不動 discord.js、不碰引擎（穢れ 已在 S2-1 引擎處理，回收只改 `recycled` 旗標）。
> 權威樹＝`/opt/sml/sweetbot-next`。做完 `node --test` 全綠 → 交 Opus 覆核 → 同步 `impl-s2/` → Codex 驗。**先不要 commit**（Opus 覆核後才提交）。

---

## 1. DAO 新增

### `DAO/DDB/ShrineOmamoriDAO.js` → 加 `recycle`
import 補 `UpdateCommand`（現有 `QueryCommand, PutCommand, GetCommand`）。
```js
// 條件寫:唯有「存在且尚未回收」才標記 recycled=true。原子擋並發重領。
// 回傳 true=這次成功回收；false=已回收/不存在(冪等,呼叫端不再給功德)。
async recycle (discordId, sk) {
  try {
    await this.ddb.send(new UpdateCommand({
      TableName: this.tableName,
      Key: { discordId: String(discordId), sk },
      UpdateExpression: 'SET recycled = :true',
      ConditionExpression: 'attribute_exists(sk) AND recycled = :false',
      ExpressionAttributeValues: { ':true': true, ':false': false }
    }));
    return true;
  } catch (err) {
    if (err.name === 'ConditionalCheckFailedException') return false; // 已回收/不存在 → 冪等
    throw err; // 其他錯誤往上拋,service 包成 {ok:false,reason:'error'}
  }
}
```
> Key 用複合鍵 `{discordId, sk}` → 天然只能回收「自己的」御守（別人的 sk 配自己的 discordId 不會命中 → ConditionalCheckFailed）。**非 scan、非 base.get(PK=id)**。

### `DAO/DDB/ShrineFortuneDAO.js` → 加 `addMerit`
import 補 `UpdateCommand`（現有 `GetCommand, PutCommand`）。
```js
// 原子累加功德值(ADD;merit 不存在時自動從 0 起)。避免 read-modify-write 競態。
async addMerit (discordId, n) {
  await this.ddb.send(new UpdateCommand({
    TableName: this.tableName,
    Key: { discordId: String(discordId) },
    UpdateExpression: 'ADD merit :n',
    ExpressionAttributeValues: { ':n': n }
  }));
  return true;
}
```

---

## 2. service：`ShrineOmamoriService.recycle`（加進**既有** service）

在既有 `model/shrine/ShrineOmamoriService.js` 加 `recycle` 方法，並**擴 `_daos()` 加 `fortuneDAO`**（lazy require `ShrineFortuneDAO`，允許注入 stub，比照現有 viewerDetailDAO/omamoriDAO/configDAO）。

```js
// recycle(discordId, sk, ) → { ok:true, merit } | { ok:false, reason }
async recycle (discordId, sk) {
  try {
    const { omamoriDAO, fortuneDAO, configDAO } = this._daos();
    // 1) config deep-merge → meritOnRecycle(缺→DEFAULT.meritOnRecycle=50)
    let cfg = null;
    try { cfg = await configDAO.getMain(); } catch (_) { cfg = null; }
    cfg = cfg || {};
    const merit = (cfg.meritOnRecycle != null) ? cfg.meritOnRecycle : DEFAULT_SHRINE_CONFIG.meritOnRecycle;

    // 2) 條件寫回收(原子);false=已回收/不存在 → 冪等不給功德
    const done = await omamoriDAO.recycle(discordId, sk);
    if (!done) return { ok: false, reason: 'already_recycled_or_missing' };

    // 3) 成功回收才給功德(原子累加)
    await fortuneDAO.addMerit(discordId, merit);
    return { ok: true, merit };
  } catch (err) {
    console.warn(`[ShrineOmamori] recycle error for ${discordId} sk=${sk}:`, err && err.message);
    return { ok: false, reason: 'error' };
  }
}
```

**鐵律**
- **冪等**：同一 sk 回收兩次 → 第二次 `recycle` 回 false → **不再給功德**（功德只給一次）。
- **原子**：回收用 ConditionExpression、給功德用 ADD；兩者各自原子。
- 順序：**先條件寫回收成功、才給功德**（避免「給了功德但沒回收」）。若 addMerit 罕見失敗，御守已標回收但功德沒入 → 記 `console.warn`（可 S3 補償；本格不做補償交易）。
- 絕不 throw；未預期錯誤 → `{ok:false, reason:'error'}`。

---

## 3. 檔案清單
| 檔 | 動作 |
|---|---|
| `DAO/DDB/ShrineOmamoriDAO.js` | 加 `recycle`（+import UpdateCommand） |
| `DAO/DDB/ShrineFortuneDAO.js` | 加 `addMerit`（+import UpdateCommand） |
| `model/shrine/ShrineOmamoriService.js` | 加 `recycle` 方法、`_daos()` 加 `fortuneDAO` |
| `test/shrineRecycle.test.js` | **新**，node:test（§4） |

---

## 4. 單元測試矩陣（node:test，stub 注入）

用可記錄呼叫的 stub（仿 `shrineOmamori.test.js` 的 makeStubs）：
1. **正常回收**：omamoriDAO.recycle 回 true → fortuneDAO.addMerit 被呼叫一次、金額=meritOnRecycle、回 `{ok:true, merit}`。
2. **重複回收（冪等）**：omamoriDAO.recycle 回 false → **addMerit 未被呼叫**、回 `{ok:false, reason:'already_recycled_or_missing'}`。
3. **不存在 sk**：同 2（recycle 回 false）→ 不給功德。
4. **config 缺 meritOnRecycle**：getMain 回 null → fallback DEFAULT（50）。
5. **DAO 拋非 Conditional 錯**：omamoriDAO.recycle throw → service 回 `{ok:false, reason:'error'}`，addMerit 未呼叫。
6. **DAO 層 recycle 條件寫**（可另用 stub ddb.send 驗）：UpdateCommand 的 Key=`{discordId,sk}`、`ConditionExpression` 含 `recycled = :false`、`:true/:false` 值正確；ConditionalCheckFailedException → 回 false（非 throw）。
7. **DAO 層 addMerit**：UpdateExpression=`ADD merit :n`、`:n` 正確、Key=`{discordId}`。

> 全用注入 stub、不打真 AWS。金額/呼叫次數用 fake 陣列記錄驗。

---

## 5. 規範
- 只 commit shrine 相關檔（`sweetbot-next` 有其他 session 在製，別掃到）。**先不 commit**（Opus 覆核後提交）。
- 六軸英文 key、node:test 全綠才交。
- 有疑問（尤其「回收成功但 addMerit 失敗」的補償）標註，Opus 覆核處理。
- 完成回報：改/新增檔案（絕對路徑）+ `recycle`（DAO 與 service）+ `addMerit` 全文 + `node --test` 結果 + 偏離處。
