// 甜甜神社 S2-4 — 御祈禱受付所 厄年除厄 service + DAO setYakuHarai 單測(HANDOFF-S2-4 §5 測試矩陣)。
// 全部注入 stub、不打真 AWS。
const test = require('node:test');
const assert = require('node:assert');

const ShrineHaraiService = require('../model/shrine/ShrineHaraiService.js');
const ShrineFortuneDAO = require('../DAO/DDB/ShrineFortuneDAO.js');
const { DEFAULT_SHRINE_CONFIG } = require('../model/shrine/defaults.js');

// 厄年 fixture 對齊 shrineLuck.test.js:台北年 2026
const NOW = Math.floor(Date.UTC(2026, 6, 1) / 1000);
const YEAR = 2026;
const BD_M42 = '1985-01-01'; // 男 42 大厄(kazoe 42, honyaku)
const BD_M30 = '1997-01-01'; // 男 30 非厄(kazoe 30, none)
const FEE = DEFAULT_SHRINE_CONFIG.fees.gokitou; // 800

// ── stub 工廠:可記錄呼叫的 fake DAO ──
function makeStubs ({
  birthday = BD_M42,
  balance = 10000,
  fortune = null,
  config = DEFAULT_SHRINE_CONFIG,
  setYakuHaraiThrows = false
} = {}) {
  const calls = { givePoint: [], setYakuHarai: [], setGender: [], selectOne: [], getByDcID: [], getByPlayer: [] };
  const viewerDAO = {
    async getByDcID (dcID) {
      calls.getByDcID.push(dcID);
      return birthday == null ? null : { dcID, birthday };
    }
  };
  const viewerDetailDAO = {
    async selectOne (where) {
      calls.selectOne.push(where);
      return balance == null ? null : { id: where.discordId, point: balance };
    },
    async givePoint (ids, amount, column, reason) {
      calls.givePoint.push({ ids, amount, column, reason });
      return true;
    }
  };
  const fortuneDAO = {
    async getByPlayer (discordId) {
      calls.getByPlayer.push(discordId);
      return fortune;
    },
    async setYakuHarai (discordId, year, gender) {
      if (setYakuHaraiThrows) throw new Error('ddb boom');
      calls.setYakuHarai.push({ discordId, year, gender });
      return true;
    },
    async setGender (discordId, gender) {
      calls.setGender.push({ discordId, gender });
      return true;
    }
  };
  const configDAO = { async getMain () { return config; } };
  return { calls, deps: { fortuneDAO, viewerDAO, viewerDetailDAO, configDAO } };
}

// 1. 正常除厄(男42、足額、未除過)
test('harai: 正常除厄(男42)→ 扣 gokitou、setYakuHarai(2026,male)、回 ok', async () => {
  const { calls, deps } = makeStubs();
  const svc = new ShrineHaraiService(deps);
  const r = await svc.harai('123', 'male', NOW);

  assert.deepStrictEqual(r, { ok: true, yakuLevel: 'honyaku', year: YEAR, fee: FEE });
  assert.strictEqual(calls.givePoint.length, 1);
  assert.deepStrictEqual(calls.givePoint[0].ids, ['123']);
  assert.strictEqual(calls.givePoint[0].amount, -FEE);
  assert.strictEqual(calls.givePoint[0].column, 'point');
  assert.strictEqual(calls.givePoint[0].reason, '御祈禱除厄');
  assert.strictEqual(calls.setYakuHarai.length, 1);
  assert.deepStrictEqual(calls.setYakuHarai[0], { discordId: '123', year: YEAR, gender: 'male' });
  // gender 持久化(fortune 原無 gender)
  assert.strictEqual(calls.setGender.length, 1);
  assert.deepStrictEqual(calls.setGender[0], { discordId: '123', gender: 'male' });
});

// 2. gender 缺/非法 → gender_required,不扣不寫
test('harai: gender 缺/非法 → gender_required,不扣不寫', async () => {
  const { calls, deps } = makeStubs();
  const svc = new ShrineHaraiService(deps);
  for (const g of [undefined, null, '', 'x', 'MALE']) {
    const r = await svc.harai('123', g, NOW);
    assert.strictEqual(r.ok, false);
    assert.strictEqual(r.reason, 'gender_required');
  }
  assert.strictEqual(calls.givePoint.length, 0);
  assert.strictEqual(calls.setYakuHarai.length, 0);
});

// 3. birthday 缺/非 8 碼 → birthday_required,不扣不寫
test('harai: 生日缺/非 8 碼 → birthday_required,不扣不寫', async () => {
  for (const bd of [null, '1985-1-1', 'abcd-ef-gh']) {
    const { calls, deps } = makeStubs({ birthday: bd });
    const svc = new ShrineHaraiService(deps);
    const r = await svc.harai('123', 'male', NOW);
    assert.strictEqual(r.ok, false);
    assert.strictEqual(r.reason, 'birthday_required');
    assert.strictEqual(calls.givePoint.length, 0);
    assert.strictEqual(calls.setYakuHarai.length, 0);
  }
});

// 4. 非厄年(男30)→ not_in_yakudoshi,不扣不寫
test('harai: 非厄年(男30)→ not_in_yakudoshi,不扣不寫', async () => {
  const { calls, deps } = makeStubs({ birthday: BD_M30 });
  const svc = new ShrineHaraiService(deps);
  const r = await svc.harai('123', 'male', NOW);
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.reason, 'not_in_yakudoshi');
  assert.strictEqual(calls.givePoint.length, 0);
  assert.strictEqual(calls.setYakuHarai.length, 0);
  assert.strictEqual(calls.setGender.length, 1); // 非厄年也持久化 gender(未收費)
});

// 5. 同年已除厄 + rechargeable=false → already_haraied,不扣不寫
test('harai: 同年已除厄 + rechargeable=false → already_haraied,不扣不寫', async () => {
  const { calls, deps } = makeStubs({ fortune: { discordId: '123', yakuHaraiYear: YEAR } });
  const svc = new ShrineHaraiService(deps);
  const r = await svc.harai('123', 'male', NOW);
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.reason, 'already_haraied');
  assert.strictEqual(calls.givePoint.length, 0);
  assert.strictEqual(calls.setYakuHarai.length, 0);
  assert.strictEqual(calls.setGender.length, 1); // 同年已除也持久化 gender(未收費)
});

// 6. 同年已除厄 + rechargeable=true → 允許再除(再扣、再 setYakuHarai)
test('harai: 同年已除厄 + rechargeable=true → 允許再除', async () => {
  const cfg = { ...DEFAULT_SHRINE_CONFIG, yakuHaraiRechargeable: true };
  const { calls, deps } = makeStubs({ fortune: { discordId: '123', yakuHaraiYear: YEAR }, config: cfg });
  const svc = new ShrineHaraiService(deps);
  const r = await svc.harai('123', 'male', NOW);
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.year, YEAR);
  assert.strictEqual(calls.givePoint.length, 1);
  assert.strictEqual(calls.givePoint[0].amount, -FEE);
  assert.strictEqual(calls.setYakuHarai.length, 1);
});

// 7. 餘額不足 → insufficient,不扣不寫
test('harai: 餘額不足 → insufficient,不扣不寫', async () => {
  const { calls, deps } = makeStubs({ balance: FEE - 1 });
  const svc = new ShrineHaraiService(deps);
  const r = await svc.harai('123', 'male', NOW);
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.reason, 'insufficient');
  assert.strictEqual(r.need, FEE);
  assert.strictEqual(r.have, FEE - 1);
  assert.strictEqual(calls.givePoint.length, 0);
  assert.strictEqual(calls.setYakuHarai.length, 0);
  assert.strictEqual(calls.setGender.length, 1); // ★Codex Blocking:餘額不足也持久化 gender(未收費)
});

// 8. setYakuHarai 失敗退款 → givePoint 兩次(-fee 後 +fee)、write_failed
test('harai: setYakuHarai 拋錯 → 退款(-fee 後 +fee)、write_failed', async () => {
  const { calls, deps } = makeStubs({ setYakuHaraiThrows: true });
  const svc = new ShrineHaraiService(deps);
  const r = await svc.harai('123', 'male', NOW);
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.reason, 'write_failed');
  assert.strictEqual(calls.givePoint.length, 2);
  assert.strictEqual(calls.givePoint[0].amount, -FEE);
  assert.strictEqual(calls.givePoint[0].reason, '御祈禱除厄');
  assert.strictEqual(calls.givePoint[1].amount, FEE);
  assert.strictEqual(calls.givePoint[1].reason, '御祈禱除厄退款');
  assert.strictEqual(calls.givePoint[1].column, 'point');
});

// 9. config 缺(getMain null)→ fee fallback DEFAULT 800、rechargeable fallback false
test('harai: config 缺 → fee fallback 800、rechargeable fallback false', async () => {
  // 9a. fee fallback:正常除厄扣 DEFAULT 800
  const a = makeStubs({ config: null });
  const r1 = await new ShrineHaraiService(a.deps).harai('123', 'male', NOW);
  assert.strictEqual(r1.ok, true);
  assert.strictEqual(r1.fee, 800);
  assert.strictEqual(a.calls.givePoint[0].amount, -800);
  // 9b. rechargeable fallback false:同年已除 → already_haraied
  const b = makeStubs({ config: null, fortune: { yakuHaraiYear: YEAR } });
  const r2 = await new ShrineHaraiService(b.deps).harai('123', 'male', NOW);
  assert.strictEqual(r2.ok, false);
  assert.strictEqual(r2.reason, 'already_haraied');
  assert.strictEqual(b.calls.givePoint.length, 0);
});

// 10. DAO.setYakuHarai:stub ddb.send 驗 UpdateExpression / #g alias / Key
test('DAO.setYakuHarai: 帶 gender 寫 #g alias;不帶只寫年;Key={discordId}', async () => {
  const dao = new ShrineFortuneDAO();
  const sent = [];
  dao.ddb = { async send (cmd) { sent.push(cmd.input); return {}; } };

  // 帶 gender
  await dao.setYakuHarai(123, 2026, 'male');
  assert.strictEqual(sent[0].TableName, 'sweetbot-shrine-fortune');
  assert.deepStrictEqual(sent[0].Key, { discordId: '123' }); // String()、非 id
  assert.strictEqual(Object.prototype.hasOwnProperty.call(sent[0].Key, 'id'), false);
  assert.strictEqual(sent[0].UpdateExpression, 'SET yakuHaraiYear = :y, #g = :g');
  assert.deepStrictEqual(sent[0].ExpressionAttributeNames, { '#g': 'gender' });
  assert.deepStrictEqual(sent[0].ExpressionAttributeValues, { ':y': 2026, ':g': 'male' });

  // 不帶 gender → 只 SET 年、無 ExpressionAttributeNames
  await dao.setYakuHarai('456', 2026);
  assert.deepStrictEqual(sent[1].Key, { discordId: '456' });
  assert.strictEqual(sent[1].UpdateExpression, 'SET yakuHaraiYear = :y');
  assert.strictEqual(sent[1].ExpressionAttributeNames, undefined);
  assert.deepStrictEqual(sent[1].ExpressionAttributeValues, { ':y': 2026 });

  // 非法 gender 字串 → 視同不帶
  await dao.setYakuHarai('789', 2026, 'attack-helicopter');
  assert.strictEqual(sent[2].UpdateExpression, 'SET yakuHaraiYear = :y');
});

// 11. DAO.setGender:SET #g = :g、#g→'gender'、Key={discordId}
test('DAO.setGender: SET #g = :g、Key={discordId}', async () => {
  const dao = new ShrineFortuneDAO();
  const sent = [];
  dao.ddb = { async send (cmd) { sent.push(cmd.input); return {}; } };
  await dao.setGender(123, 'female'); // number → String()
  assert.deepStrictEqual(sent[0].Key, { discordId: '123' });
  assert.strictEqual(Object.prototype.hasOwnProperty.call(sent[0].Key, 'id'), false);
  assert.strictEqual(sent[0].UpdateExpression, 'SET #g = :g');
  assert.deepStrictEqual(sent[0].ExpressionAttributeNames, { '#g': 'gender' });
  assert.deepStrictEqual(sent[0].ExpressionAttributeValues, { ':g': 'female' });
});

// 12. gender 已存且相同 → 不重寫(冪等,省無謂寫入)
test('harai: fortune.gender 已等於傳入 → 不再 setGender', async () => {
  const { calls, deps } = makeStubs({ fortune: { discordId: '123', gender: 'male' } });
  const svc = new ShrineHaraiService(deps);
  const r = await svc.harai('123', 'male', NOW); // 男42、已有 gender、未除過 → 正常除厄
  assert.strictEqual(r.ok, true);
  assert.strictEqual(calls.setGender.length, 0); // gender 未變 → 不寫
  assert.strictEqual(calls.setYakuHarai.length, 1);
});
