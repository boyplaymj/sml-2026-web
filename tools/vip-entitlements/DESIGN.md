# 甜甜 VIP 特權管理（VIP Entitlements）— 設計冊 v0.1

> 狀態：**決策已定案，待交 Codex 打底**。
> 一句話：在遊戲館後台開**單一頁面**，集中管理 VIP / VVIP / VVVIP 三階在**各遊戲/功能**的特權；各遊戲透過一支共用存取器 `vipPerk()` 讀取，特權值存 DDB、後台可調。
> 誰觸發：使用者（甜甜遊戲館後台）。
> 關聯：現成 `model/VipControl.js`（身分組→等級解析，直接複用）、[[報稅系統 tools/tax-system/DESIGN.md]]（第一個試點）、`project_sweetbot_vip_payment`（VIP 身分來源上游）。

---

## 1. 設計定案（本次討論拍板）

| # | 決策 | 定案 | 理由 |
|---|---|---|---|
| D1 | 中央 vs 各遊戲各做 | **聯邦式**：中央總表管理，特權型別由各遊戲宣告 | 各遊戲特權不同質，硬做統一格子裝不下；純各遊戲做則管理面碎裂 |
| D2 | 三階是否累進繼承 | **獨立、不累進** | 特權有的是次數、有的是獎勵倍率，不同質無法自動繼承；每階逐格設定 |
| D3 | 身分來源 | **Discord 身分組**（= YT 會員等級，目前同一個東西） | 互動自帶 `member.roles`，即時真相；不用查名冊、不用開特權 intent |
| D4 | 多重身分組如何解析 | **取最高階** | 安全保險；`VipControl.js` 既有邏輯已如此（`item.level > nowVipLevel`） |
| D5 | 後台頁形式 | **單一頁面**：上唯讀總覽矩陣 + 下各遊戲摺疊編輯區 | 一次檢視 + 個別修改，且不用先幫每個遊戲蓋後台頁 |
| D6 | 特權型別 | **2 種**：開關（gate）/ 數值（number，帶單位標籤） | 次數/倍率/秒數/加碼🦷都是「數值+單位」，收斂最簡 |
| D7 | 手殘防護 | 高階數值 < 低階時後台跳**軟警示**（不擋存） | 獨立設定的代價是可能「高階反而給更少」，軟提醒補洞 |

---

## 2. 架構總覽

```
玩家跑遊戲指令
   │  互動自帶 message.roles（即時真相）
   ▼
getVipLevel(roles) → 0/1/2/3   ← 複用 VipControl 的 vipRole 清單（取最高階）
   │
   ▼
vipPerk(message, game, perkKey) ── 共用存取器（新做，像 em()/getPoint）
   │   回傳：開關→bool、數值→number
   ▼
DDB 表 sweetbot-vip-entitlements   ← 只存「遊戲 × 特權 × 階級 → 值」
   │   （不存「誰是VIP」；那是 Discord 身分組的事）
   ▲
   │  後台單頁讀寫（Lambda + APIGW + Firebase 登入）
遊戲館 vip_entitlements_admin.html
```

**身分（誰是VIP）與特權（VIP能幹嘛）分離**：前者永遠現場問 Discord 身分組，後者才是這套系統存的東西。「YT 會員 → 自動掛身分組」是上游別的系統的事，本套只認身分組。

---

## 3. 資料層（DDB：`sweetbot-vip-entitlements`，PAY_PER_REQUEST）

一筆 = 一個（遊戲, 特權）；三階的值放同一筆。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `game` (PK) | S | 遊戲/功能 key，如 `tax`、`bingo`、`crossroad` |
| `perkKey` (SK) | S | 特權 key，如 `dependentSlots`、`extraLives` |
| `gameLabel` | S | 遊戲顯示名（後台總覽用），如「報稅系統」 |
| `perkLabel` | S | 特權顯示名，如「扶養名額」 |
| `type` | S | `gate`（開關）或 `number`（數值） |
| `unit` | S | 數值單位標籤：`名`/`次`/`倍`/`秒`/`🦷`…（gate 型忽略） |
| `values` | M | `{ "1": <VIP值>, "2": <VVIP值>, "3": <VVVIP值> }`；gate 存 bool、number 存數字 |
| `note` | S | 備註（給後台管理者看，選填） |
| `updatedAt` | S | 最後修改時間 |

- **level 0（非 VIP）不入表**：`vipPerk` 對 level 0 一律回「無特權」（gate=false、number=0）。特權只描述 1/2/3。
- **key 是程式與表的契約**：`game`+`perkKey` 由遊戲程式碼引用；表只存可調的值。新增全新特權 = 開發在遊戲碼引用新 key + 後台「新增特權」開一列（或 seed migration）。後台可調值/開關，但**要程式有引用該 key 才會生效**。

### migration
初始 seed 只灌**第一個試點（報稅）**的特權列（§7），其餘遊戲逐步加。

---

## 4. 特權型別（D6：收斂成 2 種）

| type | 意義 | 後台控件 | `vipPerk` 回傳 | 遊戲碼用法範例 |
|---|---|---|---|---|
| `gate` | 能/不能做某事（資格閘門） | 三個開關（VIP/VVIP/VVVIP） | `boolean` | `if (await vip.perk(msg,'tax','canDependent')) {...}` |
| `number` | 次數/名額/倍率/秒數/加碼… | 三個數字框 + 單位標籤 | `number` | `const slots = await vip.perk(msg,'tax','dependentSlots')` |

> 倍率型建議約定：存「倍數」本身（如 `1.5` = 1.5 倍），遊戲碼自己乘。單位標籤填 `倍`。

---

## 5. 讀取路徑（bot 端）

### 5.1 `getVipLevel(roles)` — 抽共用 helper
把 `VipControl.js` 裡的 `vipRole` 清單 + 取最高階迴圈抽成獨立函式（`model/VipControl.js` 匯出，或移到 `CommonUtil`），供 `vipPerk` 與既有 `check()` 共用，避免兩份 role 清單漂移。

```js
// 現有邏輯（VipControl.js:47-52）抽出
function getVipLevel (roles) {
  let level = 0;
  vipRole.forEach(item => {
    if (CommonUtil.hasRole(roles, item.role) && item.level > level) level = item.level;
  });
  return level; // 0/1/2/3，取最高階
}
```

### 5.2 `vipPerk(message, game, perkKey)` — 共用存取器（新做 `model/VipPerk.js`）
```
1. level = getVipLevel(message.roles)
2. if level === 0 → 回 type 對應的「無特權」預設（gate:false / number:0）
3. 讀 DDB (game, perkKey)（帶記憶體快取，TTL 60s；後台寫入可推播失效，v1 先靠 TTL）
   - 查無此列 → 同樣回無特權預設（保守 fail-safe）
4. 依 type 回 values[level]（gate→bool、number→number）
```
- **fail-safe**：查表失敗 / 無資料 / DDB error → 一律回「無特權」，絕不因為 VIP 系統掛掉而讓遊戲崩或誤發特權。
- **快取**：讀多寫少，記憶體快取 60s；避免每個遊戲動作打 DDB。

---

## 6. 後台頁（D5：單頁 · 遊戲館）

檔案 `sweetbot-site/public/vip_entitlements_admin.html`，照 `tax_admin.html` / `livevote_admin.html` 慣例：Firebase 登入 + `gameAdmins` 白名單 + 呼叫 Lambda。

### 版面
```
┌ VIP 特權管理 ────────────────────────────────┐
│ 📊 總覽矩陣（唯讀）                              │
│  遊戲 · 特權 │  VIP  │ VVIP │ VVVIP │ 型別      │
│  報稅·扶養名額│  0    │  5   │  5    │ number 名 │
│  過馬路·多命 │  1    │  2   │  0 ⚠️ │ number 次 │← 高階反低警示
│  …                                              │
├──────────────────────────────────────────────┤
│ ▸ 📋 報稅系統   (點開 → 編輯區)                  │
│ ▸ 🏃 過馬路     (點開 → 編輯區)                  │
│   每個編輯區 = 該遊戲所有特權列，逐階控件         │
│   [＋ 新增特權] [儲存]                           │
└──────────────────────────────────────────────┘
```
- **上半**：總覽矩陣，唯讀，一次掃全部；`values` 高階 < 低階時該格標 ⚠️（D7 軟警示）。
- **下半**：每遊戲一個可摺疊區塊，點開才是編輯面板（只看到那個遊戲）。
- **共用編輯元件**：依 `type` 渲染開關 or 數字框+單位；寫一次，各遊戲區塊複用。
- **加分項（v1 免做）**：已有後台頁的遊戲（報稅/live-vote…）日後可把同一編輯元件嵌一份進自己頁面，資料同一支 API。

### Lambda actions（`sml-vip-entitlements`，照 sml-tax/sml-vote 認證樣式）
| action | 說明 |
|---|---|
| `list` | 回全部列（總覽 + 各遊戲區塊初始化） |
| `upsert` | 新增/更新一列（game, perkKey, labels, type, unit, values, note） |
| `delete` | 刪一列（下架某特權） |

- 認證抄 `sml-tax`：驗 Firebase token + 同步 `gameAdmins` 白名單。
- schema 對齊 §3；`values` 的 `%`/倍率不做隱式換算，前後端同單位存取。

---

## 7. 試點順序（別大爆炸；P0/P1 切小）

> ⚠️ **已驗證的落差(2026-07-16)**：`Tax.js:105-110` 的 `dependentCount: 0` 是**寫死**的(註解明講扶養/勳功 P3/P4 前固定 0)，Tax.js 完全沒讀任何 VIP 等級，**扶養資料源尚未存在**。因此報稅「接 vipPerk」只能驗**讀取管線**，不會有可見稅單變化(仍是 0 扶養)。可見行為驗證改用下面 SicBo。

### P0 — bot 端讀取管線打底（不含後台頁）
1. 抽 `getVipLevel(roles)`，`VipControl.check()` 改用它，補測「多身分組取最高階」。
2. 新增 `VipEntitlementDAO` + `model/VipPerk.js`：只做讀取 + 60s cache + fail-safe。
3. seed script 建 `sweetbot-vip-entitlements`，先灌兩批：
   - **讀回單元測試用**（報稅，暫不接行為）：
     | game | perkKey | type | unit | VIP | VVIP | VVVIP |
     |---|---|---|---|---|---|---|
     | `tax` | `canDependent` | gate | — | ✗ | ✓ | ✓ |
     | `tax` | `dependentSlots` | number | 名 | 0 | 5 | 5 |
   - **第一個可見整合**（SicBo，已上線的 VVVIP 閘門）：
     | game | perkKey | type | unit | VIP | VVIP | VVVIP |
     |---|---|---|---|---|---|---|
     | `sicbo` | `canOpenGame` | gate | — | ✗ | ✗ | ✓ |
4. **SicBo 收斂**：`SicBo.js` 現行 `isVVVIP = player.vipLevel == VVVIP`（`createNewGame` + 按鈕版兩處，line 30/81）改讀 `vipPerk(msg,'sicbo','canOpenGame')`。
   → 端到端可見驗證：VVVIP 能開骰寶局、非 VVVIP 不能，且**後台把 `canOpenGame` 對 VVIP 打開即時放行**。
   - ⚠️ 注意 SicBo 現讀 **cached `player.vipLevel`**（VipControl.check 才更新）；`vipPerk` 改走 **real-time `message.roles`**，語義更即時，Codex 換接時留意兩者差異、確認 `message.roles` 在該路徑可得。
5. 驗證：`node --check` + 單元測試 + 實際 DDB seed/read-back + Discord 真人開骰寶。

### P1 — 完整後台頁（P0 穩了才做）
`vip_entitlements_admin.html` + Lambda 認證 + 前端 CRUD + 軟警示 + upsert/delete（§6）。面較大，獨立一個 PR。

### P2+ — 逐遊戲搬入
過馬路多命、賓果多票、賭場上限…每個先在遊戲頻道確認語義再灌列。**報稅扶養**要等 tax-system 的扶養資料源/指令(P3/P4)做出來，才會有可見效果。

---

## 8. 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：DDB 新表 `sweetbot-vip-entitlements`（config 級，讀多寫少 + bot 端 60s 記憶體快取）、Lambda `sml-vip-entitlements`（免費額度內）。量級極小，預估 < $1/月。
- 所有新表 **PAY_PER_REQUEST**；**無 LLM / 無付費 API**，故免帳本封頂四件套。
- 若日後某特權要接 LLM 生成，回本規範補齊「四件套」。

---

## 9. 交 Codex 驗收點

- [ ] `getVipLevel` 抽出後，`VipControl.check()` 行為不變（只有一份 role 清單）。
- [ ] `vipPerk` 對 level 0 / 查無列 / DDB error → 一律回無特權（fail-safe，不崩不誤發）。
- [ ] 快取 60s：後台改值後最遲 60s 生效；不因快取回舊值誤判。
- [ ] 「取最高階」：身上同時掛多個階的身分組，回最高。
- [ ] 報稅試點：Tax.js 改讀 `vipPerk` 後，扶養行為與現行一致（VVIP 才可、上限 5）。
- [ ] 後台軟警示：高階值 < 低階值時該格標記，但仍可儲存。
- [ ] Lambda 認證對齊 `sml-tax`（Firebase + gameAdmins 白名單）。
```
