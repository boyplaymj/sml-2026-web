# 🀄 麻將「胡牌／聽牌」判定核心 — 共用模組規格

> **目的**：把台灣麻將「這手牌胡了沒／聽哪些牌」的判定抽成一支**無相依、純函式**的共用模組，讓多個遊戲/功能同時取用（奧社聽牌試煉、ReadyHand 聽牌遊戲、語音判台、両雀…），不再各寫一份。
>
> **只判「胡/聽」結構，不算台數、不判役種**（台灣麻將免役即可胡）。台數/番種是另一層（見 §6 邊界）。
>
> 定稿日：2026-07-18　狀態：**已實作 + 差分驗證通過**（`sweetbot-next/Common/MahjongHand.js` + `test/mahjongHand.test.js`，commit `901a849`，未 push）。本 §5 內嵌的程式碼＝權威實作逐字副本。

> **✅ 落地驗證（2026-07-18）**：17 項單測全綠；並對地城 `ReadyHandLogic` 出題器 **6000 手差分比對**，核心判定與 `isCanHU` **100% 一致（0 分歧）** → 確認忠實重現實戰邏輯。唯一行為差異＝本模組的 **`>=4` 守衛**：手上已 4 張的牌不列入聽（地城會把「湊第 5 張」也算聽，6000 手中犯 472 次＝其潛在 bug）。此守衛為**刻意改良**、符合「一種牌最多 4 張」物理事實，預設開啟。

---

## 1. 為什麼做這個

- 地城工程師**早已寫好**台灣麻將胡牌判定：`sweetbot-next/Common/ReadyHandLogic.js` 的 `checkHuPai()` / `isCanHU()`，且已在 **ReadyHand 聽牌遊戲**（`model/ReadyHand.js`）與地城實戰驗證。
- 但它與**出題/DAO/圖片**耦合在同一個 class（`createCards`/`createBaseCards`/`ReadyHandTopicDAO`）。要給別的遊戲共用，需把**純判定核心**抽出來、改成吃「牌 id 整數陣列」、零相依。
- 抽出後，任何遊戲只要把手牌轉成 id 陣列就能問：**胡了沒？聽哪些牌？**

---

## 2. 現成實作（權威演算法來源）

`Common/ReadyHandLogic.js`：

- **`checkHuPai(idList)`**：遞迴結構拆解——把（已抽掉將牌的）牌堆全部拆成**面子**（刻子/順子）。空了＝成立。
- **`isCanHU(handCards, card)`**：手牌 + 一張牌能否胡——枚舉可當**將牌**（對子）的牌，抽掉 2 張後丟給 `checkHuPai`。
- 花色出題器 `createBaseCards(color)` 支援 `m/s/p/ms/mp/sp/msp` 花色約束 → **正好對應奧社難度軸 B（花色數）**，出題側也可重用。
- ReadyHand 遊戲已用它預生成題庫（`sweetbot-readyhand-topic` 表：`cards`/`answer`/`level=聽幾張`/`cardColor`），**奧社試煉可直接沿用這套題庫或出題器**。

> 本規格的純模組＝把上面兩支核心 port 成 int 陣列版、並補「聽牌/聽哪些牌」的對外 API。演算法邏輯**不變**（僅硬化：拆解同時嘗試刻子與順子兩支，見 §5 註）。

---

## 3. 牌 id 編碼（與 `Common/MahjongCards.js` 一致，正典）

| 花色 | id 範圍 |
|---|---|
| 萬 m | `1–9` |
| 索 s | `11–19` |
| 筒 p | `21–29` |
| 字牌 | 東`101` 南`201` 西`301` 北`401` 中`501` 發`601` 白`701` |

**設計巧思**：花色間留 id 間隔（9→11）、字牌各佔百位 → `first+1 / first+2` 的順子判定**天然不會跨花色、字牌永不成順**（只能刻/對）。共 **34 種**。

```js
const TILE_IDS = [
  1,2,3,4,5,6,7,8,9,            // 萬
  11,12,13,14,15,16,17,18,19,  // 索
  21,22,23,24,25,26,27,28,29,  // 筒
  101,201,301,401,501,601,701  // 東南西北中發白
];
```

---

## 4. 手牌張數契約（台灣麻將 16 張制）

台灣麻將完成型 ＝ **5 面子 + 1 將 = 17 張**（每面子 3、將 2）。

| 手牌張數 | = | 用途 |
|---|---|---|
| **3k+2**：`2 / 5 / 8 / 11 / 14 / 17` | k 面子 + 1 將 | **判胡** `isHu(ids)` |
| **3k+1**：`1 / 4 / 7 / 10 / 13 / 16` | 差一張成 3k+2 | **判聽** `isTenpai(ids)` / `waitingTiles(ids)` |

- `isHu`：張數非 3k+2 → 直接 `false`。
- `waitingTiles`：張數非 3k+1 → 回 `[]`。
- **不需役種**：任何「5 面子 + 將」的結構即胡（免斷么、免門清、免任何番種）。
- 不含 7 對子等特殊型（台灣 16 張胡型不採；如未來要，另加旗標，預設關）。

---

## 5. 對外 API（提議的純模組 `Common/MahjongHand.js`）

零相依、可離線單測。全部吃「牌 id 整數陣列」。

```js
// 台灣麻將「胡/聽」純結構判定。不算台數、不判役種。
// 演算法 port 自 Common/ReadyHandLogic.js（checkHuPai/isCanHU）。

const TILE_IDS = [/* 見 §3 */];

function removeN (cards, id, n) {
  const out = cards.slice();
  for (let k = 0; k < n; k++) {
    const idx = out.indexOf(id);
    if (idx >= 0) out.splice(idx, 1);
  }
  return out;
}

// 已抽將的牌堆能否全拆成面子（刻子/順子）。cards 需已排序升冪。
// ⚠️ 硬化：刻子與順子「兩支都試」（原 ReadyHandLogic 是 count==3 才刻、否則只試順，
//    對 4 張同牌等情形可能漏解）。存在任一組拆法即成立 → 兩支都試才完備。
function decompose (cards) {
  if (cards.length === 0) return true;
  const first = cards[0];
  const count = cards.filter(c => c === first).length;
  if (count >= 3 && decompose(removeN(cards, first, 3))) return true;            // 刻子
  if (cards.includes(first + 1) && cards.includes(first + 2)) {                  // 順子
    let rest = removeN(cards, first, 1);
    rest = removeN(rest, first + 1, 1);
    rest = removeN(rest, first + 2, 1);
    if (decompose(rest)) return true;
  }
  return false;
}

// 判胡：3k+2 張。枚舉將牌 → 抽 2 → 剩下全拆成面子。
function isHu (ids) {
  if (!Array.isArray(ids) || ids.length % 3 !== 2) return false;
  const cards = ids.slice().sort((a, b) => a - b);
  if (cards.length === 2) return cards[0] === cards[1];
  const tried = new Set();
  for (const t of cards) {
    if (tried.has(t)) continue;
    tried.add(t);
    if (cards.filter(c => c === t).length >= 2 && decompose(removeN(cards, t, 2))) return true;
  }
  return false;
}

// 聽哪些牌：3k+1 張 → 回可胡的牌 id 陣列（升冪）。非 3k+1 → []。
function waitingTiles (ids) {
  if (!Array.isArray(ids) || ids.length % 3 !== 1) return [];
  const waits = [];
  for (const t of TILE_IDS) {
    if (ids.filter(c => c === t).length >= 4) continue; // 一種最多 4 張
    if (isHu([...ids, t])) waits.push(t);
  }
  return waits;
}

// 是否聽牌：3k+1 且至少聽一張。
function isTenpai (ids) { return waitingTiles(ids).length > 0; }

module.exports = { TILE_IDS, isHu, isTenpai, waitingTiles, decompose };
```

---

## 6. 邊界（這模組**不**負責）

- **台數/番種計算**（門清、自摸、碰碰胡、清一色…）→ 另一層。既有 `tools/mahjong-voice-tai`（語音判台）走後台 yakuList，與本模組互補：本模組判「胡/聽」，判台模組算「幾台」。
- **食牌/吃碰槓的副露狀態**：本模組吃「當前手牌 id 陣列」，副露面子若要納入，呼叫端先把副露攤平成 id 一併傳入（總張數仍守 3k+1／3k+2）。
- **紅中賴子/花牌/百搭**：預設不支援；如要，另加參數，預設關。

---

## 7. 重用對象

| 使用者 | 怎麼用 |
|---|---|
| **奧社聽牌試煉**（`tools/jinja-shrine` §5.2） | `waitingTiles(手牌)` 出題與驗答（玩家組出的手牌聽牌集合是否**正好**== 題目目標）；花色約束沿用 `createBaseCards` |
| **ReadyHand 聽牌遊戲**（既有） | 收斂到共用核心，`isCanHU` → `isHu`/`waitingTiles` |
| **語音判台**（`tools/mahjong-voice-tai`） | 先用本模組確認「這手真的胡了」，再算台 |
| **両雀 / 未來麻將玩法** | 任何要問「胡沒／聽啥」的地方 |

---

## 8. 測試矩陣（實作時 node:test，命門）

**判胡（isHu, 3k+2）**
1. 最小：一對將（`[5,5]`）→ true；`[5,6]` → false。
2. 純刻子胡：`111 222 333 + 東東`（5 面子版擴充）。
3. 純順子胡：`123 456 789 + 對`。
4. 刻順混合、跨三花。
5. 字牌只成刻/將：`中中中 + …`；`123字`不成順 → 對應 false 案例。
6. **手內槓（4 張同牌）**：`1111 + 23 + …` 需靠「兩支都試」才判對（§5 硬化重點）。
7. 完整 17 張（5 面子 + 將）大手。
8. 差一張的 16 張 → isHu false（張數 3k+1）。

**判聽 / 聽哪些牌（waitingTiles / isTenpai, 3k+1）**
9. 兩面：`45餅` → 聽 `{3,6}餅`（`[24,25]`→`[23,26]`）。
10. 嵌張：`46` → 聽 `5`；邊張：`89`→聽`7`。
11. 單騎：`…+單`→聽該單張。
12. 多面聽：延べ単/三面 → 聽 3 張以上，集合正確。
13. 非聽牌手 → `waitingTiles=[]`、`isTenpai=false`。
14. 一種牌已 4 張時不列入聽（`>=4` 排除）正確。
15. 16 張聽牌（滿手差一張）大場景。

**契約**
16. 張數非 3k+1 傳 `waitingTiles` → `[]`；非 3k+2 傳 `isHu` → `false`。
17. 對拍：`isTenpai(h)` ⟺ 存在 t 使 `isHu([...h,t])`。

---

## 9. 落地步驟

1. ✅ **已做**：`sweetbot-next/Common/MahjongHand.js`（§5 純模組）＋ `test/mahjongHand.test.js`（§8 矩陣，17 綠）。差分驗證見開頭。commit `901a849`（未 push）。
2. ⬜ 把 `Common/ReadyHandLogic.js` 的判定改成**委派**新模組（保留其出題器 `createCards`/`createBaseCards`），避免兩份邏輯漂移。⚠️ 注意：委派後 ReadyHand 遊戲的「聽牌答案」會少掉「手上滿 4 張」的幻聽（正確化）；若要與舊題庫完全相容，委派時可加參數 `allowImpossibleFourth`（預設 false）。
3. ⬜ 奧社聽牌試煉、語音判台改用共用核心。
4. ⬜ 若他 repo（両雀等）要用，複製 `MahjongHand.js`（純檔、零相依）或抽 npm 私包；本規格為單一真理。

> **成本**：純邏輯、$0、無 LLM、無新表（沿用既有 `readyhand-topic` 題庫）。
