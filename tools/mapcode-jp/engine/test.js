const MC = require('./mapcode.engine.js');
let pass=0, fail=0;
function eq(name, got, want){ if(got===want){pass++;console.log('  ✓',name,'=',got);} else {fail++;console.log('  ✗',name,'got',got,'want',want);} }
function ok(name, cond, info){ if(cond){pass++;console.log('  ✓',name,info||'');} else {fail++;console.log('  ✗',name,info||'');} }

console.log('== 對官方 base 碼 (zone+block+unit) ==');
// 札幌時計台 官方 9 522 206*06 (worldnet-rentacar 公佈)
const sap = MC.generate(43.062637, 141.353857);
eq('札幌時計台 base', sap.base, '9 522 206');

console.log('== round-trip 自洽 (偏移應 < 半格 ~4m) ==');
for(const [n,la,lo] of [['東京駅',35.681236,139.767125],['大阪城',34.687315,135.526201],['函館五稜郭',41.7968,140.7570]]){
  const r=MC.generate(la,lo);
  ok(n+' 偏移<5m', r.ok && r.offsetM<5, r.ok?`${r.code} off=${r.offsetM.toFixed(1)}m`:'OOB');
}

console.log('== 出界處理 ==');
ok('太平洋中央=OOB', MC.generate(30.0,150.0).ok===false, '');

console.log('== splitCode ==');
const s=MC.splitCode('9 522 206*06'); eq('base',s.base,'9 522 206'); eq('hi',s.hi,'9 522 206*06');

console.log(`\n== ${pass} passed, ${fail} failed ==`);
process.exit(fail?1:0);
