const test = require('node:test');
const assert = require('node:assert/strict');

const {
  AXES, computeLuck, computeYaku, revenueMultiplier, probWeight, resistFactor, clamp
} = require('../model/shrine/ShrineLuck');
const ShrineLuckService = require('../model/shrine/ShrineLuckService');
const { DEFAULT_SHRINE_CONFIG } = require('../model/shrine/defaults');

// 固定 now = 2026-07-01（台北年 2026）。厄年以此年判定。
const NOW = Math.floor(Date.UTC(2026, 6, 1) / 1000);
const day = (n) => n * 86400;

test('1) fortune=null → 六軸皆 50、sougou=50', () => {
  const r = computeLuck({ fortune: null, omamori: [], nowEpoch: NOW });
  for (const a of AXES) assert.equal(r.axes[a], 50);
  assert.equal(r.sougou, 50);
});

test('2) 有效 buff 加成、過期 buff 忽略、未知 axis 跳過', () => {
  const fortune = {
    buffs: [
      { axis: 'zaiun', delta: 8, expireAt: NOW + day(1) },   // 有效
      { axis: 'shengun', delta: 8, expireAt: NOW - day(1) },  // 過期→忽略
      { axis: 'nonsense', delta: 99, expireAt: NOW + day(1) } // 未知軸→跳過
    ]
  };
  const r = computeLuck({ fortune, omamori: [], nowEpoch: NOW });
  assert.equal(r.axes.zaiun, 58);
  assert.equal(r.axes.shengun, 50);
  assert.equal(r.breakdown.buffDelta.zaiun, 8);
});

test('3) buff 疊加超過 100 → 夾到 100', () => {
  const fortune = { base: { ...base(), zaiun: 98 }, buffs: [{ axis: 'zaiun', delta: 10, expireAt: NOW + day(1) }] };
  const r = computeLuck({ fortune, omamori: [], nowEpoch: NOW });
  assert.equal(r.axes.zaiun, 100);
});

test('4) 穢れ:過期未回收御守按天扣 body;已回收/未到期不扣;多張累加', () => {
  const omamori = [
    { axis: 'zaiun', expireAt: NOW - day(3), recycled: false }, // 過期3天 → -3
    { axis: 'body', expireAt: NOW - day(2), recycled: true },   // 已回收 → 不扣
    { axis: 'body', expireAt: NOW + day(10), recycled: false }  // 未到期 → 不扣
  ];
  const r = computeLuck({ fortune: null, omamori, nowEpoch: NOW }); // decay=1
  assert.equal(r.breakdown.kegarePenalty, 3);
  assert.equal(r.axes.body, 47);

  const r2 = computeLuck({
    fortune: null,
    omamori: [
      { expireAt: NOW - day(3), recycled: false },
      { expireAt: NOW - day(5), recycled: false }
    ],
    nowEpoch: NOW
  });
  assert.equal(r2.breakdown.kegarePenalty, 8);
  assert.equal(r2.axes.body, 42);
});

test('5) 厄年:男42大厄本厄扣-10;女33大厄扣-10;缺 gender/birthday 不扣', () => {
  // 男 42(大厄本厄) birthYear=2026-42+1=1985
  const male = computeLuck({ fortune: null, omamori: [], nowEpoch: NOW, birthday: '19850101', gender: 'male' });
  assert.equal(male.breakdown.yakuLevel, 'honyaku');
  assert.equal(male.breakdown.yakuPenalty, -10); // honyaku(-6)+taiyakuExtra(-4)
  assert.equal(male.axes.body, 40);

  // 女 33(大厄本厄) birthYear=1994
  const female = computeLuck({ fortune: null, omamori: [], nowEpoch: NOW, birthday: '19940101', gender: 'female' });
  assert.equal(female.breakdown.yakuPenalty, -10);
  assert.equal(female.axes.body, 40);

  // 缺 gender → 不扣
  const noGender = computeLuck({ fortune: null, omamori: [], nowEpoch: NOW, birthday: '19850101', gender: null });
  assert.equal(noGender.breakdown.yakuLevel, 'none');
  assert.equal(noGender.axes.body, 50);

  // 缺 birthday → 不扣
  const noBd = computeLuck({ fortune: null, omamori: [], nowEpoch: NOW, birthday: null, gender: 'male' });
  assert.equal(noBd.axes.body, 50);
});

test('6) clamp:大量負面不低於 0、大量正面不高於 100', () => {
  const lo = computeLuck({ fortune: { buffs: [{ axis: 'zaiun', delta: -999, expireAt: NOW + day(1) }] }, omamori: [], nowEpoch: NOW });
  assert.equal(lo.axes.zaiun, 0);
  const hi = computeLuck({ fortune: { buffs: [{ axis: 'zaiun', delta: 999, expireAt: NOW + day(1) }] }, omamori: [], nowEpoch: NOW });
  assert.equal(hi.axes.zaiun, 100);
});

test('7) 公式 helper:revenue/prob/resist 邊界', () => {
  assert.equal(revenueMultiplier(0), 0.9);
  assert.equal(revenueMultiplier(50), 1.0);
  assert.equal(revenueMultiplier(100), 1.1);
  assert.equal(probWeight(100, 100), 120); // 100*(1+50/250)=120
  assert.equal(probWeight(100, 0), 80);
  assert.ok(probWeight(100, -9999) >= 0); // 不為負
  assert.equal(resistFactor(100), 0.75);   // 1-50/200
  assert.equal(resistFactor(50), 1.0);
});

test('8) computeYaku:男42=大厄本厄、前/後厄、女33大厄、非厄年', () => {
  assert.deepEqual(computeYaku(42, 'male'), { level: 'honyaku', isTaiyaku: true });
  assert.deepEqual(computeYaku(41, 'male'), { level: 'maeyaku', isTaiyaku: false });
  assert.deepEqual(computeYaku(43, 'male'), { level: 'atoyaku', isTaiyaku: false });
  assert.deepEqual(computeYaku(25, 'male'), { level: 'honyaku', isTaiyaku: false });
  assert.deepEqual(computeYaku(33, 'female'), { level: 'honyaku', isTaiyaku: true });
  assert.deepEqual(computeYaku(30, 'male'), { level: 'none', isTaiyaku: false });
  assert.deepEqual(computeYaku(42, null), { level: 'none', isTaiyaku: false });
});

test('9) getLuck fail-safe:DAO 拋錯→50;未知 axis→50;正常 stub→正確值', async () => {
  // 拋錯的 DAO
  const throwing = new ShrineLuckService({
    fortuneDAO: { getByPlayer: async () => { throw new Error('boom'); } },
    omamoriDAO: { listByPlayer: async () => [] },
    configDAO: { getMain: async () => DEFAULT_SHRINE_CONFIG },
    viewerDAO: { getByDcID: async () => null }
  });
  assert.equal(await throwing.getLuck('u1', 'zaiun', 1000, NOW), 50);

  // 未知 axis
  assert.equal(await throwing.getLuck('u1', 'bogus', 1000, NOW), 50);

  // 正常 stub:zaiun base 70 + 有效 buff +5 = 75
  const good = new ShrineLuckService({
    fortuneDAO: { getByPlayer: async () => ({ base: { ...base(), zaiun: 70 }, buffs: [{ axis: 'zaiun', delta: 5, expireAt: NOW + day(1) }] }) },
    omamoriDAO: { listByPlayer: async () => [] },
    configDAO: { getMain: async () => DEFAULT_SHRINE_CONFIG },
    viewerDAO: { getByDcID: async () => null }
  });
  assert.equal(await good.getLuck('u2', 'zaiun', 2000, NOW), 75);
});

function base () {
  const o = {};
  for (const a of AXES) o[a] = 50;
  return o;
}
