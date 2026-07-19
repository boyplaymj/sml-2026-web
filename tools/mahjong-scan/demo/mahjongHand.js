// 台灣麻將「胡/聽」純結構判定核心。不算台數、不判役種（免役即胡）。
// 演算法 = tools/mahjong-hand-core/SPEC.md §5 權威逐字副本
//        （port 自 sweetbot-next/Common/ReadyHandLogic.js checkHuPai/isCanHU，6000 手差分驗證 100% 一致）。
// 瀏覽器 + Node 皆可用。全部吃「牌 id 整數陣列」。
(function (root) {
  'use strict';

  // 牌 id 編碼（與 Common/MahjongCards.js 一致）：
  //   萬 1–9 / 索 11–19 / 筒 21–29 / 東101 南201 西301 北401 中501 發601 白701
  //   花色間留間隔、字牌各佔百位 → 順子 first+1/first+2 天然不跨花色、字牌永不成順。
  var TILE_IDS = [
    1, 2, 3, 4, 5, 6, 7, 8, 9,           // 萬
    11, 12, 13, 14, 15, 16, 17, 18, 19,  // 索
    21, 22, 23, 24, 25, 26, 27, 28, 29,  // 筒
    101, 201, 301, 401, 501, 601, 701    // 東南西北中發白
  ];

  function removeN (cards, id, n) {
    var out = cards.slice();
    for (var k = 0; k < n; k++) {
      var idx = out.indexOf(id);
      if (idx >= 0) out.splice(idx, 1);
    }
    return out;
  }

  // 已抽將的牌堆能否全拆成面子（刻子/順子）。cards 需已排序升冪。
  // 刻子與順子「兩支都試」才完備。
  function decompose (cards) {
    if (cards.length === 0) return true;
    var first = cards[0];
    var count = cards.filter(function (c) { return c === first; }).length;
    if (count >= 3 && decompose(removeN(cards, first, 3))) return true;            // 刻子
    if (cards.indexOf(first + 1) >= 0 && cards.indexOf(first + 2) >= 0) {          // 順子
      var rest = removeN(cards, first, 1);
      rest = removeN(rest, first + 1, 1);
      rest = removeN(rest, first + 2, 1);
      if (decompose(rest)) return true;
    }
    return false;
  }

  // 判胡：3k+2 張。枚舉將牌 → 抽 2 → 剩下全拆成面子。
  function isHu (ids) {
    if (!Array.isArray(ids) || ids.length % 3 !== 2) return false;
    var cards = ids.slice().sort(function (a, b) { return a - b; });
    if (cards.length === 2) return cards[0] === cards[1];
    var tried = {};
    for (var i = 0; i < cards.length; i++) {
      var t = cards[i];
      if (tried[t]) continue;
      tried[t] = true;
      var n = cards.filter(function (c) { return c === t; }).length;
      if (n >= 2 && decompose(removeN(cards, t, 2))) return true;
    }
    return false;
  }

  // 聽哪些牌：3k+1 張 → 回可胡的牌 id 陣列（升冪）。非 3k+1 → []。
  function waitingTiles (ids) {
    if (!Array.isArray(ids) || ids.length % 3 !== 1) return [];
    var waits = [];
    for (var i = 0; i < TILE_IDS.length; i++) {
      var t = TILE_IDS[i];
      if (ids.filter(function (c) { return c === t; }).length >= 4) continue; // 一種最多 4 張
      if (isHu(ids.concat([t]))) waits.push(t);
    }
    return waits;
  }

  // 是否聽牌：3k+1 且至少聽一張。
  function isTenpai (ids) { return waitingTiles(ids).length > 0; }

  var api = { TILE_IDS: TILE_IDS, isHu: isHu, isTenpai: isTenpai, waitingTiles: waitingTiles, decompose: decompose };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.MahjongHand = api;
})(typeof window !== 'undefined' ? window : this);
