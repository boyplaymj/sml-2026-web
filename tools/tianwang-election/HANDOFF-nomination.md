# 天王里選舉 — 提名制改版交接稿（給 Codex）

> 這是**替換流程**，不是疊加。把現行「自薦 + 保證金 + 連署 + 文宣閘門」換成「里民互相提名，達門檻強迫參選」。
> quorum／投票／開票／綁身分組／任期到期 全部沿用原設計不動。
> 涉及檔案：`model/Election.js`、`DAO/ElectionDAO.js`、`discord.js`。**不新增 DDB 表、不燒 LLM → 無額外成本**，免成本控管段。

---

## 一、五項定案（LOCKED）

1. **提名門檻**：固定 `N=5`，後台可調。config 正名為 `nominationQuota`（保留讀舊 `signatureQuota`/`sigQuota` 當 alias 相容）。
2. **不能拒絕**：達門檻即自動成為正式候選人，無婉拒流程。
3. **美化競選（可選、事後補）**：可補口號／政見／照片／文宣；沒補就用 Discord 暱稱＋頭像。**非參選門檻**。
4. **保證金**：整段砍掉（扣款／退還／沒收／退還門檻全移除）。
5. **提名上限**：一人可提名多位；同一對象只算一次（沿用 signature dedup）；**被提名者必須具備里民身分組**（`voterRole`）。

**待你確認的 1 個微決策**：能否提名自己？現行程式擋「不能連署自己」。預設**沿用＝不能自提**，後台不特別開關。若要允許自提請告知。

---

## 二、資料流：提名如何產生候選人（核心結構變更）

現行 `addSignature` 的交易會 `Update` 候選人列且帶 `ConditionExpression: attribute_exists(electionId)`——但新制**提名本身就是候選人的誕生點**，被提名者一開始沒有候選人列。所以：

**提名 target T（提名人 A）時：**
1. `getCandidate(electionId, T)`；若不存在 → `putCandidate` 建最小列（race-safe：`ConditionExpression: attribute_not_exists(electionId)`，撞到 `ConditionalCheckFailed` 就吞掉）：
   ```
   { electionId, userId:T, name/displayName(取自 guild member),
     status:'nominated', official:false, signatureCount:0,
     ballotNo: candidates.length+1, createdAt }
   ```
   （不再有 deposit/depositPaid/photo 相關必填欄位）
2. 呼叫 `addSignature(electionId, T, A, nominationQuota)`（交易 Put 提名列 + ADD signatureCount，pk=`electionId#T`、sort=voterId，dedup 不變）。
3. **升格條件改為純票數**：`signatureCount >= nominationQuota` → `{ official:true, status:'official' }`。
   → **移除 `addSignature` 內與 `maybePromoteOfficial` 內的 `&& c.depositPaid` 判斷。**

`ballotNo` 於建列時指派即可（沿用 `candidates.length+1`）。

---

## 三、discord.js — UserSelectMenu 分派（你點出的缺口）

現行 `discord.js:511`：
```js
if (interaction.isSelectMenu() || interaction.isChannelSelectMenu()) {
```
v14 的 `isSelectMenu()` 只認字串下拉。**加上 `|| interaction.isUserSelectMenu()`**，讓使用者下拉走同一套 `.selects` 派發（`values` 即被選 user id 陣列，與 channelSelect 同機制）。

新的 `elecNominate` 註冊進 `election.selects`（標 `skipBindCheck:true`，與 elecStyle/elecPick 一致，未綁定里民也放行、由 func 內自行驗 voterRole）。

---

## 四、Election.js 具體改動清單

**面板（nomination 期）components 換成：**
- 直接放一個 `UserSelectMenuBuilder`（row）：`customId = elecNominate[electionId]`，placeholder「提名一位里民參選」。（免額外按鈕，符合一指令開場後全互動）
- 保留（可選）「美化文宣」按鈕 → 開 modal（口號／政見／宣言皆非必填）＋武裝照片視窗。
- 保留 elecStyle 文宣風格下拉（可選、非門檻）。
- **移除**：`我要參選`(elecApply)、`繳保證金`(elecDeposit)、逐候選人的「連署 XXX」灰按鈕。

**候選人列文字**：`提名 N/nominationQuota`（原「連署 N/…」），移除保證金欄。
**規則列**：`提名門檻 ${nominationQuota}｜quorum ${quorumPct}%｜任期 ${termDays} 天`（拿掉保證金）。

**移除的方法／路徑**：
- `openApplyModal`、`handleModal` 內 `elecApplyForm` 分支、`payDeposit`。
- `settleDeposits` / `refundDeposit` / `forfeitDeposit` 的呼叫（tally 內移除保證金結算段）。

**新增 `nominate(client, select)`**（elecNominate 的 func）：
1. election.phase 必須是 `nomination`（或你保留的 `signature` 同義），否則 ephemeral 擋。
2. 提名人 `hasRole(member, voterRole)`，否則「限天王里里民提名」。
3. `target = select.values[0]`；fetch target member；`hasRole(target, voterRole)`，否則「只能提名天王里里民」。
4. 自提檢查（預設擋，見一.微決策）。
5. 走「二、資料流」建列＋提名＋升格。
6. ephemeral 回「已提名 <@target>（目前 N/nominationQuota）」；`refreshPanel`。dedup 撞到回「你已提名過這位里民」。

**`startVoting`**：升格條件改 `Number(c.signatureCount||0) >= cfg.nominationQuota && c.status!=='removed'`（去掉 depositPaid）。未達標者投票期自動落選（不 official）。

**`maybePromoteOfficial`**：去 depositPaid，純看 `signatureCount >= nominationQuota`。

**照片（可選補件）**：沿用 `pendingPhotos` + `handleMessage` 影像收件機制，但**改由「美化文宣」按鈕武裝視窗**（原本是報名 modal 武裝）；收件 gate 改為「該 user 是本屆未 removed 候選人」，與 deposit/status 解耦。

**管理指令**：`!選舉候選人 add/remove @user` 保留；`add` 時 deposit 相關欄位填 0/略即可，直接 official。

---

## 五、config（DEFAULTS）調整

- 新增正典 `nominationQuota: 5`；`mergeConfig` 讀 `nominationQuota || signatureQuota || sigQuota`。
- 移除 `deposit`、`refundThreshold` 的使用（欄位可留但不參與流程）。
- `quorumPct` / `seats` / `replaceIncumbent` / `termExpiry` / `termDays` 不動。

---

## 六、⚠️ 需先確認：當選身分組 ID 對不上

- 定案：當選＝里長助理身分組 **`944276962602536960`**。
- 但現行 `model/Election.js:21` `WINNER_ROLE = '877894550570565642'` **仍是舊值**（前一輪「已改」的結果沒落到這支檔）。
- 且 `877894550570565642` 同時被 **`model/tax/TaxBill.js:8` 當作「公職抵稅」身分組**（`PUBLIC_SERVICE_ROLE_IDS`）。
- → 改 `WINNER_ROLE` 前需拍板：報稅的「公職」是否要跟著換成 `944276962602536960`，或維持 `877894550570565642`。**此點等使用者確認再動，Codex 不要自行改。**

`FORMER_ROLE = '1526441135881326614'`（前任徽章）已對，不動。

---

## 七、驗收點

- [ ] 里民 A 對里民 T 提名 → 面板出現 T（提名 1/5），重複提名被擋。
- [ ] 5 位不同里民提名 T → T 自動 official（無保證金、無自薦）。
- [ ] 非里民被提名 → 擋。
- [ ] 投票／開票／當選綁 `944276962602536960`／連任不掛前任徽章／任期到期改前任 徽章 全數照舊通過。
- [ ] 「美化文宣」補口號＋貼照片 → 候選人列與（可選）文宣更新；不補則用暱稱＋頭像。
- [ ] `!選舉候選人 add/remove` 仍可用。
- [ ] `discord.js` UserSelect 能觸發 elecNominate。
