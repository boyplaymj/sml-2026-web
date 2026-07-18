# ARG 兔子洞 · Phase 2 設計冊 v2 — 全服同步 · 關鍵洞察推進 · 伺服器端加固

> 使用者拍板模型（取代 v1 的時間閘）：
> 1. **全服同步單一 stage**（現況 `sml_config/puzzle_stage` 不改）——因為有人答出關鍵、大家都看得到他的推理＝共用資訊，所以推進是**全服一起**。
> 2. **推進條件＝有人的回答「達到當前階段的關鍵洞察」**（不是最終答案）→ 全服 stage +1。
> 3. **推進方式＝現有 CASE-11 靜態推進**：原地改 Discord 面板 embed、**不另發通知、不能回看**。
> 4. **判定＝關鍵字 accept-set**（同現有 core/partial 一套、**不燒 LLM、$0**）；LLM 讀自由推理列為日後升級。
> 5. **加固**：stage≥4 的 keystone 內文移到伺服器端閘門（讀同一個全服 stage），view-source 讀不到未解鎖內文。

---

## A. 兩條工作線

### 線 2b（主體）— 甜甜 bot：關鍵洞察自動推進
**現況**：`sweetbot-next/model/PuzzleQuest.js` 的 `evaluateAnswer` 只判「破案(core 全中)/partial(紅鯡魚)/不足」，推進 stage 靠 admin 手動。
**改動**：
1. case JSON 加 `stageGates`（每階「推進關鍵」accept-set，見 §C）。
2. 提交評估流程加一層：**命中『當前階段』的 gate accept-set → 觸發 `advanceStage()`（全服 stage +1）**。
   - 破案（S4 core 全中）仍走既有 win；`stageGates` 只管「中途推進」。
   - 未命中 gate、但命中紅鯡魚 partial → 照舊給 nudge、**不推進**。
3. `advanceStage()`＝寫 `sml_config/puzzle_stage`（+1，clamp≤stageCount）＋走**既有靜態推進**（commit d5e1a10：原地改 embed、不發新訊息、不 @、不能回看）。
4. **冪等/防抖**：同一階段只推進一次；用 `puzzle_stage` 目前值當守門（TransactWrite 或 conditional：只有 `stage==N` 時才寫 `N+1`），避免兩個人同時答中把 stage 跳兩格。
5. 觸發者可得一筆小獎（沿用 stageBonus §8.1），但**不另發通知**（靜默）。

### 線 2a（加固）— 網站：stage≥4 內文伺服器閘門
**現況**：50 頁全靜態；stage≥4 keystone 內文與 `del-*` 還原註解**烘在檔案裡、無論階段都送達**，view-source 可繞。
**改動**：
1. `build.py` 對 **stage≥4 節點＋`del-*` 還原註解**：靜態檔只留「殼」（版面外框＋「🔒 載入中/未解鎖」），機密內文抽到 `secret_bundle.json`。
2. 殼載入時 `GET /arg?case=mingyan&node=<id>` → 閘門 Lambda。
3. 閘門 Lambda `sml-puzzle-arg` + HTTP API：讀**全服 stage**（Firestore `puzzle_stage`，快取 30–60s）→ `node.minStage<=stage && puzzleId 符` 才回內文 HTML，否則 403（不回內文）。
4. CORS 允許 `https://image.boyplaymj.link`。
5. stage1–3 節點**維持純靜態**（本就該讀、已無 keystone）。
6. 全服同步 → 閘門**不需玩家 token**（比 v1 的 per-player 更單純）。

> 兩線同讀一個 `puzzle_stage`：**bot 寫（2b 推進）、網站閘門讀（2a 解鎖）**。單一權威、天然一致。

---

## B. 資料流
```
玩家在 Discord 提交推理
      │
      ▼  甜甜 PuzzleQuest.js.evaluateAnswer
  命中當前階 stageGates?──是──► advanceStage(): 
      │                         conditional 寫 puzzle_stage N→N+1(冪等)
      否                        + 靜態推進(原地改embed,不另發,不回看)
      │                              │
   紅鯡魚partial→nudge               ▼
   core全中→破案win           Firestore sml_config/puzzle_stage (全服權威)
                                     │ 讀
                    ┌────────────────┴───────────────┐
                    ▼                                 ▼
        Discord面板embed(現階段線索)      ARG網站(image.../pq/case13/)
                                          stage1–3: 靜態
                                          stage≥4殼 ─GET /arg?node=─► 閘門Lambda
                                                                      讀stage,夠了才回內文/否則403
```

---

## C. `stageGates` schema ＋ 明硯草案
```jsonc
"stageGates": [
  { "from": 1, "advanceAny": ["卓文瀚","助理","署名","被壓","升等","怨","恨","筆記本","有動機","盯梢","懷疑他"] },
  { "from": 2, "advanceAny": ["早退","沒門禁","進不去","刷不進","洗清","不是卓","轉向","郭崇德","藏家","為了錢","行情"] },
  { "from": 3, "advanceAny": ["高博彥","高董","負責人","董事長","M-001","深夜","反常","不在場","被利用","人頭","那幅畫的錢"] }
]
```
（S4＝最終破案，用既有 `solution.core`，不在 stageGates。）

### 每階「關鍵」的意義（對齊 storyboard，但**綁定 ARG 迷宮各階實際揭露的內容**）
| 推進 | 這一階要答出的關鍵洞察 | 為什麼是「中途洞察、不是答案」 |
|---|---|---|
| S1→S2 | 這不單純，矛頭先指向**有恨的助理卓文瀚** | 只是浮出第一個嫌疑人（紅鯡魚①），還沒手法/動機 |
| S2→S3 | **卓被洗清**（早退/無門禁）→ 轉向**錢/藏家郭崇德** | 推翻紅鯡魚①、轉到紅鯡魚②，仍不知真兇 |
| S3→S4 | 藏家也不在場/被利用 → **館內深夜反常的高董、M-001** | 逼近真兇「機會」，但 method/motive 仍鎖 S4 |

> ⚠️ 草案詞需**再對一次 ARG 迷宮各階實際內容**：某詞若在該階頁面根本還沒出現，玩家答不出來＝不公平；反之若某詞其實是下一階才該懂的，放進來＝提前爆雷。§D 是這關的鐵律。

---

## D. gate accept-set 的埋深/公平鐵律（Codex 專驗）
1. **可答性**：`stageGates[from=N].advanceAny` 的每個詞，都要能從**「stage≤N 已解鎖內容」**推得（玩家手上有料才答得出）。→ 驗法：該詞的概念在 stage≤N 的頁面/線索出現過。
2. **不預告**：`advanceAny` **不得含 method/motive 的 core keystone**（人為破壞/接地/鈦白/贗品/洗錢/滅口…）——否則「推進關鍵」等於把 S4 答案講白。兇手名（高博彥/M-001）依 §5 可在 S3 gate 出現（那本就是 S3 該逼近的「機會」洞察，不構成破案）。
3. **紅鯡魚分野**：某階的 gate ≠ 該階的紅鯡魚「錯答」。例：S2 咬定「卓是兇手」→ 給 nudge、**不推進**；S2 的推進 gate 是「卓被洗清＋轉向錢」。
4. **單向**：gate 只前進、不倒退；已達 stage N 後，答更早階的關鍵不重複推進（冪等）。

---

## E. 子階段（每關交 Codex 驗）
| 關 | 內容 | 交付/驗收 |
|---|---|---|
| **2b-1** | case JSON `stageGates` 明硯定稿（對齊迷宮各階內容、過 §D 鐵律） | `VERIFY-gates.md`：逐詞驗可答性＋不預告＋紅鯡魚分野 |
| **2b-2** | `PuzzleQuest.js` 推進邏輯（命中 gate→冪等 advanceStage→靜態改 embed 不回看）＋單元測試 | Codex 驗：冪等、不重複推進、破案仍走 win、併發不跳兩格 |
| **2a-1** | `build.py` 產「殼＋secret_bundle」；stage1–3 不變 | Codex 驗：view-source stage≥4 殼**無 secret**；bundle 完整 |
| **2a-2** | 閘門 Lambda `sml-puzzle-arg`＋HTTP API＋CORS；讀全服 stage 回內文/403 | `VERIFY-gate.md`：直打 API 帶低 stage→403；到階才回；CORS 對 |
| **2a-3** | 部署（S3 殼＋Lambda）＋接線；E2E 實測 | 需使用者確認上線；Codex 部署前檢查 |

依賴：2b 先（推進是主體、可先在 Discord 端跑通）；2a 緊接（加固）。2b 不阻塞 2a。

---

## F. 相依與回滾
- 2b 只改 `PuzzleQuest.js`＋case JSON，**不動網站**；出事回滾＝admin 手動推進（現況）。
- 2a 只把 stage≥4 節點改殼；出事回滾＝`build.py --legacy-static` 全靜態（保留旗標）。stage1–3 全程不動。
- `puzzle_stage` 仍是唯一權威，既有 `mingyan.html`／面板不受影響。

---

## G. 💰 成本控管（遵循 tools/COST_CONTROL.md）
- **成本來源**：線 2b＝**零額外成本**（改 bot 邏輯＋既有 Firestore 寫，無新表/無 LLM）。線 2a＝Lambda `sml-puzzle-arg`＋HTTP API（讀 stage 回內文），量級極小、**免費額度內、預估 < $1/月**。
- 判定用**關鍵字 accept-set，不燒 LLM**；閘門讀 stage 可快取。故**免帳本／月封頂四件套**。
- 若日後把「gate 判定」升級成 LLM 讀自由推理，**回本規範補齊四件套**（帳本表/月 cap/後台卡/kill switch，走 Bedrock 無 key）。
- 無新 DDB 表（2a 內文 bundle 進 Lambda 部署包；全服 stage 用既有 Firestore）。

---

## H. 待確認 / 待辦
1. §C 明硯 `advanceAny` 詞表——先確認方向，2b-1 會**逐詞對迷宮各階內容**收斂（過 §D）。
2. 判定＝關鍵字先做、LLM 日後——已定。
3. 動工順序：2b-1 → 2b-2（Discord 端跑通）→ 2a-1/2/3（網站加固）→ 部署（確認上線）。
