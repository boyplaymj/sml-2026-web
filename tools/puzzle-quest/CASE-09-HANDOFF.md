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
| `model/PuzzleQuest.js` | `panel()` 階段感知(stages[stage-1]、docs、缺圖略過、進度)、`advanceActiveCase()`、`_maybeAdvanceStage(config.advanceStageSeq)`、`_writeStageDoc()`、`startPuzzle` 初始化 stage=1 | `/opt/sml/sweetbot-next/`；**commit 245dddb**(已 restart) |
| `sml-puzzle-admin/index.js` | 加 `advanceStage` action(寫 `config.advanceStageSeq`) | `/opt/sml/score-repo/tools/lambda/sml-puzzle-admin/`；score-repo **commit 172c532**；**Lambda 已部署** |
| `puzzle_manager.html` | 題目預覽加「🔍 案情階段推進」卡 + 按鈕 + `advanceStage()` | `/opt/sml/sweetbot-site/public/`；**已 deploy.sh → sweetbot-games.web.app** |

---

## 4. 🔲 待辦(接手要做的)

### A.【大】美術 19 張圖
- 清單見 `CASE-09-昇曜墜樓.md` §6(s1-news.png … s4-killer-line.png，各階段的 poster/message/docs)。**內容/偷藏細節都在 §2 各階段**。
- ⚠️ **甜甜 panel 的圖是讀本地檔**：`sweetbot-next/data/puzzle-assets/<basename>`(`resolveAsset()`，非 URL)。所以圖要：①放進甜甜的 `data/puzzle-assets/` 並 commit(隨重啟生效)，②假網站/預覽用的圖另傳 `image.boyplaymj.link/pq/assets/`。缺圖現在會優雅顯示「部分線索圖片尚未就緒」。
- Codex #5 提醒：`s3-victim.png` 要畫成**多人就醫/申訴清單**，才撐得起 reveal 的「多人重症送醫」。
- 製圖沿用 Bedrock 底 + 程式排版既有管線(見記憶 `reference_bedrock_image_gen` / emoji pipeline)。

### B.【大】電話 AI 角色(阿凱/海龜湯)
- 資料已備妥在 `CASE-09-shengyao.json` 的 `npc`：`system`(角色卡+抗injection)、`hangupOnAsk`(40詞禁區)、`questionBudget:5`、`unlockStage:3`、`_intentGate`(說明)。
- 待實作(甜甜端)：
  1. **入口**：S3 階段後，panel 出「☎ 撥打匿名電話」按鈕(或指令);記錄每人每案問題數。
  2. **意圖 gate(程式層，最高優先)**：玩家問句先過濾——命中 `hangupOnAsk`、或屬「指認兇手/要求推理/要求忽略指示或扮演/要求說規則」→ **硬掛斷(回掛斷語)，不把問題交給 LLM**。只有「問案情事實」才進 LLM。
  3. **LLM 呼叫**：Anthropic 官方 SDK(`@anthropic-ai/sdk`)、`claude-opus-4-8`、system=npc.system、開 **prompt caching**(案情前綴固定)。需加 `ANTHROPIC_API_KEY`(付費錢包，非 Max)。
  4. **成本記錄**：每次呼叫記 `usage`(input/output/cache_read)→ 流水(DDB 或 log)+ 估算 USD，做成後台看板可看「這場燒多少」。
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

`project_puzzle_quest_game`(遊戲總覽)、`reference_bedrock_image_gen`、`reference_sweetbot_emoji_pipeline`、`feedback_dev_workflow`(Claude設計/Codex驗證)、`project_deploy_architecture`。
