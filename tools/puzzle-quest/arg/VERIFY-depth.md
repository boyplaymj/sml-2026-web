# Phase B · 埋深／keystone 洩漏稽核 — Codex 驗收單

**標的**：`dist/mingyan/` 全 50 頁源碼 ＋ `mingyan-world.json`。
**為什麼獨立一關**：解謎最容易出包處＝「答案在源碼裡被一步讀光」或「早階段就湊得齊 core」。
本關專查埋深，沿用 `DESIGN_DIRECTION.md §1/§5` 精神，但**因為玩家會用檢視原始檔**，判準比一般更嚴：
**任何 stage<4 頁面的『源碼』grep keystone 都必須零命中**（不是「顯示時看不到」，是「源碼裡根本沒有」）。

## 我方自審結果（audit.py，全通過）
```
B1 stage<4頁(含隱藏頁)源碼grep keystone零命中               ✅  詞表:人為破壞/接地被剪/剪斷接地/外殼帶電/鈦白/贗品/洗錢/滅口/偽作/他殺/動過手腳/接外殼
B2 四還原鏈:刪檔頁註解藏隱藏檔 & 隱藏檔0 href連結           ✅  _ca9558ea/_624caea4/_53796fa6/_dde24f5d
B3 數字遞增鏈:0417不被連結、0418頁有提示                    ✅
B4 公平麵包屑:n-webmaster + n-archive-notice 教學頁存在      ✅
B5 關鍵路徑三core證物齊                                     ✅
```

## Codex 逐條複驗清單

### 1. keystone 洩漏（最重要）
- [ ] 用**真 core.any**（見 `CASE-13-mingyan.json` solution.core 三顆 method/motive 詞表）重跑 grep，掃全部 stage<4 頁源碼 → 應零命中。
- [ ] 特別抽驗四張隱藏頁的**入口（刪檔存根/數字提示頁）**源碼：`del-*` 與 `uploads-0418` 本身是 stage2–4，其源碼**不得**出現手法/動機 keystone（它們只指路）。
- [ ] 主串 `t-main` S4 留言（「看新聞的」「嚇到」）已改為**只指路、不明講**——確認沒有「他殺/洗錢/滅口/動過手腳」等詞回流。

### 2. 早階段湊不齊 core
- [ ] 只用 stage1–3 可達內容（含 S3 還原的 `d-safety-check`、數字頁 `uploads-0417`），能否湊齊三 core？→ **必須不能**（method 完整結論鎖在 `d-electrical`＝S4；motive 鎖在 `d-ledger`/`d-pigment`＝S4）。
- [ ] culprit 名（高博彥/M-001/高董/負責人）允許在 S2–S3 當公平伏筆出現、不構成 win（同 §5 分野）——確認只是「指認需綁 S4 的 `d-access-named`」。

### 3. 四還原鏈 + 數字鏈的「公平性」（不通靈）
- [ ] 每個要玩家「改網址」的關卡，事前都有**站內明示**的機制教學或線索：
  - 檢視原始檔還原：`n-webmaster`（按鈕幹嘛用、備份寫在註解）＋`n-archive-notice`（已刪內容有備份、位置只在該頁註解）＋各 `del-*` 的 `hintText`。
  - 數字遞增：`uploads-0418` 頁面文案＋EXIF 明講「把 0418 改成 0417」＋`n-webmaster` 提「檔名連號、缺一號不代表不存在」。
- [ ] 教學鋪陳順序合理：低風險的教學還原（S2 `del-zhuo-comment`→筆記本紅鯡魚）在前，S4 keystone 還原在後。

### 4. 紅鯡魚公平（事後可被 S4 證物解釋，非純耍人）
- [ ] 助理卓文瀚線（`t-artgossip`/`p-zhuo`/`d-hr`/`_dde24f5d`筆記本）：所有指向他的線索，都能被 `d-access-log`（19:40 早退、無修復室權限）合理洗清。
- [ ] 藏家郭崇德線（`t-collector`/`p-guo`/`d-buyer-alibi`）：能被外地不在場＋`d-ledger`（他是被利用的人頭）洗清。
- [ ] `_dde24f5d`（卓筆記本第二頁）翻案：像預謀跟蹤 → 實為「想當面討署名公道」，公平反轉。

### 5. 時間軸一致
- [ ] 跨頁時間點對得上：8/20 安檢合格 → 9/16 19:40 卓離館 → 20:05 沈進 → 22:51 M-001 進 → 23:20 離。`d-timeline`／`d-access-log`／`uploads-0417`／`d-safety-check`／`d-electrical` 五處無矛盾。

## 若 C 階段（Fable5 加內容）改了世界圖
**B 關必須回歸重跑**：新寫的氛圍/紅鯡魚文字最容易不小心把 keystone 或早洩露的動機講白。C 完成 → 重跑 `audit.py` → 重新交本關。
