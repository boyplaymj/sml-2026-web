# 交接文件 ｜ 偽文件解謎「四階段推進 + CASE-09」專案

> **給接手的 session：** 這份是整個專案的現況與待辦。先讀本檔，再讀 `CASE-09-昇曜墜樓.md`(設計)與 `CASE-09-shengyao.json`(引擎資料)。全程全虛構、勿影射真實個案。

---

## 0. 一句話總覽

偽文件解謎(PuzzleQuest)的**新方向**：更深、多層線索、**4 階段手動推進**、**電話 AI 角色(海龜湯)**、**活證物(留言隨階段增刪)**。試作案 = **CASE-09 昇曜生技 品保課長墜樓案**。
**「四階段推進」引擎已完成上線；內容經 Codex 三輪複驗可封測。剩「美術 19 張圖」與「電話 AI 角色」兩大塊未做。**

---

## 1. 設計決策(已定案，勿再翻案)

- **全服共用階段**(非個人化)；**主持人手動推進**(後台按鈕，不用 Discord 指令)；主持人是唯一開題者、一定在場。
- **電話 AI 角色 = 劇情內線索**(不是提示)：海龜湯式問答、答案隨玩家問題變化；**問題預算 5 題**、命中禁區/追問兇手就掛斷。提示(hint)維持原本 3 階付費規則、與 AI 分開。
- **B 方案**(LLM 看完整案情)＋ **Opus 4.8**(`claude-opus-4-8`)＋每次呼叫**記 token 成本**。
- **計費**：走**付費 API token**(需 `ANTHROPIC_API_KEY`)，**不是月費 Max 額度**(Max 只給互動式 Claude Code/bridge)。開 prompt caching 後 ~$0.05/場。

---

## 2. 架構：四階段推進的資料流(已上線)

```
甜甜遊戲館後台「偽文件解謎」題目預覽
  └─[按「🔍 推進到下一階段」]→ api('advanceStage')
       └→ Lambda sml-puzzle-admin：寫 DDB sweetbot-puzzle/__config__.advanceStageSeq = 時間戳
            └→ 甜甜 poll(30s) processEndCaseRequests 讀 config → _maybeAdvanceStage 比對 seq(新→執行)
                 └→ advanceActiveCase()：找進行中 round → round.stage+1
                      ├→ 寫 Firestore sml_config/puzzle_stage = {puzzleId, stage}   （給假網站）
                      └→ 在案件頻道重貼「案情有新進展 第N階段」+ 該階段 panel(素材)
                           └→ 假網站 shengyao.html poll(15s) sml_config/puzzle_stage → 渲染對應階段留言(增/刪/隱藏)
```

**與既有 endCase 完全同套**(config seq + priming 防重啟重放)。網站狀態 doc = `sml_config/puzzle_stage`；後台觸發 = `__config__.advanceStageSeq`。

---

## 3. ✅ 已完成(檔案 + commit + 部署)

### 內容(Codex 三輪複驗，判定「可上小規模封測」)
| 檔 | 內容 | 位置/commit |
|---|---|---|
| `CASE-09-昇曜墜樓.md` | 真相聖經、4階段19素材、電話角色卡、§7 鎖定時間軸、§8 留言權威表、§5 引擎相容表 | `/opt/sml/repo/tools/puzzle-quest/`；repo commit **4740ba9** |
| `CASE-09-shengyao.json` | 引擎資料：3-core 詞庫(homicide/motive/object)、partial、hints、reveal、npc(system/hangupOnAsk 40詞/questionBudget/_intentGate)、stages。**已 put 進 DDB `sweetbot-puzzle`**(id=`shengyao-fall-coverup`) | 同上；repo commit 4740ba9 |
| `shengyao.html` | 4 版活證物假討論串頁(留言增刪、純文字無 emoji)。**已上線** | `image.boyplaymj.link/pq/shengyao.html`；repo commit 4740ba9 |

### 引擎(四階段推進，已上線+重啟生效)
| 檔 | 改動 | 位置/commit |
|---|---|---|
| `model/PuzzleQuest.js` | `panel()` 階段感知(stages[stage-1]、docs、缺圖略過、進度)、`advanceActiveCase(preferPuzzleId)`、`_maybeAdvanceStage(config.advanceStageSeq)`、`_writeStageDoc()`、`startPuzzle` 初始化 stage=1 | `/opt/sml/sweetbot-next/`；**commit 245dddb → c2840f3**(已 restart) |

> **✅ E2E 已實測(2026-07-13)**：造進行中 round → 寫 `config.advanceStageSeq` → 甜甜約 30s 內 `round.stage 1→2`、`sml_config/puzzle_stage` doc→2(假網站 ~15s 跟進)。全鏈路通。
>
> **⚠️ 修正 c2840f3**：`advanceActiveCase` 原本盲取 `getActiveByChannel` 的**最舊一筆** round;若封測頻道殘留更早、無階段的舊 round(如 five-star-review-sos),會選中它→`continue`→分階段案件永遠推不動。改為**優先推進 `config.activePuzzleId` 對應的 round**(`channelId#activePuzzleId` 直取),殘留舊 round 不再擋路。`startPuzzle` 開題時會設 activePuzzleId,故正式 `!解謎 <案件>` 開題後推進就會對到本案。
| `sml-puzzle-admin/index.js` | 加 `advanceStage` action(寫 `config.advanceStageSeq`) | `/opt/sml/score-repo/tools/lambda/sml-puzzle-admin/`；score-repo **commit 172c532**；**Lambda 已部署** |
| `puzzle_manager.html` | 題目預覽加「🔍 案情階段推進」卡 + 按鈕 + `advanceStage()` | `/opt/sml/sweetbot-site/public/`；**已 deploy.sh → sweetbot-games.web.app** |

---

## 4. 🔲 待辦(接手要做的)

### A.【大】美術 19 張圖 — ✅ **全數完成(2026-07-13)**
> **18 圖全備 + shengyao.html 假頁(已上線)= 19 樣完成。** commit e382c3f / f6725e5 / 1eba938 / 6996359。都在 `sweetbot-next/data/puzzle-assets/` + 圖床 `image.boyplaymj.link/pq/assets/`。
> S1=`s1-news/s1-coworkers/s1-receipt/s1-notice/s1-photo`；S2=`s2-zhou-line/s2-release-form/s2-personnel/s2-phonelog`；S3=`s3-lab-report/s3-shipping/s3-meeting/s3-victim`；S4=`s4-autopsy/s4-access-log/s4-guardlog/s4-evidence/s4-killer-line`。
> 巧思:放行單偽簽 vs 人事命令陳志偉署名同款藍筆(冒簽線索);阿凱=王凱簽在檢驗報告;S1三種子(照片/發票/公告)在S4收束(採證呼應發票、門禁呼應公告)。
> **要改圖**:改 `tools/puzzle-quest/posters/<name>.html` → `shot.py` 重截 → cp 進 puzzle-assets + 上 S3 + commit。
> **製圖管線(已建,沿用)**：①文件/LINE/報告/紀錄類 → 寫 HTML 版型放 `tools/puzzle-quest/posters/`,`FONTCONFIG_FILE=~/.fonts/fonts.conf python3 tools/puzzle-quest/shot.py <html> <out.png> [selector]`(selector 文件用 `.stage`、LINE 用 `.phone`)。②照片類(如 s1-photo)→ `python3 tools/puzzle-quest/bedrock_gen.py "<英文prompt>" <base.png>` 生無字底圖,再 HTML 疊可讀藏字 → shot.py。③**emoji 會變豆腐框**,一律改用文字或 inline SVG。④產出後 `cp` 進 `sweetbot-next/data/puzzle-assets/` + `aws s3 cp ... s3://boyplaymj-image/pq/assets/ --content-type image/png` + commit。
- 清單見 `CASE-09-昇曜墜樓.md` §6(s1-news.png … s4-killer-line.png，各階段的 poster/message/docs)。**內容/偷藏細節都在 §2 各階段**。
- ⚠️ **甜甜 panel 的圖是讀本地檔**：`sweetbot-next/data/puzzle-assets/<basename>`(`resolveAsset()`，非 URL)。所以圖要：①放進甜甜的 `data/puzzle-assets/` 並 commit(隨重啟生效)，②假網站/預覽用的圖另傳 `image.boyplaymj.link/pq/assets/`。缺圖現在會優雅顯示「部分線索圖片尚未就緒」。
- Codex #5 提醒：`s3-victim.png` 要畫成**多人就醫/申訴清單**，才撐得起 reveal 的「多人重症送醫」。
- 製圖沿用 Bedrock 底 + 程式排版既有管線(見記憶 `reference_bedrock_image_gen` / emoji pipeline)。

### B.【大】電話 AI 角色(阿凱/海龜湯)
> **進度(2026-07-13):核心邏輯骨架完成** ✅ `sweetbot-next/model/PuzzlePhoneNPC.js`(commit d4bd252)。含:意圖 gate(免費/程式層/不送 LLM,擋 hangupOnAsk 40詞+補充樣式,實測精準)、問題預算(每人每案5題,in-memory)、LLM 呼叫(`@anthropic-ai/sdk` 0.111.0 已裝、claude-opus-4-8、prompt caching 角色卡前綴、只灌角色卡不灌真相避洩題)、成本記錄(usage→USD log)。**無 `ANTHROPIC_API_KEY` 時回 stub 不計費**,加 key 即生效。gate/預算/stub 全實測過。
> **①Discord 入口接線 ✅完成**(commit 87c7944):PuzzleQuest `this.phoneNPC`+按鈕`puzzlePhone`;panel() 僅 npc 存在且 stage>=unlockStage 顯示「☎撥打匿名電話」鈕;`openPhoneModal`(檢查+開問句Modal 顯示剩幾次)、`handlePhoneAsk`(gate+預算+LLM→ephemeral回);discord.js Modal 派發已接。實測 panel 按鈕出現邏輯+gate+預算全過。
> **③成本 DDB 帳本 ✅完成**(commit 甜甜端 2c5e642 / Lambda 8a59284):表 `sweetbot-puzzle-ai-usage`(PAY_PER_REQUEST/TTL 90天)已建;`PuzzleAiLedger.js`(明細+rollup#month/#puzzle 原子彙總、costMicros 整數、月度封頂 `PUZZLE_AI_MONTHLY_CAP_USD` 預設15)接進 NPC(呼叫前守門忙線、呼叫後 record);Lambda `aiUsage` action + `puzzle_manager.html`「☎電話AI用量」卡(本月呼叫/成本/距上限/各題)——Lambda+網頁**已部署**;role puzzle-ddb 已加該表讀權。定價用現價 $5/$25(非§8舊稿15/75)。實測全過。
> **金鑰走 SSM ✅接線完成**(commit ac15c6d):`PuzzlePhoneNPC.resolveApiKey()` 優先 env、否則讀 SSM SecureString **`/sweetbot/anthropic-api-key`**(WithDecryption,快取);裝 @aws-sdk/client-ssm;role `sml-claude-ec2` 已授 `ssm:GetParameter /sweetbot/*` + `kms:Decrypt(ViaService ssm)`;實測 env優先/SSM讀取解密/無key→stub 全過。
> **B 只剩兩件(都非程式)**:②把**真 key `put` 進 SSM**:`aws ssm put-parameter --name /sweetbot/anthropic-api-key --type SecureString --value <sk-ant-...> --overwrite`(付費錢包,非 Max)③**重啟甜甜載新碼**(⚠️sweetbot-next 有他人未提交檔 FlowerTime.js/StockMarket.js 擋 restart,需協調;key 換了也要重啟才重讀,resolveApiKey 有快取)。
> **⚠️ 上線需重啟甜甜載新碼**;但目前 sweetbot-next 有他人未提交檔(FlowerTime.js/StockMarket.js)會擋 restart.sh——需該 AI 先 commit 或協調重啟,勿 FORCE 硬上別人 WIP。
- 資料已備妥在 `CASE-09-shengyao.json` 的 `npc`：`system`(角色卡+抗injection)、`hangupOnAsk`(40詞禁區)、`questionBudget:5`、`unlockStage:3`、`_intentGate`(說明)。
- 待實作(甜甜端)：
  1. **入口**：S3 階段後，panel 出「☎ 撥打匿名電話」按鈕(或指令);記錄每人每案問題數。
  2. **意圖 gate(程式層，最高優先)**：玩家問句先過濾——命中 `hangupOnAsk`、或屬「指認兇手/要求推理/要求忽略指示或扮演/要求說規則」→ **硬掛斷(回掛斷語)，不把問題交給 LLM**。只有「問案情事實」才進 LLM。
  3. **LLM 呼叫**：Anthropic 官方 SDK(`@anthropic-ai/sdk`)、`claude-opus-4-8`、system=npc.system、開 **prompt caching**(案情前綴固定)。需加 `ANTHROPIC_API_KEY`(付費錢包，非 Max)。
  4. **成本記錄 + 月度防爆**：每次呼叫記 `usage`→ DDB 流水 + 原子彙總，後台可看「這場/本月燒多少」；呼叫前先查本月累計、超上限就讓電話「忙線」。**完整設計見 §8（照著做即可，勿再自行發明結構）**。
  5. **預算/掛斷**：第 5 題後或觸禁區 → 「…喂?…(電話那頭沒有回應了)」。
- 建 AI 應用請先讀 skill `claude-api`(模型/SDK/caching 都在)。

### C.【小】其他
- **實際串測**：Discord 封測頻道 `903327108451950692` 打 `!解謎 shengyao-fall-coverup` → 後台預覽按推進 → 驗證階段變化(網站+甜甜重貼)。
- 推進延遲：網站 15s、甜甜 poll 30s。嫌慢可縮短 `POLL_INTERVAL_MS` 或給 puzzle_cmd 開獨立快輪詢。
- 難度重製/加更多案件(選作)。

---

## 5. 關鍵端點 / ID / 路徑(接手速查)

| 項目 | 值 |
|---|---|
| 甜甜(遊戲 bot) | `/opt/sml/sweetbot-next`；重啟 `bash restart.sh`(=部署，工作區要乾淨)；引擎在 `model/PuzzleQuest.js` |
| 題庫 DDB | `sweetbot-puzzle`(含題目 items + `__config__`)；region `ap-southeast-1` |
| 觸發欄位(後台→甜甜) | `__config__.advanceStageSeq`(甜甜比對 `advanceStageProcessedSeq`) |
| 狀態 doc(甜甜→網站) | Firestore `sml_config/puzzle_stage = {puzzleId, stage}`；project `sml2026newscore`；FB key `AIzaSyAZaa_yHu7gsRaj71YL8x3REHfL_V5Tq4w` |
| 後台管理頁 | `/opt/sml/sweetbot-site/public/puzzle_manager.html`；`bash /opt/sml/sweetbot-site/deploy.sh` → `sweetbot-games.web.app` |
| 後台 API Lambda | `sml-puzzle-admin`(端點 `vndcoon46m.execute-api.ap-southeast-1.amazonaws.com`)；原始碼 `score-repo/tools/lambda/sml-puzzle-admin/index.js` |
| 圖床 | S3 `boyplaymj-image`、路徑 `pq/`、CloudFront `E2IJWN6FWT2XYG`、`image.boyplaymj.link` |
| 假網站 | `image.boyplaymj.link/pq/shengyao.html`(帶 `?stage=N` 可預覽) |
| 封測頻道 | `903327108451950692`(只此頻道 + admin 可開題) |
| 案件 id | `shengyao-fall-coverup` |

---

## 6. Gotchas(踩過的雷)

- **甜甜 restart = 部署**：有別的 session 未提交 WIP 會被 restart.sh 守衛擋下(要等乾淨或請對方 commit；別 FORCE 硬上別人 WIP)。
- **panel 圖讀本地**：`data/puzzle-assets/basename`，不是 URL。做完圖要放進去 + commit。
- **CASE-09 已在 DDB 題庫**：`!解謎進度` 會列出它；但 `startPuzzle` 是 admin(usePermission 99)、只在封測頻道，玩家不會隨機拿到。
- **推進防重放**：`_maybeAdvanceStage` 首次啟動只 priming、不追溯歷史 seq(與 endCase 同套)。
- **時間軸/一致性已鎖**：見 md §7；改素材要對齊(監視錄影暫停但門禁刷卡仍記錄；重擊致死非擊昏；多人重症非人命)。
- **全虛構**：勿影射真實個案/公司/人物/判決。

---

## 7. 相關記憶(sml-brain)

`project_puzzle_quest_game`(遊戲總覽)、`reference_bedrock_image_gen`、`reference_sweetbot_emoji_pipeline`、`feedback_dev_workflow`(Claude設計/Codex驗證)、`project_deploy_architecture`、`reference_token_usage_report`(現有用量工具，**涵蓋不到本功能**，見下)。

---

## 8. 電話 AI Token 記帳層設計（實作規格）

> **為什麼要自己記帳**：電話 AI 走**直接付費 Anthropic API**（`ANTHROPIC_API_KEY`），不是甜甜平常的 Claude Code / bridge。
> - 現有 `tools/token-usage/report.py` 只讀 `~/.claude/**/*.jsonl`（bridge transcript）→ **抓不到**這種直接 SDK 呼叫。
> - `cost_tracker.html`（`billing_sync.py` 走 Anthropic **Admin Cost API**）**抓得到，但只到整個 API key 帳戶總額**，拆不出「解謎/哪一場/哪個玩家」。
> - 所以在 SDK 呼叫點**自己記一筆**，才能做到 per-場/per-題/per-玩家 的歸屬 + 月度封頂。帳戶總額（cost_tracker）當交叉對帳的上界即可。
> 思路借自 `/opt/sml/stock-intel/budget.py`（定價表 + 防爆），但那是 Python 本地 jsonl；本功能在 **sweetbot-next（Node）**，改落 **DDB** 讓後台直接讀。

### 8.1 儲存：新 DDB 表 `sweetbot-puzzle-ai-usage`
- `PAY_PER_REQUEST`、region `ap-southeast-1`、keys：`pk`(S) + `sk`(S)。
- **明細列（每次呼叫一筆，可回溯精算）**：
  - `pk = call#<yyyy-mm-dd>`（台灣時區 TPE 日期，方便按日 Query）
  - `sk = <isoTs>#<userId>`
  - 屬性：`puzzleId, channelId, roundId, stage, model, tin(input_tokens), tout(output_tokens), tcw(cache_creation), tcr(cache_read), costMicros(int), ttl`
  - `ttl` = 現在 +90 天 epoch 秒（明細自動過期、表不長胖；彙總永久保留）。
- **彙總列（原子 `ADD`，dashboard 只讀這幾筆，免 scan 明細）**：
  - `pk = rollup#month, sk = <yyyy-mm>`：`ADD calls :1, tin, tout, tcr, costMicros`
  - `pk = rollup#puzzle, sk = <puzzleId>`：同上（單題累計終身）
  - （選）`pk = rollup#total, sk = ALL`

### 8.2 定價與成本（整數 micro-USD，避浮點漂移）
Opus 4.8 牌價（USD / Mtok）：`in 15 / out 75 / cacheWrite 18.75 / cacheRead 1.5`。
```
costMicros = Math.round(tin*15 + tout*75 + tcw*18.75 + tcr*1.5)   // = USD * 1e6
```
> 註：`cache_read` 佔比常最大但單價僅 1/10 input、1/50 output——**看成本一定用加權後的 costMicros，別用 token 原始加總**（同 `reference_token_usage_report` 的坑）。開 prompt caching 後單場估 ~$0.05。

### 8.3 新模組 `sweetbot-next/model/PuzzleAiLedger.js`
```
const AWS = require('aws-sdk');                 // 沿用專案既有 SDK 版本/寫法
const ddb = new AWS.DynamoDB.DocumentClient({ region: 'ap-southeast-1' });
const TABLE = 'sweetbot-puzzle-ai-usage';
const PRICE = { in:15, out:75, cw:18.75, cr:1.5 };   // USD / Mtok（Opus 4.8）

function costMicros(u){
  return Math.round((u.input_tokens||0)*PRICE.in + (u.output_tokens||0)*PRICE.out
    + (u.cache_creation_input_tokens||0)*PRICE.cw + (u.cache_read_input_tokens||0)*PRICE.cr);
}

// 呼叫前守門：回本月累計 micro-USD。超上限 → 呼叫端讓電話忙線、不打 LLM。
async function monthCostMicros(month /* 'yyyy-mm' TPE */){
  const r = await ddb.get({ TableName: TABLE, Key:{ pk:'rollup#month', sk:month } }).promise();
  return (r.Item && r.Item.costMicros) || 0;
}

// 呼叫後記帳：fire-and-forget，務必 try/catch，記帳失敗絕不擋玩家對話。
async function record({ usage, puzzleId, userId, channelId, roundId, stage, model, tsIso, dateTpe, month }){
  const c = costMicros(usage);
  const detail = ddb.put({ TableName: TABLE, Item:{
    pk:`call#${dateTpe}`, sk:`${tsIso}#${userId}`,
    puzzleId, channelId, roundId, stage, model,
    tin:usage.input_tokens||0, tout:usage.output_tokens||0,
    tcw:usage.cache_creation_input_tokens||0, tcr:usage.cache_read_input_tokens||0,
    costMicros:c, ttl: Math.floor(Date.now()/1000)+90*86400,
  }}).promise();
  const add = (pk, sk) => ddb.update({ TableName: TABLE, Key:{pk,sk},
    UpdateExpression:'ADD calls :one, tin :i, tout :o, tcr :r, costMicros :c',
    ExpressionAttributeValues:{ ':one':1, ':i':usage.input_tokens||0, ':o':usage.output_tokens||0,
      ':r':usage.cache_read_input_tokens||0, ':c':c } }).promise();
  await Promise.allSettled([ detail, add('rollup#month',month), add('rollup#puzzle',puzzleId) ]);
  return c;
}
module.exports = { costMicros, monthCostMicros, record };
```
（TPE 日期/月份請用專案既有的時區工具算，別用 UTC 直取。）

### 8.4 接呼叫點（電話 AI handler，§4.B.3）
```
// 1) 防爆：本月超上限就忙線
const CAP_USD = parseFloat(process.env.PUZZLE_AI_MONTHLY_CAP_USD || '15');
if (await Ledger.monthCostMicros(month) >= CAP_USD*1e6){
  return '「嘟——嘟——」電話那頭一直忙線中…（本月匿名專線已達額度，改天再撥）';
}
// 2) 意圖 gate（§4.B.2，命中禁區/追兇 → 硬掛斷，不進 LLM）
// 3) 呼叫
const resp = await anthropic.messages.create({ model:'claude-opus-4-8', system: npc.system, /* +caching */ messages });
// 4) 記帳（fire-and-forget、不 await 阻塞回覆）
Ledger.record({ usage:resp.usage, puzzleId, userId, channelId, roundId, stage,
  model:'claude-opus-4-8', tsIso, dateTpe, month }).catch(e=>console.error('[puzzle-ai ledger]', e));
```
- 意圖 gate 硬掛斷的**不算 token**（根本沒打 LLM）→ 天然省錢，符合設計。
- 環境變數：`ANTHROPIC_API_KEY`（付費錢包）、`PUZZLE_AI_MONTHLY_CAP_USD`（預設 15）。

### 8.5 後台看板（讓「這個後台」看得到）
主管理面在 `puzzle_manager.html`（主持人本來就在用）——**在那裡加一張「☎ 電話 AI 用量」卡**最省事：
- Lambda `sml-puzzle-admin` 加 action `aiUsage`：`get rollup#month/<yyyy-mm>` +（選）`query pk=rollup#puzzle` → 回 `{month, calls, costUsd, byPuzzle[]}`。
- 頁面顯示：本月呼叫數 / 本月成本 USD（`costMicros/1e6`）/ 距上限 `PUZZLE_AI_MONTHLY_CAP_USD` 還剩多少 / 各題累計。
- **交叉對帳**：`cost_tracker.html` 的 Anthropic Admin Cost API 是帳戶總額（上界），本表是解謎歸屬（明細），兩者該相符（本表 ≤ 帳戶）。
- （選）若要進 `economy.html/cost_tracker.html`，比照 `tools/ddb-usage/gen_usage.py` 產一份 json 給前端；但既然主持人只在 puzzle_manager 操作，先做那張卡即可。

### 8.6 驗收點
1. 打一通測試電話 → `sweetbot-puzzle-ai-usage` 出現 1 筆 `call#<date>` 明細 + `rollup#month`/`rollup#puzzle` 的 `calls/costMicros` 遞增。
2. `costMicros` 與手算 `tin*15+tout*75+tcw*18.75+tcr*1.5` 一致。
3. 把 `PUZZLE_AI_MONTHLY_CAP_USD` 設超小 → 下一通電話回「忙線」、**不產生新 usage 明細**（確認沒打 LLM）。
4. 意圖 gate 命中（問兇手）→ 掛斷、**不新增 usage 明細**。
5. 記帳故意丟錯（改壞表名）→ 玩家對話照常、只 console 報錯（記帳絕不擋遊戲）。
6. `puzzle_manager.html` 卡片數字 = DDB rollup 值。
