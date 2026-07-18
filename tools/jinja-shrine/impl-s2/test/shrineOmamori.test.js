// 甜甜神社 S2-2 — 請御守 service + 御守 DAO getBySk 單測(HANDOFF-S2-2 §6 測試矩陣)。
// 全部注入 stub、不打真 AWS。
const test = require('node:test');
const assert = require('node:assert');

const ShrineOmamoriService = require('../model/shrine/ShrineOmamoriService.js');
const ShrineOmamoriDAO = require('../DAO/DDB/ShrineOmamoriDAO.js');
const { DEFAULT_SHRINE_CONFIG } = require('../model/shrine/defaults.js');

const NOW = 1721000000;

// ── stub 工廠:可記錄呼叫的 fake DAO ──
function makeStubs ({ balance = 10000, config = DEFAULT_SHRINE_CONFIG, putThrows = false } = {}) {
  const calls = { givePoint: [], put: [], selectOne: [] };
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
  const omamoriDAO = {
    async put (item) {
      if (putThrows) throw new Error('ddb boom');
      calls.put.push(item);
      return item;
    }
  };
  const configDAO = { async getMain () { return config; } };
  return { calls, deps: { viewerDetailDAO, omamoriDAO, configDAO } };
}

// 1. 正常請御守:扣 fee 正確、item axis/boost/expireAt/recycled 對上 config、回 ok:true
test('grant: 正常請御守(扣款+item 欄位對上 config)', async () => {
  const { calls, deps } = makeStubs({ balance: 1000 });
  const svc = new ShrineOmamoriService(deps);
  const r = await svc.grant('123', 'kinunmori', NOW);

  assert.strictEqual(r.ok, true);
  const def = DEFAULT_SHRINE_CONFIG.omamoriTypes.kinunmori;
  // 扣款:一次、-fee、column='point'、reason 含 type
  assert.strictEqual(calls.givePoint.length, 1);
  assert.deepStrictEqual(calls.givePoint[0].ids, ['123']);
  assert.strictEqual(calls.givePoint[0].amount, -def.fee);
  assert.strictEqual(calls.givePoint[0].column, 'point');
  assert.strictEqual(calls.givePoint[0].reason, '請御守:kinunmori');
  // item schema
  assert.strictEqual(calls.put.length, 1);
  const item = calls.put[0];
  assert.strictEqual(item.discordId, '123');
  assert.match(item.sk, /^omamori#[0-9a-f-]{36}$/);
  assert.strictEqual(item.type, 'kinunmori');
  assert.strictEqual(item.axis, def.axis);
  assert.strictEqual(item.boost, def.boost);
  assert.strictEqual(item.acquiredAt, NOW);
  assert.strictEqual(item.expireAt, NOW + DEFAULT_SHRINE_CONFIG.omamoriTtlDays * 86400);
  assert.strictEqual(item.recycled, false);
  assert.strictEqual(item.source, 'juyosho');
  assert.deepStrictEqual(r.omamori, item);
});

// 2. 餘額不足:不扣不寫
test('grant: 餘額不足 → insufficient,givePoint/put 都沒被呼叫', async () => {
  const { calls, deps } = makeStubs({ balance: 100 }); // fee=300
  const svc = new ShrineOmamoriService(deps);
  const r = await svc.grant('123', 'kinunmori', NOW);

  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.reason, 'insufficient');
  assert.strictEqual(r.need, 300);
  assert.strictEqual(r.have, 100);
  assert.strictEqual(calls.givePoint.length, 0);
  assert.strictEqual(calls.put.length, 0);
});

// 3. 未知 type:不扣不寫
test('grant: 未知 type → unknown_type,不扣不寫', async () => {
  const { calls, deps } = makeStubs({ balance: 10000 });
  const svc = new ShrineOmamoriService(deps);
  const r = await svc.grant('123', 'no_such_mori', NOW);

  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.reason, 'unknown_type');
  assert.strictEqual(calls.givePoint.length, 0);
  assert.strictEqual(calls.put.length, 0);
});

// 4. put 失敗退款:givePoint 兩次(-fee 後 +fee)、回 write_failed
test('grant: put 拋錯 → 退款(-fee 後 +fee)、write_failed', async () => {
  const { calls, deps } = makeStubs({ balance: 1000, putThrows: true });
  const svc = new ShrineOmamoriService(deps);
  const r = await svc.grant('123', 'shoumori', NOW);

  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.reason, 'write_failed');
  assert.strictEqual(calls.givePoint.length, 2);
  assert.strictEqual(calls.givePoint[0].amount, -300);
  assert.strictEqual(calls.givePoint[0].reason, '請御守:shoumori');
  assert.strictEqual(calls.givePoint[1].amount, 300);
  assert.strictEqual(calls.givePoint[1].reason, '請御守退款:shoumori');
  assert.strictEqual(calls.givePoint[1].column, 'point');
});

// 5. config 缺:getMain 回 null → deep-merge DEFAULT 後 6 種御守都能請(不炸)
test('grant: configDAO.getMain 回 null → fallback DEFAULT 仍能請御守', async () => {
  const { calls, deps } = makeStubs({ balance: 100000, config: null });
  const svc = new ShrineOmamoriService(deps);
  for (const type of Object.keys(DEFAULT_SHRINE_CONFIG.omamoriTypes)) {
    const r = await svc.grant('456', type, NOW);
    assert.strictEqual(r.ok, true, `type=${type} 應成功`);
    assert.strictEqual(r.omamori.axis, DEFAULT_SHRINE_CONFIG.omamoriTypes[type].axis);
    assert.strictEqual(r.omamori.boost, DEFAULT_SHRINE_CONFIG.omamoriTypes[type].boost);
  }
  assert.strictEqual(calls.put.length, 6);
});

// 6. sk 唯一:連請兩次 → 兩個不同 sk
test('grant: 連請兩次 → sk 不同', async () => {
  const { calls, deps } = makeStubs({ balance: 10000 });
  const svc = new ShrineOmamoriService(deps);
  const r1 = await svc.grant('123', 'enmusubi', NOW);
  const r2 = await svc.grant('123', 'enmusubi', NOW);
  assert.strictEqual(r1.ok, true);
  assert.strictEqual(r2.ok, true);
  assert.notStrictEqual(r1.omamori.sk, r2.omamori.sk);
  assert.strictEqual(calls.put.length, 2);
});

// 7. getBySk:stub doc client 驗 correct-key {discordId, sk};存在回 item、不存在回 null
test('DAO.getBySk: correct-key GetItem,存在回 item、不存在回 null', async () => {
  const dao = new ShrineOmamoriDAO();
  const stored = { discordId: '123', sk: 'omamori#abc', type: 'kinunmori' };
  const sentKeys = [];
  dao.ddb = {
    async send (cmd) {
      const { TableName, Key } = cmd.input;
      sentKeys.push({ TableName, Key });
      assert.strictEqual(TableName, 'sweetbot-shrine-omamori');
      if (Key.discordId === stored.discordId && Key.sk === stored.sk) return { Item: stored };
      return {};
    }
  };
  const hit = await dao.getBySk('123', 'omamori#abc'); // 傳 number-ish 前已 String()
  assert.deepStrictEqual(hit, stored);
  const miss = await dao.getBySk('123', 'omamori#nope');
  assert.strictEqual(miss, null);
  // Key 正確:{discordId:String, sk} 而非 {id}
  assert.deepStrictEqual(sentKeys[0].Key, { discordId: '123', sk: 'omamori#abc' });
  assert.strictEqual(Object.prototype.hasOwnProperty.call(sentKeys[0].Key, 'id'), false);
});
