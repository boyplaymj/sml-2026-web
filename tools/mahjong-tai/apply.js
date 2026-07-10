#!/usr/bin/env node
/**
 * 糾正回灌 CLI(飛輪的操作端)
 *
 *   node apply.js corrections.jsonl              # 只分析、印出建議(dry-run)
 *   node apply.js corrections.jsonl --write      # 把 add_confusion 建議寫回 fan_table.json
 *   node apply.js corrections.jsonl --min 3      # 調整升級門檻(預設 2)
 *
 * corrections.jsonl:每行一筆 JSON,欄位同 feedback.recordCorrection 的輸入
 *   {"text":"征化","parsed":[],"corrected":["zhenghua"],"unmatched":"征化","ts":1}
 *
 * 刻意設計成:add_confusion 才自動寫入;review_mapping(判錯家)一律只印、不動,交人工。
 */
var fs = require('fs');
var path = require('path');
var fb = require('./feedback');

var args = process.argv.slice(2);
var logPath = args.find(function (a) { return !a.startsWith('--'); });
var doWrite = args.includes('--write');
var minIdx = args.indexOf('--min');
var minCount = minIdx !== -1 ? parseInt(args[minIdx + 1], 10) : 2;

if (!logPath) {
  console.error('用法:node apply.js <corrections.jsonl> [--write] [--min N]');
  process.exit(2);
}

var tablePath = path.join(__dirname, 'fan_table.json');
var table = JSON.parse(fs.readFileSync(tablePath, 'utf8'));

var records = fs.readFileSync(logPath, 'utf8')
  .split('\n')
  .filter(function (l) { return l.trim(); })
  .map(function (l) { return fb.recordCorrection(JSON.parse(l)); });

var suggestions = fb.extractSuggestions(records, table, { minCount: minCount });

console.log('讀入 ' + records.length + ' 筆糾正,門檻 ' + minCount + ' 次\n');
if (!suggestions.length) { console.log('沒有達門檻的建議。'); process.exit(0); }

var names = {};
table.fans.forEach(function (f) { names[f.id] = f.name; });
var applied = 0;

suggestions.forEach(function (s) {
  if (s.type === 'add_confusion') {
    var line = '  [新誤聽詞] 「' + s.term + '」 → ' + names[s.fanId] + '  (×' + s.count + ')';
    if (doWrite && fb.applySuggestion(table, s)) { applied++; line += '  ✓已回灌'; }
    console.log(line);
  } else if (s.type === 'review_mapping') {
    console.log('  [需人工複核] ' + names[s.fromFanId] + ' 常被改成 ' + names[s.toFanId] + '  (×' + s.count + ')  ← 檢查共用糾錯詞是否指錯家');
  }
});

if (doWrite && applied) {
  fs.writeFileSync(tablePath, JSON.stringify(table, null, 2) + '\n');
  console.log('\n已寫回 ' + applied + ' 筆到 fan_table.json');
} else if (doWrite) {
  console.log('\n沒有可自動回灌的項目(review_mapping 不自動套用)。');
} else {
  console.log('\n(dry-run:加 --write 才會實際寫入)');
}
