/* 判讀邏輯測試:node scoring.test.js */
var assert = require('assert');
var fs = require('fs');
var path = require('path');
var { parse } = require('./scoring');
var table = JSON.parse(fs.readFileSync(path.join(__dirname, 'fan_table.json'), 'utf8'));

var pass = 0, fail = 0;
function t(name, fn) {
  try { fn(); pass++; console.log('  ✓ ' + name); }
  catch (e) { fail++; console.log('  ✗ ' + name + '\n      ' + e.message); }
}
function ids(r) { return r.hits.map(function (h) { return h.id; }).sort(); }

console.log('判讀測試:');

t('使用者的例子:門清 正花 獨聽', function () {
  var r = parse('門清 正花 獨聽', table);
  assert.deepStrictEqual(ids(r), ['dandiao', 'menqing', 'zhenghua']);
  // 門清1 + 正花1 + 獨聽1 + 底1 = 4
  assert.strictEqual(r.total, 4);
});

t('無空白也能斷詞:門清正花獨聽', function () {
  var r = parse('門清正花獨聽', table);
  assert.deepStrictEqual(ids(r), ['dandiao', 'menqing', 'zhenghua']);
});

t('長詞優先:門清自摸 不會被拆成 門清+自摸', function () {
  var r = parse('門清自摸', table);
  assert.deepStrictEqual(ids(r), ['menqing_zimo']);
  assert.strictEqual(r.total, 3 + 1); // 門清自摸3 + 底1
});

t('口語同義詞:單吊 = 獨聽', function () {
  var r = parse('單吊', table);
  assert.deepStrictEqual(ids(r), ['dandiao']);
});

t('誤聽糾正:爭花 → 正花', function () {
  var r = parse('爭花', table);
  assert.deepStrictEqual(ids(r), ['zhenghua']);
});

t('互斥:清一色 + 混一色 → 保留清一色(8台)', function () {
  var r = parse('清一色 混一色', table);
  assert.deepStrictEqual(ids(r), ['qingyise']);
  assert.strictEqual(r.warnings.some(function (w) { return w.level === 'exclude'; }), true);
  assert.strictEqual(r.total, 8 + 1);
});

t('花牌數量詞:三張花 = 3台', function () {
  var r = parse('三張花', table);
  var hua = r.hits.find(function (h) { return h.id === 'hua'; });
  assert.strictEqual(hua.units, 3);
  assert.strictEqual(hua.tai, 3);
});

t('海底撈月本身即自摸,單獨不報矛盾', function () {
  var r = parse('海底撈月', table);
  assert.strictEqual(r.warnings.some(function (w) { return w.level === 'conflict'; }), false);
});

t('槓上開花單獨不報矛盾', function () {
  var r = parse('槓上開花', table);
  assert.strictEqual(r.warnings.some(function (w) { return w.level === 'conflict'; }), false);
});

t('矛盾偵測:自摸 + 全求人(胡別人)→ 警告', function () {
  var r = parse('自摸 全求人', table);
  assert.strictEqual(r.warnings.some(function (w) { return w.level === 'conflict'; }), true);
});

t('矛盾偵測:海底撈月(自摸) + 河底撈魚(胡別人)→ 警告', function () {
  var r = parse('海底撈月 河底撈魚', table);
  assert.strictEqual(r.warnings.some(function (w) { return w.level === 'conflict'; }), true);
});

t('未收錄殘字回報:門清 加上亂詞', function () {
  var r = parse('門清 蛤蜊', table);
  assert.deepStrictEqual(ids(r), ['menqing']);
  assert.strictEqual(r.unmatched, '蛤蜊');
});

t('大牌:大三元 排除 小三元', function () {
  var r = parse('大三元 小三元', table);
  assert.deepStrictEqual(ids(r), ['dasanyuan']);
  assert.strictEqual(r.total, 8 + 1);
});

// ---- Codex review 修正回歸 ----
t('F1 數量詞前導不留殘字:十張花', function () {
  var r = parse('十張花', table);
  var hua = r.hits.find(function (h) { return h.id === 'hua'; });
  assert.strictEqual(hua.units, 10);
  assert.strictEqual(r.unmatched, ''); // 「十張」不可再變殘字
});

t('F2 不跨邊界偷數字:大四花', function () {
  var r = parse('大四花', table);
  var hua = r.hits.find(function (h) { return h.id === 'hua'; });
  assert.strictEqual(hua.units, 1); // 「四」屬大四喜,不可被讀成 4 張花
  var sixi = r.hits.find(function (h) { return h.id === 'dasixi'; });
  assert.ok(sixi);
});

t('F2 裸數字仍可讀:三花 = 3台', function () {
  var r = parse('三花', table);
  var hua = r.hits.find(function (h) { return h.id === 'hua'; });
  assert.strictEqual(hua.units, 3);
});

t('F3 無花與花牌互斥(並存代表誤聽,警告)', function () {
  var r = parse('無花 正花', table);
  assert.strictEqual(r.warnings.some(function (w) { return w.level === 'exclude'; }), true);
  // 不可兩者都計台
  assert.strictEqual(r.hits.filter(function (h) { return h.id === 'wuhua' || h.id === 'zhenghua'; }).length, 1);
});

t('F3 八仙過海不再疊逐張花', function () {
  var r = parse('八仙過海 花花花花花花花花', table);
  assert.strictEqual(r.hits.some(function (h) { return h.id === 'hua'; }), false);
  assert.strictEqual(r.total, 8 + 1); // 八仙8 + 底1
});

t('F4 搶槓胡 + 自摸 → 矛盾警告', function () {
  var r = parse('搶槓胡自摸', table);
  assert.strictEqual(r.warnings.some(function (w) { return w.level === 'conflict'; }), true);
});

t('F5 人胡 + 自摸 → 矛盾警告', function () {
  var r = parse('人胡自摸', table);
  assert.strictEqual(r.warnings.some(function (w) { return w.level === 'conflict'; }), true);
});

t('F5 地胡 + 全求人(胡別人)→ 矛盾警告', function () {
  var r = parse('地胡全求人', table);
  assert.strictEqual(r.warnings.some(function (w) { return w.level === 'conflict'; }), true);
});

t('F8 超長輸入截斷 + 警告', function () {
  var r = parse('門清' + '亂'.repeat(500), table);
  assert.strictEqual(r.warnings.some(function (w) { return w.level === 'too_long'; }), true);
  assert.strictEqual(r.hits.some(function (h) { return h.id === 'menqing'; }), true);
});

console.log('\n結果:' + pass + ' 通過 / ' + fail + ' 失敗');
process.exit(fail ? 1 : 0);
