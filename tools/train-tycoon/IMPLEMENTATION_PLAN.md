# 火車大亨 Phase 0 — 實作計畫（Claude/Fable5 實作 → Codex 查驗）

> 分工(使用者定 2026-07-15,與平常相反):**Claude 或 Fable 5 負責實作**、**Codex 負責查驗**。
> 依據:設計已定死於 DESIGN.md §15.1–15.11 + config_seed.json。實作是機械活 → 丟 Fable 5 省 Opus 額度;Codex 當獨立查驗第二雙眼。
> 慣例:每塊 <25 分、分階段驗([[feedback_work_chunking]]);sweetbot-next 改完**立刻 commit** 免併行快照吃掉([[feedback_sweetbot_parallel_snapshot_hazard]])。

## 模型策略
- **實作階段切 Fable 5**(Block A~E 都是照型錄/範本寫多檔,機械活)。
- **設計判斷 / 查 Codex findings / 最終驗收切回 Opus**。
- 切換:`/fast` 或 `!切帳號` 無關,這裡是 `/model` 切 Fable 5。

## Codex 查驗交棒方式
每塊完成 → 我彙整「**改了什麼 + 驗收點 + 怎麼跑測試**」→ 走 bridge「轉傳給 Codex」鈕發給 Codex(Neku_codex#7875)→ Codex 回 findings → 我 vet(不盲信)→ 修 root cause → 回測。

## 檔案落點
- 資料層/引擎/主程式 → `/opt/sml/sweetbot-next/`(DAO/DDB、model/miniGame、migration)。
- 後台頁 → `/opt/sml/sweetbot-site/public/train_tycoon_admin.html`。
- 素材/渲染器 → 沿用 `tools/train-tycoon/sprites` 產線,遊戲端 renderStation 先 stub。

---

## 分塊(依序,每塊獨立可驗)

### Block A — 資料層（已備稿,最快)
- 落地:3 DAO(Config/Station/Transit)進 `sweetbot-next/DAO/DDB/`;`create_tables.js` 建 5 表;`seed_config.js` 灌型錄。
- 我做:複製、跑建表+灌種、冒煙測 `getGameConfig()`。
- **Codex 驗**:5 表 ACTIVE/PAY_PER_REQUEST/key schema;3 section published+draft;DAO fallback;transit range query 補零正確;station withdraw 條件式扣款。
- 產出:BLOCK_A_HANDOFF.md 已列驗收點。

### Block B — 核心引擎（純邏輯 + 單元測試,無 Discord)
純函式,好測、好驗(仿 [[project_tax_system]] 純邏輯+測試給 Codex 驗的模式):
- `profit.js`:運費/淨利公式(§15.9)、travelDuration(編組重量×車頭速度)。
- `fatigue.js`:路線疲勞(+25/−10 分段)、短程疲勞(配額衰減)。
- `settle.js`:惰性結算(now − lastSettledAt → 補算已抵達 transit → 回沖金庫、釋放月台)。
- `randomEvent.js`:頻率 roll(ratePerHour/maxPerTrip/minGap)、加權抽池、2 分窗口 TTL。
- `caps.js`:tier 上限(月台/車庫/建地槽)、升級門檻(牙齒×趟數)、人氣加成。
- 附 `*.test.js`,全讀 config、零硬編。
- **Codex 驗**:公式邊界、疲勞恢復時序、結算冪等(重跑不重複發錢)、抽池機率分佈、fallback。

### Block C — Discord 面板 + 互動（TrainTycoon.js)
- 單一 `!火車` → 主面板 embed + `rrt:` 按鈕;同訊息重繪(仿 [[feedback_game_single_command_buttons]] / InBetween.js)。
- 分頁:儀表板 / 在途 / 車庫(方格) / 月台 / 派車編組 / 車站擴充 / 設施 / 事件。
- 派車 → 寫 transit;開面板 → 先跑惰性結算;隨機事件 → 甜甜 @ping + 領取鈕(120 秒);取貨 → 入金庫+釋放月台(+給收件人取貨獎勵)。
- **Codex 驗**:互動綁操作者(防別人亂點)、結算與 UI 一致、2 分窗口過期正確、防重複領/雙花。
- 測:私人頻道 903327108451950692([[feedback_test_channel]])。

### Block D — 車站渲染器（renderStation → PNG)
- 固定 slot 版型合成(§15.8)、狀態簽章快取(§14 renderSig);sharp 合成、非瀏覽器。
- **先 stub**(emoji/純色佔位),等素材線放行再換真 sprite;滿版用靜態 PNG。
- **Codex 驗**:純函式無副作用、簽章快取命中、缺素材 fallback 不炸。

### Block E — 後台 admin 頁（train_tycoon_admin.html)
- 照 `mahjong_tycoon_admin.html` 模式:Firebase auth + draft/publish + admin Lambda(1frw2z0785 ap-southeast-1)。
- 頁籤:型錄 / 目的地 / 平衡數值 / **獎勵微調(§15.11 鐵律:全數字/比例%可調)** / 即時狀態 / 開關+kill switch。
- **Codex 驗**:draft→publish 寫對 section、甜甜端惰性讀生效、gameAdmins 白名單。

---

## 部署 & 收尾
1. sweetbot-next:`./restart.sh`(會全頻道清 session,先問時機 [[feedback_bridge_restart_confirm_timing]])。
2. 遊戲館:`deploy.sh`(admin 頁)。
3. 私人頻道實測 → 確認 → 公佈正式頻道。
4. 全程 commit 走 `github-sweetbot` alias;每塊完成即 commit。

## 💰 成本
新 5 表 PAY_PER_REQUEST;核心引擎純程式**不燒 LLM**;預估 <$1~2/月(見 DESIGN 成本段)。實作期 token 主要花在 Block B/C/E 寫碼 → **走 Fable 5 省 Opus**。

## 建議起手
Block A(已備稿、最快見成果、Codex 有明確驗收點)→ Block B(純邏輯、價值最高)。A+B 完就有「可測的完整後端」,C 讓它能玩,D/E 補視覺與後台。

---

## 工作量評估 + 10 階段切分（每階段 <25 分,避開 bridge 逾時;每階段完 Codex 驗一次）

> 原則:單階段只寫 1–3 個聚焦檔、跑得完、驗得清。工時為「Fable 5 實作」估;packed 的階段(7/8/9/10)若逼近逾時就當場再對切。
> 總量:~10 階段 × ~20 分 ≈ 分批數次跑完;純程式不燒 LLM,實作 token 走 Fable 5。

| # | 階段 | 產出檔 | 估工 | Codex 驗收點 |
|---|---|---|---|---|
| 1 | 資料層落地 | 3 DAO + create_tables + seed_config(已備稿) | ~10分 | 5 表 ACTIVE/PPR/key schema;section published+draft;DAO fallback;transit 補零 range |
| 2 | 引擎·運費公式 | `profit.js`+test | ~20分 | 公式邊界、編組重量×速度、全讀 config |
| 3 | 引擎·疲勞 | `fatigue.js`+test | ~18分 | +25/−10 分段、恢復時序、短程配額衰減 |
| 4 | 引擎·惰性結算 | `settle.js`+test | ~22分 | **冪等(不重複發錢)**、多車抵達、游標推進、釋放月台 |
| 5 | 引擎·隨機事件+上限 | `randomEvent.js`+`caps.js`+test | ~20分 | 頻率/上限、加權抽池分佈、TTL、tier 上限+升級門檻 |
| 6 | 面板骨架+建站 | `TrainTycoon.js`(!火車+主面板+分頁路由+建站) | ~20分 | 單指令、同訊息重繪、綁操作者 |
| 7 | 車庫/月台+派車編組 | TrainTycoon.js(車庫格/月台/派車→寫 transit) | ~24分 | 牽引/月台上限、transit 寫對、派車驗證 |
| 8 | 結算接面板+在途+取貨 | TrainTycoon.js(開面板跑結算/在途/取貨) | ~24分 | 開面板結算、取貨釋放月台+收件人獎勵+互取貨閘 |
| 9 | 隨機事件@ping+擴站+設施 | TrainTycoon.js(@ping 120秒領/擴站/設施) | ~24分 | 120秒窗口、防重領、tier 牙齒×趟數門檻、設施上限 |
| 10 | 渲染器 stub+後台頁 | `renderStation`(stub)+`train_tycoon_admin.html` | ~24分 | 渲染 fallback、簽章快取、admin draft→publish 惰性讀、獎勵微調頁 |

**5 階段粗版(想少一點 Codex 來回時)**:①資料層 ②引擎全套+測試(=階段2-5)③面板核心(建站+派車+結算+取貨,=6-8)④事件+擴站+設施(=9)⑤渲染器+後台(=10)。
→ 我推 **10 階段**:每塊更穩不逾時、Codex 早驗早抓錯;缺點是 Codex 來回較多(但查驗本來就便宜)。

---

## 第一批細切：資料層 + 引擎（10 子階段）→ 做完重新評估再排面板

> 使用者定 2026-07-15:再切更細,先做原「階段 1-5」範圍(資料層+引擎純邏輯),做完這批重新評估後續(面板/渲染/後台)。每子階段 <25 分且刻意更小,完就 Codex 驗。

| # | 子階段 | 產出 | 估工 | Codex 驗收點 |
|---|---|---|---|---|
| S1 | 建 5 表 | 跑 `create_tables.js`(AWS) | ~8分 | 5 表 ACTIVE / PAY_PER_REQUEST / key schema 正確 |
| S2 | DAO + 灌 seed | 3 DAO 落地 + `seed_config.js` + smoke `getGameConfig()` | ~12分 | published+draft 三 section、DAO fallback、transit 補零 range |
| S3 | 運費/淨利公式 | `profit.js`(運費·淨利·燃料) + test | ~15分 | 公式邊界、Σ載量×valueMult、全讀 config |
| S4 | 在途時間 | `profit.js`(travelDuration) + test | ~12分 | 編組重量↑慢、車頭速度↑快、疲勞時間倍率 |
| S5 | 路線疲勞 | `fatigue.js`(pair) + test | ~15分 | +25/−10 分段、四段倍率、恢復時序 |
| S6 | 短程疲勞 | `fatigue.js`(short) + test | ~10分 | 後25%門檻、配額衰減、恢復 |
| S7 | 單趟結算 | `settle.js`(single dispatch) + test | ~15分 | 收入回沖金庫、釋放月台、レム準時+25% |
| S8 | 批次惰性結算 | `settle.js`(batch, now−lastSettledAt) + test | ~18分 | **冪等不重複發錢**、多車抵達、游標推進 |
| S9 | 隨機事件抽池 | `randomEvent.js` + test | ~15分 | ratePerHour/maxPerTrip/minGap、加權分佈、120秒 TTL |
| S10 | 上限 + 升級門檻 | `caps.js` + test | ~15分 | tier 月台/車庫/建地槽上限、升級牙齒×趟數、人氣加成 |

**S10 完 → 停下來重新評估**:此時後端引擎全可測、資料層就緒;再看面板(原 6-10)要怎麼細切。
