// 甜甜神社 S2-5 — 生日祝賀「厄年鉤子」_yakuHint 單測。
// 用 Object.create 繞過 HappyBirthday 建構子 side-effect,只測 _yakuHint 純邏輯(注入 ShrineFortuneDAO stub)。
const test = require('node:test');
const assert = require('node:assert');
const HappyBirthday = require('../model/HappyBirthday.js');

const NOW = Math.floor(Date.UTC(2026, 6, 1) / 1000); // 台北年 2026
const BD_M42 = '1985-01-01'; // 男 kazoe 42 → 大厄(本厄)
const BD_M41 = '1986-01-01'; // 男 kazoe 41 → 前厄
const BD_M30 = '1997-01-01'; // 男 kazoe 30 → 非厄

// 造一個只有 _yakuHint + 注入 ShrineFortuneDAO 的最小實例
function make (fortune, { throws = false } = {}) {
  const hb = Object.create(HappyBirthday.prototype);
  hb.ShrineFortuneDAO = {
    async getByPlayer () { if (throws) throw new Error('ddb boom'); return fortune; }
  };
  return hb;
}

test('1) 男42大厄 + gender male + 未除厄 → 提示含「大厄」', async () => {
  const hb = make({ gender: 'male' });
  const hint = await hb._yakuHint('123', BD_M42, NOW);
  assert.ok(hint && hint.includes('大厄'), hint);
  assert.ok(hint.includes('御祈禱'));
});

test('2) 男41前厄 → 提示含「前厄」', async () => {
  const hb = make({ gender: 'male' });
  const hint = await hb._yakuHint('123', BD_M41, NOW);
  assert.ok(hint && hint.includes('前厄'), hint);
});

test('3) 缺 gender → null(保守不附)', async () => {
  assert.strictEqual(await make({})._yakuHint('123', BD_M42, NOW), null);          // fortune 無 gender
  assert.strictEqual(await make(null)._yakuHint('123', BD_M42, NOW), null);         // fortune 為 null
  assert.strictEqual(await make({ gender: 'x' })._yakuHint('123', BD_M42, NOW), null); // 非法 gender
});

test('4) 非厄年(男30)→ null', async () => {
  assert.strictEqual(await make({ gender: 'male' })._yakuHint('123', BD_M30, NOW), null);
});

test('5) 今年已除厄(yakuHaraiYear===本年)→ null(不嘮叨)', async () => {
  const hb = make({ gender: 'male', yakuHaraiYear: 2026 });
  assert.strictEqual(await hb._yakuHint('123', BD_M42, NOW), null);
});

test('5b) 去年除厄(yakuHaraiYear=2025)→ 仍提示(除厄只當年有效)', async () => {
  const hb = make({ gender: 'male', yakuHaraiYear: 2025 });
  const hint = await hb._yakuHint('123', BD_M42, NOW);
  assert.ok(hint && hint.includes('大厄'), hint);
});

test('6) 生日非 8 碼 → null', async () => {
  const hb = make({ gender: 'male' });
  assert.strictEqual(await hb._yakuHint('123', '1985-1-1', NOW), null);
  assert.strictEqual(await hb._yakuHint('123', null, NOW), null);
});

test('7) fortune 讀取拋錯 → null(fail-safe,絕不影響生日祝賀)', async () => {
  const hb = make({ gender: 'male' }, { throws: true });
  assert.strictEqual(await hb._yakuHint('123', BD_M42, NOW), null);
});
