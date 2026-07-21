# 🛠️ S3-sanpai 施工單:本殿「參拜」(二拝二拍手一拝 → 月度取得獎勵乘數)

> **任務**:本殿多步參拜儀式 → 定「當月 sanpai 取得乘數」,套在**御守/御神籤/御朱印取得的獎勵**上。做錯 → 當月取得獎勵全歸零;做對 → 祈求軸取得獎勵上升;沒做 → 中性。
> **權威樹**=`/opt/sml/sweetbot-next`。做完 `node --test test/shrine*.test.js` 全綠 + eslint 乾淨 → 交 Opus 覆核。
> **實作者**:Fable5。**風格/結構嚴格照既有手水(temizu)那條線**(applyTemizuMult 的孿生機制)。
> **命門 = 順序判定 + 月度 gate + 取得乘數解析(純函式、可離線單測)**。

---

## 0. 定案規則(照做)
**流程(玩家在本殿依序做 5 個決策;customId 累積、完成才判定、無中途 DDB 寫,銅板除外):**
1. **賽銭**:按鈕 `[🪙 1🦷][🪙 5🦷][🪙 10🦷][🪙 50🦷]` → 面額=**牙齒成本**,按下當下扣款。正解面額 = **5 或 50**。
2. **手勢①**:`[🙇 舉恭1][🙇🙇 舉恭2][👏 拍手1][👏👏 拍手2][👏👏👏 拍手3]` → 正解 = **舉恭2**。
3. **手勢②**:同上五鈕 → 正解 = **拍手2**。
4. **祈願**:StringSelect(6 軸,見 §比照籤詩)→ 選祈求對象(任一皆可,不影響對錯,只決定加乘落哪軸)。
5. **手勢③**:同上五鈕 → 正解 = **舉恭1**。

**正解全序** = `coin∈{5,50}` 且 `手勢①=舉恭2` 且 `手勢②=拍手2` 且 `手勢③=舉恭1`(祈願任選)。

**判定與效果(月制):**
- **月度 gate**:`fortune.sanpaiMonth === 台北當月(YYYY-MM)` → 本月已參拜 → 擋(本殿只回「今月は参拜済み」氛圍文字,不能重做)。**一個月一次、完成即定生死。**
- **完成後 setSanpai(month, ok, wish)**:
  - **做對** → `ok=true, wish=<選的軸>`。效果:當月該 wish 軸的「取得獎勵」×`wishMult`(預設 1.5),其餘軸 ×1.0。
  - **做錯** → `ok=false, wish=null`。效果:當月**所有**取得獎勵 ×`failMult`(預設 0)= 買御守 boost、抽御神籤祝福、御朱印獎勵全歸零,直到下月重新參拜。
  - **本月沒參拜**(sanpaiMonth≠當月)→ 中性 ×1.0(不罰)。
- **黑箱**:全程不顯數字、不顯對錯;完成才給氛圍文字(對:神威加持;錯:神色黯然,但**不明說錯**)。
- **銅板扣款時機**:第 1 步按下即扣(丟出去了)。中途放棄=香油錢沒了、月度未鎖、可再擲。餘額<面額 → 不扣、停在賽銭步。

**gate by `config.sanpai.enabled`(預設 true=已上線生效)。**

---

## 1. 照抄的既有接口(別另寫)
- **完全比照手水**:`model/shrine/ShrineTemizu.js`(純核心)+ `resolveTemizuMult`/`applyTemizuMult` 的用法。sanpai 是它的**月度孿生**。
- **扣費/餘額** `DAO/DDB/ViewerDetailDAO.js`:`selectOne({discordId})` 查 `point`、`givePoint([id], -coin, 'point', '本殿參拜(賽銭)')`(先查再扣,同 grant)。
- **config** `ShrineConfigDAO.getMain()`:可能 null/缺欄 → deep-merge `DEFAULT_SHRINE_CONFIG.sanpai`。
- **fortune 表** `DAO/DDB/ShrineFortuneDAO.js`:本單新增 `setSanpai`(§4)。欄位加在既有 item 上。
- **台北日期工具**:`ShrineOmikujiService.taipeiDateStr` 已 export;**新增月字串** helper(見 §2)。
- **面板/按鈕註冊** `Shrine.js`:本殿操作鈕在 `_facilityActionRow`(現 honden 分支=null,改成加 `[🙏 参拜する]` = `shract honden/sanpai`);handler 表照 `shrtemizu` 加 `shrsanpai`(按鈕)+ `shrsanpaiwish`(select);act dispatch 加 `honden/sanpai → openSanpai`。
- **customId 累積 + 讀訊息保留版位**:照手水 `pressTemizu`/`_temizuRow`/`_readTemizuOrder` 那套(手勢步同理)。

---

## 2. 純核心 `model/shrine/ShrineSanpai.js`(可單測,命門)
```js
// 手勢 token:b1/b2=舉恭1/2、c1/c2/c3=拍手1/2/3。正解手勢序(不含賽銭/祈願)=[b2,c2,b1]。
const CORRECT_GESTURES = ['b2', 'c2', 'b1'];

// ① 判定:acc=[coin, g1, g2, wish, g3](完整 5 元素)。
//    correct ⇔ correctCoins.includes(coin) && g1===b2 && g2===c2 && g3===b1(wish 任意)。
function judgeSanpai(acc, correctCoins) {
  if (!Array.isArray(acc) || acc.length !== 5) return { ok: false, wish: null };
  const [coin, g1, g2, wish, g3] = acc;
  const ok = correctCoins.map(String).includes(String(coin)) &&
             g1 === 'b2' && g2 === 'c2' && g3 === 'b1';
  return { ok, wish: ok ? wish : null };
}

// ② 台北月字串:nowEpoch → 'YYYY-MM'(+8h 後取 UTC 年月)。
function taipeiMonthStr(nowEpoch) {
  return new Date((nowEpoch + 8 * 3600) * 1000).toISOString().slice(0, 7);
}

// ③ 當月某軸的「取得獎勵乘數」解析(取用端):enabled gate + 月界 + 缺欄 fail-safe。
function resolveSanpaiMult(config, fortune, monthStr, axis) {
  const s = config && config.sanpai;
  if (!s || s.enabled !== true) return 1.0;                 // 未啟用=不動
  if (!fortune || fortune.sanpaiMonth !== monthStr) return 1.0; // 本月沒參拜=中性
  if (fortune.sanpaiOk !== true) return (s.failMult != null) ? s.failMult : 0; // 做錯=歸零
  // 做對:祈求軸 ×wishMult、其餘 ×1.0
  return (axis && axis === fortune.sanpaiWish) ? ((s.wishMult != null) ? s.wishMult : 1.5) : 1.0;
}

// ④ 折扣套用(只折正向 delta;逐 buff 依自身 axis 取乘數)。全 1.0 → 原陣列(省算)。
function applySanpaiMult(config, fortune, buffs, monthStr) {
  const s = config && config.sanpai;
  if (!s || s.enabled !== true) return buffs;
  return (buffs || []).map(b => {
    if (!b || !(b.delta > 0)) return b;                     // 負向/零不動
    const m = resolveSanpaiMult(config, fortune, monthStr, b.axis);
    return (m === 1.0) ? b : { ...b, delta: Math.round(b.delta * m) };
  });
}
module.exports = { judgeSanpai, taipeiMonthStr, resolveSanpaiMult, applySanpaiMult, CORRECT_GESTURES };
```
> ⚠️ 只折**正向**(獎勵),負面(凶籤負項)不動——同手水鐵律。做錯 failMult=0 → 正向獎勵全 0。

---

## 3. config 新增 `sanpai` 區塊(`defaults.js` + `seed_shrine_config.js`)
```js
sanpai: {
  enabled: true,
  coins: [1, 5, 10, 50],        // 可擲面額(=牙齒成本)
  correctCoins: [5, 50],        // 正解面額(5円/50円=御縁)
  wishMult: 1.5,                // 做對:祈求軸取得獎勵 ×1.5
  failMult: 0,                  // 做錯:當月所有取得獎勵 ×0
  image: null                   // 本殿參拜圖(null → 用 MAP honden.png;待使用者提供後填 CDN URL)
}
```

## 4. `ShrineFortuneDAO.setSanpai(discordId, {month, ok, wish})`
- 單次 Update:`SET sanpaiMonth=:m, sanpaiOk=:o, sanpaiWish=:w`(correct-key `{discordId}`、doc client;wish 可為 null)。不動 buffs。

---

## 5. `Shrine.js` 本殿參拜面板 + 狀態機
**比照手水的 customId 累積法。acc 元素為字串:coin∈{'1','5','10','50'}、gesture∈{'b1','b2','c1','c2','c3'}、wish=軸key。**

- **本殿操作鈕**:`_facilityActionRow` honden 分支 → `[🙏 参拜する]` = `shract honden/sanpai`。act dispatch 加 `honden/sanpai → openSanpai`。
- **openSanpai(struct)**:讀 fortune;`month=taipeiMonthStr(now)`;若 `fortune.sanpaiMonth===month` → reply「🙏 今月はもう参拜されました。来月またどうぞ。」;否則 reply ephemeral **本殿圖 embed**(`config.sanpai.image || MAP.cdnBase+'honden.png'`)+ 賽銭按鈕列(4 顆,customId `shrsanpai`+[coinVal],acc 空)。
- **pressSanpai(client, struct)**(button `shrsanpai`;args=[choice, ...priorAcc]):
  - `month=taipeiMonthStr(now)`;讀 fortune;若 `sanpaiMonth===month` → update「今月はもう…」收面板(防競態)。
  - `choice=args[0]`; `priorAcc=args.slice(1)`; `newAcc=[...priorAcc, choice]`。
  - **若 newAcc.length===1(剛擲幣)**:choice 是 coin。查餘額 `< coin` → reply/update「牙齒が足りないみたい」停在賽銭步(不進);足 → `givePoint(-coin, …)` 扣款 → 進手勢①。
  - **依 newAcc.length 決定下一控件**:
    - 1 → 手勢①(5 手勢鈕,acc=newAcc)
    - 2 → 手勢②(5 手勢鈕)
    - 3 → **祈願 select**(`shrsanpaiwish`,customId 帶 acc=newAcc=[coin,g1,g2];6 軸選項)
    - 4 → (不會由 button 觸發,見 select)
    - 5 → **完成判定**(見下)
  - **手勢/賽銭鈕列**:照手水,已按不重要(逐步換頁),每次 render 帶 acc 在 customId;顯示「參拜中… N/5」。手勢鈕**位置每次可固定**(不必打散,本儀式重點是選對「內容」非位置;但賽銭 4 顆固定順序即可)。
- **pickSanpaiWish(client, struct)**(select `shrsanpaiwish`):`priorAcc=args`(=[coin,g1,g2]);`wish=values[0]`;`newAcc=[...priorAcc, wish]`(len4)→ update 手勢③(5 手勢鈕,acc=newAcc)。
- **完成(newAcc.length===5,在 pressSanpai 手勢③按下)**:
  - `cfg=deep-merge sanpai`;`{ok, wish}=judgeSanpai(newAcc, cfg.correctCoins)`。
  - `setSanpai(discordId, {month, ok, wish})`。
  - update 收面板:對→「🙏 神威が宿りました。祈りは聞き届けられた。」;錯→「🙏 参拜を終えました。…神殿は静まりかえっている。」(不明說錯、不顯數字)。
- **註冊**:buttons 加 `shrsanpai`;selects 加 `shrsanpaiwish`。
- **黑箱**:全程不顯乘數/對錯。

**祈願 6 軸(比照籤詩分項→軸,label 用中文)**:`zaiun 財運 / shengun 勝運 / zhiun 智運 / body 厄除 / renyuan 人緣 / xingyun 行運`。

---

## 6. 接線:御守 grant / 御神籤 draw 套 sanpai 乘數(疊在手水之後)
**取得當下,手水折扣後再套 sanpai 折扣(兩層相乘)。**
- **`ShrineOmikujiService.draw`**:寫首抽 buff 前,現有 `buffs = applyTemizuMult(...)` 之後**再加一行** `buffs = applySanpaiMult(fullCfg||DEFAULT, fortune, buffs, taipeiMonthStr(nowEpoch))`(fortune 已讀、fullCfg 已取)。
- **`ShrineOmamoriService.grant`**:算 `boostToStore` 時,現有 temizu 折扣後**再乘** sanpai:`mult = resolveTemizuMult(...) * resolveSanpaiMult(cfg||DEFAULT, fortune, taipeiMonthStr(nowEpoch), axis)`;`boostToStore = boost>0 ? Math.round(boost*mult) : boost`。(fortune 這裡已為 temizu 讀取;若 temizu 停用而 sanpai 啟用,仍需讀 fortune → 調整 gate:temizu 或 sanpai 任一啟用就讀 fortune。)
- **御朱印**:尚未實作;日後蓋印給 buff 前同樣套 applySanpaiMult(本單先不做,留註解)。
- ⚠️ **負面不折**(helper 內 delta>0 守門)。做錯 failMult=0 → 這兩處正向獎勵全 0。

---

## 7. 測試 `test/shrineSanpai.test.js`(純核心 + handler + 接線)
1. `judgeSanpai`:`['5','b2','c2','zaiun','b1']`→ok+wish=zaiun;`['50',...]`同;`['10',...]`→ok:false;手勢錯任一→ok:false;長度≠5→ok:false。
2. `resolveSanpaiMult`:enabled=false→1.0;本月無參拜→1.0;做錯→failMult(0);做對+wish軸→wishMult(1.5);做對+他軸→1.0。
3. `applySanpaiMult`:做錯→正向×0、負向原樣;做對→wish軸正向×1.5、他軸×1.0。
4. `taipeiMonthStr`:跨月/台北時區邊界正確。
5. handler(stub DAO):賽銭扣款(足/不足)、逐步 acc 累積(customId 帶序)、祈願 select 進第5步、第5按完成判定 setSanpai(對/錯)、月度 gate 擋重做。
6. 接線:draw/grant 疊 sanpai——做錯→buff/boost 歸 0;做對 wish 軸→×1.5;手水×參拜相乘(如 temizu0.5×sanpai1.5)。
7. 既有測試不受影響:未帶 sanpai 欄位的 fortune → 1.0(所有 shrine* 測試仍全綠)。**omamori/omikuji 既有測試預設玩家改成「本月已正確參拜對應狀態 or sanpai 停用」以隔離**(比照手水隔離手法:預設 config sanpai.enabled=false 或 fortune 帶 sanpaiMonth=本月+ok+wish;擇一,保持既有斷言不變)。

---

## 💰 成本控管
純 fortune 欄位讀寫(既有表)+ 面板 + 一次賽銭 givePoint,**無新表、無 LLM、無付費 API**。免四件套。**不動 ShrineLuck 引擎**(全在取得端乘數)。
