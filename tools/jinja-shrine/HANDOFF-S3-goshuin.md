# 🛠️ S3-goshuin 施工單：御朱印系統 @ 御朱印受付所

> **任務**：月度蓋御朱印——每月一枚、統一 500🦷、給六軸小幅長效 buff（30 天、隨累計枚數成長），收藏進御朱印帳。
> **權威樹**＝`/opt/sml/sweetbot-next`。做完 `node --test` 全綠 → Opus 覆核 → 同步 `tools/jinja-shrine/impl-s3/` → Codex 驗。
> **規格正典**：`DESIGN.md §5.4`（機制）、§5.3（時間閘）、§1.2（buff 溫和/PvP 鐵律）、§6（表）。
> **不要做**：御神籤（S3-omikuji，已交）、奧社、其他設施；不動 S1 引擎公式（buff 走既有 `fortune.buffs[]`，引擎已會讀）。

---

## 0. 定案規則（數值全 config 可調）
- **一個月只能蓋 1 枚**（台北月曆），統一 **500🦷**，差在款式。⏰ 受付 09:00–15:00。
- **同款可再蓋**（每月一枚、記年月）→ 每月蓋即 +1 收藏。
- **蓋印給 buff**：六軸各 `+delta`、`source:'goshuin'`、效期 30 天、**覆蓋制**；`delta = min(buffBase + (枚數−1)×buffPerStamp, buffCap)`（預設 2/1/10）。**不碰 PvP**。
- 缺當月新款也能蓋（重蓋任一款純續 buff）。

---

## 1. 照抄的既有接口（同 S3-omikuji）
- **扣費/查餘額** `ViewerDetailDAO`：`givePoint([id], -500, 'point', '御朱印:<版本>')`；**先 `selectOne` 查 point 再扣**。
- **config** `ShrineConfigDAO.getMain()` → deep-merge `DEFAULT_SHRINE_CONFIG`。
- **fortune buff** `ShrineFortuneDAO`：buff 進 `fortune.buffs[]`（`{axis, delta, expireAt, source:'goshuin'}`）。覆蓋制 → 用**與 omikuji 相同的 replace 手法**（濾掉舊 `source==='goshuin'` 再 append 6 筆；可抽共用 `replaceBuffsBySource(discordId, source, newBuffs)`）。
- **時間閘**：§5.3 `config.hours.goshuin=[9,15]`（台北時區）；若 S3 已有 `isOpen(facility, now)` helper 則沿用，否則本單建一支純比較台北小時、fail-safe 缺設定＝全日開放。
- **設施面板** `Shrine.js`：`facility==='goshuin'` 已有 nav 項；加操作鈕「蓋御朱印」`shract goshuin/stamp` 與「御朱印帳」`shract goshuin/book`。互動路由 `handleAction`、按鈕註冊照 `shromamori` 那筆加。
- **service 樣板**：照 `ShrineOmamoriService` 結構（injectable deps、try/catch 不 throw、回 `{ok, reason}`）。

---

## 2. 御朱印 DAO `DAO/DDB/ShrineGoshuinDAO.js`（新）
表 `sweetbot-shrine-goshuin`，PK=`discordId`(S)、SK=`goshuin#<YYYY-MM>`(S)。doc client 自寫（base DAO 寫死 PK=id 不可用，比照 ShrineFortuneDAO）。
- `stamp(discordId, ym, item)`：**條件 Put** `attribute_not_exists(sk)` → 已蓋過當月則 `ConditionalCheckFailed`（=本月已蓋，service 攔成 `{ok:false, reason:'already_this_month'}`）。**這就是「一枚/月」的原子強制，別用 read-then-write。**
- `listByPlayer(discordId)`：Query（**必分頁**）回全部枚。
- `countByPlayer(discordId)`：Query `Select:'COUNT'`（累計枚數，驅動 buff 幅度）。

---

## 3. service `model/shrine/ShrineGoshuinService.js`（新）

### `stamp(discordId, versionId, now)` → `{ok, goshuin, delta, count} | {ok:false, reason, need?, have?}`
1. deep-merge config；`fee = cfg.goshuin.stampFee ?? 500`。
2. **時間閘**：非 09–15 → `{ok:false, reason:'closed'}`。
3. **驗版本**：`versionId` 在 `cfg.goshuin.versions` 且（季節款→今在 window 內；奧社款→`requireOkumiya` 且該玩家 `fortune.okumiyaClearedAt` 有值）；否則 `reason:'unavailable'`。
4. `ym = 台北 YYYY-MM(now)`；查餘額不足→`insufficient`。
5. 扣 500 → **條件 stamp**（`attribute_not_exists`）；若 `ConditionalCheckFailed` → **退款** + `{ok:false, reason:'already_this_month'}`（先扣後條件寫，失敗必退，同 omamori 退款鐵律）。
   - item：`{discordId, sk:'goshuin#'+ym, versionId, ym, stampedAt:now, imageKey}`。
6. `count = countByPlayer`（含本枚）；`delta = min(cfg.goshuin.buffBase + (count-1)*cfg.goshuin.buffPerStamp, cfg.goshuin.buffCap)`。
7. **套 buff**：六軸各一筆 `{axis, delta, expireAt: now + cfg.goshuin.buffDays*86400, source:'goshuin'}`，`replaceBuffsBySource(discordId,'goshuin',6筆)`。
8. 回卡片資料（§5）。
> 順序：扣款 → 條件 stamp → 算 count → 套 buff。stamp 失敗在扣款後 → 退款；buff 套用失敗不影響已蓋（buff 下月重蓋會補，或記 log）。

### `book(discordId)` → `{count, items:[{versionId,ym,name}...], versionsTotal}`
- listByPlayer → 組御朱印帳分頁資料（已蓋年月＋款名；未蓋款式列出灰階＝`versions` 減已集 versionId 去重）。

---

## 4. config 區塊（`defaults.js` + seed_shrine_config）
```js
goshuin: {
  stampFee: 500, buffDays: 30, buffBase: 2, buffPerStamp: 1, buffCap: 10,
  versions: [
    { id:'honsha',   name:'本社印「麻雀大明神」', category:'常駐' },
    { id:'shogatsu', name:'初詣・正月', category:'季節', window:['01-01','01-15'] },
    { id:'sakura',   name:'春櫻詣',     category:'季節', window:['03-20','04-10'] },
    { id:'nagoshi',  name:'夏越大祓',   category:'季節', window:['06-25','07-31'] },
    { id:'momiji',   name:'秋葉紅葉',   category:'季節', window:['11-01','11-30'] },
    { id:'okumiya',  name:'奧社・牌神', category:'奧社', requireOkumiya:true },
    { id:'okumiya-season', name:'季節×奧社', category:'限定', requireOkumiya:true, window:[...] }
  ]
}
```
> hours：`config.hours.goshuin=[9,15]`。imageKey/base URL 走圖床（御朱印圖程式合成、先 placeholder，素材不進 git）。

---

## 5. Discord 卡片（Shrine.js）
- **蓋御朱印**：面板加 `shract goshuin/stamp` → 若當月未蓋 → 列**當前可蓋款式**（StringSelect，季節/奧社依條件過濾）→ 選款 → `service.stamp` → ephemeral 更新（顯示新枚＋「六軸運勢 +delta（30 天）」＋累計枚數）。已蓋過當月 → 提示「本月已蓋（下月請早）」。
- **御朱印帳**：`shract goshuin/book` → `service.book` → embed 分頁列已蓋（款名＋年月）＋「已集 N 枚」＋未蓋款式灰列。
- 圖：御朱印圖 `imageBaseUrl/<versionId>.png`。

---

## 6. 測試（`test/shrineGoshuin.test.js`，stub deps）
1. 首蓋：扣 500、寫 goshuin#當月、buff 六軸各 +2/30 天、count=1。
2. 同月再蓋 → ConditionalCheckFailed → 退款、reason=already_this_month。
3. 隔月蓋 → 成功、count=2、delta=3（隨枚數）；buff 覆蓋舊 goshuin buff。
4. delta 封頂：count≥9 → delta=10 不再增。
5. 餘額<500 → 不扣不寫、insufficient。
6. 時間閘：非 09–15 → closed（fail-safe 缺 hours → 放行）。
7. 版本過濾：季節款窗口外 / 奧社款未通關 → unavailable。
8. book：組帳正確（已集年月＋未集灰列）。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）
- 純 DDB（既有 goshuin/fortune/config，PAY_PER_REQUEST）+ 圖床（程式合成、$0）。**無 LLM、無付費 API** → 免四件套。蓋印 500🦷／月＝牙齒 sink。
