# 試煉之門「內容全後台化」— 系統圖 + 文字模板 + 道具(emoji) 設計規格 v1（2026-07-14）

Claude 設計，交 Codex 建 + 自驗。延續 `DESIGN.md` / `DESIGN_blessings.md` 同套路(沿用 DDB 表 `sweetbot-trialgate-layers`、bot 讀 DDB+fallback、擴 Lambda `sml-laoshiji-admin`、擴前端 `trialgate_admin.html`)。本規格補三塊,讓「地城會用到的所有 embed 圖、文字、道具」都能後台管。

⚠️ **一個跨界限制先講**:道具在遊戲裡是 **Discord 自訂 emoji**(`const/emoji.js` 的 `<:name:id>`)。「把上傳的圖做成 emoji 並塞進金庫伺服器」是 Discord 特權操作(需 bot token + guild emoji 額度),**Lambda 做不到、Codex 不做這步**。Codex 只做「上傳圖 + 記錄 + 前端」;**emoji 生成與回填由 Claude 手動接**(見 §C)。

---

## A. 系統 embed 圖(4 張,可上傳替換)
非 BOSS 的框架圖,`TrialGate.js` 寫死引用固定路徑:

| slot | 路徑 | 用途 | 引用行 |
|------|------|------|--------|
| door1 | trialgate/game/door1.png | 進門畫面 | L272 |
| door2 | trialgate/game/door2.png | 進門畫面2 | L275 |
| died | trialgate/game/died.png | 玩家戰敗 | L658 |
| stageClear | trialgate/game/stageClear.png | 單層通關 | L669 |

### 設計:固定槽上傳,**不動 bot、不進 DDB**
路徑寫死在程式,所以「管理」= 上傳覆蓋同名 S3 物件即可(bot 仍引用同路徑,自動吃到新圖)。完全複用現有 `putBossImage` 那套。
- **Lambda 新增** `POST /trialgate/sysimage`:body `{ slot, imageBase64, contentType }`。`slot` 須在白名單 `{door1,door2,died,stageClear}`;只收 png;**key 由伺服器組** `rpg/trialgate/game/<slot>.png`(不收前端 key);`CacheControl: public,max-age=300`;PutObject 後 invalidate CloudFront `E2IJWN6FWT2XYG`(try/catch 兜底,回 `invalidated`)。
- **前端**:「🎨 圖片」頁籤加「系統圖」區,4 槽各一張:現況縮圖 + 上傳鈕(破快取即時預覽),同 BOSS 圖卡樣式。
- bot **零改動**。

---

## B. 系統文字模板(約 16 條,可編輯 + 變數插值)
散在 `TrialGate.js` 的框架訊息(BOSS 的 5 句台詞已在關卡數據可編、不在此列)。搬成**具名模板**,後台改字、bot 用變數渲染。

### B1. 儲存:DDB 表 `sweetbot-trialgate-layers` 一筆 `layer="__texts__"`,屬性 `texts` = Map<key,string>
### B2. bot fallback 常數 `const/trialGateTexts.js`(單一事實來源 + 種子)
### B3. 渲染 helper（bot）
`renderText(key, vars)`:取 `this.layersCache.texts[key]` → 無則 `FALLBACK_TEXTS[key]` → 用 `{name}` 佔位符做字串替換;**未知佔位符原樣保留、缺變數填空字串、絕不 throw**。TrialGate.js 各處寫死字串改呼叫 `renderText('key', {...})`。

### B4. 模板清單(= 種子;`{}` 為變數)
| key | 現行字串(模板化) | 變數 |
|-----|------------------|------|
| award.win | `打敗了強大的 {boss}, 女神給予 {teeth} {teethEmoji} 還有 {exp} {expEmoji} 的獎勵` | boss,teeth,exp,(emoji 由 bot 帶入) |
| layer.title | `試煉之塔 第{layer}層` | layer |
| layer.hpRemain | `{boss} 血量剩餘 {hp}` | boss,hp |
| player.saying | `{playerMention} 說 : {saying}` | playerMention,saying |
| turn.p1 | `輪到 {p1Mention} 對BOSS發起攻擊` | p1Mention |
| turn.p2 | `輪到 {p2Mention} 對BOSS發起攻擊` | p2Mention |
| record.title | `攻擊紀錄` | — |
| record.empty | `無任何翻牌紀錄` | — |
| hint.buy | `{playerMention}用 {pay} 點攻擊力為代價 ~ 獲得了女神的提示! 目前攻擊力為 {attack}` | playerMention,pay,attack |
| answer.correct | `回答正確 {playerMention} 對BOSS造成了 {dmg} 點傷害!` | playerMention,dmg |
| answer.wrong | `回答錯誤 {playerMention} 並沒有對BOSS造成任何傷害!` | playerMention |
| boss.soulDrain | `BOSS對 {targetMention} 發起奪魂攻擊` | targetMention |
| boss.attack | `BOSS對 {targetMention} 發起攻擊, 造成 {dmg} 點傷害` | targetMention,dmg |
| layer.cleared | `第 {layer} 層的BOSS已被您擊敗~` | layer |
| event.bonus | `{p1Mention} {p2Mention} 額外獲得活動特別獎勵 {amount} {hPointEmoji}` | p1Mention,p2Mention,amount |

> ⚠️ **測試作弊碼**(L443)`已獲得創世神的加持，血量上升為9999999...` 疑似 debug 秘技,**不納入可編集合**;請 Codex 在回報時**標出這行的觸發條件**(誰/什麼指令會走到),交使用者決定拔除或保留。先不動它。

### B5. Lambda
- `GET /trialgate/texts` → 回 `{ texts:{...} }`(缺鍵用 fallback 補齊回傳,方便前端顯示完整清單)。
- `PUT /trialgate/texts` → 整包替換,驗證:**key 必須在已知集合內**(白名單,擋任意鍵注入)、value 為字串且長度 ≤ 500、非空。失敗 400。
- 不做佔位符強校驗(允許使用者刪掉某變數);但可**軟提示**(回應帶 warning 列出模板裡少了哪些原有變數)——非阻擋。

### B6. 前端
「📝 文字」新頁籤:每條一個 textarea + 旁邊列「可用變數」小抄(從清單帶)+ 復原成預設鈕;一顆「儲存全部」→ `PUT /trialgate/texts`。

---

## C. 道具(emoji)— 後台上傳圖 → Claude 做 emoji → 綁回;掉落機率已可編
### 現況
- 道具目錄 = **全域** `const/rpgPropsEnum.js`(id/name,跨所有遊戲共用,**不搬**);顯示用 emoji 在 `const/emoji.js`(`<:WATERSUI:...>` 等,部分道具有、部分沒有)。
- 每層掉落 = award `props`(道具 id)+ `propsProbability`(機率),**已在關卡數據頁可編**——但 `props` 目前是**填裸數字**、對不出是哪個道具。

### C1. 儲存:DDB `sweetbot-trialgate-layers` 一筆 `layer="__items__"`,屬性 `items` = Map<idStr, {name, img, emoji, emojiPending}>
- 種子:掃 `rpgPropsEnum` 產生每個 item 的 `{name}`;`emoji` 從 `const/emoji.js` 現有對應帶入(對不到留空);`img` 空;`emojiPending=false`。
- 這是**地城後台的道具視圖層**,不改全域 enum。

### C2. 上傳道具圖(Codex 做)
- **Lambda** `POST /trialgate/props/image`:body `{ id, imageBase64, contentType }`。`id` 須存在於 `__items__`;只收 png;key 伺服器組 `rpg/trialgate/props/<id>.png`;PutObject + CF invalidate;寫回 `__items__[id].img = 'trialgate/props/<id>.png'`、`emojiPending=true`(標記「圖已換、emoji 待重做」)。
- **Lambda** `GET /trialgate/items` → 回 `{ items:{...} }`。
- **Lambda** `PUT /trialgate/item/{id}` → 可編 `name`(供後台顯示);`emoji`/`img` 由系統流程管,不由此改。

### C3. Claude 手動接:圖 → emoji → 回填(**不是 Codex**)
文件化流程(給 Claude 之後照做,Codex 不實作):
1. `GET /trialgate/items` 找出 `emojiPending=true` 的道具,抓其 `img`(S3)。
2. 跑 `tools/emoji/` 產線(`upload.js`)把圖建成金庫 guild 自訂 emoji → 得 `<:name:id>`。注意金庫 stale-hash 雷([[reference_emoji_stale_hash_gotcha]])與動圖管線雷([[reference_animated_gif_pipeline]])。
3. 回填 emoji 字串:寫 `const/emoji.js` 對應 key(**遊戲讀這裡,故要 commit + 部署 bot**)並同步 `__items__[id].emoji`、清 `emojiPending`(給後台顯示)。
- 之所以 emoji 存 `const/emoji.js` 而非只存 DDB:遊戲多處直接 `emoji.XXX` 引用、且 emoji 極少變動,走常數最穩;换 emoji 本來就伴隨我手動出圖+commit,一起部署即可。

### C4. 掉落 UI 升級(Codex 做)
- 關卡數據頁每層 award 的「道具 ID」**裸數字欄改成下拉**:選項來自 `GET /trialgate/items`(顯示 `id · name`,有 emoji 圖者顯示縮圖),存回仍是 id(相容既有 `award.props`)。
- 「道具機率」欄不動(已可編)。旁邊顯示所選道具的名稱+emoji 預覽,一目了然。
- 新增「🎁 道具」頁籤:列全道具(id/name/emoji 預覽/上傳圖鈕/`emojiPending` 待製作標記),供檢視與上傳。
- 外鍵軟驗證:`PUT /trialgate/layer/{n}` 時若 `award.props` 不在 `__items__` → 回**警告**(不阻擋,因 enum 可能有新品項),提示去道具頁補。

### C5. bot 改動(小)
- DAO `loadConfig()` 多回 `items`(抓 `__items__`),`this.layersCache.items` 供後台一致(遊戲實際 emoji 仍走 `const/emoji.js`,故 bot 遊戲邏輯**幾乎不用改**;掉落照舊讀 `award.props/propsProbability`)。
- 若某道具 `const/emoji.js` 無對應 → 顯示退回名稱字串(現行行為),不 crash。

---

## 儲存總表(全在既有表 `sweetbot-trialgate-layers`,不新建表)
| PK | 內容 | 本規格 |
|----|------|--------|
| `"1".."10"` | 每層 bosses+award(含 props/propsProbability) | 既有 |
| `__meta__` | maxLayer | 既有 |
| `__blessings__` | 附魔 | DESIGN_blessings |
| `__texts__` | 系統文字模板 | B ✨ |
| `__items__` | 道具視圖(name/img/emoji/pending) | C ✨ |
| (系統圖) | 直接覆蓋 S3 `game/<slot>.png` | A ✨(無 DDB) |

DAO 既有 `/^\d+$/` 過濾天然忽略所有 `__xxx__`,不衝突。

## 分工 / 時序
- **Codex 建**:Lambda(sysimage / texts GET·PUT / props image / items GET·PUT item + layer.props 軟驗證)、bot(`renderText` helper + 各處字串改呼叫 + `const/trialGateTexts.js` + DAO 多回 texts/items)、種子(`__texts__` 從 FALLBACK_TEXTS、`__items__` 從 rpgPropsEnum+emoji.js)、前端(圖片頁系統圖區、📝文字頁、🎁道具頁、award 道具下拉)。
- **Codex 不做**:emoji 生成/上金庫/回填 `const/emoji.js`(§C3 = Claude 手動)。
- 自驗:`node --check`、scoped eslint、DDB 讀寫、`renderText` 佔位符/缺變數/未知鍵不 crash、Lambda 各驗證分支(白名單 slot/key、非 png、text 白名單鍵+長度、item id 存在)、fallback(texts/items 空→用常數/現行行為)。
- **bot 改動 commit 後不自行部署,交使用者**(未部署前:系統圖換了會即時生效(S3),文字仍用 FALLBACK=現值,道具照舊)。回 diff + 測試結果。

## 驗收點
1. A:後台上傳 door1/died 等 → S3 覆蓋 + CF invalidated;遊戲即時顯示新圖。非 png/未知 slot 被 400。
2. B:後台改 `answer.correct` 文案 → DDB `__texts__` 更新;bot(部署後)答對顯示新文案;變數 `{dmg}` 正確代入;清空某鍵→用 fallback;未知鍵 PUT 被 400。
3. B:作弊碼那行已被 Codex 標出觸發條件、未納入可編集合。
4. C:道具頁上傳某道具圖 → S3 `props/<id>.png` + `emojiPending=true`;GET items 看得到。
5. C:關卡 award「道具 ID」改成下拉、選項帶 name/emoji;存回 id 相容;機率照舊可編。
6. C(Claude 步驟文件化):pending 道具能循 §C3 產 emoji 回填(此步不列入 Codex 驗收,列入 Claude 待辦)。
7. Fallback / 既有(關卡數據、附魔、BOSS 圖、圖片頁)全不受影響。

## 💰 成本控管（遵循 tools/COST_CONTROL.md）
- 沿用既有 DDB 表(加 `__texts__`/`__items__` 兩筆 item,**不新增表**)+ 擴既有 Lambda + 既有 S3 圖床/CloudFront;**無 LLM、無付費 API**。
- 表 PAY_PER_REQUEST;故免「帳本表＋月度封頂」四件套。emoji 產線用既有金庫 guild 額度,無金流。

相關:`DESIGN.md`、`DESIGN_blessings.md`、`model/RPG/TrialGate.js`、`const/{emoji,rpgPropsEnum}.js`、`DAO/DDB/TrialGateLayerDAO.js`、`aws/laoshiji-admin/index.js`、`sweetbot-site/public/trialgate_admin.html`、`tools/emoji/`(金庫產線)。
