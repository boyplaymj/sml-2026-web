# 🛠️ S3-1 施工單：手水舍（五步作法 → temizuMult 折扣）

> **任務**：手水舍五步互動 → 定當日 `temizuMult`（未做0.2/錯序0.5/正解1.0），折扣**所有運氣提升的取得**。含跨系統共用 helper `applyTemizuMult` 與御守 boost 折扣特例。
> **權威樹**＝`/opt/sml/sweetbot-next`。做完 `node --test` 全綠 → Opus 覆核 → 同步 `tools/jinja-shrine/impl-s3/` → Codex 驗。
> **正典**：`RITUAL.md §3/§4`、`HANDOFF-S3-dispatch.md §1`（共用前置）、`STAGE0`（fortune schema）。
> **命門＝順序判定 + enabled gate**（純函式、可離線單測，Opus 親寫）。

---

## 0. 定案規則（RITUAL §3/§4）
- 手水舍面板：作法本文 + **5 顆按鈕、位置每次打散**；玩家依序按。
- **全程無提示對錯**：按任何一顆只顯「已進行」，5 顆按完才一次判定。
- **判定**：按的順序 `temizuState === [1,2,3,4,5]` → 正解；否則錯序。
- **當日第一次定生死**：`fortune.temizuDate===台北今日` 已定 → 多做不算、不能重做救回。
- **成效**：正解 `temizuMult=1.0`；錯序 `temizuMult=0.5` + 一次性失礼扣幸運（負 buff）；未做（`temizuDate`≠今日）→ 取用時視為 0.2。
- **非 gate**：不擋任何設施；只折「正向」運氣提升（負面不折）。
- **gate by `config.temizu.enabled`（預設 false→mult 恆 1.0）**：手水 UI 未上線前不折。

---

## 1. 照抄的既有接口
- `ShrineFortuneDAO`：`getByPlayer` / `appendBuff`（失礼負 buff 用）；本單新增 `setTemizu`（§4）。
- 失礼負 buff 形式＝`{axis, delta, expireAt, source:'shitsurei_temizu'}`（比照既有 `SHITSUREI`，Shrine.js:47）。
- 面板／按鈕註冊：`Shrine.js` handler 表（照 `shromamori` 加 `shrtemizu`）；customId 走 `DiscordButtonHelper.getCustomID('shrtemizu', [stepId])`。
- 台北日字串：沿用專案既有台北時區工具（與 omikuji/goshuin 同一支，勿各寫）。

---

## 2. 純核心（可單測，Opus 親寫）— `model/shrine/ShrineTemizu.js`
```js
const CORRECT = [1,2,3,4,5];
// ① 順序判定
function judgeTemizu(temizuState){           // temizuState = 按下的 stepId 序
  return (Array.isArray(temizuState) && temizuState.length===5 &&
          temizuState.every((s,i)=>s===CORRECT[i])) ? 'correct' : 'wrong';
}
// ② 當日乘數解析(取用端)：enabled gate + 日界 + 缺欄 fail-safe
function resolveTemizuMult(config, fortune, todayStr){
  const t = config && config.temizu;
  if (!t || t.enabled !== true) return 1.0;                 // 上線保護：未啟用=不折
  if (!fortune || fortune.temizuDate !== todayStr) return (t.mult && t.mult.none) ?? 0.2; // 未做/隔日
  const m = fortune.temizuMult;
  return (typeof m === 'number') ? m : 1.0;                 // 已做但欄髒 → 保守不折
}
// ③ 折扣套用(只折正向 delta)
function applyTemizuMult(config, fortune, buffs, todayStr){
  const mult = resolveTemizuMult(config, fortune, todayStr);
  if (mult === 1.0) return buffs;
  return buffs.map(b => (b.delta>0) ? {...b, delta: Math.round(b.delta*mult)} : b);
}
module.exports = { judgeTemizu, resolveTemizuMult, applyTemizuMult, CORRECT };
```
> ⚠️ `applyTemizuMult` **介面必帶 config**（Codex point 3）。三檔值取自 `config.temizu.mult`。

---

## 3. 手水 handler（`Shrine.js`，shrtemizu）
- **開手水面板**：5 顆按鈕（label＝五步，見 RITUAL §3 表），**顯示順序每次隨機打散**；customId 帶真實 stepId。描述區放作法本文。
- **按一顆**：
  - 若 `fortune.temizuDate===今日`（當日已定）→ 不再判、只回氛圍文字（多做不算）。
  - 否則 append stepId 進 `visit.temizuState`、**該按鈕 disable**（防重按）；面板顯示「已進行 N/5」（不透露對錯）。
  - `temizuState.length===5` → `judgeTemizu`：
    - `correct` → `setTemizu(discordId, {date:今日, mult: config.temizu.mult.correct})` + 神職正向氛圍文字。
    - `wrong` → `setTemizu(discordId, {date:今日, mult: config.temizu.mult.wrong})` + `appendBuff(失礼負 buff)`（`config.temizu.wrongPenalty`）+ 神職氛圍文字（**不明說錯了**）。
  - 清 `visit.temizuState`（本趟暫存用完）。
- **黑箱**：全程不顯 mult 數字、不顯對錯。

---

## 4. DAO 新增：`ShrineFortuneDAO.setTemizu(discordId, {date, mult})`
- 單次 Update：`SET temizuDate=:d, temizuMult=:m`（correct-key `{discordId}`、doc client）。
- 不動 buffs（失礼扣運走既有 appendBuff）。

---

## 5. 御守 boost 折扣特例（改既有 S2-2 上線碼，Codex point 5）
- 御守加成存 omamori item 的 `boost`、`computeLuck` 直接讀 → **折扣必須在請御守當下做**（不能在 compute 端，否則連舊御守一起打折）。
- 改 `ShrineOmamoriService.grant`：存 item 前，
  ```js
  const mult = resolveTemizuMult(cfg, fortune, todayStr); // 需注入 fortuneDAO 取 fortune
  const boostToStore = (boost>0) ? Math.round(boost*mult) : boost;
  ```
  存 `boost: boostToStore`（折扣鎖進該枚、跟 365 天效期）。grant 已有 configDAO；補取 fortune（同表）。
- 補測試：`temizu.enabled=true` + 未手水 → 請御守存入 boost = 原值×0.2。

---

## 6. 御神籤 / 御朱印 / 本殿参拜 接線（走 fortune.buffs）
- 三者 grant buff（寫 `fortune.buffs[]`）**前**呼叫 `applyTemizuMult(config, fortune, buffs, todayStr)`，用回傳的折扣後 buffs 再寫。
- 負面 buff（凶籤/失礼/pendingKyo）**不經此**（只折正向；helper 內已 `delta>0` 守門，但呼叫端也別把負 buff 丟進去折）。

---

## 7. config（併入共用 §1-3 的 `temizu` 區塊）
```js
temizu: { enabled:false, mult:{ none:0.2, wrong:0.5, correct:1.0 },
          wrongPenalty:{ axis:'body', delta:-5, days:3 } }
```

---

## 8. 測試 `test/shrineTemizu.test.js`（純核心，最穩先做）
1. `judgeTemizu([1,2,3,4,5])==='correct'`；任何亂序/長度≠5 → `'wrong'`。
2. `resolveTemizuMult`：enabled=false → 1.0（不論 fortune）；enabled=true + temizuDate≠今日 → 0.2；=今日 → 取 temizuMult；欄髒 → 1.0。
3. `applyTemizuMult`：mult=0.2 → 正向 delta×0.2 四捨五入、負向原樣；mult=1.0 → 原陣列。
4. handler（可測部分）：第 5 按觸發判定、當日已定則不重判（多做不算）。
5. 御守特例：enabled=true+未手水 → grant 存 boost=原×0.2；enabled=false → 原值。

---

## 💰 成本控管
- 純 fortune 欄位讀寫（既有表）+ 面板，**無新表、無 LLM、無付費 API**。手水免費。免四件套。
