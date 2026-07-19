# Phase 2b-1 · 明硯 `stageGates`（關鍵洞察推進）— Codex 驗收單

**標的**：`tools/puzzle-quest/CASE-13-mingyan.json` 新增的 `stageGates`（S1/S2/S3 三關推進 accept-set）。
**模型**：全服同步、有人答中「當前階的關鍵洞察」→ 全服 stage+1（推進邏輯在 2b-2）。本關只驗**詞表本身**過 §D 鐵律。

## 定義（已寫入 case JSON）
| from | 關鍵洞察（intent） | advanceAny 摘要 |
|---|---|---|
| 1 | 察覺不是單純意外——那份不肯簽的報告、那晚異常有內情 | 不單純/有內情/那份報告/不肯簽/深色/人影/有外人… (19 詞) |
| 2 | 矛頭指向有恨的助理卓文瀚（紅鯡魚①） | 卓文瀚/小卓/署名/被壓/筆記本/盯梢/預謀/卓懷恨… (18 詞) |
| 3 | 卓被洗清(早退/無門禁)→轉向錢與郭崇德＋察覺高董/M-001 反常 | 早退/沒門禁/洗清/郭崇德/高博彥/M-001/反常/不在場… (27 詞) |
（S4＝最終破案，用既有 `solution.core`，不在 stageGates。）

## 我方自審（自動校驗，全過）
- **① 不預告**：三關 advanceAny **無一命中 method/motive core.any**（keystone）→ 零命中 ✅（推進不等於把答案講白）。
- **② 兇手名分野**：culprit 名（高博彥/高董/負責人/董事長/M-001）**只出現在 S3 gate**（§5 允許——那本就是 S3 該逼近的「機會」洞察，且只答兇手名不構成 win）✅。
- **③ 可答性錨點**（每關關鍵詞可從 stage≤N 內容推得）：
  - S1：`那份報告/不肯簽`←t-main「卡著一份報告遲遲不肯簽」；`深色`←t-blackout「側門停了一台深色的車」；`人影/有外人`←t-blackout「有人影在裡面走來走去」。
  - S2：`卓文瀚/署名/被壓/升等`←t-artgossip・d-hr；`筆記本/盯梢/預謀`←img-notebook-a・p-zhuo。
  - S3：`早退/離館`←d-access-log「19:40 卓文瀚 刷卡離館」；`權限不足/進不去`←同表「權限不足，修復室拒絕」；`不在場/簽到/人證`←d-buyer-alibi；`反常/深夜`←p-gao・t-jobrant；`M-001/董事長`←d-access-log。

## Codex 逐條複驗
- [ ] 重跑校驗：`advanceAny` ∩ (method.any ∪ motive.any) = ∅（拿真 case JSON 掃）。
- [ ] 兇手名只在 `from:3`；S1/S2 gate 不含任何 culprit 名。
- [ ] **可答性**：逐詞判斷「玩家讀完 stage≤N 內容後，能否合理講出此詞/此概念」。抽象改述詞（洗清/不在場/人頭/有內情）視為玩家 paraphrase，接受；具體詞要有 stage≤N 頁面錨點（上表）。
- [ ] **紅鯡魚分野**：S2 gate＝「懷疑卓」（＝該階要你採納的紅鯡魚，正確）；S3 gate 不含「卓是兇手」（在 S3 咬定卓應只得 nudge、不推進）。
- [ ] **過寬風險**：S1 gate 詞偏泛（有鬼/不對勁/不單純）——請判斷是否過寬到「隨便講都推進」。設計意圖＝S1 低門檻讓人動起來（全服共享），可接受但請標意見。
- [ ] **搶跑摩擦**：sharp player 在 S2 就直指「高董」→ 因 S2 gate 只認「卓」故不推進、只得 nudge。這是刻意保敘事節奏；請判斷此摩擦可接受否，或建議 S3 gate 提前併入 S2。

## 交給 2b-2（引擎）的前置約束（本關順帶標記，供下關驗）
- **win 仍須鎖終章**：全服 auto-advance 後，早階段就算有人硬猜出 `solution.core` 也不能 win（靠 keystone 只在 S4 ＋ 既有 stage-gate-on-win）。stageGates 只管「中途推進」，不碰 win 判定。
- **冪等**：命中 gate 的推進要 conditional（只有 `stage==from` 才寫 `from+1`），防兩人同時答中跳兩格。
- **推進 UX**：沿用 CASE-11 靜態推進（原地改 embed、不另發、不回看）。

## 重新驗證指令
```bash
cd tools/puzzle-quest
python3 - <<'PY'
import json
c=json.load(open('CASE-13-mingyan.json')); core=c['solution']['core']
mm=set(w for x in core if x['id'] in('method','motive') for w in x['any'])
cul=set(w for x in core if x['id']=='culprit' for w in x['any'])
for g in c['stageGates']:
    print('from',g['from'],'| keystone命中',[w for w in g['advanceAny'] if w in mm] or '無',
          '| 兇手名',[w for w in g['advanceAny'] if w in cul] or '無')
PY
```

---
## round-1 修正（回應 Codex Medium：過寬詞誤推進）
移除 Codex 點名的 6 個泛詞（會被 normalize+includes 誤命中日常語）：
- S2 移 `助理/怨/恨` → 補 `卓懷恨/卓的怨氣/被搶功`（仍留 卓文瀚/署名/被壓/筆記本/盯梢…鑑別詞）
- S3 移 `下班/拒絕/藏家` → 補 `門禁拒絕/郭崇德不在場`（藏家改由 郭崇德 涵蓋）
複驗：keystone 仍零命中、兇手名仍只在 from=3。剩餘 ≤2 字詞（早退/署名/M-001/反常…）為本案專屬概念、非通用聊天詞，未再收窄（避免非連續片語漏判）。請 Codex 再掃一次。

---
## round-2 裁決請求（2026-07-19，兩個 open design 問題請 Codex 拍板）

**授權重掃結果（拿真 CASE-13-mingyan.json）**：`from1=19詞 / from2=18詞 / from3=27詞`；三關 `advanceAny ∩ (method.any∪motive.any)=∅`（keystone 零命中）；兇手名（高博彥/高董/負責人/董事長/M-001）**僅 from3**。硬鐵律（不預告/兇手名分野/單向）全過，**無 blocking**。以下兩題是設計取捨、非驗證錯誤，請 Codex 裁：

### Q1 — S1 過寬（7 個泛詞）是否接受
S1 有 7 個泛詞會「隨便講就推進」：`不單純/有內情/有蹊蹺/有鬼/不對勁/另有隱情/不尋常`（另 12 詞是具體錨定：那份報告/不肯簽/深色/側門的車/人影/有外人…）。
- **我的建議＝保留（accept）**。理由：① S1 的 insight 本就只是「這不是單純意外」＝低資訊量的第一步，泛詞正好對應；② 推進到 S2 只揭露卓文瀚紅鯡魚串，不爆任何 keystone、無爆雷風險；③ 全服同步下，一人先動起來把大家拉到 S2 是設計要的效果。
- **請 Codex 確認的風險點**：substring/normalize 命中會不會被**無關 meta 聊天**誤觸（例：有人打「這遊戲有鬼」）。→ 緩解：2b-2 只在**解謎作答流程 `evaluateAnswer`** 評 stageGates（非一般頻道閒聊），故 meta 聊天不進判定。請 Codex 確認此路徑成立；若成立則泛詞安全、保留。

### Q2 — sharp player 搶跑摩擦是否接受
sharp player 在 S2 直接答「高董」→ S2 gate 只認「卓」→ **不推進、只得 nudge**。
- **我的建議＝保留摩擦（不把 S3 併進 S2）**。理由：紅鯡魚 arc 是本遊戲主體；全服同步下若讓一人跳關會替**全服**塌掉四階結構。
- **但配套（engine/copy，非詞表改動）**：2b-2 對「其實猜對但太早」的答案，nudge 文案要鼓勵向（「方向有了，先把眼前線索挖透再說」）而非平板「不對」，免得搶跑玩家覺得被判錯。請 Codex 判斷此摩擦可接受否，或是否堅持 S3 提前併入 S2。

**若 Q1/Q2 都 accept → 2b-1 詞表定稿、無需再改**；Codex 的裁示（尤其 Q2 的 nudge 文案要求）帶入 2b-2 部署前收尾。
