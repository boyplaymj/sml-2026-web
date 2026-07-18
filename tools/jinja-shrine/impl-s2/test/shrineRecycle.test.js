// 甜甜神社 S2-3 — 古札納所回收 + 功德值 單測(HANDOFF-S2-3 §4 測試矩陣)。
// 全部注入 stub、不打真 AWS。
const test = require('node:test');
const assert = require('node:assert');

const ShrineOmamoriService = require('../model/shrine/ShrineOmamoriService.js');
const ShrineOmamoriDAO = require('../DAO/DDB/ShrineOmamoriDAO.js');
const ShrineFortuneDAO = require('../DAO/DDB/ShrineFortuneDAO.js');
const { DEFAULT_SHRINE_CONFIG } = require('../model/shrine/defaults.js');

// ── stub 工廠:可記錄呼叫的 fake DAO ──
// recycleResult: true=成功回收 / false=已回收或不存在 / 'throw'=拋非 Conditional 錯
function makeStubs ({ config = DEFAULT_SHRINE_CONFIG, recycleResult = true } = {}) {
  const calls = { recycle: [], addMerit: [] };
  const omamoriDAO = {
    async recycle (discordId, sk) {
      calls.recycle.push({ discordId, sk });
      if (recycleResult === 'throw') throw new Error('ddb boom');
      return recycleResult;
    }
  };
  const fortuneDAO = {
    async addMerit (discordId, n) {
      calls.addMerit.push({ discordId, n });
      return true;
    }
  };
  const configDAO = { async getMain () { return config; } };
  return { calls, deps: { omamoriDAO, fortuneDAO, configDAO } };
}

// 1. 正常回收:recycle 回 true → addMerit 一次、金額=meritOnRecycle、回 {ok:true, merit}
test('recycle: 正常回收 → addMerit 一次、金額=meritOnRecycle、ok:true', async () => {
  const cfg = { ...DEFAULT_SHRINE_CONFIG, meritOnRecycle: 77 };
  const { calls, deps } = makeStubs({ config: cfg, recycleResult: true });
  const svc = new ShrineOmamoriService(deps);
  const r = await svc.recycle('123', 'omamori#abc');

  assert.deepStrictEqual(r, { ok: true, merit: 77 });
  assert.strictEqual(calls.recycle.length, 1);
  assert.deepStrictEqual(calls.recycle[0], { discordId: '123', sk: 'omamori#abc' });
  assert.strictEqual(calls.addMerit.length, 1);
  assert.deepStrictEqual(calls.addMerit[0], { discordId: '123', n: 77 });
});

// 2. 重複回收(冪等):recycle 回 false → addMerit 未被呼叫、already_recycled_or_missing
test('recycle: 已回收(recycle 回 false)→ 不給功德、already_recycled_or_missing', async () => {
  const { calls, deps } = makeStubs({ recycleResult: false });
  const svc = new ShrineOmamoriService(deps);
  const r = await svc.recycle('123', 'omamori#abc');

  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.reason, 'already_recycled_or_missing');
  assert.strictEqual(calls.addMerit.length, 0); // 冪等:功德只給一次
});

// 3. 不存在 sk:同 2(條件寫命不中 → recycle 回 false)→ 不給功德
test('recycle: 不存在的 sk → 不給功德、already_recycled_or_missing', async () => {
  const { calls, deps } = makeStubs({ recycleResult: false });
  const svc = new ShrineOmamoriService(deps);
  const r = await svc.recycle('123', 'omamori#no-such');

  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.reason, 'already_recycled_or_missing');
  assert.strictEqual(calls.addMerit.length, 0);
});

// 4. config 缺 meritOnRecycle:getMain 回 null → fallback DEFAULT(50)
test('recycle: getMain 回 null → merit fallback DEFAULT_SHRINE_CONFIG.meritOnRecycle', async () => {
  const { calls, deps } = makeStubs({ config: null, recycleResult: true });
  const svc = new ShrineOmamoriService(deps);
  const r = await svc.recycle('456', 'omamori#abc');

  assert.deepStrictEqual(r, { ok: true, merit: DEFAULT_SHRINE_CONFIG.meritOnRecycle });
  assert.strictEqual(calls.addMerit.length, 1);
  assert.strictEqual(calls.addMerit[0].n, DEFAULT_SHRINE_CONFIG.meritOnRecycle);
});

// 5. DAO 拋非 Conditional 錯:omamoriDAO.recycle throw → {ok:false, reason:'error'}、addMerit 未呼叫
test('recycle: DAO 拋錯 → ok:false reason=error、addMerit 未被呼叫(不 throw)', async () => {
  const { calls, deps } = makeStubs({ recycleResult: 'throw' });
  const svc = new ShrineOmamoriService(deps);
  const r = await svc.recycle('123', 'omamori#abc');

  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.reason, 'error');
  assert.strictEqual(calls.addMerit.length, 0);
});

// 6. DAO 層 recycle 條件寫:UpdateCommand Key={discordId,sk}、ConditionExpression 含 recycled = :false、
//    :true/:false 值正確;ConditionalCheckFailedException → 回 false(非 throw);其他錯往上拋。
test('DAO.recycle: 條件寫參數正確;ConditionalCheckFailed → false;其他錯 → throw', async () => {
  const dao = new ShrineOmamoriDAO();
  const sent = [];
  let mode = 'ok'; // ok | conditional | boom
  dao.ddb = {
    async send (cmd) {
      sent.push(cmd.input);
      if (mode === 'conditional') {
        const err = new Error('cond failed');
        err.name = 'ConditionalCheckFailedException';
        throw err;
      }
      if (mode === 'boom') throw new Error('ddb boom');
      return {};
    }
  };

  // 成功回收 → true;參數逐項驗
  const ok = await dao.recycle(123, 'omamori#abc'); // 傳 number 驗 String() 收斂
  assert.strictEqual(ok, true);
  const input = sent[0];
  assert.strictEqual(input.TableName, 'sweetbot-shrine-omamori');
  assert.deepStrictEqual(input.Key, { discordId: '123', sk: 'omamori#abc' }); // 複合鍵,非 {id}
  assert.strictEqual(Object.prototype.hasOwnProperty.call(input.Key, 'id'), false);
  assert.strictEqual(input.UpdateExpression, 'SET recycled = :true');
  assert.strictEqual(input.ConditionExpression, 'attribute_exists(sk) AND recycled = :false');
  assert.deepStrictEqual(input.ExpressionAttributeValues, { ':true': true, ':false': false });

  // ConditionalCheckFailedException → false(冪等,非 throw)
  mode = 'conditional';
  const dup = await dao.recycle('123', 'omamori#abc');
  assert.strictEqual(dup, false);

  // 其他錯 → 往上拋
  mode = 'boom';
  await assert.rejects(() => dao.recycle('123', 'omamori#abc'), /ddb boom/);
});

// 7. DAO 層 addMerit:UpdateExpression='ADD merit :n'、:n 正確、Key={discordId}
test('DAO.addMerit: ADD merit :n、Key={discordId} 正確', async () => {
  const dao = new ShrineFortuneDAO();
  const sent = [];
  dao.ddb = {
    async send (cmd) {
      sent.push(cmd.input);
      return {};
    }
  };
  const r = await dao.addMerit(456, 50); // 傳 number 驗 String() 收斂
  assert.strictEqual(r, true);
  assert.strictEqual(sent.length, 1);
  const input = sent[0];
  assert.strictEqual(input.TableName, 'sweetbot-shrine-fortune');
  assert.deepStrictEqual(input.Key, { discordId: '456' }); // 非 {id}
  assert.strictEqual(input.UpdateExpression, 'ADD merit :n');
  assert.deepStrictEqual(input.ExpressionAttributeValues, { ':n': 50 });
});
