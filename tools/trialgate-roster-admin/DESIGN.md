# 試煉之門「關卡數據後台」（可線上編輯）— 設計規格 v1（2026-07-14）

Claude 設計，交 Codex 建 + 自驗。目標:後台能清楚檢視並**編輯每關的牌型規則、怪數據、5 句台詞、獎勵**,存檔即改遊戲(經 DDB,不用改程式檔/重啟)。

## 為什麼要搬 DDB
關卡設定現在寫在 `const/trialGateLayers.js`(bot `require()` 的程式檔)。後台 Lambda 碰不到 bot 主機檔案 → 無法線上編輯。解法沿用捍衛路權車款模式:**設定搬 DynamoDB,bot 讀 DDB(fallback JS),後台 Lambda CRUD DDB**。JS 檔保留當 fallback + 種子,不刪。

## 1. DynamoDB 表 `sweetbot-trialgate-layers`
- PK: `layer`(String,"1".."10");另一筆 `__meta__` 存 `maxLayer`。
- 每層 item = 現有 layer 物件原樣:`bosses`(List<Map>)、`award`(Map)。
- boss Map 欄位:`name, hp(N), attack(N), noAttackTime(N), cardType(S: sp|msp|ms), cardLevel([N,N]), sort(BOOL), img(S), appearanceTxt, attackTxt, beAttackedTxt, diedTxt, killPlayerTxt, stageEmoji, increase(L<N>), soulDrain(BOOL,選填)`。
- `award` Map:`teeth(N), experience(N), props(S), propsProbability(N)`。
- billing = PAY_PER_REQUEST(同其他 sweetbot 表)。

## 2. 種子腳本(一次性,冪等)
讀**當前 `const/trialGateLayers.js`**(= b643e6c 鎖定後數值)→ 每層寫一筆 DDB item + `__meta__{maxLayer:10}`。可重跑(PutItem 覆蓋)。放 `tools/trialgate-roster-admin/seed.js`。

## 3. bot 改動 `model/RPG/TrialGate.js`
- 新增載入器:遊戲開局(`createGame`/`initGame`)時把 DDB 全部層讀進 `this.layersCache`;讀不到/錯 → fallback `require('../../const/trialGateLayers.js')`。
- `initBoss(layer)`、`getAward()`、`maxLayer` 改讀 `this.layersCache`(而非直接 require 的常數)。
- **fallback 一定要在**:DDB 掛了遊戲照常用 JS 值跑,不可 crash。
- 快取粒度 = 每場開局載一次(遊戲短、保場內一致、不狂打 DDB)。
- ⚠️ 部署前:此改動 commit 後要 deploy 才生效。**未部署前遊戲讀 JS(值正確)、後台可編輯 DDB 但不生效**——這是預期,別誤判成 bug。

## 4. 後台 Lambda(擴 `sml-laoshiji-admin`,同 Firebase 認證+白名單)
- `GET /trialgate/layers` → scan 表回全部層 + meta。
- `PUT /trialgate/layer/{n}` → **伺服器端驗證**後寫一筆:
  - `n` 為 1..maxLayer 整數;`bosses` 非空陣列;每隻 `hp/attack/noAttackTime` 為 ≥0 數字;`cardType ∈ {sp,msp,ms}`;`cardLevel=[min,max]` 整數且 min≤max;五句台詞為字串;`soulDrain` 為 bool;`increase` 為數字陣列;`award` 欄位型別正確。
  - 驗證失敗回 400,不寫入(避免灌爛遊戲資料)。
- key 一律伺服器組,不收前端原始 key。

## 5. 後台頁(擴我已建的 `sweetbot-site/public/trialgate_admin.html`)
- 改成兩頁籤:**🎨 圖片**(現有上傳功能不動)/ **📊 關卡數據**(新)。
- 關卡數據頁:載 `GET /trialgate/layers`,10 層每層一張卡。多變體層(L4/L7/L8 各 3 隻)要能分別編輯每隻變體。
- 每隻可編:name、hp、attack、cardType(下拉 sp/msp/ms)、cardLevel min/max、5 句台詞(textarea)、soulDrain(勾選)、noAttackTime;每層可編 award(teeth/exp/props/propsProbability)。
- 每層一顆「儲存」→ `PUT /trialgate/layer/N`;成功顯示已存。
- 唯讀檢視需求(「清楚管理每關規則」)由此頁天然滿足;可讓 `trialgate_roster.html` 改導向此頁或保留美術名冊並存。

## 6. 分工 / 時序
- 種子取自 b643e6c 的 JS 值 → 與 16:00 數值上線**無衝突**(JS 值已定案)。
- bot DAO 改動(§3)commit 後可**隨 16:00 或之後的 deploy** 生效;在那之前遊戲照舊讀 JS。
- Codex 建全部(DDB 表+seed+bot DAO+Lambda 路由+前端兩頁籤),自驗(node --check/eslint scoped/DDB 讀寫/驗證分支/fallback 路徑),回 diff + 測試結果。**bot 改動不自行部署**,交使用者。

## 7. 驗收點
- 種子後 DDB 10 層 + meta 齊、值等於現有 JS。
- 後台改某層 attack/台詞 → DDB 該筆更新;bot(部署後)開新局讀到新值;DDB 清空/斷線 → fallback JS 正常開局。
- 驗證分支:非法 cardType/負血/cardLevel min>max 被 400 擋。
- 圖片頁籤原功能不受影響。

## 8. 追加(2026-07-14 使用者確認需求)— 入口 + 一目了然
使用者從 `sweetbot-games.web.app/#trialgate_roster.html` 這個入口進來,要「所有地城資料一目了然 + 可編輯同步」。
- **入口整併**:遊戲館 `index.html` 的「試煉之門」卡目前文案過時(寫「6 層難度重製」)且指向唯讀美術名冊 `trialgate_roster.html`。→ 改成指向本可編輯後台(`trialgate_admin.html`),文案更新為「地城關卡總管:牌型/數據/台詞/分歧/特殊事件,可編輯同步」。舊 `trialgate_roster.html` 美術名冊可留作圖片頁籤內的檢視,或併入。
- **一目了然版面**:關卡數據頁預設一個**總覽表**(10 層 × 關鍵欄:層/怪名/HP/攻擊/牌型/圖/分歧數/特殊事件標記),一眼看完全部;點某層展開才進逐欄編輯。
- **分歧要顯眼**:同層多變體(L4/L7/L8)在總覽標「⑂3」之類標記,展開後每隻變體一張子卡分別編輯(HP/攻擊/台詞可不同,圖共用)。
- **特殊事件要顯眼**:`soulDrain=true` 的層在總覽打「☠ 奪魂」標記;`increase`(指定祝福池)與 `award`(獎勵)在展開區清楚呈現可編。
- (未來)若之後加「層間隨機事件/分歧劇情」,總覽的「特殊事件」欄預留擴充。

## 9. 附魔（女神祝福）後台 — 另冊
「檢視+編輯所有附魔(女神祝福)的圖片與數據」= 另開規格 `DESIGN_blessings.md`(2026-07-14)。同套路搬 DDB(沿用本表 `__blessings__` 一筆 item)、bot 讀 DDB+FALLBACK、Lambda `GET/PUT /trialgate/blessings`、前端附魔管理區,並把各層 `increase` 改成祝福多選(id 為外鍵、雙向完整性驗證)。細節見該冊。

## 10. 內容全後台化（系統圖 + 文字 + 道具）— 另冊
「地城所有 embed 圖/文字/道具都能後台管」= 另開規格 `DESIGN_content.md`(2026-07-14)。A 系統圖 4 張(door1/door2/died/stageClear)固定槽上傳(不動 bot);B 系統文字約 16 條搬 `__texts__` 做可編模板+變數插值;C 道具走 emoji——後台上傳圖(Codex)、Claude 手動做 emoji 進金庫回填、award 道具改下拉。細節見該冊。

相關:`tools/trialgate-rebalance/DESIGN.md`(數值)、`DESIGN_blessings.md`(附魔)、`DESIGN_content.md`(系統圖/文字/道具)、`aws/laoshiji-admin/index.js`(Lambda)、`sweetbot-site/public/trialgate_admin.html`(前端)、`sweetbot-site/public/index.html`(遊戲館入口卡)。

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：新 DDB 表 `sweetbot-trialgate-layers`（§1）＋擴既有 Lambda `sml-laoshiji-admin`（非新開）。量級極小（PAY_PER_REQUEST，關卡設定類讀寫；bot 每場開局載一次、不狂打 DDB，§3）。
- 新表 **PAY_PER_REQUEST**（同其他 sweetbot 表，§1）；附魔圖已在圖床 `image.boyplaymj.link/rpg/`，**不新增圖床成本**。
- **無 LLM／無付費 API**，故免「帳本表＋月度封頂」四件套。
