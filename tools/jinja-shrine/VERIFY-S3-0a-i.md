# ⛩️ 神社 S3-0a-i（visit DAO + 面板純核心）· Codex 查驗交接單

> **範圍**：STAGE3 §8 第一格。**只做可離線單測的純邏輯 + DAO**;無 Discord 互動 handler、無 discord.js 改動(那是 S3-0a-ii)。
> 實作＝Fable 5、已 Opus 覆核。依據:`HANDOFF-S3-0a.md §3.5/§2/§3`＋ `RITUAL.md`。

## 0. 讀哪些檔
權威 sweetbot-next commit `c3889c7`(未 push);Codex 讀 repo 唯讀副本 `tools/jinja-shrine/impl-s3/`(byte-identical):
```
impl-s3/DAO/DDB/ShrineFortuneDAO.js       + openVisit/closeVisit/appendBuff
impl-s3/model/shrine/Shrine.js            純核心(resolveLocation/navFacilities/_panel/_shitsureiOnEnter)
impl-s3/model/shrine/mapPositions.js      內嵌 positions.json
impl-s3/test/shrinePanel.test.js          15 測
```
**全 shrine 套件:`node --test test/shrinePanel.test.js test/shrineLuck.test.js test/shrineHarai.test.js test/shrineRecycle.test.js test/shrineOmamori.test.js` = 61 pass / 0 fail(既有 46 零破壞)。**

## 1. DAO(correct-key、原子)
- [ ] `openVisit(id, now)`:GetItem 拿舊 `lastVisit` → SET `lastVisit={openAt,closed:false}` → **回舊值**(供進場 lazy 失礼判斷);Key `{discordId:String}`。
- [ ] `closeVisit(id)`:`SET lastVisit.#c = :true`(`#c`→'closed')。⚠️ **注意**:此為巢狀路徑更新,要求 `lastVisit` 已存在;流程上 closeVisit 只在 openVisit 之後(退場礼)呼叫 → 安全。**S3-0a-ii handler 須保證 openVisit 先於 closeVisit**(記為給 ii 的提醒,非本格 bug)。
- [ ] `appendBuff(id, buff)`:`SET buffs = list_append(if_not_exists(buffs, :empty), :b)` 原子 append;`:empty`=[]、`:b`=[buff]。
- [ ] 既有 5 方法(getByPlayer/put/addMerit/setYakuHarai/setGender)未動、既有測試零破壞。

## 2. 純核心(不碰 interaction、絕不 throw)
- [ ] `resolveLocation(key)`:合法→location;未知/空→null。
- [ ] `navFacilities()`:9 項(value=location key,奧社→`okusha_stair`),回淺拷貝(防外部污染)。
- [ ] `_panel(locKey)`:embed `image.url`=`cdnBase+image`、description 含 name+flavor;未知 key→fallback torii。
- [ ] `_shitsureiOnEnter(oldLastVisit, nowEpoch)`:`{closed:false}`→負 buff `{axis:'body',delta:-5,expireAt:now+3d,source:'shitsurei_taijou'}`;`{closed:true}` 或 null/undefined→null。
- [ ] **失礼 buff 與引擎相容**:`{axis:'body',delta:number,expireAt}` 正好走 computeLuck step2 buff 路徑(body 合法軸、delta 數字、未過期)→ 會被扣到。黑箱不顯數字。
- [ ] commands/buttons/selects 為空陣列(handler 屬 S3-0a-ii)。

## 3. 已知/刻意(非 bug)
- 建構子 `(connection, redis, deps={})`:第三參選填供測注入,不影響 discord.js `new Shrine(connectionPool, redis)`。
- `_shitsureiOnEnter` 帶 `nowEpoch` 參數(可注入以離線測 expireAt)。
- customId 組裝測試未做 → 屬 S3-0a-ii(本格無 handler)。

## 4. Findings 回報
Blocking / Non-blocking / Nit。修正回 sweetbot-next 改後同步 `impl-s3/`。過了 → **S3-0a-ii 面板互動接線(Fable5)**。
