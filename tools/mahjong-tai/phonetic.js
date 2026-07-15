/*
 * phonetic.js — 音近比對前處理層(Stage A / ①)
 *
 * 問題:瀏覽器內建 ASR 是通用中文聽寫,對麻將術語會用常用詞「腦補改寫」
 *       (門清→門青、獨聽→讀聽、大四喜→大思喜),字錯但「音」通常對。
 * 解法:不信任「字」,只信任「音」。把 ASR 生文字與台種詞庫都轉成無聲調拼音,
 *       用詞級容錯比對,校正回正規台種名,再交給 scoring.js 判台。
 *
 * 依賴:pinyin-pro(vendor/pinyin-pro.js,全域 window.pinyinPro)
 * 匯出:window.MahjongPhonetic = { buildIndex(table), normalize(rawText) }
 */
(function (global) {
  var PY_OPT = { toneType: 'none', type: 'array', nonZh: 'consecutive' };

  function toPinyin(text) {
    if (!global.pinyinPro || !text) return [];
    // 只保留有拼音的音節(過濾空字串 / 純符號殘留)
    return global.pinyinPro.pinyin(text, PY_OPT)
      .map(function (s) { return (s || '').toLowerCase().trim(); })
      .filter(function (s) { return /[a-z]/.test(s); });
  }

  // 台灣國語音變正規化:把系統性的口音/誤聽合流成同一形式再比對。
  //   聲母:平舌翹舌不分  zh→z、ch→c、sh→s
  //   韻母:前後鼻音不分  -eng→-en、-ing→-in
  // 例:大「十」喜(shi)↔ 大「四」喜(si)→ 皆 si;門「親」(qin)↔ 門「清」(qing)→ 皆 qin
  function canon(s) {
    return s
      .replace(/^zh/, 'z').replace(/^ch/, 'c').replace(/^sh/, 's')
      .replace(/eng$/, 'en').replace(/ing$/, 'in');
  }

  // 兩個音節的相似度:
  //   完全相同         = 1.0
  //   台灣音變同形(平翹舌/前後鼻音) = 0.9(視為強命中)
  //   僅差一個字元(其他誤聽)        = 0.5
  //   否則             = 0
  function syl(a, b) {
    if (a === b) return 1;
    if (canon(a) === canon(b)) return 0.9;
    if (lev(a, b) === 1) return 0.5;
    return 0;
  }

  // Levenshtein(短字串,足夠快)
  function lev(a, b) {
    var m = a.length, n = b.length;
    if (Math.abs(m - n) > 1) return 2; // 早退:只在乎 <=1
    var prev = [], cur = [], i, j;
    for (j = 0; j <= n; j++) prev[j] = j;
    for (i = 1; i <= m; i++) {
      cur[0] = i;
      for (j = 1; j <= n; j++) {
        var cost = a.charCodeAt(i - 1) === b.charCodeAt(j - 1) ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
      }
      for (j = 0; j <= n; j++) prev[j] = cur[j];
    }
    return prev[n];
  }

  var INDEX = []; // [{ id, name, py:[...], n }]

  // 從 fan_table.json 建索引:每個台種的正規名 + 所有別名,各自算拼音
  function buildIndex(table) {
    INDEX = [];
    var fans = (table && table.fans) || [];
    fans.forEach(function (f) {
      // 正規名 + 別名 + 飛輪學到的誤聽詞(asr_confusions),都建進音近索引
      var surfaces = [f.name].concat(f.aliases || []).concat(f.asr_confusions || []);
      var seen = {};
      surfaces.forEach(function (s) {
        var py = toPinyin(s);
        if (!py.length) return;
        var key = py.join(' ');
        if (seen[key]) return; // 同台種內拼音重複的別名略過
        seen[key] = 1;
        INDEX.push({ id: f.id, name: f.name, surface: s, py: py, n: py.length });
      });
    });
    // 長詞優先(貪婪比對時先吃長的,避免「碰碰胡」被「胡」搶走)
    INDEX.sort(function (a, b) { return b.n - a.n; });
    return INDEX.length;
  }

  // 一個台種詞條 entry 是否能對齊 rawPy 從 pos 起的窗口;回傳分數 0~1
  function scoreAt(entry, rawPy, pos) {
    if (pos + entry.n > rawPy.length) return 0;
    var strong = 0, sum = 0; // strong = 完全相同或台灣音變同形(>=0.9)
    for (var k = 0; k < entry.n; k++) {
      var s = syl(entry.py[k], rawPy[pos + k]);
      if (s >= 0.9) strong++;
      sum += s;
    }
    var avg = sum / entry.n;
    // 單音節台種:必須強命中(完全相同或口音變體),否則太容易誤判
    if (entry.n === 1) return strong === 1 ? avg : 0;
    // 多音節:平均 >=0.75 且至少過半是強命中才算(容 1 個較遠的近音)
    if (avg >= 0.75 && strong >= Math.ceil(entry.n / 2)) return avg;
    return 0;
  }

  /*
   * normalize(rawText) → {
   *   normalizedText: 校正後的正規台種名(空白分隔,可直接餵 MahjongTai.parse),
   *   matched: [{id, name, score}],
   *   leftover: 未對到的殘音(給使用者看「這段沒聽懂」),
   *   rawPinyin: 原始拼音字串(除錯用)
   * }
   */
  function normalize(rawText) {
    var rawPy = toPinyin(rawText);
    var used = new Array(rawPy.length).fill(false);
    var matched = [];
    var pos = 0;
    while (pos < rawPy.length) {
      if (used[pos]) { pos++; continue; }
      var best = null;
      for (var i = 0; i < INDEX.length; i++) {
        var e = INDEX[i];
        // 窗口內若已有被吃掉的音節則跳過
        var free = true;
        for (var k = 0; k < e.n && pos + k < rawPy.length; k++) {
          if (used[pos + k]) { free = false; break; }
        }
        if (!free) continue;
        // 單音節台種太容易同音誤判(花/話/化/畫),要求原文真的出現該字才採計
        if (e.n === 1 && rawText.indexOf(e.surface) < 0) continue;
        var sc = scoreAt(e, rawPy, pos);
        if (sc > 0 && (!best || sc > best.score || (sc === best.score && e.n > best.n))) {
          best = { id: e.id, name: e.name, score: sc, n: e.n };
        }
      }
      if (best) {
        for (var j = 0; j < best.n; j++) used[pos + j] = true;
        matched.push({ id: best.id, name: best.name, score: Math.round(best.score * 100) / 100 });
        pos += best.n;
      } else {
        pos++;
      }
    }
    var leftover = rawPy.filter(function (_, i) { return !used[i]; }).join(' ');
    // 同一台種可能重複命中(例:兩次自摸),parse 端自行處理;這裡保留順序去重相鄰重覆的名稱串
    var normalizedText = matched.map(function (m) { return m.name; }).join(' ');
    return {
      normalizedText: normalizedText,
      matched: matched,
      leftover: leftover,
      rawPinyin: rawPy.join(' ')
    };
  }

  global.MahjongPhonetic = { buildIndex: buildIndex, normalize: normalize, _toPinyin: toPinyin };
})(typeof window !== 'undefined' ? window : globalThis);

// Node 端測試用
if (typeof module !== 'undefined' && module.exports) {
  module.exports = globalThis.MahjongPhonetic;
}
