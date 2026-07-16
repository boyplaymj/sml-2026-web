# D1 派車分頁 — Fable 5 實作交接（Claude 出規格 → Fable 5 實作 → Codex 驗）

> 目標:把 `dispatch` 分頁的 `🚧 佔位` 換成真的派車流程,接上 P3a `planDispatch` + P3b `commitDispatch`。
> 這是 P3a/P3b 的收成點。**派車不動玩家錢包**(燃料/收益在 settle 才結算)→ 無退款邏輯,只寫 transit + 更新疲勞(=commitDispatch 一筆交易)。
> 慣例一律照 `model/miniGame/TrainTycoon.js` 現有寫法(P1/P2/P2.1 已定型),**零硬編數值**,全讀 config / 復用引擎模組。

## 動到的檔案
- `model/miniGame/TrainTycoon.js`(主要):
  - 頂部 `require` 加 `TrainTycoonTransitDAO`;constructor 加 `this.TransitDAO = new TrainTycoonTransitDAO()`。
  - constructor 加**派車草稿 map**:`this.dispatchDraft = new Map()`(key = 車站擁有者 uid,value = `{ locoId, carId, count, destId }`)。純暫存編組用,重啟遺失可接受(使用者重選即可)。
  - 引擎:`const { planDispatch } = require('./trainTycoon/dispatch.js')`、`const { commitDispatch } = require('./trainTycoon/commitDispatch.js')`。
  - `dispatch` 分頁改由新 `dispatchPayload(...)` 畫(不再走 `stubPayload`);在 `tab()` 路由把 `dispatch` 導到它。
  - `this.selects` 註冊 4 個:`rrt:d.loco` / `rrt:d.car` / `rrt:d.count` / `rrt:d.dest`。
  - `this.buttons` 註冊:`rrt:d.confirm`(確認派車)、`rrt:d.reset`(重選)。
- 測試:`trainTycoon.d1.smoke.js`(照現有 `trainTycoon.p1.smoke.js` / `trainTycoon.p2.smoke.js` 的位置與風格:mock DAO、Node assert、可 `node` 直跑)。
- **不需**改任何 DAO(`commitDispatch` + `TransitDAO.listAll` 都已存在)。

## UI 流程(漸進揭露 select + 確認鈕;Codex 選型)
四個 select menu(車頭 / 車廂 / 節數 / 目的地)始終在面板上,未滿足前置的先 `disabled`;全選齊才算 preview、`確認派車` 才 enable。Discord 上限 5 個 action row → 4 select row + 1 鈕列(確認/重選/返回),此分頁**不放 tabRow**,用「返回儀表板」鈕導航。

1. **進 dispatch 分頁**:先驗擁有 ≥1 貨運車頭 且 ≥1 貨運車廂(用 `buyableItems` 同款過濾 ∩ `fleetMap` 持有量)。缺 → embed 提示「先去車庫買車」+ 車庫/返回鈕,不畫 select。
2. **車頭 select**:選項 = 持有且 `kind∈{freight,both}` 且 `unlockTier≤tier` 的車頭(去重、顯示 牽引/速度)。選後存 draft.locoId,car/count select 解禁。
3. **車廂 select**:選項 = 持有且 `kind==='freight'` 的車廂(顯示容量/貨值)。Phase 0 **單一車種**(planDispatch 支援多車種,但 UI 先做一種簡單好懂)。選後存 draft.carId。
4. **節數 select**:選項 `1..min(loco.traction, 持有該車廂數)`。選後存 draft.count。
5. **目的地 select**:選項 = `unlockTier≤tier` 的 destinations(顯示距離)。選後存 draft.destId。
6. **全選齊 → preview**:embed 顯示 **收益 / 在途時間 / 疲勞倍率 / 事件期望**(見下),`確認派車` enable(除非 planDispatch !ok,如月台滿 → 顯示中文 error、鈕 disabled)。
7. **確認派車**:見「落地」。成功 → 成功 embed(路線/預計抵達時刻)+ 清 draft + 返回儀表板鈕(在途看板是 D2,先不跳)。

每次 select 互動:更新 draft → `defer` → 重繪同一則(`renderInteraction`)。`notOwner` 閘照舊。customId 尾巴一律帶 uid(`ownerId` 讀最後一個 arg)。

## Preview 與 落地 的關鍵差異(必讀,別搞混)
`planDispatch` 內部只有 `rollTripEvents` 吃 rng;其餘(revenue/fuel/net/durationMin/arriveAt/rewardMult/shortMult/lossChance)**與 rng 無關**。

- **Preview(步驟 6)**:`planDispatch(input, cfg, () => 1, now)` → 只用回傳的 `.preview` 欄(rng 無關,穩定)。**不要拿 preview 這次 roll 的 events 顯示**(會與落地時不一致)。「事件期望」= 用 `randomEvent.js` 的頻率參數**算期望值**(`ratePerHour × 時數`,capped `maxPerTrip`);若 randomEvent.js 有可復用的頻率/期望導出就用它,否則讀**同一 config 路徑**計算,勿另立數字。顯示如「途中約 N 起事件」。
- **落地(步驟 7)**:重新 `now = Date.now()`、重查 `platformUsed = (await this.TransitDAO.listAll(uid)).length` → `planDispatch(input, cfg, Math.random, now)` **真 roll 一次** → `if (!plan.ok) 顯示 plan.error 不落地` → `await commitDispatch({ transitDAO: this.TransitDAO, stationDAO: this.StationDAO }, plan, now)`。

## planDispatch 的 input 組法
```js
const station = await this.StationDAO.get(uid);          // 需 active、含 fleet/pairFatigue/shortFatigue
const order = { locoId, cars: [{ carId, count }], destId }; // Phase 0 單車種 → cars 一個元素
const dispatchId = `${uid}-${now.toString(36)}-${Math.random().toString(36).slice(2, 6)}`; // 呼叫端產,唯一
const input = { station, order, dispatchId, platformUsed, stationMods: {} }; // stationMods Phase 0 全預設
```
- `platformUsed`:preview 用當下 `listAll(uid).length`;落地時**重查**(接受狂點短暫超派=既定擱置的 preflight,不在此解)。
- `stationMods` 傳 `{}`(planDispatch 內部預設 popularity/fuelSavePct/depotSpeedPct/hasSignal=0/false)。

## 落地失敗處理
- 派車**不扣錢包** → 無退款。
- `commitDispatch` 丟例外(交易被取消:月台 race / dispatchId 撞 / station 非 active)→ catch,embed 顯示「派車沒成功,再試一次」,**保留 draft** 讓使用者重按。不可 partial(交易保證原子)。
- `plan.ok===false` → 直接顯示 `plan.error`(已是可給玩家看的中文),不呼叫 commitDispatch。

## Codex 驗收點
1. **零硬編**:倍率/門檻/事件率全讀 config;preview 的「事件期望」不是寫死、與 randomEvent.js 同源。
2. **preview 不 roll events**:preview 用 `()=>1` 或忽略 events;落地才 `Math.random` roll。二者 arriveAt/收益一致(rng 無關欄)。
3. **落地=單一 commitDispatch 交易**:transit 寫 1 筆 + 疲勞更新該 dest 一格;不動 treasury/錢包。
4. **platformUsed 落地時重查**;月台滿 → planDispatch !ok → 不落地、鈕 disabled。
5. **綁操作者**:`notOwner` 擋別人點;customId 帶 uid。
6. **前置守衛**:無車頭/車廂 → 提示買車,不讓進 select。
7. **草稿隔離**:draft 以 uid 為 key,成功後清除;不同人不互汙。
8. 回歸:`p1.smoke` 19 / `p2.smoke` 43 / `trainTycoon/*.test.js` 222 不得破。

## 怎麼跑測試
`node trainTycoon.d1.smoke.js`(新);回歸照 Codex 既有三組。
