# 交接：股市 criminal gate + 稅務赦免/假釋 — 已驗證且已上線

> 建立 2026-07-17。此文件是為了把討論從臨時頻道遷回原頻道而寫的狀態快照。
> 相關記憶：[[project_tax_system]]、[[project_tooth_stock_game]]、[[project_sweetbot_jail_system]]。

## 一句話結論
報稅系統 P5 的「逃稅入獄→逐級鎖權」與股市進場動作的 criminal gate，兩批都經 Codex 複驗乾淨收斂、`git status` 乾淨，已於 2026-07-17 走 `./restart.sh` 部署到 **sweetbot-next**（線上生效）。

## 現在跑的是哪個版本
- 真身：`/opt/sml/sweetbot-next`（Node + DynamoDB），重啟＝部署（`./restart.sh`）。
- 上線 HEAD：`5a5de1f`（報稅P5d-3：連年逃稅加重勞役門檻 escalatedParoleNeeded）。
- 部署結果：systemd `active`，主程序 PID `2730508`，頻道 pause→30s 預告→resume 全 OK。

## 已驗證的兩批（Codex 複驗，Findings 皆無）

### A. 股市 criminal gate（stock market，commit 脈絡 `889967b`）
- `mkt_long / mkt_short / mkt_buy / mkt_pick` 四個進場動作都補上 `blockCriminal:true`，逃稅犯先被 `passCriminalGate` 擋。
- 掃全部 `taxBlock:true` 宣告，沒有「taxBlock 但缺 criminal gate metadata」的漏網。
- `mkt_sell` **維持放行**是刻意的政策例外：賣股變現才有錢繳稅／繳保釋金，連賣都鎖會把人卡死在監獄無法翻身。
- 行為 stub：逃稅犯 `mkt_buy` criminal 擋；欠稅戶 `mkt_buy` criminal 放行、tax 擋；`mkt_sell` 放行。
- 驗證：`node --test test/*.test.js` 31/31 pass；`node --check model/StockMarket.js model/CommonUtil.js discord.js` pass；diff-check pass。

### B. 稅務赦免/假釋（model/Tax.js、model/tax/TaxBill.js）
- `pardonTaxpayer`（Tax.js:642）只在 `sentence.crimeId === 5`（逃稅）清 `sentence`，**洗牙罪等其他罪的服刑檔保留**；role 只撤欠稅戶與逃稅犯 → 分罪隔離正確。
- `confirmPayment`（Tax.js:328）只在 `pay.finalStatus === 'paid'` 才呼叫 `pardonTaxpayer`，**partial 不誤赦**（分期/部分繳不解鎖）。
- `escalatedParoleNeeded`（TaxBill.js:187）：base=6、前科每次 +1、封頂 9。
- `runEvaderSweep`（Tax.js:581）判刑前讀 `crimeCounts['5']`，0/2/5 前科對應 paroleNeeded 6/8/9 成立。
- 空跑三情境（無 role／無 viewer／準時繳）不 throw，fail-safe 到位。
- 驗證：`npm test` 32/32 pass；`node --check` + `npx eslint` pass；自訂 stub 三情境 + paid/partial + 0/2/5 前科邊界皆 pass。

## 依賴關係（已對上）
股市 criminal gate 依賴稅務的 `passCriminalGate` / 監獄三態閘門。B 這批已確認底層（閘門／赦免／假釋）在 sweetbot-next 同一份 running code 裡驗過，所以 A 不會叫不到函式。**兩批依賴已補齊，一起上線。**

## 已知限制（v1，非 bug）
- `viewer.sentence` 單槽位會互相覆蓋（多罪同押時）。這是 v1 已知限制；赦免那段已主動避免誤清非逃稅 sentence。
- eslint 在 `model/StockMarket.js`、`discord.js` 仍有既有舊債（各 2 筆），非本次新增，不阻斷。

## 待辦 / 下一步
- [ ] **Discord 實測**：到私頻 `903327108451950692` 或正式股市頻道，用欠稅/逃稅狀態帳號打 `mkt_buy` 確認被擋、`mkt_sell` 確認放行變現。
- [ ] 觀察線上是否有 criminal gate 誤擋正常玩家的回報。
- [ ] eslint 舊債擇日一併清（非急）。

## 部署備忘
- 重啟＝部署，會全域清所有頻道 session 並殺掉 in-flight，非緊急先問時機。
- 工作樹要乾淨才重啟。本次部署前已確認 `git status --short` 空。

---

# ⚠️ 更新 2026-07-17（繳費路徑後續複驗）— 上線版 `5a5de1f` 有斷點，修正未部署

前述「B. 稅務赦免/假釋」的**赦免邏輯本身**（pardon 只清 crimeId=5、partial 不誤赦、前科加重）Codex 確認正確。但**新一輪複驗發現：通往赦免的「繳費路徑」對真正被鎖權者是斷的** → 已部署版 `5a5de1f` 的補繳即赦**實際不可用**。已修，但**尚未 redeploy**。

## 這輪修了什麼（4 commit，皆 Codex 複驗畢無 finding）
- `3b08cc6` — 2 Blocker + follow-up：
  - `claimPaying` 原只收 `assessed/filed/partial`→`paying`，**加 `overdue/evader`**（否則被鎖者按 taxPay 拿到 null，走不到 pardon）。
  - 繳費鈕原只申報期(5月)顯示，但 overdue/evader 是 6/1 後 → `showTaxBill` 在試算模式查未清欠稅、組 `debt` → embed 警示欄 + 「補繳欠稅解鎖」鈕（customId 帶 debt 稅年）。
  - rollback 捕捉 `ensureFiling` 的 `originalStatus`，交易失敗還原原狀態（原 `alreadyPaid>0?partial:assessed` 會把 evader 降級）。
  - `resolvePayment` 加 `currentStatus`：overdue/evader **部分繳不降級**（保留 enforcement 層，繳清才 paid 觸發 pardon）。
- `9cfa14e` — Medium：debt 原只查「當前年-1」，欠稅拖過一年會漏 → `listUnpaidByUser`（Query PK 撈全年份未清）取最舊；`pardonTaxpayer` 加守衛「仍有他年欠稅則不解鎖」（繳一年不整個放出）。
- `8b9a98f` — Blocker：pardon 守衛的 `listUnpaidByUser` 加 `ConsistentRead:true`（剛 paid 後強一致讀）；拿掉 `.catch(()=>[])` 改 **fail-closed**（Query 失敗不誤赦，因 list 在最前面、throw 不會解到一半）。
- 驗證：`node --test test/*.test.js` 53/53、`node --check`+`eslint` pass、離線 stub（可達/多年取最舊/仍欠他年保留鎖/list throw fail-closed）皆 pass。

## 🚦 P5 完整部署清單（redeploy 才會讓補繳即赦真的可用）

**A. Code redeploy（`restart.sh`）**
- 上線版 `5a5de1f` 缺上述 3 commit → 被鎖者無法自救繳稅解鎖，**務必 redeploy**。
- ⚠️ 主 branch HEAD 已被並行 session 推進（P3 扶養 / 每日任務「未接線未重啟」/ 麻將 WIP）。redeploy HEAD 會一併帶上這些 → **需跨 session 協調安全 commit 點**，別單方觸發。
- **好消息**：enforcement 預設全關（見 D），即使 code 上了也不會突然鎖人。

**B. Migrations（restart 不會跑，人工，依序）**
1. `create_tax_filing_table.js`（建 sweetbot-tax-filing + nontax 規則；P2b 可能已跑、idempotent）
2. `patch_tax_class_redenvelope.js`（② 天降紅包→gift 進線上 tax-class）
3. `patch_tax_config_p5.js`（P5 config 欄位 enforcementEnabled/overdueRoleId/evaderSentenceHours/evaderParoleNeeded 進 tax-config，if_not_exists 不覆寫）
4. `backfill_tax_ledger.js --apply`（point-log 灌 tax-ledger，否則核定 0 人）

**C. IAM**（sweetbot 執行角色）
- `sweetbot-tax-filing`：**Query**（新增，`listUnpaidByUser`）+ Scan（scanUnpaid/scanOverdue）+ GetItem/PutItem/UpdateItem/TransactWriteItems。
- `sweetbot-tax-ledger`：Scan + Get/Put/Update；`sweetbot-tax-config`/`sweetbot-tax-class`：Get/Put/Update/Scan。
- **Query on tax-filing 是這輪新依賴，務必確認。**

**D. 開啟 enforcement（預設全關＝安全軟上線）**
- `config.enforcementEnabled=false`（逐級鎖權總開關）、`config.autoAssessEnabled=false`（自動核定）、`config.filingOpen=false`（申報閘）——三者都要後台**手動開**才會真動。
- 關的狀態下只有 criminal-gate/passTaxGate 的 role 層邏輯生效（擋逃稅犯炒股）；5 月申報閘 / 自動核定 / 送審 sweep 要開 flag + 跑 migration 才會動。

**E. 跨頻道待辦**
- **過馬路 CrossingRoad** 的 taxBlock 被 `crossroad-guard` hook 鎖（只頻道 `1521305720648241193` 可改）→ 需到該頻道補標 `過馬路` 進場指令的 `taxBlock:true`（放行 `crBank/crQuit`）。這是 P5c 分級閘門唯一未覆蓋的活躍賺牙遊戲。

**F. 部署後 smoke**（私頻 `903327108451950692`）
- 欠稅/逃稅帳號：`mkt_buy` 擋、`mkt_sell` 放行；`!報稅` 見「補繳欠稅解鎖」鈕 → 繳清 → 解鎖（role 一分鐘內由 checkExpired 摘除）。

## 已接受的 v1 限制
- `viewer.sentence` 單槽位，逃稅 + 他罪同押會互相覆蓋（赦免已避免誤清非逃稅 sentence）。
- FlowerTime（admin 開局 + 訊息猜測，無玩家指令可標）、PkPenalty（純獎勵無入場費）＝可接受的 taxBlock 缺口，非 spam 撈牙 vector。
