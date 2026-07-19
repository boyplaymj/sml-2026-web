# 🛠️ S3-0a 施工單（給 Fable 5）：神社境內面板 + 地圖導覽骨架

> **任務**：玩家 `!神社` → 走進神社,在 ephemeral 私人面板上用下拉選單「移動」到各設施,地圖合成圖 + 側欄同步切換。
> **只做這格(骨架)**：面板開啟 + 地圖導覽換圖。**不含任何設施操作**(抽籤/請御守/回收/除厄/市集/奧社試煉都是後續 S3-0b~S3-5)。
> **不要做**:設施業務邏輯、開放時間閘(那些屬有操作的階段)、奧社試煉。
> 權威樹 `/opt/sml/sweetbot-next`。做完 → Opus 覆核 → Codex 驗。**先不 commit。**

---

## 0. 素材與框架事實(已驗證)

- **地圖素材**:`tools/jinja-shrine/map/positions.json`(在 repo)。10 定點,CDN 圖 `https://image.boyplaymj.link/shrine/map/<image>`。側欄高亮已**烤進圖片**,程式端不用畫側欄。
- **框架**(discord.js):模組暴露 `commands`/`buttons`/`selects` 三陣列,由 `interactionCreate` 依 `interactionStruct.name === key` 派發。
  - `interactionStruct`(ButtonHelper.init 產):`.name`(customId 首段=key)、`.args`(其餘段)、**`.values`**(下拉選中值陣列)、`.interaction`、`.user`、`.msg`、`.channelId`、`.level`。
  - customId 用 `DiscordButtonHelper.getCustomID(key, dataArr)`(以 `Config.interactionDataTag` 串接;反解=`split`)。
  - **ephemeral**:文字指令 reply 是公開;要私人面板 → 由**按鈕互動** `interaction.reply({..., ephemeral:true})` 開;之後導覽用 `interaction.update(obj)` 原地換(ephemeral 持續有效)。
  - **參考範本**:`model/DailyQuest.js`(`!每日` 面板 obj `{embeds,components}` + `button.interaction.update(obj)`)。

---

## 1. 面板流程(骨架)

```
!神社(文字指令,公開)
  → 發公開一行入口訊息 + 單一按鈕 [⛩️ 參拜する](customId shrenter)
[⛩️ 參拜する] 按鈕
  → interaction.reply({ embeds:[panel(torii)], components:[nav select], ephemeral:true })
下拉選單「境內を移動」(customId shrnav,選中值=facilityKey)
  → interaction.update({ embeds:[panel(該location)], components:[nav select] })
```

- **進場預設**:`torii`(鳥居)。
- **panel(loc)**:`new EmbedBuilder().setTitle('⛩️ 甜甜神社').setDescription('**' + loc.name + '**\n' + flavor[loc.key]).setColor(0xC0392B).setImage(cdnBase + loc.image)`。
- **nav select**:`StringSelectMenuBuilder` customId `getCustomID('shrnav', [])`,9 選項(見 §2),placeholder「⛩️ どちらへ參りますか」。放進一個 ActionRow。
- **奧社**:選「奧社」→ 導到 `okusha_stair` location,description 附「(試煉は準備中です)」——本階段不接試煉,只顯示石段圖。`okusha_top` 本階段不進。

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

## 4. 檔案清單

| 檔 | 動作 |
|---|---|
| `model/shrine/Shrine.js` | **新**。載入 positions.json(require)、`commands`(`!神社`)、`buttons`(`shrenter`)、`selects`(`shrnav`)、`_panel(locKey)` 純函式組 embed obj、flavor 常數 |
| `test/shrinePanel.test.js` | **新**。單測「純」部分(見 §6) |
| `discord.js` | **⚠️ 三處各加一行**(見 §5)。此檔別 session 常動,只加你這三行、別碰其他 |

---

## 5. discord.js 註冊（只加這三行，勿動他處）

1. 模組實例(約 line 157 dailyQuest 附近):`const shrine = new Shrine(connectionPool, redis);`（Shrine 建構子簽名比照 DailyQuest `(connection, redis)`；用不到 redis 也留參數位）
2. commands 匯總(約 line 345 `...dailyQuest.commands` 之後):`...shrine.commands,`
3. buttons 匯總(約 line 475 之後):`...shrine.buttons,`
4. selects 匯總(約 line 560 之後):`...shrine.selects,`

> require:檔頭加 `const Shrine = require('./model/shrine/Shrine.js');`（比照其他模組 require 群）。

---

## 6. 單元測試（node:test，只測純邏輯）

互動流程無法離線單測 → **只測純函式**;流程留待重啟後手動點測(§8)。
1. `resolveLocation(key)`:合法 key → 回對應 location（name/image/facility）；未知 key → null（或 fallback torii）。
2. `_panel(locKey)`:回的 embed 物件 `.data.image.url` = 正確 CDN URL、`.data.description` 含 location name + flavor。
3. customId：`shrnav` select 的 customId 用 `getCustomID('shrnav',[])`；`shrenter` 同理。
4. positions.json 完整性:9 導覽選項的 value 都能在 positions.json 找到 location。

> 把可測邏輯抽成 `Shrine.prototype.resolveLocation` / `_panel`（不碰 interaction）以便單測；handler(func)薄薄呼叫它們。

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
