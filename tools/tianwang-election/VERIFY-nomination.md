# 天王里選舉・提名制上線前驗證單（給 Codex 執行）

對象：已上線 live 的提名制版本。live main HEAD 應為 `7eeb6c6`（cherry-pick fa2b8df 落 main + `./restart.sh` 已重啟、service active）。
目標：不靠真人 Discord 互動，把「邏輯層 + DDB + config 解析 + 角色綁定路徑」全驗過。全綠 → 使用者正式開選；任一紅 → 回報、先別開，取消重來。

工作目錄：`/opt/sml/sweetbot-next`（跑中的就是這棵樹）。DDB region `ap-southeast-1`。

---

## A. 部署一致性
- [ ] `git -C /opt/sml/sweetbot-next log --oneline -1` = `7eeb6c6`（或更新且仍含該 commit）。
- [ ] `node --check` 過：`discord.js`、`model/Election.js`、`DAO/ElectionDAO.js`。
- [ ] `require('./model/Election.js')`、`require('./DAO/ElectionDAO.js')` 載入無誤。
- [ ] `discord.js` 仍 require＋註冊 `EarthquakeEvent / LiveVote / Tax / MapCode / YtKeywordRewards`（確認 cherry-pick 沒把 main 這些模組洗掉）；dispatch 那行含 `|| interaction.isUserSelectMenu()`。

## B. config 解析（決定 runtime 綁哪個角色 — 最關鍵）
- [ ] 用真實路徑 `new Election().cfg()` 讀線上 DDB，斷言：
  - `winnerRole === '944276962602536960'`（DDB `sweetbot-election-config`.config 的 override 蓋過程式碼 `WINNER_ROLE=877`；**runtime 當選必須綁 944「里長的助理的助理」**）
  - `nominationQuota === 5`（且能讀舊名：把 config 暫塞 `signatureQuota` 驗 alias 後還原）
  - 無任何 deposit 閘門殘留（`cfg` 不因缺 deposit 而擋流程）
- [ ] `formerRole === '1526441135881326614'`（前任徽章，已改名「前任里長的助理的助理」）。

## C. 提名 → 強迫參選（DDB smoke，建/刪 `verifynom_<ts>`，測完清乾淨）
- [ ] **lazy 建列不覆寫**：先 `createCandidateIfAbsent` 建一列（帶 slogan='x'），再對同 key `createCandidateIfAbsent` 一次 → 回傳既有列、`slogan` 仍是 'x'、`signatureCount` 沒被歸零。
- [ ] **重複提名擋**：同一 voter 對同一 target 呼叫兩次 `addSignature` → 第二次丟 `ConditionalCheckFailed`（`nominate` 會轉成「你已提名過這位里民」）。
- [ ] **湊門檻升格（純票數）**：5 位不同 voter 提名同一 target → `signatureCount` 到 5 → 候選人 `official===true`、`status==='official'`，**且過程完全沒有 depositPaid 參與**。
- [ ] **未達門檻不升**：4 票時 `official` 仍為 false。
- [ ] 清理：刪掉 `verifynom_*` 的 candidate/signature 列。

## D. 守門邏輯（`Election.nominate` 前置條件）
以程式碼審 + 可行的話用輕量 stub（mock `select.interaction` / `guild.members.fetch` / `hasRole`）驗，四道閘門都會擋並 return：
- [ ] 非提名期（phase !== 'nomination'）→ 擋。
- [ ] 提名人無里民身分組（voterRole）→ 擋。
- [ ] 提名自己（target === 提名人）→ 擋「不能提名自己」。
- [ ] 被提名者無里民身分組 → 擋「只能提名天王里里民」。
- [ ] 被提名者已 `status==='removed'` → 擋「已被管理者剔除」。

## E. 開票 / 綁角色路徑（程式碼審，實際發角色留真人那步）
- [ ] `tally` 升格條件 = `signatureCount >= nominationQuota`（無 depositPaid）；quorum 未達 → 流選不綁；平手 → 停手不綁。
- [ ] `applyWinnerRoles` 綁的是 `cfg.winnerRole`（= 944）；連任者不卸不掛前任徽章；當選人若原持前任徽章先卸除。
- [ ] `tally` 內**沒有**保證金結算（settleDeposits/refund/forfeit 呼叫已移除）。

## F. 面板 / 美化 / fallback
- [ ] nomination 期面板三 row 型別 = UserSelect(提名) / Button(美化文宣 elecPolish) / StringSelect(文宣風格)；文案含「提名門檻 5」、不含「保證金」。
- [ ] 「美化文宣」對非候選人 → 擋（「被提名後才能美化文宣」）；候選人開啟 → 武裝 `pendingPhotos` 視窗，貼圖經 `handleMessage` 寫入 `photoUrl`。
- [ ] 無 `photoUrl` 時 poster/面板走 `avatarUrl`（提名當下擷取）或預設頭像；`check.js` 零重疊。

---

## G. `!選舉取消` 安全網（已實作，commit `651c0ec`，已 FORCE 重啟上線）
新增 admin 指令 `!選舉取消 <id> [清除|purge]`（`usePermission:99`）。驗：
- [ ] 無旗標：`!選舉取消 <id>` → meta `phase='cancelled'`＋`cancelledAt`/`cancelledBy`；面板重繪成紅色「已取消」、components 清空停用；資料保留（`!選舉稽核` 仍查得到）。
- [ ] 帶 `清除`/`purge`：額外呼叫 `deleteElectionData` 清 candidate/signature/vote 列。
- [ ] 不帶 id：作用在 `getOpenElection()` 那屆（cancelled 不算 open，故取消後再 `!選舉開始` 不會撞屆）。
- [ ] 對已 `closed` 屆取消：會標 cancelled 但 reply 提醒「不會自動卸除已發出的當選身分組」（設計如此，需要時手動處理）。
- [ ] `node --check model/Election.js`、`require` 載入 OK（已確認）。

## H. 回報格式
逐項標 ✅/❌，紅項附最小重現。全綠即回「可正式開選」；有紅項回報後**先不要開**。若要 rollback 整個上線：`git revert 651c0ec 7eeb6c6` + `./restart.sh`（會回到提名制之前的自薦/保證金版）。

> 附註：本次為 FORCE 重啟，工作樹另有 train-tycoon D2 未提交 WIP 已一併上線；與選舉驗證無關，但那個 session 需盡快 commit 以免併行快照把它吃進別的 commit。
