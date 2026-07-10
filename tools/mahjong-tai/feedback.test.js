/* 糾正回饋測試:node feedback.test.js */
var assert = require('assert');
var fs = require('fs');
var path = require('path');
var { parse } = require('./scoring');
var fb = require('./feedback');

var pass = 0, fail = 0;
function t(name, fn) {
  try { fn(); pass++; console.log('  ✓ ' + name); }
  catch (e) { fail++; console.log('  ✗ ' + name + '\n      ' + e.message); }
}
function loadTable() { return JSON.parse(fs.readFileSync(path.join(__dirname, 'fan_table.json'), 'utf8')); }

console.log('糾正回饋測試:');

t('recordCorrection 算出 added/removed 差異', function () {
  var rec = fb.recordCorrection({ text: '門清 征化', parsed: ['menqing'], corrected: ['menqing', 'zhenghua'], unmatched: '征化', ts: 1 });
  assert.deepStrictEqual(rec.added, ['zhenghua']);
  assert.deepStrictEqual(rec.removed, []);
  assert.strictEqual(rec.unmatched, '征化');
});

t('低於門檻不建議(單筆口誤不污染)', function () {
  var table = loadTable();
  var recs = [fb.recordCorrection({ text: '征化', parsed: [], corrected: ['zhenghua'], unmatched: '征化', ts: 1 })];
  var sug = fb.extractSuggestions(recs, table, { minCount: 2 });
  assert.strictEqual(sug.length, 0);
});

t('達門檻 → 建議把新誤聽詞加入該台種', function () {
  var table = loadTable();
  var recs = [
    fb.recordCorrection({ text: '征化', parsed: [], corrected: ['zhenghua'], unmatched: '征化', ts: 1 }),
    fb.recordCorrection({ text: '門清 征化', parsed: ['menqing'], corrected: ['menqing', 'zhenghua'], unmatched: '征化', ts: 2 })
  ];
  var sug = fb.extractSuggestions(recs, table, { minCount: 2 });
  assert.strictEqual(sug.length, 1);
  assert.strictEqual(sug[0].type, 'add_confusion');
  assert.strictEqual(sug[0].term, '征化');
  assert.strictEqual(sug[0].fanId, 'zhenghua');
  assert.strictEqual(sug[0].count, 2);
});

t('已收錄的詞不重複建議', function () {
  var table = loadTable();
  // 「爭花」已是 zhenghua 的 asr_confusions,不該再被建議
  var recs = [
    fb.recordCorrection({ text: '爭花', parsed: ['zhenghua'], corrected: ['zhenghua'], unmatched: '', ts: 1 }),
    fb.recordCorrection({ text: '爭花', parsed: ['zhenghua'], corrected: ['zhenghua'], unmatched: '', ts: 2 })
  ];
  var sug = fb.extractSuggestions(recs, table, { minCount: 2 });
  assert.strictEqual(sug.length, 0);
});

t('applySuggestion 回灌後,parse 立刻認得新詞(端到端飛輪)', function () {
  var table = loadTable();
  // 回灌前:「征化」認不得
  assert.strictEqual(parse('征化', table).hits.length, 0);
  var recs = [
    fb.recordCorrection({ text: '征化', parsed: [], corrected: ['zhenghua'], unmatched: '征化', ts: 1 }),
    fb.recordCorrection({ text: '征化', parsed: [], corrected: ['zhenghua'], unmatched: '征化', ts: 2 })
  ];
  var sug = fb.extractSuggestions(recs, table, { minCount: 2 });
  var ok = fb.applySuggestion(table, sug[0]);
  assert.strictEqual(ok, true);
  // 回灌後:同一個 table 立刻判得出 zhenghua
  var r = parse('征化', table);
  assert.deepStrictEqual(r.hits.map(function (h) { return h.id; }), ['zhenghua']);
});

t('判錯台種 → 產生需人工複核的 review_mapping', function () {
  var table = loadTable();
  var recs = [
    fb.recordCorrection({ text: 'x', parsed: ['hunyise'], corrected: ['qingyise'], unmatched: '', ts: 1 }),
    fb.recordCorrection({ text: 'x', parsed: ['hunyise'], corrected: ['qingyise'], unmatched: '', ts: 2 })
  ];
  var sug = fb.extractSuggestions(recs, table, { minCount: 2 });
  var rm = sug.find(function (s) { return s.type === 'review_mapping'; });
  assert.ok(rm, '應有 review_mapping');
  assert.strictEqual(rm.fromFanId, 'hunyise');
  assert.strictEqual(rm.toFanId, 'qingyise');
});

t('review_mapping 不會被自動套用(applySuggestion 回 false)', function () {
  var table = loadTable();
  var ok = fb.applySuggestion(table, { type: 'review_mapping', fromFanId: 'hunyise', toFanId: 'qingyise' });
  assert.strictEqual(ok, false);
});

// ---- Codex review 修正回歸(F7 正規化)----
// 注意:要真正走到建議分支,parsed 必須「漏掉」該台種(added.length===1),不能 parsed===corrected(空過)
t('F7 標點繞過:爭花。 正規化後=已知詞,不建議', function () {
  var table = loadTable();
  var recs = [
    fb.recordCorrection({ text: '爭花。', parsed: [], corrected: ['zhenghua'], unmatched: '爭花。', ts: 1 }),
    fb.recordCorrection({ text: '爭花。', parsed: [], corrected: ['zhenghua'], unmatched: '爭花。', ts: 2 })
  ];
  var sug = fb.extractSuggestions(recs, table, { minCount: 2 });
  assert.strictEqual(sug.filter(function (s) { return s.type === 'add_confusion'; }).length, 0);
});

t('F7 各類符號皆繞不過(-、/、_、[、"、零寬)', function () {
  var table = loadTable();
  ['爭-花', '爭/花', '爭_花', '爭[花', '爭"花', '爭花​'].forEach(function (variant) {
    var recs = [
      fb.recordCorrection({ text: variant, parsed: [], corrected: ['zhenghua'], unmatched: variant, ts: 1 }),
      fb.recordCorrection({ text: variant, parsed: [], corrected: ['zhenghua'], unmatched: variant, ts: 2 })
    ];
    var sug = fb.extractSuggestions(recs, table, { minCount: 2 });
    assert.strictEqual(sug.filter(function (s) { return s.type === 'add_confusion'; }).length, 0, '應擋下:' + variant);
  });
});

t('F7 正向控制:帶符號的「真新詞」正規化後仍能建議', function () {
  var table = loadTable();
  var recs = [
    fb.recordCorrection({ text: '毒-停', parsed: [], corrected: ['dandiao'], unmatched: '毒-停', ts: 1 }),
    fb.recordCorrection({ text: '毒。停', parsed: [], corrected: ['dandiao'], unmatched: '毒。停', ts: 2 })
  ];
  var sug = fb.extractSuggestions(recs, table, { minCount: 2 });
  var s = sug.find(function (x) { return x.type === 'add_confusion'; });
  assert.ok(s, '毒停 是新詞應被建議');
  assert.strictEqual(s.term, '毒停'); // 已去除符號
});

t('F7 過長殘字不當新詞', function () {
  var table = loadTable();
  var long = '超級長的一串亂七八糟辨識錯誤';
  var recs = [
    fb.recordCorrection({ text: long, parsed: [], corrected: ['zhenghua'], unmatched: long, ts: 1 }),
    fb.recordCorrection({ text: long, parsed: [], corrected: ['zhenghua'], unmatched: long, ts: 2 })
  ];
  var sug = fb.extractSuggestions(recs, table, { minCount: 2 });
  assert.strictEqual(sug.length, 0);
});

t('F7 applySuggestion 也擋帶標點的重複詞', function () {
  var table = loadTable();
  var ok = fb.applySuggestion(table, { type: 'add_confusion', term: '爭花。', fanId: 'zhenghua' });
  assert.strictEqual(ok, false); // 正規化後=爭花,已存在
});

// ---- F6 防單人污染:有 userId 時看不同使用者數 ----
t('F6 同一人重送兩次(帶 userId)→ 不建議', function () {
  var table = loadTable();
  var recs = [
    fb.recordCorrection({ text: '毒停', parsed: [], corrected: ['dandiao'], unmatched: '毒停', userId: 'u1', ts: 1 }),
    fb.recordCorrection({ text: '毒停', parsed: [], corrected: ['dandiao'], unmatched: '毒停', userId: 'u1', ts: 2 })
  ];
  var sug = fb.extractSuggestions(recs, table, { minCount: 2 });
  assert.strictEqual(sug.length, 0); // 同一人不算數
});

t('F6 兩個不同使用者各一次 → 建議(且記錄 distinctUsers)', function () {
  var table = loadTable();
  var recs = [
    fb.recordCorrection({ text: '毒停', parsed: [], corrected: ['dandiao'], unmatched: '毒停', userId: 'u1', ts: 1 }),
    fb.recordCorrection({ text: '毒停', parsed: [], corrected: ['dandiao'], unmatched: '毒停', userId: 'u2', ts: 2 })
  ];
  var sug = fb.extractSuggestions(recs, table, { minCount: 2 });
  assert.strictEqual(sug.length, 1);
  assert.strictEqual(sug[0].distinctUsers, 2);
});

t('F6 無 userId 時退回筆數行為(向後相容)', function () {
  var table = loadTable();
  var recs = [
    fb.recordCorrection({ text: '毒停', parsed: [], corrected: ['dandiao'], unmatched: '毒停', ts: 1 }),
    fb.recordCorrection({ text: '毒停', parsed: [], corrected: ['dandiao'], unmatched: '毒停', ts: 2 })
  ];
  var sug = fb.extractSuggestions(recs, table, { minCount: 2 });
  assert.strictEqual(sug.length, 1); // 沒帶 id → 沿用舊筆數門檻
});

console.log('\n結果:' + pass + ' 通過 / ' + fail + ' 失敗');
process.exit(fail ? 1 : 0);
