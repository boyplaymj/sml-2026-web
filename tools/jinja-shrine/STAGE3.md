# ⛩️ 甜甜神社 — STAGE 3：Discord 面板 / 境內導覽 wiring（架構）

> S3 = 把 S0~S2 的引擎/服務接成玩家可操作的 **Discord 境內地圖面板**。玩家 `!神社` 進場,在地圖上「走動」(換合成圖 + 側欄同步),到設施觸發操作(抽籤/請御守/回收/除厄/市集/奧社試煉)。
> **UI 哲學(已拍板)**：運氣全隱藏黑箱(不給數字);地圖走 embed 合成圖(非 emoji 拼圖);地標=紅圖釘;正式圖無文字。
> 素材:`tools/jinja-shrine/map/positions.json`(10 定點座標+側欄row+CDN 檔名);圖在 `image.boyplaymj.link/shrine/map/*.png`。

---

## 1. 分層(既有 vs 新增)

| 層 | 檔 | 狀態 |
|---|---|---|
| 純引擎 | `model/shrine/ShrineLuck.js`(computeLuck/getLuck 用) | ✅ S1/S2 |
| 服務 | `ShrineOmamoriService`(grant/recycle)、`ShrineHaraiService`(harai) | ✅ S2 |
| DAO | `Shrine{Fortune,Omamori,Config}DAO` | ✅ |
| **控制器(新)** | **`model/shrine/Shrine.js`** = Discord 面板 + 導覽 + 設施操作 dispatch | ⬜ S3 |
| 素材資料 | `tools/jinja-shrine/map/positions.json`(bot 端載入或內嵌成 const) | ✅ |

> `Shrine.js` **只做 Discord 互動與導覽**,所有業務邏輯呼叫既有 service(不重寫);缺的 service(抽籤/手水/市集/御朱印/奧社試煉)在各自子階段補。

---

## 2. 面板模型(進場 → ephemeral 私人面板 → 原地更新)

框架無 slash 指令,但 ephemeral 可由**按鈕互動**產生 → 用「公開入口 + 私人面板」:

1. **`!神社`**(文字指令)→ 發**公開一行入口**:`⛩️ 甜甜神社の鳥居が見える` + 單一按鈕 `[⛩️ 參拜する]`(customId `shrenter`)。多人共用同一入口訊息、各自點各自開,不洗頻。
2. **點 `[參拜する]`** → `interaction.reply({ embeds, components, ephemeral:true })` 開**私人面板**(只有點的人看得到):
   - `embed.image = CDN/<當前location>.png`(進場預設 `torii`)
   - `embed.description` = 該地點名 + 風味文字(例:鳥居「參道の入口。ようこそ」)
   - components = 導覽 + 當前設施操作(見 §3)
3. **導覽/操作按鈕** → `interaction.update(...)` **原地換圖換鈕**(ephemeral 訊息可持續 update;每次點擊是新 component interaction,token 各自有效)。**無需伺服器端面板 state**:目的地/設施 key 全編進 customId(stateless)。

> ephemeral 訊息 ~15 分後互動 token 失效 → 面板自然過期,重點 `!神社` 再開即可。

### customId 規範(沿用 `DiscordButtonHelper.getCustomID(key, data)`,`Config.interactionDataTag` 串接)
| 用途 | key | data | 行為 |
|---|---|---|---|
| 入口開面板 | `shrenter` | [] | reply ephemeral 面板(torii) |
| 前往設施(導覽) | `shrgo` | [facilityKey] | update 面板成該 location |
| 設施操作 | `shract` | [facilityKey, actionId] | 執行操作(§4)後 update/follow-up |

導覽建議用 **String Select(下拉選單)** 列 9 設施(1 元件容 9 選項、附 emoji),避免按鈕塞太多;select 的 value = facilityKey,handler 同 `shrgo`。當前設施的**操作**放 select 下方一排 context 按鈕。

---

## 3. 導覽(hybrid:可跳 + 奧社須走試煉)

- **一般設施**:下拉選單可**直接跳**到 9 設施任一(換 `positions.json` 對應 location 的 CDN 圖 + 側欄該 row 已烤進圖)。
- **奧社**:選「奧社」→ 進 `okusha_stair`(樓梯/試煉起點)location,顯示 `[挑戰聽牌試煉]` 按鈕;**通過 10 關**才切到 `okusha_top`(內殿)location 解鎖深參拜/限定品(見 §4 okusha)。
- 手水**非 gate**:主殿/奧社**不擋**;手水只決定當日 `temizuMult`(RITUAL §4),折扣運氣提升,由 `applyTemizuMult` 在各 grant 點套用。

---

## 4. 設施操作 dispatch(接既有 service / 標未建)

| 設施(facilityKey) | 操作按鈕 | 接哪個 service | 狀態 |
|---|---|---|---|
| `juyosho` 授與所 | 請御守(選 type) | `ShrineOmamoriService.grant` | ✅ 已備 |
| `kosatsu` 古札納所 | 回收御守 | `ShrineOmamoriService.recycle` | ✅ 已備 |
| `gokitou` 御祈禱 | 除厄(選性別) | `ShrineHaraiService.harai` | ✅ 已備 |
| `honden` 本殿 | 參拜抽籤 | **ShrineOmikujiService.draw(新)** — 讀 omikuji-pool→抽階→寫 fortune.buffs(分項 score→六軸 buff);抽到吉凶+和歌+定性詩文(**不顯數值**) | ⬜ 待建(S3-2) |
| `temizu` 手水舍 | 今日清め | **手水(新)** — 五步作法→寫 `fortune.temizuDate`+`temizuMult`;每日一次免費、**非 gate** | ⬜ 待建(S3-1) |
| `ichiba` 市集 | 買(折扣)/賣(納回部分牙齒) | **市集 service(新)** — config 排程開市;賣=御守/神札→部分退牙 | ⬜ 待建(S3-3) |
| `goshuin` 御朱印 | 御朱印帳 | **御朱印 service(新)** — 蓋印/收藏(季節版) | ⬜ 待建(S3-4) |
| `okusha` 奧社 | 挑戰聽牌試煉 | **奧社聽牌試煉(新,大)** — MahjongHand 核心已備;翻牌回合引擎+TTL對局表+按鈕方陣 | ⬜ 待建(S3-5) |

> 操作結果一律**不顯運氣數值**(黑箱);抽籤只給吉凶/籤詩,御守/除厄給定性確認訊息。

---

## 5. 與 discord.js 整合

- `discord.js` 模組清單加:`const shrine = new Shrine(connectionPool, redis);`(比照 happyBirthday/trialGate)。
- `shrine.commands`(`!神社`)、`shrine.buttons`(shrenter/shrgo/shract)併入既有 commands/buttons 收集器。
- ephemeral、`interaction.update`、`DiscordButtonHelper` 全沿用既有。
- 開放時間閘(§DESIGN 5.3):參拜系操作前查 `config.hours`(台北時區),閉門顯示神職旁白;**進場檢查、不中途踢**。

---

## 6. 子階段切分(每階段 Codex 驗;先骨架後設施)

| 子任務 | 內容 | 主手 |
|---|---|---|
| **S3-0 面板骨架 + 導覽 + 3 現成操作** | Shrine.js:入口→ephemeral 面板→下拉導覽換圖+側欄同步→接 grant/recycle/harai 三個現成 service;開放時間閘;positions.json 載入 | Opus 架構 → Fable5 實作 |
| **S3-1 手水舍** | 五步作法→當日 `temizuMult`(fortune.temizuDate/temizuMult);**非 gate**、跨系統折扣 | Fable5 |
| **S3-2 本殿參拜抽籤** | ShrineOmikujiService.draw + omikuji-pool 豐富籤池 seed;抽階→buff;吉凶詩文(無數值) | Opus 命門 + Fable5 |
| **S3-3 市集買賣** | 開市排程 + 買折扣 + 賣道具納回部分牙齒 | Fable5 |
| **S3-4 御朱印帳** | 蓋印/收藏(季節版) | Fable5 |
| **S3-5 奧社聽牌試煉** | 翻牌回合引擎(TTL 對局表)+ 按鈕方陣 UI + MahjongHand 驗答(規格見 DESIGN §5.2 / mahjong-hand-core) | Opus 架構 + Fable5 |

> **S3-0 先做**:玩家能「走進神社、在地圖上移動、用三個現成設施」= 最小可玩閉環。其餘設施逐一疊上。

## 7. 待拍板
- 導覽用**下拉選單**(推薦,9 設施省版面)還是**方向按鈕**(參道上下走,更有移動感)?
- 風味文字(各地點旁白)批次待寫。
- (進場預設已定:`torii` 鳥居下,先一礼硬門。)

---

## 8. 執行切分（小任務 · 標主手 · 每階段 Codex 驗）

> 原則同 S2:每子任務**小到能一次做完 + 一次驗**。**先切「可單測核心」與「互動接線」**——互動流程無法離線單測(要 bot restart 手動點),把可測的邏輯獨立出來先做穩,接線再疊。做完 → Opus 覆核 → 同步 review 副本 → Codex 驗 → 過了才下一個。

| # | 子任務 | 內容 | 主手 | 可單測? | 依賴 |
|---|---|---|---|---|---|
| **S3-0a-i** | visit DAO + 面板純核心 | `ShrineFortuneDAO` 加 openVisit/closeVisit/appendBuff;`Shrine.js` 純 helper(resolveLocation/_panel/_shitsureiOnEnter/flavor/載入 positions);node:test 全綠 | **🔵 Fable5** | ✅ 純單測(最穩,先做) | positions.json ✅ |
| **S3-0a-ii** | 面板互動接線 | `Shrine.js` commands(`!神社`)/buttons(shrenter/shrbow)/selects(shrnav) handler + discord.js 4 行註冊 | **🔵 Fable5** | ❌ 手動(restart) | S3-0a-i |
| **S3-0b** | 3 現成操作 + 選擇子流程 | 授與所 grant(選 6 御守)/古札納所 recycle(列御守選)/御祈禱 harai(選性別);接 §4 已備 service | **🔵 Fable5** | 部分(service 已測) | S3-0a-ii |
| **S3-1** | 手水五步儀式 | 5 按鈕打散 + 全按完判順序(無提示) + 錯序失礼扣 + 當日 `temizuMult`(第一次定生死、多做不算);**命門=順序 enforcement**(RITUAL §3/§4) | **Opus 命門** + Fable5 | 順序判定純測 ✅ / 互動手動 | S3-0a-ii |
| **S3-2** | 本殿參拜抽籤 | **ShrineOmikujiService.draw(新命門)** 讀 omikuji-pool→抽階→六軸 buff(× temizuMult);**非 gate**;吉凶詩文**無數值** | **Opus 命門** + Fable5 | draw 純測 ✅ | S3-1 |
| **S3-3** | 市集買賣 | 開市排程 + 買折扣 + 賣道具納回部分牙齒 | **🔵 Fable5** | 部分 | S3-0a-ii |
| **S3-4** | 御朱印帳 | 蓋印/收藏(季節版) | **🔵 Fable5** | 部分 | S3-0a-ii |
| **S3-5** | 奧社聽牌試煉 | 翻牌回合引擎 + TTL 對局表 + 按鈕方陣 UI + MahjongHand 驗答(DESIGN §5.2) | **Opus 架構** + Fable5 | 純核心 ✅(MahjongHand 已備)/ 互動手動 | S3-0a-ii |

**純 Fable5**:S3-0a-i、S3-0a-ii、S3-0b、S3-3、S3-4。
**需 Opus 定命門/架構**:S3-1(手水順序)、S3-2(抽籤 draw)、S3-5(奧社試煉引擎)。

**建議起跑順序**:**S3-0a-i(可單測核心,最穩)** → S3-0a-ii(接線)→〔此時可第一次 restart 手動測「走進神社+鞠躬+導覽」〕→ S3-1 手水 → S3-2 參拜 → S3-0b/S3-3/S3-4 設施 → S3-5 奧社。

> ⚠️ **restart 依賴**:S3-0a-ii 起的互動都要 bot restart 才測得到 → 與 S2 部署窗口一起排(清 session + 協調 daily-quest/emoji 別 session)。**S3-0a-i 可完全離線做完做穩,不受 restart 影響 → 最適合現在先開工。**
