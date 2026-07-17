---
name: puzzle-case
description: 出一個新的「偽文件解謎」case（甜甜 bot 四階段推理遊戲，仿 Threads solve.quest）。當使用者要「出新解謎題／新 case／新案件／偽文件解謎出題／接著做下一案」時使用。涵蓋選題、參考資料、生圖準則、假網站、洩漏驗收、交 Codex、上線與封存全流程。
---

# 偽文件解謎 出題 skill

甜甜 bot 的四階段推理遊戲：玩家 `!解謎` 讀偽文件（海報／對話截圖／可瀏覽假網站）、買提示、答概念、破案發牙齒；主持人後台手動推進階段；電話 AI 角色當劇情內線索。到 CASE-13 已 13 案。**這支 skill 把每次重做的流程與標準固化，照它走就不會漏步、不會犯洩漏錯。**

工作目錄 `/opt/sml/repo/tools/puzzle-quest/`。實作在 `/opt/sml/sweetbot-next`（`model/PuzzleQuest.js`）。

## 0. 動工前先讀（正典，別憑記憶）

1. `DESIGN_DIRECTION.md` — 出題方向規範 ＋ **§5 驗收 checklist**（自審＋交 Codex 同一張）。
2. `archive/LESSONS.md` — 踩雷帳本。**每次出題前讀、玩完把新雷補回去**。
3. 上一案的 `CASE-NN-*.md`（設計聖經）＋ `CASE-NN-*.json`（引擎資料）當範本。CASE-12/13 是最新最完整的樣板。
4. 記憶 `project_puzzle_quest_game`（跨 session 進度＋踩雷）。

## 1. 選題 ＋ 參考資料準則

- **改編「真實案型＋一個鑑識破口」，不影射真實個案**。流程：挑一種案型（可查真實案件類型/鑑識常識當骨架）→ 抓一個「一句話翻案的鑑識破口」（keystone）→ **整包虛構化進「城中宇宙」**：城中地檢／城中人壽／城中醫院、人名地名全改、`> 全虛構，勿影射任何真實個案／人物／判決` 開頭。
- **破口必須跟前案不同**（刻意不重複）。已用：
  | 案 | 破口 keystone |
  |---|---|
  | 09 昇曜 | 墜樓他殺＋黑心原料（砷超標/工業級冒充食品級） |
  | 10 文山 | 燒炭假象：COHb 僅 18%＋頸部索狀壓痕（生前勒斃） |
  | 11 外環 | 自撞假象：舌骨骨折生前勒斃＋撞擊傷無生活反應（死後才撞） |
  | 12 泓昌 | 投毒：乙二醇＋腎臟草酸鈣結晶（偽裝高血壓猝死） |
  | 13 明硯 | 觸電偽裝工安：電路人為破壞（接地被剪＋外殼帶電）＋贗品鈦白時代錯置＋洗錢 |
  → 下一案挑**沒用過**的破口（例：溺水矽藻/淡水海水、藥物過量、窒息、縱火助燃劑、感電以外工安、假病歷…）。
- **§8.4 雙層真相（進階，CASE-13 起）**：表層嫌犯（紅鯡魚載體，如筆記本）→ 真兇 → 最底層動機（keystone 級，只 S4）。
- **紅鯡魚要公平**：每條指向錯人的線索，事後回看都要能被 S4 證物合理解釋，不能純耍人。

## 2. 資訊配比（埋深，§1＋§4）

- **三 core（method/culprit/motive）皆 S4 才湊齊**。method/motive＝keystone，**只在 S4 文件出現**。
- **兇手名 vs keystone 分野**（重要，見 DESIGN_DIRECTION §5）：要 grep 零命中的是 **method/motive keystone**；**兇手的姓名／稱謂可在早階段當公平伏筆**（他是既有角色、clue/NPC 可提其「反常」），因為 win＝三 core 全中、method+motive 鎖 S4，只答兇手名僅 `corePartial`。`culprit.any` 稱謂是正解必需詞、不可為避早洩而移除。只有「指認＝身分綁手法/動機」（如 M-001＝某人＋機會鎖）鎖 S4。
- 各階段模板：S1 表面故事＋2-3 個「說不上哪裡怪」＋一個可早交的錯方向；S2 衝突內容仍模糊；S3 收斂對象＋電話解鎖＋洗清一條紅鯡魚；S4 物理翻案證物＋keystone。

## 3. 生圖準則（管線沿用，見 CASE-09-HANDOFF §4）

- **檔名** `mN-角色.png`（N＝階段；跨案換字母前綴 s/w/c/p/m…避免撞名）。
- **每階段欄位**：`poster`（主視覺/公告）、`message`（對話截圖，embed 標「對話截圖」）、`docs[]`（其他文件線索）、`audio[]`（語音）。
- **文件/報告/門禁/帳冊/型錄類** → 寫 HTML 版型放 `posters/`，`FONTCONFIG_FILE=~/.fonts/fonts.conf python3 shot.py <in.html> <out.png> .stage`（LINE 對話用 selector `.phone`）。抄現成版型（`m3-access-log.html` 表格、`m2-appraisal-draft.html` 工作單、`m4-ledger.html` 帳、`w4-timeline.html`/`m4-timeline.html` 時序、`s3-lab-report.html`/`m4-electrical.html` 鑑識報告）。
- **照片/現場/採證照** → `python3 bedrock_gen.py "<英文prompt>" <base.png>`（Bedrock SD3.5 us-west-2，無字純材質）→ HTML 疊可讀字/採證標牌 → shot.py。⚠️ emoji 會變豆腐框，一律改文字或 inline SVG。採證照真實性要求高時「**使用者拍真圖＋套採證 UI**」最穩（CASE-11 安全帶）。
- **同一物件跨階段**：生圖模型無法重現同一張畫/物 → 只認一張本尊當共用畫芯（如 `m3-painting.png`），需看清處用它、別處捲收/看不到就不必比對（見 LESSONS 跨階段連續性）。
- **兩處存放**：①遊戲內 panel **讀本地檔** `sweetbot-next/data/puzzle-assets/<裸檔名>`（`resolveAsset`，`fs.existsSync` 即熱、免重啟）→ `cp` 進去＋commit ②假網站/預覽用 → `aws s3 cp posters/x.png s3://boyplaymj-image/pq/assets/x.png --content-type image/png`。
- **JSON 存裸檔名，不存完整 URL**（存 URL 會被後台雙重前綴破圖，CASE-10 雷）。`site` 才存完整 URL。
- 覆蓋同名素材要清 CloudFront（distribution `E2IJWN6FWT2XYG`）＋ Discord 縮圖給新檔名。
- 全繁體、時間軸/星期一致（民國114=西元2025，截圖星期幾自檢）、簡體字自檢。

## 4. 假網站（可瀏覽線索）

- 抄 `mingyan.html`/`hongchang.html`：`城中大小事` 在地討論版（跨案同品牌），`THREAD` 陣列每則含 `appear`（第幾階段出現）／`deleteAt`／`hideAt`（活證物：刪文本身＝線索）。**不顯示階段數**。
- `PUZZLE_ID` 常數＝case id；`?stage=N` 覆寫，否則輪詢 Firestore `sml_config/puzzle_stage`（15s）。
- keystone（他殺/贗品/洗錢…）只准出現在 `appear:4` 留言。
- 上線：`aws s3 cp mingyan.html s3://boyplaymj-image/pq/mingyan.html --content-type "text/html; charset=utf-8"`；`curl -sI` 驗 200。JSON `clues.site`＋每階段 `site` 帶 `?stage=N`。

## 5. 洩漏驗收（**必跑**，這步取代手動 grep）

```
python3 verify_case.py CASE-NN-xxx.json
```
一鍵跑完 §5 機械檢查：JSON schema、**對真 core.any 掃洩漏**（hints/nudge/genericNudge/fallback 任何 core 詞都不准；intro/npc.system 不准 keystone、culprit 允許）、早階段 clue HTML＋假網站 keystone 掃描、素材↔JSON 對映、core.any 短詞警示、win-gate 提示。exit 1＝有阻斷（✗），修掉才可交 Codex。⚠ 項要人工確認（多半是 keystone 需確認只在 S4/appear:4）。

> 為什麼有這支：**別用手寫 banned 詞表自檢**——CASE-13 就這樣漏掉 `電死`（是 `core.method.any` 詞、藏在「電死人」裡），靠 Codex 對真 core.any 掃才抓到。verify_case.py 一律拿該案自己的 core.any 掃。

## 6. 交 Codex 複驗

`verify_case.py` 過後仍交 Codex 做**內容級**複驗（機械掃不出的：時間軸一致、名稱編號對映、紅鯡魚公平、事實鏈、简繁）。交接文請 Codex 逐條對 `DESIGN_DIRECTION §5`＋`archive/LESSONS.md`，回報分「阻斷／建議／已知未完成」。**不盲信 findings，逐條 vet**（見 [[feedback_dev_workflow]]）；有理據的裁決回寫 `_note`＋§5 checklist 免下輪重報。

## 7. 語音 ＋ 手寫筆記本（使用者交付）

- **語音**（每案 ≥3、各角色不同 pitch）：使用者變聲器錄→貼 Discord 訊息連結→我抓附件（bot token `SSM /sml/discord-bot/token`）→ `/opt/sml/repo/tools/bin/ffmpeg` 靜態微調（電話帶通 highpass300/lowpass3200＋信箱嘟聲＋pitch）→ 輸出 `.ogg`(libopus) 對齊 `stages[].audio`→ cp＋上圖床。配方見 [[reference_audio_clue_pipeline]]。台詞寫在 JSON `voiceScripts`（含 who/keep/script/pitch）。
- **手寫筆記本**（如 CASE-13 紅鯡魚載體）：使用者親手寫同本同筆平拍→我套輕度翻拍/採證處理。
- 缺語音/筆記本時 panel 會**優雅略過**，補齊再上。

## 8. 上線 ／ 開案 ／ 封存（DDB `sweetbot-puzzle`，region `ap-southeast-1`）

案件存 DDB，bot 每 ~60s 熱載入免重啟。**⚠️ `activePuzzleId` 空＝隨機池模式，凡有 `solution+clues` 的案都可能被 `pickUnsolvedPuzzle` 隨機抽中——半成品（缺圖/語音）別先 put。**

1. **put**（JSON 已含 `_type:"puzzle"`＋裸檔名，直接 put；加 `attribute_not_exists` 冪等）：
   `aws dynamodb put-item --table-name sweetbot-puzzle --region ap-southeast-1 --item file://<ddb-json>`（native JSON 需 marshal；用 boto3 `TypeSerializer` 或 `--item` DynamoDB JSON）。
2. **開案**：設 `__config__.activePuzzleId=<case id>`（featured；否則隨機）＋updatedAt。
3. **玩完封存**（archive SOP）：清空 `activePuzzleId=''`（恢復隨機）＋DDB/本地 json title 加 `【封存】` 前綴＋`archive/README` 補列＋**把玩後回饋補進 `archive/LESSONS.md`**。

## 9. 成本控管

電話 AI 燒 LLM → 走 `tools/COST_CONTROL.md` 四件套（帳本表 `sweetbot-puzzle-ai-usage`／月封頂／後台卡／kill switch）；新題沿用同表、只換 puzzleId。走 Bedrock 無 key。

## 收尾自檢（一行）

`python3 verify_case.py CASE-NN.json` exit 0 → 交 Codex → 補語音/筆記本 → put→開案。玩完 → 封存＋補 LESSONS。
