# YouTube 聊天關鍵字發獎 — 直播後批次結算設計冊 v1

> 設計:Claude（2026-07-14）。對象:Codex 實作/驗證。
> 一句話:直播結束後,把整場 YouTube 聊天室重跑一遍關鍵字比對,對「有綁定的觀眾」統一發牙齒;**不即時、先預覽再確認**。

---

## 0. 為什麼是批次（不是即時）

使用者定案:**發獎不需即時**。批次比即時好做太多,而且資料層早就備好:

- 直播中 `sml-chat-capture` Lambda 已把每則訊息寫進 Firestore `sml_chat_messages`（含 `channelId`/`text`/`ts`/`videoId`）——**現成,不改**。
- 批次拿全場訊息一次算 → 防刷「每人一次」變成單純去重、可**冪等重跑**、可**發放前預覽**、出錯不會直播中誤發。

**身分對應鏈已驗證通（2026-07-14）**,無斷鏈、無補資料的工:
```
sml_chat_messages.channelId  ──authorChannelId-index 反查──▶  sweetbot-viewer.id (discordId)  ──▶  givePoint()
        (YT Channel ID)              ↑ 查不到 = 未綁定 = 略過                                        (自動寫流水帳)
```

---

## 1. 目標 / 非目標

**目標**
- 後台選一場直播（`videoId`）→ 試算「誰該拿多少牙齒」→ 人工確認 → 統一發放並寫流水帳。
- 沿用既有前台規則面板 `yt_keyword_rewards.html`（`sml_config/ytKeywordRewards`）。
- 沿用既有發點函式 `ViewerDetailDAO.givePoint`（原子加點 + 自動流水帳,**不重寫**)。

**非目標**
- 不做即時發放（觀眾打字當下不發）。
- 不做未綁定觀眾的「記帳待領」——**沒綁定就是領不到**（使用者定案,保持單純）。
- 不動三層聊天抓取 / overlay（那套已穩,不碰）。

---

## 2. 放哪跑：**甜甜端（sweetbot-next）執行**

跨資料庫現實:聊天存檔在 **Firestore**、綁定與發牙齒在 **DynamoDB**。結算同時碰兩邊。定案由**甜甜端跑**:

- ✅ 直接重用 `ViewerDetailDAO.givePoint(discordIds[], teeth, 'point', reason)`——原子 ADD + 自動寫 `sweetbot-player-point-log`,一行搞定,**不在 Lambda 複製一份流水帳邏輯埋新雷**（givePoint/流水帳踩過事故）。
- ✅ 綁定反查用現成 `ViewerAuthorChannelIdDAO.selectOne({authorChannelId})`（GSI `authorChannelId-index`,不做全表 scan）。
- ✅ 甜甜本來就會匿名讀 Firestore。
- 代價:動到 sweetbot-next → 需重啟載新碼,**照 puzzle-quest 直接 commit 落 main、別走發布列車**（見 [[project_sweetbot_release_train]]）。

---

## 3. 觸發：後台寫 cmd → 甜甜輪詢（沿用 flowertime_cmd 先例）

保留「滑鼠操作」體驗,不靠打指令。兩段式（先 preview 再 commit）:

**cmd doc** `sml_config/ytKeywordCmd`（後台寫、甜甜讀後清）:
```jsonc
{
  "action": "preview" | "commit",
  "videoId": "abc123",
  "nonce": "uuid",              // 一次操作的識別,防重放
  "startTs": 0,                 // 選填,時間窗過濾(秒);預設整場
  "endTs": 0,                   // 選填
  "requestedBy": "<admin>",
  "requestedAt": 1720000000
}
```

**result doc** `sml_config/ytKeywordResult`（甜甜寫、後台輪詢顯示）:
```jsonc
{
  "nonce": "uuid",
  "videoId": "abc123",
  "status": "preview" | "done" | "error",
  "stats": { "totalMessages": 0, "matchedHits": 0, "recipients": 0, "unboundSkipped": 0, "blacklistedOut": 0, "totalTeeth": 0 },
  "recipients": [
    { "discordId": "…", "displayName": "阿凱", "channelId": "UC…", "total": 30,
      "hits": [ { "keyword": "抽獎", "reward": 10, "ts": 1720000123 } ] }
  ],
  "settledAt": 0,
  "error": ""
}
```

**流程**:後台 `yt_keyword_rewards.html` 新增「📊 直播結算」區 → 填/選 `videoId` → 按「試算」寫 `action:preview` → 輪詢 result 顯示名單與統計 → 人工看過 → 按「確認發放」寫 `action:commit`（同 nonce）→ 甜甜發放並回 `status:done`。

甜甜端輪詢器沿用既有 Firestore 輪詢機制（同 `flowertime_cmd` 那條）。

---

## 4. 結算演算法（甜甜端）

輸入:`videoId`（+選填時間窗）、規則 `ytKeywordRewards`。

1. **讀規則**:`enabled=false` → 直接回錯誤「未啟用」。取 `rules` 中 `enabled!==false` 者。
2. **讀訊息**:Firestore `sml_chat_messages` where `videoId == 本場`(+`ts` 落在時間窗)。逐則有 `channelId`/`text`/`ts`。
3. **比對每則訊息 × 每條規則**:
   - `match:'contains'` → `text` 含 `keyword`;`match:'exact'` → `text.trim() === keyword`。大小寫/全半形正規化(至少 trim + toLowerCase,中文不受影響)。
   - 命中 → 產生一筆 hit `{ channelId, ruleId, keyword, reward, listType, ts }`。
4. **套白/黑名單語意**（見 §7 待確認,暫定）:
   - `listType:'white'` 命中 → 該 channelId **+reward**。
   - `listType:'black'` 命中 → 該 channelId **本場取消發獎資格**（DQ,擋洗頻/工作人員/搗亂;black 規則的 reward 欄忽略）。黑名單優先於白名單。
5. **防刷** `antiSpam`:
   - `'once'`:同 `(channelId, ruleId)` 只計**第一次**命中（其餘丟棄）。
   - `'cooldown'`:同 `(channelId, ruleId)` 兩次命中間隔 `< cooldownSec` 秒者丟棄(按 `ts` 排序後貪婪保留)。
6. **綁定反查**:每個仍有效的 channelId → `ViewerAuthorChannelIdDAO.selectOne({authorChannelId:channelId})`。
   - 查到 → 併入該 `discordId` 的收件人,累加 total。
   - 查不到 → **未綁定,略過**,計入 `unboundSkipped`。
   - （反查建議先把本場 unique channelId 收集起來批次查/快取,避免逐則打 DDB。）
7. **彙總** → recipients 名單（每 discordId 一筆:total + hits 明細）。
8. **preview**:寫 result（`status:preview`）+ 統計,**不發**。
9. **commit**:
   - 先查冪等（§5）→ 已結算過同 videoId 直接擋。
   - 對每個 recipient 呼叫 `givePoint([discordId], total, 'point', reason)`,`reason = 'YT關鍵字獎:'+videoId`(供稽核回溯)。給陣列可一次多人。
   - 寫「已結算」記錄(§5) + result（`status:done`, `settledAt`, `totalTeeth`）。

---

## 5. 冪等 / 防重複發放

**collection** `ytKeywordSettled`,doc id = `videoId`:
```jsonc
{ "settledAt": 1720000000, "nonce": "uuid", "recipientCount": 42, "totalTeeth": 1200 }
```
- `commit` 前先讀:存在 → 拒絕（回 `error:"本場已結算 @<settledAt>"`）。**只有明確帶 `force:true` 才允許補發**（預設關）。
- `preview` 不受限,可重跑。
- 雙保險:givePoint 的流水帳 reason 帶 `videoId`,人工可查有無重複。

---

## 6. 邊界情況

- **一則訊息命中多條規則**:各規則獨立計 hit（受 §4.5 各自 once/cooldown 去重）。同關鍵字重複規則由後台自律。
- **訊息量大**（長直播上千則）:Firestore by `videoId` 需複合索引;一次讀進記憶體排序即可,量級 OK。若超大再分頁。
- **自家/工作人員帳號洗頻**:用 black 規則或(建議 §7)一個 channelId 黑名單擋。
- **reward=0 或空 keyword 規則**:略過。
- **同一觀眾換名**:靠 channelId 對應,不受顯示名稱變動影響(displayName 只做 UI 顯示)。
- **綁定在直播後才綁**:結算當下查不到就是略過,不追溯（符合「沒綁定領不到」）。

---

## 7. 🔴 待你拍板的小決策

1. **黑名單語意**:§4.4 我暫定「black 規則命中 = 該觀眾本場 DQ（擋獎）」。另一種解讀是「black = 這關鍵字純負面、不發也不擋人」。**你要哪種?**（我建議 DQ,才有防洗頻價值）
2. **要不要加「觀眾黑名單」**（直接用 channelId 擋自家/工作人員帳號,和關鍵字規則分開）?小工,但實用。
3. **一則訊息命中多關鍵字**:各自發 vs 每人每則只算一次?（我建議各自發、由 once/cooldown 控上限）
4. **cooldown 範圍**:目前設計是「同人同關鍵字」冷卻。要不要改「同人跨所有關鍵字」共用一個冷卻?（前台文案寫「同人同關鍵字」,我照這個做）

---

## 8. 待改清單

- **前台文案**:`yt_keyword_rewards.html` L35 目前寫「甜甜即時讀取／打字命中自動發」——改成「直播結束後由後台結算統一發放」以免誤解。
- **前台新增**:「📊 直播結算」區（videoId 輸入 + 試算/確認兩鈕 + 名單表 + 統計)。
- **甜甜端新增**:結算模組（讀 Firestore 訊息+規則、比對、去重、反查、發放）+ 接進既有 cmd 輪詢器。
- **Firestore 複合索引**:`sml_chat_messages` by (`videoId`, `ts`)。

---

## 9. ✅ 驗收點（給 Codex）

1. 選 videoId 試算 → 名單、`matchedHits`、`unboundSkipped`、`totalTeeth` 統計正確。
2. `once`:同人同關鍵字洗 10 次只算 1 次。
3. `cooldown`:間隔 < `cooldownSec` 的重複命中被丟。
4. black 規則命中的觀眾**不出現在發放名單**（按 §7.1 定案）。
5. 未綁定 channelId 不發、計入 `unboundSkipped`。
6. commit 後:每 recipient 牙齒正確增加 + `sweetbot-player-point-log` 每人一筆、reason 帶 videoId。
7. 二次 commit 同 videoId 被冪等擋（除非 force）。
8. 綁定反查走 GSI（無全表 scan）；上千則訊息不逾時。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **無額外成本**:無 LLM、無付費 API;規則/cmd/result/settled 皆存 Firestore `sml_config`（既有桶),發放走**既有** DDB 表（`sweetbot-viewer` / `sweetbot-player-point-log`),**不新增 DDB 表、不新增圖床**。
- 結算為**人工觸發、每場一次**的批次讀取（Firestore 讀本場訊息一輪 + 綁定反查批次查),量級極小。
- 屬正典所述「純前端 / 既有表」範疇,故**免「帳本表＋月度封頂」四件套**。若日後改即時常駐輪詢再回本規範評估。
