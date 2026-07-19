// 甜甜神社 S3-0a-i — 面板純核心 + visit DAO 單測(HANDOFF-S3-0a §6 測試矩陣)。
// 只測純邏輯 + DAO stub(ddb.send),不打真 AWS、不碰 interaction。
const test = require('node:test');
const assert = require('node:assert/strict');

const Shrine = require('../model/shrine/Shrine.js');
const { FLAVOR, SHITSUREI } = require('../model/shrine/Shrine.js');
const MAP = require('../model/shrine/mapPositions.js');
const ShrineFortuneDAO = require('../DAO/DDB/ShrineFortuneDAO.js');

const NOW = 1721000000;
const shrine = new Shrine(null, null);

// ── 1. resolveLocation ──────────────────────────────────────
test('resolveLocation: 合法 key → location 物件(name/image/facility/sidebarRow)', () => {
  const loc = shrine.resolveLocation('honden');
  assert.equal(loc.key, 'honden');
  assert.equal(loc.name, '本殿');
  assert.equal(loc.image, 'honden.png');
  assert.equal(loc.facility, 'honden');
  assert.equal(loc.sidebarRow, 2);
});

test('resolveLocation: 未知/空 key → null(不 throw)', () => {
  assert.equal(shrine.resolveLocation('nonsense'), null);
  assert.equal(shrine.resolveLocation(''), null);
  assert.equal(shrine.resolveLocation(null), null);
  assert.equal(shrine.resolveLocation(undefined), null);
});

// ── 2. navFacilities ────────────────────────────────────────
test('navFacilities: 9 項、每項 label/emoji/value 齊、value 都能 resolveLocation', () => {
  const nav = shrine.navFacilities();
  assert.equal(nav.length, 9);
  for (const o of nav) {
    assert.ok(o.label && o.emoji && o.value, JSON.stringify(o));
    const loc = shrine.resolveLocation(o.value);
    assert.ok(loc, 'nav value 找不到 location: ' + o.value);
  }
  // 奧社入口對到 okusha_stair(石段),不是 okusha_top
  const okusha = nav.find((o) => o.label === '奧社');
  assert.equal(okusha.value, 'okusha_stair');
});

// ── 3. _panel ───────────────────────────────────────────────
test('_panel: 合法 key → embed image=正確 CDN URL、description 含 name+flavor', () => {
  const embed = shrine._panel('honden');
  assert.equal(embed.data.image.url, MAP.cdnBase + 'honden.png');
  assert.equal(embed.data.title, '⛩️ 甜甜神社');
  assert.equal(embed.data.color, 0xC0392B);
  assert.ok(embed.data.description.includes('本殿'));
  assert.ok(embed.data.description.includes(FLAVOR.honden));
});

test('_panel: 全 9 個導覽 value 都能出面板且 CDN URL 對上', () => {
  for (const o of shrine.navFacilities()) {
    const loc = shrine.resolveLocation(o.value);
    const embed = shrine._panel(o.value);
    assert.equal(embed.data.image.url, MAP.cdnBase + loc.image);
    assert.ok(embed.data.description.includes(loc.name));
    assert.ok(embed.data.description.includes(FLAVOR[o.value]));
  }
});

test('_panel: 未知 key → fallback torii(不 throw)', () => {
  const embed = shrine._panel('no_such_place');
  assert.equal(embed.data.image.url, MAP.cdnBase + 'torii.png');
  assert.ok(embed.data.description.includes('鳥居'));
});

// ── 4. _shitsureiOnEnter ────────────────────────────────────
test('_shitsureiOnEnter: closed:false(放置未退場礼)→ 負 buff(扣 body、3 天過期)', () => {
  const buff = shrine._shitsureiOnEnter({ openAt: NOW - 999, closed: false }, NOW);
  assert.ok(buff);
  assert.equal(buff.axis, 'body');
  assert.equal(buff.delta, SHITSUREI.delta);
  assert.ok(buff.delta < 0);
  assert.equal(buff.expireAt, NOW + 3 * 86400);
  assert.equal(buff.source, 'shitsurei_taijou');
});

test('_shitsureiOnEnter: closed:true(乾淨退場)→ null(不扣)', () => {
  assert.equal(shrine._shitsureiOnEnter({ openAt: NOW - 999, closed: true }, NOW), null);
});

test('_shitsureiOnEnter: null/undefined(首次參拜)→ null(不扣)', () => {
  assert.equal(shrine._shitsureiOnEnter(null, NOW), null);
  assert.equal(shrine._shitsureiOnEnter(undefined, NOW), null);
});

// ── 5. DAO(stub ddb.send)────────────────────────────────────
test('DAO.openVisit: 先 Get 拿舊 lastVisit、再 SET 新值、回傳舊值', async () => {
  const dao = new ShrineFortuneDAO();
  const sent = [];
  const oldVisit = { openAt: 111, closed: false };
  dao.ddb = {
    async send (cmd) {
      sent.push(cmd.input);
      // 第一發是 GetCommand(無 UpdateExpression)→ 回舊 Item
      if (!cmd.input.UpdateExpression) return { Item: { discordId: '123', lastVisit: oldVisit } };
      return {};
    }
  };
  const ret = await dao.openVisit('123', NOW);
  assert.deepEqual(ret, oldVisit);
  assert.equal(sent.length, 2);
  // Get:Key 正確
  assert.deepEqual(sent[0].Key, { discordId: '123' });
  assert.equal(sent[0].UpdateExpression, undefined);
  // Update:SET lastVisit 整包覆蓋
  assert.deepEqual(sent[1].Key, { discordId: '123' });
  assert.equal(sent[1].UpdateExpression, 'SET lastVisit = :v');
  assert.deepEqual(sent[1].ExpressionAttributeValues[':v'], { openAt: NOW, closed: false });
});

test('DAO.openVisit: 無舊紀錄(Item 不存在)→ 回 undefined、仍 SET 新值', async () => {
  const dao = new ShrineFortuneDAO();
  const sent = [];
  dao.ddb = {
    async send (cmd) {
      sent.push(cmd.input);
      return {}; // Get 回無 Item
    }
  };
  const ret = await dao.openVisit(456, NOW); // 數字 id 也要轉字串
  assert.equal(ret, undefined);
  assert.equal(sent.length, 2);
  assert.deepEqual(sent[1].Key, { discordId: '456' });
  assert.deepEqual(sent[1].ExpressionAttributeValues[':v'], { openAt: NOW, closed: false });
});

test('DAO.closeVisit: SET lastVisit.closed=true(#c alias)、Key 正確', async () => {
  const dao = new ShrineFortuneDAO();
  const sent = [];
  dao.ddb = { async send (cmd) { sent.push(cmd.input); return {}; } };
  await dao.closeVisit('123');
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0].Key, { discordId: '123' });
  assert.equal(sent[0].UpdateExpression, 'SET lastVisit.#c = :true');
  assert.deepEqual(sent[0].ExpressionAttributeNames, { '#c': 'closed' });
  assert.deepEqual(sent[0].ExpressionAttributeValues, { ':true': true });
});

test('DAO.appendBuff: list_append + if_not_exists 原子 append、buff 包成單元素陣列', async () => {
  const dao = new ShrineFortuneDAO();
  const sent = [];
  dao.ddb = { async send (cmd) { sent.push(cmd.input); return {}; } };
  const buff = { axis: 'body', delta: -5, expireAt: NOW + 3 * 86400, source: 'shitsurei_taijou' };
  await dao.appendBuff('123', buff);
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0].Key, { discordId: '123' });
  assert.equal(sent[0].UpdateExpression, 'SET buffs = list_append(if_not_exists(buffs, :empty), :b)');
  assert.deepEqual(sent[0].ExpressionAttributeValues[':empty'], []);
  assert.deepEqual(sent[0].ExpressionAttributeValues[':b'], [buff]);
});

// ── 6. 既有方法沒被破壞(存在性快檢;完整行為測試在 shrineLuck/shrineHarai)──
test('ShrineFortuneDAO: 既有方法仍在(getByPlayer/put/addMerit/setYakuHarai/setGender)', () => {
  const dao = new ShrineFortuneDAO();
  for (const m of ['getByPlayer', 'put', 'addMerit', 'setYakuHarai', 'setGender', 'openVisit', 'closeVisit', 'appendBuff']) {
    assert.equal(typeof dao[m], 'function', m);
  }
});

// ── 7. handler 尚未接線(S3-0a-ii 前空陣列)──
test('Shrine: commands/buttons/selects 先為空陣列(S3-0a-i 不含 handler)', () => {
  assert.deepEqual(shrine.commands, []);
  assert.deepEqual(shrine.buttons, []);
  assert.deepEqual(shrine.selects, []);
});
