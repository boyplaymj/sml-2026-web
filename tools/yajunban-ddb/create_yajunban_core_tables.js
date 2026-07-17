// 建表腳本:牙菌斑怪獸 · DDB 核心 4 表(階段9a)
// - sweetbot-yajunban-monster : PK userId + SK sk           (無 TTL / 無 GSI)
// - sweetbot-yajunban-ledger  : PK userId + SK sk           (無 TTL / season-index 延後不建)
// - sweetbot-yajunban-battle  : PK battleId                 (TTL=leaseExpireAt 秒)
// - sweetbot-yajunban-world   : PK pk + SK sk               (TTL=ttl 秒)
// BillingMode 一律 PAY_PER_REQUEST。堡壘 5 表不在此腳本(見 STAGE9a 文末,另立 9b)。
//
// 設計依據:STAGE2/3/4/5a/6/7b/8(全定稿)。TTL 慣例對齊 migration/create_earthquake_tables.js,
// 強化(STAGE8 §2 P2-a + Codex S9a 二驗):
//   - 既有表也「驗 key schema/BillingMode/GSI 數」,不符即 throw(P1-1:key 建錯不是可自動補的小事)。
//   - TTL/schema 任一錯累積成 error,結尾 process.exit(1),不讓部署誤判成功(P1-2)。
//   - 不該開 TTL 的表 ENABLED/ENABLING 都算錯(P1-3);表非 ACTIVE 先 wait 再驗(P1-4)。
//
// 用法(冪等,可重跑):複製到 sweetbot-next/migration/ 後 → node migration/create_yajunban_core_tables.js
const {
  DynamoDBClient,
  DescribeTableCommand,
  CreateTableCommand,
  DescribeTimeToLiveCommand,
  UpdateTimeToLiveCommand,
  waitUntilTableExists
} = require('@aws-sdk/client-dynamodb');

const REGION = 'ap-southeast-1';

// ttlAttr=null 代表此表永不開 native TTL(monster/ledger 裝永久資料,誤開=foot-gun,STAGE8 §2)。
const TABLES = [
  {
    name: 'sweetbot-yajunban-monster',
    attrs: [
      { AttributeName: 'userId', AttributeType: 'S' },
      { AttributeName: 'sk', AttributeType: 'S' }
    ],
    keys: [
      { AttributeName: 'userId', KeyType: 'HASH' },
      { AttributeName: 'sk', KeyType: 'RANGE' }
    ],
    ttlAttr: null
  },
  {
    name: 'sweetbot-yajunban-ledger',
    attrs: [
      { AttributeName: 'userId', AttributeType: 'S' },
      { AttributeName: 'sk', AttributeType: 'S' }
    ],
    keys: [
      { AttributeName: 'userId', KeyType: 'HASH' },
      { AttributeName: 'sk', KeyType: 'RANGE' }
    ],
    ttlAttr: null // season-index GSI 延後不建(STAGE7a ⑪);season 欄仍由 DAO 每列必帶
  },
  {
    name: 'sweetbot-yajunban-battle',
    attrs: [
      { AttributeName: 'battleId', AttributeType: 'S' }
    ],
    keys: [
      { AttributeName: 'battleId', KeyType: 'HASH' }
    ],
    ttlAttr: 'leaseExpireAt' // 秒級 10 位(STAGE6);唯一真 TTL 生命週期表
  },
  {
    name: 'sweetbot-yajunban-world',
    attrs: [
      { AttributeName: 'pk', AttributeType: 'S' }, // <season>#<gridBucket>(overloaded 空間分桶)
      { AttributeName: 'sk', AttributeType: 'S' }  // OCC#<userId> / LOOT#<ulid>
    ],
    keys: [
      { AttributeName: 'pk', KeyType: 'HASH' },
      { AttributeName: 'sk', KeyType: 'RANGE' }
    ],
    ttlAttr: 'ttl' // OCC=season-end、LOOT=壽命(STAGE7b);OCC 禁 idle TTL 由 DAO 保證,非表層
  }
];

// 累積本次執行結果與致命錯誤(P1-2:結尾一次退出碼)。
const summary = []; // { table, create, schema, ttl }
const fatals = [];  // string[]

function normPairs (arr, a, b) {
  return arr.map((x) => `${x[a]}:${x[b]}`).sort();
}
function sameSet (actual, expected, a, b) {
  const x = normPairs(actual, a, b);
  const y = normPairs(expected, a, b);
  return x.length === y.length && x.every((v, i) => v === y[i]);
}

async function describe (client, name) {
  try {
    const res = await client.send(new DescribeTableCommand({ TableName: name }));
    return res.Table;
  } catch (err) {
    if (err.name === 'ResourceNotFoundException') return null;
    throw err;
  }
}

// P1-1:既有表驗 key schema / AttributeDefinitions / BillingMode / GSI 數。錯了累積 fatal。
function verifySchema (def, table) {
  const problems = [];
  if (!sameSet(table.KeySchema || [], def.keys, 'AttributeName', 'KeyType')) {
    problems.push(`KeySchema 不符(實際 ${JSON.stringify(table.KeySchema)} vs 期望 ${JSON.stringify(def.keys)})`);
  }
  // 本批表都無 GSI,故 AttributeDefinitions 應恰等於 key 屬性。
  if (!sameSet(table.AttributeDefinitions || [], def.attrs, 'AttributeName', 'AttributeType')) {
    problems.push(`AttributeDefinitions 不符(實際 ${JSON.stringify(table.AttributeDefinitions)} vs 期望 ${JSON.stringify(def.attrs)})`);
  }
  const billing = table.BillingModeSummary && table.BillingModeSummary.BillingMode;
  if (billing !== 'PAY_PER_REQUEST') {
    problems.push(`BillingMode 應為 PAY_PER_REQUEST,實際「${billing || '未知'}」`);
  }
  const gsiCount = (table.GlobalSecondaryIndexes || []).length;
  if (gsiCount !== 0) {
    problems.push(`GSI 數應為 0,實際 ${gsiCount}`);
  }
  if (problems.length) {
    for (const p of problems) fatals.push(`[${def.name}] schema 驗證失敗:${p}`);
    return 'MISMATCH';
  }
  return 'OK';
}

async function ensureTable (client, def) {
  const row = { table: def.name, create: '', schema: '-', ttl: '' };
  let table = await describe(client, def.name);

  if (!table) {
    console.log(`表 ${def.name} 不存在,開始建立...`);
    await client.send(new CreateTableCommand({
      TableName: def.name,
      AttributeDefinitions: def.attrs,
      KeySchema: def.keys,
      BillingMode: 'PAY_PER_REQUEST'
    }));
    await waitUntilTableExists({ client, maxWaitTime: 120 }, { TableName: def.name });
    console.log(`表 ${def.name} 建立完成。`);
    row.create = 'created';
    row.schema = 'OK';
    table = await describe(client, def.name);
  } else {
    row.create = 'existed';
    // P1-4:非 ACTIVE 先等到 ACTIVE 再驗,避免 CREATING/UPDATING 時查 TTL 不穩。
    if (table.TableStatus !== 'ACTIVE') {
      console.log(`表 ${def.name} 狀態 ${table.TableStatus},等待 ACTIVE...`);
      await waitUntilTableExists({ client, maxWaitTime: 120 }, { TableName: def.name });
      table = await describe(client, def.name);
    }
    // P1-1:驗既有表 schema。
    row.schema = verifySchema(def, table);
    console.log(`表 ${def.name} 已存在,schema 驗證:${row.schema}`);
  }

  row.ttl = await ensureTtl(client, def);
  summary.push(row);
}

async function ensureTtl (client, def) {
  const desc = await client.send(new DescribeTimeToLiveCommand({ TableName: def.name }));
  const cur = desc.TimeToLiveDescription || {};
  const curStatus = cur.TimeToLiveStatus; // ENABLED / DISABLED / ENABLING / DISABLING
  const curAttr = cur.AttributeName || null;

  if (!def.ttlAttr) {
    // 永久資料表:不該有 TTL。ENABLED/ENABLING 都算錯(P1-3),累積 fatal,不自動關(避免誤動)。
    if (curStatus === 'ENABLED' || curStatus === 'ENABLING') {
      fatals.push(`[${def.name}] 不應開 TTL,卻偵測到 TTL ${curStatus}(attr=${curAttr})。請人工確認並關閉。`);
      return `ERR(${curStatus})`;
    }
    if (curStatus === 'DISABLING') {
      console.log(`表 ${def.name} TTL 正在關閉(DISABLING),符合最終無 TTL 目標。`);
      return 'disabling';
    }
    return 'none';
  }

  // 應開 TTL 的表:
  if (curStatus === 'ENABLED' && curAttr === def.ttlAttr) {
    console.log(`表 ${def.name} TTL 已正確啟用(${def.ttlAttr})。`);
    return 'ok';
  }
  if (curStatus === 'ENABLING' && curAttr === def.ttlAttr) {
    // 正確 attr、轉換中 → 視同成功(P2-6:不強迫重跑)。
    console.log(`表 ${def.name} TTL 啟用轉換中(ENABLING, ${def.ttlAttr}),稍後自動生效。`);
    return 'enabling';
  }
  if ((curStatus === 'ENABLED' || curStatus === 'ENABLING') && curAttr !== def.ttlAttr) {
    fatals.push(`[${def.name}] TTL 啟用在錯誤 attr「${curAttr}」(應為「${def.ttlAttr}」)。需人工先關再開,腳本不自動改。`);
    return `ERR(wrong-attr:${curAttr})`;
  }
  if (curStatus === 'DISABLING') {
    fatals.push(`[${def.name}] TTL 正在 DISABLING,無法立即啟用。待其完成後重跑本腳本。`);
    return 'ERR(disabling)';
  }
  // DISABLED / 未設 → 啟用
  await client.send(new UpdateTimeToLiveCommand({
    TableName: def.name,
    TimeToLiveSpecification: { Enabled: true, AttributeName: def.ttlAttr }
  }));
  console.log(`表 ${def.name} 已啟用 TTL(${def.ttlAttr})。`);
  return 'enabled';
}

function printSummary () {
  console.log('\n=== 結果彙總 ===');
  for (const r of summary) {
    console.log(`  ${r.table.padEnd(30)} create=${r.create.padEnd(8)} schema=${String(r.schema).padEnd(9)} ttl=${r.ttl}`);
  }
}

async function main () {
  const client = new DynamoDBClient({ region: REGION });
  console.log(`=== 牙菌斑核心 4 表建表 @ ${REGION} ===`);
  for (const def of TABLES) await ensureTable(client, def);
  printSummary();
  if (fatals.length) {
    console.error('\n❌ 偵測到問題,建表未完全成功:');
    for (const f of fatals) console.error('  - ' + f);
    process.exit(1);
  }
  console.log('\n✅ 全部完成。');
}

main().catch((err) => {
  console.error('牙菌斑建表失敗:', err);
  process.exit(1);
});
