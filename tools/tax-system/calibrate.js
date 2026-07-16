#!/usr/bin/env node
/*
 * 報稅系統 P0 — 級距校準腳本（唯讀）
 * 掃 sweetbot-player-point-log（pointType=point，即牙齒），
 * 用 DESIGN.md §3 的稅務分類 taxonomy 聚合「近 365 天」每位玩家的各類淨所得，
 * 套 DESIGN.md §5 的台灣版級距試算稅負，輸出分布，供校準級距/免稅額。
 *
 * 用法：
 *   aws dynamodb scan --table-name sweetbot-player-point-log --region ap-southeast-1 \
 *     --output json > /tmp/ptlog.json
 *   node calibrate.js /tmp/ptlog.json
 */
const fs = require('fs');

const file = process.argv[2] || '/tmp/ptlog.json';
const raw = JSON.parse(fs.readFileSync(file, 'utf8'));
const items = raw.Items || [];

// 近 365 天窗（以現在往回推）
const now = new Date('2026-07-16T00:00:00Z').getTime();
const WINDOW_MS = 365 * 24 * 3600 * 1000;
const cutoff = now - WINDOW_MS;

// ── 稅務分類（DESIGN.md §3）：reason 子字串 → 類別 ──
// 順序有意義（BJM 要在 BJ 之前）。同一遊戲的「下注/開盤/退款」與「中獎」歸同類 → 淨額自動相抵。
const RULES = [
  // welfare（免稅福利）
  [/每日登入獎勵|每日獎勵|簽到/, 'welfare'],
  // nontax（非所得：系統校正/管理員空投/消費支出——不計入所得也不當虧損）
  [/負債加回|超過限額扣回|指令給予|兌換貨幣|指令升級|投稿|活動商店|投票選項|生日/, 'nontax'],
  // gift（贈與，淨額，分離課稅）
  [/紅包|壽星|祝福/, 'gift'],
  // salary（薪資）
  [/法官判決獎勵/, 'salary'],
  // contest（競技/博弈，淨額；含下注與中獎與該遊戲退款）
  [/賓果/, 'contest'],
  [/骰寶/, 'contest'],
  [/BJM/, 'contest'],
  [/BJ/, 'contest'],
  [/四連環/, 'contest'],
  [/猜數字|1A2B|達文西/, 'contest'],
  [/射龍門|隆巴|inbetween/i, 'contest'],
  [/推筒子|戳戳|pusher/i, 'contest'],
  [/猜拳/, 'contest'],
  [/過馬路/, 'contest'],
  [/試煉之門/, 'contest'],
  [/龍舟|屈原/, 'contest'],
  [/競猜/, 'contest'],
  [/精華/, 'contest'],
  [/PK/, 'contest'],
  [/抽籤/, 'contest'],
  [/猜花/, 'contest'],
];
function classify (reason) {
  const r = reason || '';
  for (const [re, cat] of RULES) if (re.test(r)) return cat;
  return 'other'; // 未命中 → 其他所得（併累進，比照 DESIGN.md 未分類先課再調）
}

// ── 聚合：per player per category 淨額（只算 pointType=point 牙齒）──
const players = new Map(); // discordId -> {contest,salary,other,gift,welfare,nontax}
const reasonAgg = new Map(); // reason -> {cat, sum, count}  （給後台逐項檢視參考）
let scanned = 0; let inWindow = 0;

for (const it of items) {
  scanned++;
  const pt = it.pointType && it.pointType.S;
  if (pt !== 'point') continue; // 只課牙齒
  const created = it.createdAt && it.createdAt.S;
  if (!created) continue;
  const t = Date.parse(created.replace(/Z-\d+$/, 'Z')); // 去尾綴序號 ...Z-0
  if (isNaN(t) || t < cutoff) continue;
  inWindow++;
  const id = it.discordId && it.discordId.S;
  const v = it.variation ? Number(it.variation.N) : 0;
  const reason = (it.reason && it.reason.S) || '(空)';
  const cat = classify(reason);

  if (!players.has(id)) players.set(id, { contest: 0, salary: 0, other: 0, gift: 0, welfare: 0, nontax: 0 });
  players.get(id)[cat] += v;

  const key = reason.trim() || '(空)';
  if (!reasonAgg.has(key)) reasonAgg.set(key, { cat, sum: 0, count: 0 });
  const ra = reasonAgg.get(key); ra.sum += v; ra.count++;
}

// ── 年化：資料窗實際天數 → ×係數推估「一整年」 ──
let tmin = Infinity;
for (const it of items) {
  const c = it.createdAt && it.createdAt.S; if (!c) continue;
  const t = Date.parse(c.replace(/Z-\d+$/, 'Z')); if (isNaN(t) || t < cutoff) continue;
  if (t < tmin) tmin = t;
}
const windowDays = Math.max(1, (now - tmin) / 86400000);
const ANN = 365 / windowDays; // 年化係數

// ── 逐玩家聚合（年化毛額）──
const rows = [];
for (const [id, c] of players) {
  const taxableGross = (Math.max(0, c.contest) + Math.max(0, c.salary) + Math.max(0, c.other)) * ANN;
  const giftNet = Math.max(0, c.gift) * ANN;
  rows.push({ id, taxableGross, giftNet });
}
const N = rows.length;

function pct (arr, p) {
  if (!arr.length) return 0;
  const s = [...arr].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(p / 100 * s.length))];
}
const grossArr = rows.map(r => r.taxableGross);

console.log('══════════ 報稅級距校準（pointType=point）══════════');
console.log(`掃描 ${scanned} 列｜窗內牙齒列 ${inWindow}｜有活動玩家 ${N}`);
console.log(`資料窗 ≈ ${windowDays.toFixed(1)} 天 → 年化係數 ×${ANN.toFixed(1)}`);
console.log('');
console.log('── 年化應稅所得毛額分布（未扣免稅額前，估算一整年）──');
for (const p of [50, 75, 90, 95, 99]) console.log(`  p${p}: ${Math.round(pct(grossArr, p)).toLocaleString()}🦷`);
console.log(`  max: ${Math.round(Math.max(...grossArr, 0)).toLocaleString()}🦷`);
console.log('');

// ── 級距縮放掃描：台灣表 ÷ scale，看被課到%與稅收 ──
const TW_EXEMPT = 97000, TW_STD = 131000;
const TW_BRACKETS = [[590000, 0.05, 0], [1330000, 0.12, 41300], [2660000, 0.20, 147700], [4980000, 0.30, 413700], [Infinity, 0.40, 911700]];
const GIFT_RATE = 0.02;
function simulate (scale) {
  const threshold = (TW_EXEMPT + TW_STD) / scale;
  const brackets = TW_BRACKETS.map(([cap, rate, q]) => [cap === Infinity ? Infinity : cap / scale, rate, q / scale]);
  const tax = (net) => { if (net <= 0) return 0; for (const [cap, rate, q] of brackets) if (net <= cap) return Math.round(net * rate - q); return 0; };
  let taxed = 0, revenue = 0, giftRev = 0;
  for (const r of rows) {
    const t = tax(Math.max(0, r.taxableGross - threshold));
    if (t > 0) taxed++;
    revenue += t; giftRev += Math.round(r.giftNet * GIFT_RATE);
  }
  return { scale, threshold, taxed, pctTaxed: taxed / N * 100, revenue, giftRev };
}
console.log('── 級距縮放掃描（台灣表 ÷ scale）──');
console.log('  scale｜課稅門檻🦷｜被課到綜所稅人數｜%｜年綜所稅收🦷｜年贈與稅🦷');
for (const s of [1, 2, 5, 10, 20]) {
  const r = simulate(s);
  console.log(`  ÷${s}｜${Math.round(r.threshold).toLocaleString()}｜${r.taxed}/${N}｜${r.pctTaxed.toFixed(1)}%｜${r.revenue.toLocaleString()}｜${r.giftRev.toLocaleString()}`);
}
console.log('');
console.log('── 年化稅負 TOP 12（以 ÷10 級距示意）──');
const sc = 10, thr = (TW_EXEMPT + TW_STD) / sc;
const brk = TW_BRACKETS.map(([cap, rate, q]) => [cap === Infinity ? Infinity : cap / sc, rate, q / sc]);
const taxfn = (net) => { if (net <= 0) return 0; for (const [cap, rate, q] of brk) if (net <= cap) return Math.round(net * rate - q); return 0; };
rows.forEach(r => { r.tax = taxfn(Math.max(0, r.taxableGross - thr)); r.giftTax = Math.round(r.giftNet * GIFT_RATE); r.total = r.tax + r.giftTax; });
rows.sort((a, b) => b.total - a.total);
for (const r of rows.slice(0, 12)) {
  console.log(`  ${r.id}｜年化毛額 ${Math.round(r.taxableGross).toLocaleString()}｜綜所稅 ${r.tax.toLocaleString()}｜贈與稅 ${r.giftTax.toLocaleString()}｜合計 ${r.total.toLocaleString()}🦷`);
}
console.log('');
console.log('── 各 reason 歸類 + 年度總額（後台逐項檢視預覽，TOP 25 by |sum|）──');
const raList = [...reasonAgg.entries()].sort((a, b) => Math.abs(b[1].sum) - Math.abs(a[1].sum));
for (const [reason, ra] of raList.slice(0, 25)) {
  console.log(`  [${ra.cat}] ${reason}｜淨 ${ra.sum.toLocaleString()}🦷｜${ra.count} 筆`);
}
