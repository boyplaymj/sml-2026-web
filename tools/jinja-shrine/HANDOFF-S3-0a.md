# 🛠️ S3-0a 施工單（給 Fable 5）：神社境內面板 + 導覽 + 入退場礼（visit 狀態機地基）

> **任務**：玩家 `!神社` → 鳥居前**先一礼(硬門)才入境** → ephemeral 私人面板下拉「移動」各設施(換圖+側欄同步) → 離開時**一礼して退く**;沒好好退場(放置)→ 下次進場**失礼補扣運**。
> **這格含**:面板開啟 + 地圖導覽換圖 + **入場一礼硬門 + 退場一礼 + visit 開/關 + 失礼 lazy 結算地基**。
> **不含**:手水五步(S3-1)、本殿參拜/請御守/回收/除厄/市集/御朱印/奧社試煉(各自後續)。**設施選單到了只顯示圖+風味文字,操作按鈕先不放。**
> 依據:`RITUAL.md`(參拜作法,§決策已定案)。權威樹 `/opt/sml/sweetbot-next`。做完 → Opus 覆核 → Codex 驗。**先不 commit。**

---

## 0. 素材與框架事實(已驗證)

- **地圖素材**:`tools/jinja-shrine/map/positions.json`(在 repo)。10 定點,CDN 圖 `https://image.boyplaymj.link/shrine/map/<image>`。側欄高亮已**烤進圖片**,程式端不用畫側欄。
- **框架**(discord.js):模組暴露 `commands`/`buttons`/`selects` 三陣列,由 `interactionCreate` 依 `interactionStruct.name === key` 派發。
  - `interactionStruct`(ButtonHelper.init 產):`.name`(customId 首段=key)、`.args`(其餘段)、**`.values`**(下拉選中值陣列)、`.interaction`、`.user`、`.msg`、`.channelId`、`.level`。
  - customId 用 `DiscordButtonHelper.getCustomID(key, dataArr)`(以 `Config.interactionDataTag` 串接;反解=`split`)。
  - **ephemeral**:文字指令 reply 是公開;要私人面板 → 由**按鈕互動** `interaction.reply({..., ephemeral:true})` 開;之後導覽用 `interaction.update(obj)` 原地換(ephemeral 持續有效)。
  - **參考範本**:`model/DailyQuest.js`(`!每日` 面板 obj `{embeds,components}` + `button.interaction.update(obj)`)。

---

## 1. 面板流程(含入退場礼)

```
!神社(文字指令,公開)
  → 公開一行入口訊息 + 單一按鈕 [⛩️ 甜甜神社へ](customId shrenter)
[⛩️ 甜甜神社へ] 按鈕
  → ① 先做「上一趟 lazy 結算」(§3):若上趟未一礼退場 → 失礼扣運(append 負 buff)
  → ② 開新 visit(fortune.lastVisit = { openAt, closed:false })
  → ③ reply ephemeral:torii 圖 + 描述「鳥居の前。まず一礼を。」+ 唯一按鈕 [🙇 一礼して入る](shrbow{tag}in)
      ⚠️ 硬門:此時「不出」導覽選單,必須先一礼
[🙇 一礼して入る]
  → update:torii 圖 + 導覽下拉(§2) + [🙇 一礼して退く](shrbow{tag}out) → 正式入境
下拉「境內を移動」(shrnav,值=facilityKey)
  → update:panel(該 location) + 導覽下拉 + [🙇 一礼して退く]
[🙇 一礼して退く]
  → 標記 fortune.lastVisit.closed = true(乾淨退場,無失礼)
  → update:一行「またのお參りを。」+ 清空 components(面板結束)
```

- **進場預設**:`torii`(鳥居)。
- **panel(loc)**:`EmbedBuilder().setTitle('⛩️ 甜甜神社').setDescription('**'+loc.name+'**\n'+flavor[loc.key]).setColor(0xC0392B).setImage(cdnBase+loc.image)`。
- **入場前**只給 `[🙇 一礼して入る]`;一礼後才給導覽 + 退場礼鈕。
- **nav select**:`StringSelectMenuBuilder` customId `getCustomID('shrnav',[])`,9 選項(§2),placeholder「⛩️ どちらへ參りますか」。每個 location 面板都要**同時帶導覽下拉 + 退場礼鈕**兩個 ActionRow。
- **奧社**:選「奧社」→ `okusha_stair` 石段圖,description 附「(試煉は準備中です)」;不接試煉。

> **運氣黑箱**:失礼扣運**不顯數字**,只給神職文字(例:「礼を欠いたようですね…」)。守禮的微加持本階段可先不發(留 S3-1 手水一起),但**退場礼要能標記 closed**。

---

## 2. 導覽選單選項(9 設施 → facilityKey)

依 positions.json 的 facility(奧社只出 1 個入口,對到 okusha_stair):

| label | emoji | value(facilityKey→location key) |
|---|---|---|
| 鳥居 | ⛩️ | torii |
| 表參道の市集 | 🎪 | ichiba |
| 古札納所 | ♻️ | kosatsu |
| 手水舍 | 💧 | temizu |
| 本殿 | ⛩️ | honden |
| 授與所 | 🏪 | juyosho |
| 御朱印受付所 | 📿 | goshuin |
| 御祈禱受付所 | 🙏 | gokitou |
| 奧社 | ⛰️ | okusha_stair |

> value 直接用 location key(torii/ichiba/…/okusha_stair),handler 拿 `struct.values[0]` 去 positions.json 找 location。

---

## 3. 風味文字 flavor[key]（無運氣數值、純情境）

```
torii:        參道の入口。鳥居をくぐって境內へ。
ichiba:       表參道の市集。掘り出し物があるかも。
kosatsu:      古札納所。古いお守りやお札を納める所。
temizu:       手水舍。參拜の前に心身を清めよう。
honden:       本殿。麻雀大明神が祀られている。
juyosho:      授與所。お守りや神札を授かれる。
goshuin:      御朱印受付所。參拜の証をいただこう。
gokitou:      御祈禱受付所。厄を祓う場所。
okusha_stair: 奧社への石段。この先の試煉を越えた者だけが辿り着ける。
```

---

## 3.5 visit 狀態機 + 失礼 lazy 結算（本階段地基）

**設計(對齊 RITUAL.md,最省 DDB 寫入)**:
- 儀式進度(入場/退場)**跨 visit 的關鍵狀態存 fortune**,面板內的暫態進度靠 customId 帶(stateless);**只在進場、退場各寫一次**。
- `fortune.lastVisit = { openAt:epoch, closed:bool }`。
  - **進場** [shrenter]:先 lazy 結算(見下)→ 再 `openVisit`:寫 `lastVisit={openAt:now, closed:false}`。
  - **退場礼** [shrbow out]:`closeVisit`:`SET lastVisit.closed = true`。
  - **一礼して入る** [shrbow in]:本階段只是硬門解鎖導覽(可不寫 DB,或標 `lastVisit.bowedIn=true` 供將來);簡化:不寫、純 UI 解鎖即可。
- **lazy 結算(進場時跑一次)**:讀舊 `lastVisit`;若存在且 `closed===false`(上趟沒一礼退場就放置)→ **失礼**:append 負 buff `{axis:'綜合視為六軸或標記', delta:-5, expireAt:now+3*86400, source:'shitsurei_taijou'}` + 記一筆給玩家的神職斥責(下次面板頂或本次進場提示)。→ **然後才 openVisit 覆蓋**。
  > 綜合運是衍生值(六軸均值),要扣「綜合」等於扣某軸;**本階段失礼 buff 直接扣 `body`(厄除)一項當代表**(config 可調哪軸/幾點);或引擎另加「visit 失礼」因子(S3 尾再精緻化)。**S3-0a 先用「append 負 buff 到 body」最省事、且 computeLuck 既有 buff 路徑會吃到。**

**DAO 需新增(`ShrineFortuneDAO`)**
```js
// 開新 visit(覆蓋)。回傳舊的 lastVisit 供 lazy 結算判斷。
async openVisit(discordId, now) // GET 舊 lastVisit → SET lastVisit={openAt:now,closed:false} → 回舊值
async closeVisit(discordId)     // SET lastVisit.closed = true
async appendBuff(discordId, buff) // SET buffs = list_append(if_not_exists(buffs,:empty), :b)（原子 append）
```
> `appendBuff` 用 UpdateExpression `list_append`;`openVisit` 可先 GetItem 拿舊值(給 lazy 判斷)再 Update。correct-key `{discordId}`。

---

## 4. 檔案清單

| 檔 | 動作 |
|---|---|
| `model/shrine/Shrine.js` | **新**。載入 positions.json、`commands`(`!神社`)、`buttons`(`shrenter`/`shrbow`)、`selects`(`shrnav`)、`_panel(locKey)`、`_openingPanel()`(只有一礼鈕)、flavor 常數、失礼 lazy 結算邏輯 |
| `DAO/DDB/ShrineFortuneDAO.js` | **加** `openVisit`/`closeVisit`/`appendBuff`(§3.5,import 已有 UpdateCommand/GetCommand) |
| `test/shrinePanel.test.js` | **新**。單測純部分 + DAO 方法 stub 驗(見 §6) |
| `discord.js` | **⚠️ 四處各加一行**(見 §5)。此檔別 session 常動,只加你這幾行、別碰其他 |

---

## 5. discord.js 註冊（只加這三行，勿動他處）

1. 模組實例(約 line 157 dailyQuest 附近):`const shrine = new Shrine(connectionPool, redis);`（Shrine 建構子簽名比照 DailyQuest `(connection, redis)`；用不到 redis 也留參數位）
2. commands 匯總(約 line 345 `...dailyQuest.commands` 之後):`...shrine.commands,`
3. buttons 匯總(約 line 475 之後):`...shrine.buttons,`
4. selects 匯總(約 line 560 之後):`...shrine.selects,`

> require:檔頭加 `const Shrine = require('./model/shrine/Shrine.js');`（比照其他模組 require 群）。

---

## 6. 單元測試（node:test，只測純邏輯 + DAO stub）

互動流程無法離線單測 → **測純函式 + 失礼判定 + DAO**;面板點擊留重啟後手動測(§8)。
1. `resolveLocation(key)`:合法→location;未知→null(或 fallback torii)。
2. `_panel(locKey)`:embed `.data.image.url`=正確 CDN URL、`.data.description` 含 name+flavor。
3. customId:`shrnav`/`shrenter`/`shrbow`(in/out)都用 `getCustomID` 組;`shrbow` 的 args 能反解出 in/out。
4. positions.json:9 導覽 value 都能找到 location。
5. **失礼判定純函式** `_shitsureiOnEnter(oldLastVisit)`:`{closed:false}` → 回失礼 buff 物件(delta 負、expireAt=now+3d、source);`{closed:true}` 或 `null` → 回 null(不扣)。
6. **DAO(stub ddb.send)**:`openVisit` 回舊 lastVisit 且 SET 新值;`closeVisit` UpdateExpression 設 `lastVisit.closed=true`、Key `{discordId}`;`appendBuff` 用 `list_append`。

> 可測邏輯抽成 `resolveLocation`/`_panel`/`_shitsureiOnEnter`(不碰 interaction);handler 薄薄呼叫。

---

## 7. 鐵律
- **只做導覽骨架**,設施操作按鈕**先不放**(下一格 S3-0b)。奧社試煉不接。
- 面板私人(ephemeral),導覽用 `interaction.update`。
- bind 檢查走框架預設(不 skipBindCheck→未綁定者框架自動擋,無需自寫)。
- 只 commit shrine 相關 + discord.js 那三行;**先不 commit**（Opus 覆核後提交）。
- 回報:新檔全文 + discord.js 改的三行 + `node --test` 結果 + 不確定處。

## 8. 驗收(Opus/Codex + 手動)
- Codex:程式正確性 + 只動該動的行 + 純測綠。
- 手動(重啟後):`!神社` → 點參拜 → 私人面板出現(torii 圖)→ 下拉切各設施 → 圖與側欄同步換 → 奧社顯示石段+試煉準備中。**此步需 bot restart,與 S2 部署窗口一起排。**
