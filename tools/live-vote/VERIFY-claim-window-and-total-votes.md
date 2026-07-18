# 直播應援投票 — 修正驗收單（交 Codex）

> 對象：Codex ／ 目的：獨立複驗本次「領獎視窗放寬 + 顯示總票數」兩處改動。
> 背景：使用者實測「60 秒內按領獎卻顯示已蒸發」。已排除單位錯與時鐘偏移，
> 根因＝60s 視窗從「後台按開獎那刻」起算，但 bot 每 5 秒才輪詢刷出領獎鈕、
> 玩家還要切回 App，實際只剩 40 幾秒 → 幾乎不可能領到。

---

## 一、改了什麼（2 檔 2 commit，均已 commit + 已部署）

### A. Bot — `/opt/sml/sweetbot-next/model/LiveVote.js`（commit `cd1260e`）

**A1. 領獎視窗常數改為可 env 覆寫（預設 60s → 180s）**
```diff
- const CLAIM_WINDOW_MS = 60000;
+ const CLAIM_WINDOW_MS = Number(process.env.LIVEVOTE_CLAIM_WINDOW_MS) || 180000;
```
- 位置：`model/LiveVote.js:11`

**A2. `poolLine()` 加「總票數」行**
```diff
- return lines.join('\n') || '—';
+ const body = lines.join('\n') || '—';
+ return total > 0 ? `${body}\n總票數：${total} 票` : body;
```
- 位置：`model/LiveVote.js:129-139`（`total = Number(pool.total) || 0`，第 131 行既有）

### B. 後台 — `/opt/sml/sweetbot-site/public/livevote_admin.html`（deploy snapshot `2eff931`）

`openDetail()` 明細改版：
```diff
- <div>票數：${opts.map(o=>`${esc(o.label)} ${Number(pool[o.key])||0}`).join(' / ')||'—'}</div>
- <div>下注人數：${r.summary.totalBets}・已扣 ${...}🦷・開獎可領 ${...}🦷</div>
+ <div>各選項票數：${opts.map(o=>`${esc(o.label)}：${Number(pool[o.key])||0}票`).join('・')||'—'}</div>
+ <div>總票數：${Number(pool.total)||0} 票・下注人數：${r.summary.totalBets} 人</div>
+ <div>已扣 ${...}🦷・開獎可領 ${...}🦷</div>
```
- 原格式「1 1 / 22 4」數字選項標籤與票數併排難讀 → 改「1：1票・22：4票」。

**未動 Lambda**（總票數用題目記錄現成的 `pool.total`，少一個部署面）。

---

## 二、要 Codex 複驗的點（逐項打勾）

### V1. 視窗常數的所有引用點都跟著變（最重要）
- [ ] `CLAIM_WINDOW_MS` 只有這一個定義處，改後**倒數顯示**與**領獎判斷**是否共用同一常數？
  - 倒數顯示：`model/LiveVote.js:172` — `<t:${Math.floor((Number(question.revealAt) + CLAIM_WINDOW_MS)/1000)}:R>`
  - 領獎判斷：`model/LiveVote.js:361` — `if (Date.now() - Number(question.revealAt||0) > CLAIM_WINDOW_MS) return reply('已蒸發…')`
  - **驗收點**：兩處都吃同一 const，故「畫面倒數」與「實際可領時間」一致、不會出現「倒數還有時間但按了說蒸發」。請確認沒有其他地方寫死 60000/60。

### V2. env 覆寫的型別安全
- [ ] `Number(process.env.LIVEVOTE_CLAIM_WINDOW_MS) || 180000`：
  - env 未設 → `Number(undefined)=NaN` → `|| 180000` 生效 ✅
  - env 設非數字（如 `"abc"`）→ `NaN` → fallback 180000 ✅
  - env 設 `"0"` → `Number("0")=0` → `|| 180000` 會被當 falsy 覆蓋回 180000（即無法設 0，符合預期，不可能有 0 秒視窗）。請確認這是可接受行為。

### V3. `pool.total` 是否為真實累計、與各選項加總一致
- [ ] Bot 面板總票數（`poolLine` 用 `pool.total`）與後台明細總票數（`pool.total`）同源。
- [ ] `pool.total` 是否等於各選項票數（`pool[optKey]`）之和？請對 DAO 押票路徑複核：每次押票 `pool.total` 與 `pool[key]` 是否在**同一次原子寫入**（TransactWrite）內同步 +1，避免兩者飄移。
  - 相關：`DAO/LiveVoteBetDAO.js`、`DAO/LiveVoteQuestionDAO.js`。
- [ ] `total > 0` 才顯示總票數行（0 票不顯示），符合預期。

### V4. 顯示不破版
- [ ] `poolLine` 多一行不會超過 Discord embed field value 上限。
- [ ] 後台 `openDetail`：選項標籤走 `esc()` 轉義（XSS）；`Number(pool[o.key])||0` 對缺鍵 / 非數字安全。

### V5. 不回歸
- [ ] 開獎/領獎/作廢全退流程未受影響（本次只動顯示字串 + 一個常數，不碰結算 TransactWrite）。
- [ ] `git diff` 確認改動範圍就是上面 2 檔、無夾帶其他 WIP。

---

## 三、E2E 手動測試腳本（使用者側）

> 舊那題的 400🦷 已蒸發沉金庫救不回，開**新題**乾淨測。

1. 後台開新題 → Discord 押幾票 → 面板應顯示「總票數：N 票」，後台明細顯示「各選項票數：… ・總票數：N 票・下注人數：N 人」。
2. 後台 **截止** → **開獎** 選正解。
3. 回 Discord，**3 分鐘內**按「領獎」→ 應看到「領獎成功，獲得 X🦷」；倒數 `:R` 顯示應為約 3 分鐘。
4. DDB 坐實：`claimed=true` + 餘額增加 + 流水帳有「直播應援投票中獎」進帳。

---

## 四、部署狀態
- Bot：`cd1260e` 已 commit、已重啟部署、健康。
- 後台頁：`2eff931` 已 Firebase 部署（遊戲館）。
- env `LIVEVOTE_CLAIM_WINDOW_MS` 未設 → 現行 180000ms（3 分鐘）。

## 五、預期 findings 方向（給 Codex 聚焦）
主要風險在 **V3（pool.total 一致性）** 與 **V1（常數唯一來源）**，其餘為顯示層低風險。若 `pool.total` 非原子同步更新，是唯一可能的真 bug；顯示改動基本無虞。
