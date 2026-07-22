# HANDOFF S4 — 麻將御神籤（開運牌守）｜跨系統：甜甜神社 × 試煉之門地城

> 狀態：**階段1 設計定案 v3（已納入 Codex 兩輪查驗，累計 6 blocking 全數解決）**。實作分階段 2→3→4→5。
> v1→v2：propId 改 15~23、持有上限改 deterministic row 條件寫原子化、抽籤先發牌後扣款回滾。
> v2→v3（Codex 次輪）：B4 背包按鈕 String 正規化、B5 砸碎消耗改原子條件寫、B6 draw() 扣款後全程退款契約。
> v3→v3.1（Codex 三輪）：清除 §3/§5 殘留 v2 舊文字。
> v3.1→v3.2（Codex 四輪, 階段3a 實作查驗）：**B7** 改 reserve/commit 兩階段（pending 哨兵 → activate 真牌）消除 tile-without-charge；單測補 B6 退款直測 + activate 失敗路徑。

## 0. 一句話
在**神社授與所**用 700🦷 抽一張「麻將御神籤」：籤詩與一般御神籤**完全相同**（複用 `draw()`），但**額外附贈一張隨機麻將牌道具**進地城背包；玩家在**試煉之門地城**可「砸碎」該道具，**不扣攻擊力直接翻開一張牌**。

## 1. 定案規格（使用者拍板）
| 項目 | 定案 |
|---|---|
| 抽籤地點 | 神社授與所（御守區） |
| 籤詩內容 | **與一般御神籤完全相同**（複用 `ShrineOmikujiService.draw()`：籤詩池/rank/六軸buff/凶籤 pendingKyo/當日首抽計運），只差 fee=700 |
| 費用 | **700🦷**（一般御神籤 100，透過 `draw()` 新增 feeOverride 參數注入，不改預設） |
| 持有上限 | **1**：玩家同時只能持有一張未用掉的麻將御神籤（原子保證，見 §5） |
| 附贈道具 | 抽成功隨機發 **1/9** 牌面道具進地城背包（`sweetbot-rpg-backpack`） |
| 地城效果 | 砸碎 → 免扣 attack 翻開一張牌 |
| 砸到題外牌 | **方案A（永不落空）**：對應牌在 `topic.cards` 且未翻 → 翻它；否則從「`topic.cards` 未翻集合」隨機翻一張 |

## 2. 九牌 → cardId → propId → emoji 對照表（正典，v2 修訂 propId）
emoji 全部沿用 `model/MahjongCardsImg.js` 既有麻將牌（`w`=萬 `s`=索 `p`=筒；`r`=紅中 `g`=發財；`701 MJ2_w`=白板，**注意與 `301 MJ2_w`=西風同名不同 emoji id**）。

| propId | 道具名 | 牌 | cardId | dcImg (emoji) |
|---|---|---|---|---|
| 15 | 御神籤・三筒 | 三筒 | 23 | `<:MJ2_3p:1023949556393717770>` |
| 16 | 御神籤・四萬 | 四萬 | 4 | `<:MJ2_4w:1027593350066491404>` |
| 17 | 御神籤・一索 | 一索 | 11 | `<:MJ2_1s:1027592917302382644>` |
| 18 | 御神籤・紅中 | 紅中 | 501 | `<:MJ2_r:1027593547408490507>` |
| 19 | 御神籤・發財 | 發財 | 601 | `<:MJ2_g:1027593585119469608>` |
| 20 | 御神籤・白板 | 白板 | 701 | `<:MJ2_w:1027623770535514192>` |
| 21 | 御神籤・八萬 | 八萬 | 8 | `<:MJ2_8w:1027593477204226048>` |
| 22 | 御神籤・六筒 | 六筒 | 26 | `<:MJ2_6p:1023949564522283079>` |
| 23 | 御神籤・九筒 | 九筒 | 29 | `<:MJ2_9p:1023949543756284066>` |

> **[Codex-B1 已解]** propId 15~23 經 live scan 確認在 `sweetbot-rpg-props`（現有 id：1,2,3,6-14）與 `sweetbot-rpg-backpack`（持有涵蓋 1-14，含 orphan 4,5）**皆為空號**。**12~14 已被瘋火輪/計風器碎片A/精華丸佔用、且 backpack 有玩家持有，嚴禁使用**。migration 前仍須 read-back 一次再寫。

## 3. DDB `sweetbot-rpg-props` 每列 schema（照 WaterSUI 樣板）
真實欄位（get-item 驗證）：`id(S) / name(S) / enable(N) / category(N) / dcImg(S) / action(N) / maxQuantity(N)`。
- `enable = 1`
- `category = 2`（＝WaterSUI/LiveWaterSUI 同組＝地城消耗品；TDK 是 3）
- `action = 0`（**no-op**：`Props.actions` 只註冊 id=1；action=0 → `useAction`/`getAction` 找不到 → Props.js 端不做事，效果全在 TrialGate。**註**：WaterSUI 樣板的消耗走 `Props.useLogic`→`useProps`；**麻將御神籤 15~23 例外，消耗改走原子 `useMikujiSingleton`**（見 §5 B5），不經 useLogic/useProps）
- `dcImg` = §2 emoji
- `maxQuantity = 1`
- region `ap-southeast-1`

## 4. 各階段接口

### 階段2：地城道具定義層（純機械，可 Fable5）
- `const/rpgPropsEnum.js` 加 9 條（例 `Mikuji3p:{id:15,name:'御神籤・三筒'}` … 供程式引用）
- DDB 插 9 列（§3，id 15~23）
- **Props.js 僅一處微改（B4）**：`getBackpack` 的按鈕判斷 `canUseProps.includes(item.propsId)` → 改 `canUseProps.map(String).includes(String(item.propsId))`（String 正規化、向後相容，順修既有水道具 String-row 潛在不出鈕 bug）。action=0 no-op pattern 不變。

### 階段3：神社授與所抽籤（發放端）
- `defaults.js` omikuji 區塊加：`mahjongDrawFee: 700` + `mahjongTiles: [{propId,cardId,tile,dcImg}×9]`
- `ShrineOmikujiService.draw()` 兩處硬化：
  1. **加 opts 參數**：`async draw(discordId, nowEpoch, opts = {})`；`const fee = (opts.feeOverride != null) ? opts.feeOverride : cfg.drawFee;`（line 103，扣費/退款共用同一 `fee`，一般籤零影響）
  2. **[Codex-B6] 扣款後全程退款契約**：現行退款 try 只包 `replaceOmikujiState`（line 148），但 line 132~147 的 buff 組裝在 try 外，扣款(127)後若拋例外會走外層 catch(175) 不退款。→ **把退款 try 邊界上移，涵蓋「扣款之後到 return 之前」整段**；catch 內退款後回 `{ok:false, reason}`。契約收斂為 **「`ok:false` ⟹ 保證無淨扣款」**（此為既有潛在漏洞的修補，一般籤 success 路徑不變）。單元測試補「扣款後拋例外 → 已退款」。
- `ShrineOmikujiService.drawMahjong(discordId, nowEpoch?)`（依賴可注入 `RPG_BackpackDAO`）：**reserve/commit 兩階段，「持有上限=1」且「絕不留免費牌」**（見 §5，Codex-B7）
  1. 隨機挑 1/9 tile（propId∈15~23, cardId, dcImg），propsId 於 activate 時才寫入
  2. `backpackDAO.reserveMikuji(discordId)`（占鎖＝寫 pending row：`quantity:1, propsId:'pending'` 哨兵不可用；原子條件寫）
     - 拋 `ConditionalCheckFailedException` → 回 `{ok:false, reason:'has_pending_tile'}`（**未扣款**）
  3. `draw(discordId, now, {feeOverride:700})`（籤詩/buff/pendingKyo 全同一般籤）
     - `ok:false`（餘額不足/B6 write_failed 等）→ 依 B6 契約 draw 已保證無淨扣款 → `backpackDAO.clearMikujiReserve(discordId)`（清鎖 qty→0；清失敗也只留不可用 pending，**不留免費牌**）→ 回傳 draw 的 reason
  4. `draw ok:true` → `backpackDAO.activateMikuji(discordId, tile.propId)`（pending→真牌，SET propsId=牌，**此刻才可用**）
     - `activated=false`（極罕 activate 條件失敗）→ **退款 fee + 清鎖** → 回 `{ok:false, reason:'grant_failed'}`（無淨扣款、無可用牌）
     - `activated=true` → 回 `{ok:true, ...drawResult, tile:{propId,cardId,tile,dcImg}}`
- `Shrine.js` 授與所加「🀄 麻將御神籤を引く」入口 + handler：
  - **[Codex-NB 已納入]** **不可**複用一般御神籤結果卡的「もう一度引く」鈕（那顆會回到 100🦷 一般籤）。改用**專屬結果訊息**：顯示籤詩（rank/和歌/總合）＋「獲得 <emoji> 御神籤・XX，已放進🗡️試煉之門背包」＋**不放再抽鈕**（持有上限=1，抽不了）
  - gate 擋（reason=has_pending_tile）→ 訊息引導「你還有一張麻將御神籤沒用掉，先去試煉之門砸碎它」
- 單元測試 stub `RPG_BackpackDAO`（grantMikujiSingleton 成功/ConditionalCheckFailed 兩路徑 + draw 失敗回滾）

### 階段4：地城砸碎消耗端（方案A）
- `TrialGate.js`：`getCanUseProps` 白名單加 15~23
- `buttons` 加 `rpgProps_15`~`rpgProps_23` → `useOmikujiCrash(client, button)`
- `useOmikujiCrash`（**先驗後扣，順序照既有水道具**）：
  1. `gameInfo.data` 空 → 忽略
  2. **[Codex-NB 已修]** `if (!(await this.Prop.checkPropsOwner(client, button)))` → **務必加 `await`**（既有水道具 handler 漏 await＝bug，勿複製）
  3. 驗場內玩家（button.user.id ∈ player1/player2.dcID）、存活（hp>0）
  4. 反查 button propId → cardId
  5. 邊界：無 topic / 非答題階段 / `topic.cards` 全在 `showCards`（無未翻）→ 友善回覆、**不消耗**
  6. **[Codex-B5] 原子消耗**：`await backpackDAO.useMikujiSingleton(button.user.id, propId)`；**回傳 false（條件寫失敗＝已被扣/併發雙點）→ 中止、不翻牌**。**不走泛用 `useLogic`/`useProps`**（那是 scan+RMW 非原子，雙點會翻兩張）。propId 15~23 的 action=0，無 useAction 副作用，自行做①~③驗證即可
  7. **方案A翻牌**（僅在步驟6成功後）：cardId ∈ `topic.cards` 且 ∉ `showCards` → `showCards.push(cardId)`；否則從 `topic.cards \ showCards` 隨機挑一張 push。**不扣 attack**
  8. `printTopic()` 重印
- **[Codex-NB]** `showCards` 是 cardId 非位置；題目若有重複牌，push 一個 cardId 會顯示所有同牌 → 與既有答題翻牌一致，屬預期。

### 階段5：整合E2E + 部署 + 真人實測 + Codex複驗
E2E：抽(700扣款+gate)→背包有道具→砸碎→免費翻牌→qty歸0→可再抽。並發抽兩次只拿一張。`check-conflict.sh`→commit只加自己檔→deploy(先問時機)→私頻 903327108451950692 實測。

## 5. 並發與回滾（Codex-B2 / B3 / B7 解法）

### 原子持有上限＝1 + reserve/commit（B2 + B7「絕不留免費牌」）
背包表 PK=`id`（surrogate）、無 (user,propId) 唯一鍵，`addProps` 為 scan+RMW **非原子** → 併發抽籤會各拿一張。且若「一發就 qty=1（可用）」，draw 失敗+回滾失敗的雙重故障會留下**免費可用牌**（B7 經濟漏洞）。
**解法**：麻將御神籤走**專屬 deterministic row**（`id=mikuji:<discordId>`）+ **reserve/commit 兩階段**，三支新 DAO 方法：
```js
// ① reserveMikuji(discordId)：占鎖 = 寫 pending row(quantity:1, propsId:'pending' 哨兵不可用)
await ddb.send(new PutCommand({
  TableName: 'sweetbot-rpg-backpack',
  Item: { id: `mikuji:${discordId}`, discordUserId: String(discordId), propsId: 'pending', quantity: 1 },
  ConditionExpression: 'attribute_not_exists(id) OR quantity = :zero',
  ExpressionAttributeValues: { ':zero': 0 }
})); // 併發第二抽 → row 已 qty1 → 條件失敗 → ConditionalCheckFailedException → 擋抽(未扣款)。原子。

// ② activateMikuji(discordId, propId)：draw 成功後 pending→真牌(此刻才可用)。回 true/false
await ddb.send(new UpdateCommand({
  TableName, Key: { id: `mikuji:${discordId}` },
  UpdateExpression: 'SET propsId = :pid',
  ConditionExpression: 'quantity = :one AND propsId = :pending',
  ExpressionAttributeValues: { ':pid': String(propId), ':one': 1, ':pending': 'pending' }
}));

// ③ clearMikujiReserve(discordId)：draw 失敗清鎖(qty→0，可再抽)。條件 propsId='pending' 只清未 activate 的鎖。回 true/false
await ddb.send(new UpdateCommand({
  TableName, Key: { id: `mikuji:${discordId}` },
  UpdateExpression: 'SET quantity = :zero',
  ConditionExpression: 'propsId = :pending',
  ExpressionAttributeValues: { ':zero': 0, ':pending': 'pending' }
}));
```
- **哨兵 `propsId:'pending'` 無對應 rpg-props 列** → `Props.getBackpack` 的 `propsDAO.get('pending')` 回 null → 該 row 被跳過 → **pending 期間天然不出使用鈕**（不必改共用 getBackpack）。
- **絕不留免費牌**：任何雙重故障（draw 失敗 + 清鎖失敗 / activate 失敗 + 清鎖失敗）殘留最壞 = 不可用的 pending 鎖（可回收 lockout），永不留下 qty=1 的真牌。
- 再抽：consume/clear 後 row qty=0 → reserve 條件 `quantity = :zero` 成立 → 覆寫新 pending。
- getBackpack 靠 `select({discordUserId})` 撈得此 row；真牌 qty=1 顯示 emoji/按鈕，qty=0 或 pending 不出鈕。
- deterministic row 的真牌 `propsId` 存 **String**（與 props 表 `id`(S) 一致）；**[B4]** 按鈕出現靠 `Props.getBackpack` 的 `canUseProps.map(String).includes(String(item.propsId))` 正規化。
- **限制（可接受）**：`!give`（admin usePermission 99）灌 propId 15~23 會建 surrogate row 繞過本機制；規範上麻將御神籤**只由 drawMahjong 發放**。

### 原子砸碎消耗（B5，防雙點翻兩張）
既有 `useProps` 是 scan→讀 qty→update **無條件**，雙互動同時進來都看到 qty1、都扣成 0、都放行翻牌（＝按鈕連點雙結算同類 bug）。地城砸碎**不走 useProps**，改走新增的 deterministic-id 條件更新：
```js
// RPG_BackpackDAO.useMikujiSingleton(discordId, propId) → true(消耗成功) | false(條件失敗)
try {
  await ddb.update({
    TableName: 'sweetbot-rpg-backpack',
    Key: { id: `mikuji:${discordId}` },
    UpdateExpression: 'SET quantity = :zero',
    ConditionExpression: 'quantity >= :one AND propsId = :pid',
    ExpressionAttributeValues: { ':zero': 0, ':one': 1, ':pid': String(propId) }
  });
  return true;
} catch (e) {
  if (e.name === 'ConditionalCheckFailedException') return false; // 已被扣/併發雙點/牌種不符
  throw e;
}
```
- 只有第一次點擊條件成立 → qty 歸 0；第二次點擊 `quantity>=1` 失敗 → 回 false → TrialGate 不翻牌。**原子**。
- 消耗只動背包 deterministic row、**不回寫神社**（零耦合）。
- 注意：地城消耗走 `useMikujiSingleton`（真牌 qty1→0）；抽籤失敗回滾走 `clearMikujiReserve`（pending qty1→0），兩者不同支。

### 扣款/發牌回滾（B3 + B6 + B7）
- **順序＝reserve 占鎖 → 扣款抽籤 → 成功才 activate**（§4 階段3）。reserve 是 pending（不可用），activate 後才是真牌 → 消除 tile-without-charge（B7）。
- `draw()` 依 **B6 契約 = 「`ok:false` ⟹ 無淨扣款」**（退款 try 上移涵蓋整個扣款後區塊，任何扣款後失敗都退款）。
- `draw ok:false` → `clearMikujiReserve` 清鎖；`activate` 失敗（極罕）→ **退款 fee + 清鎖** → `grant_failed`。
- 殘留最壞 = 不可用 pending 鎖（lockout，可回收），**永不 charged-without-usable-tile 的免費牌**；B6 亦涵蓋一般 100🦷 籤的既有潛在漏洞。

## 6. 💰 成本控管
無額外成本：無 LLM / 無新 DDB 表（既有 `sweetbot-rpg-props`+`sweetbot-rpg-backpack` 加列）/ 無付費 API / 圖沿用既有 emoji（零生圖）。依 `tools/COST_CONTROL.md` 屬「既有表加欄位／純前端」→ **免四件套**。

## 7. Codex 查驗結果對照
**首輪（v2 處理）**
- **B1（propId 12~20 非空號）** → 已改 15~23（scan 驗證空號）。✓
- **B2（持有上限非原子）** → deterministic row 條件寫原子化（§5）。✓
- **B3（扣款無 rollback）** → 先發牌後扣款＋失敗回滾（§5）。✓
- NB：category=2/action=0✓；先驗後扣✓；showCards=cardId 重複牌顯示屬預期✓；DAO 可注入✓；改專屬結果卡不放再抽鈕✓；新 handler 補 `await checkPropsOwner`✓。

**次輪（v3 處理）**
- **B4（deterministic row String propsId → 背包不出使用鈕）** → `Props.getBackpack` 按鈕判斷 String 正規化（§4 階段2 + §5）。✓
- **B5（砸碎消耗非原子 → 雙點翻兩張）** → 新增 `useMikujiSingleton` deterministic-id 條件更新，地城不走泛用 useProps（§4 階段4 + §5）。✓
- **B6（draw 扣款後其他例外不退款）** → draw() 退款 try 邊界上移涵蓋整個扣款後區塊，契約「ok:false ⟹ 無淨扣款」（§4 階段3）。✓
- 已確認通過：propId 15~23 空號（AWS read-back）✓；feeOverride 第三參數不影響既有呼叫點✓；category=2/action=0、先驗後扣、showCards=cardId 方向 OK✓。

**四輪（v3.2 處理，階段3a 實作查驗）**
- **B7（drawMahjong 仍有 tile-without-charge：占位一發即 qty1 可用，draw 失敗+回滾失敗留免費牌）** → 改 reserve/commit：reserve 寫 pending 哨兵（不可用）→ draw 成功才 activate 成真牌；draw 失敗 clearMikujiReserve、activate 失敗退款+清鎖。雙重故障殘留最壞=不可用 pending 鎖，永不留免費牌（§5）。✓
- **B8（新 3 測未覆蓋 B6 退款邊界與 activate/rollback 失敗）** → 補：`draw()` B6 退款直測、drawMahjong replace 拋錯退款+清鎖、drawMahjong activate 失敗退款+清鎖+grant_failed。shrine 全組 156 pass。✓
- 已確認通過：grant/use ConditionExpression 與 deterministic row 自洽、feeOverride 只影響麻將路徑、一般 draw success path 仍綠（Codex 四輪原話）。
