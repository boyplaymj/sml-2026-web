// 建表腳本:甜甜神社(jinja-shrine)運勢中樞 — Stage 0 資料層
//   規格見 repo tools/jinja-shrine/STAGE0.md。全 PAY_PER_REQUEST、region ap-southeast-1。
//   核心零 GSI、本批皆無 TTL(玩家狀態/御守/收藏皆永久保留)。
//   冪等且「既有表也驗」(照牙菌斑 migration 慣例,P1):
//     - 既有表驗 KeySchema / AttributeDefinitions / BillingMode / GSI 數=0,不符即累積 fatal。
//     - 用 DescribeTimeToLive 驗 TTL「未啟用」(本批不該有 TTL);偵測到 TTL 開啟即 fatal,不自動關(避免誤動)。
//     - 任一 fatal → 印彙總後 exit 1,絕不假裝成功。
//   用法:node migration/create_shrine_tables.js
const {
  DynamoDBClient,
  DescribeTableCommand,
  CreateTableCommand,
  UpdateTimeToLiveCommand,
  DescribeTimeToLiveCommand,
  waitUntilTableExists
} = require('@aws-sdk/client-dynamodb');

const REGION = 'ap-southeast-1';

const TABLES = [
  { // 1) 玩家運氣狀態(核心) PK=discordId 單鍵
    name: 'sweetbot-shrine-fortune',
    attrs: [{ AttributeName: 'discordId', AttributeType: 'S' }],
    keys: [{ AttributeName: 'discordId', KeyType: 'HASH' }],
    ttlAttr: null
  },
  { // 2) 御守持有 PK=discordId SK=sk('omamori#<instanceId>')
    name: 'sweetbot-shrine-omamori',
    attrs: [
      { AttributeName: 'discordId', AttributeType: 'S' },
      { AttributeName: 'sk', AttributeType: 'S' }
    ],
    keys: [
      { AttributeName: 'discordId', KeyType: 'HASH' },
      { AttributeName: 'sk', KeyType: 'RANGE' }
    ],
    ttlAttr: null
  },
  { // 3) 御朱印帳 PK=discordId SK=sk('goshuin#<versionId>')
    name: 'sweetbot-shrine-goshuin',
    attrs: [
      { AttributeName: 'discordId', AttributeType: 'S' },
      { AttributeName: 'sk', AttributeType: 'S' }
    ],
    keys: [
      { AttributeName: 'discordId', KeyType: 'HASH' },
      { AttributeName: 'sk', KeyType: 'RANGE' }
    ],
    ttlAttr: null
  },
  { // 4) 繪馬牆(公開) PK=bucket('month#<yyyymm>') SK=sk('<createTimeEpoch>#<emaId>')
    name: 'sweetbot-shrine-ema',
    attrs: [
      { AttributeName: 'bucket', AttributeType: 'S' },
      { AttributeName: 'sk', AttributeType: 'S' }
    ],
    keys: [
      { AttributeName: 'bucket', KeyType: 'HASH' },
      { AttributeName: 'sk', KeyType: 'RANGE' }
    ],
    ttlAttr: null
  },
  { // 5) 石柱捐獻榮譽榜 PK=discordId(一人一柱累加)
    name: 'sweetbot-shrine-pillar',
    attrs: [{ AttributeName: 'discordId', AttributeType: 'S' }],
    keys: [{ AttributeName: 'discordId', KeyType: 'HASH' }],
    ttlAttr: null
  },
  { // 6) 籤詩池(後台可增修) PK=omikujiId
    name: 'sweetbot-shrine-omikuji-pool',
    attrs: [{ AttributeName: 'omikujiId', AttributeType: 'S' }],
    keys: [{ AttributeName: 'omikujiId', KeyType: 'HASH' }],
    ttlAttr: null
  },
  { // 7) 後台設定(單列 key='main')
    name: 'sweetbot-shrine-config',
    attrs: [{ AttributeName: 'key', AttributeType: 'S' }],
    keys: [{ AttributeName: 'key', KeyType: 'HASH' }],
    ttlAttr: null
  }
];

const summary = []; // 每表一列彙總
const fatals = [];  // string[] 累積致命問題

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

// P1:既有表驗 key schema / AttributeDefinitions / BillingMode / GSI 數。錯了累積 fatal。
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

// P1:本批表都不該有 TTL。用 DescribeTimeToLive 驗未啟用;開了就 fatal,不自動關(避免誤動)。
async function verifyTtlDisabled (client, def) {
  const desc = await client.send(new DescribeTimeToLiveCommand({ TableName: def.name }));
  const cur = desc.TimeToLiveDescription || {};
  const curStatus = cur.TimeToLiveStatus; // ENABLED / DISABLED / ENABLING / DISABLING
  const curAttr = cur.AttributeName || null;
  if (curStatus === 'ENABLED' || curStatus === 'ENABLING') {
    fatals.push(`[${def.name}] 不應開 TTL,卻偵測到 TTL ${curStatus}(attr=${curAttr})。請人工確認並關閉。`);
    return `ERR(${curStatus})`;
  }
  if (curStatus === 'DISABLING') return 'disabling';
  return 'none';
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
    // 非 ACTIVE 先等到 ACTIVE 再驗,避免 CREATING/UPDATING 時查 TTL 不穩。
    if (table.TableStatus !== 'ACTIVE') {
      console.log(`表 ${def.name} 狀態 ${table.TableStatus},等待 ACTIVE...`);
      await waitUntilTableExists({ client, maxWaitTime: 120 }, { TableName: def.name });
      table = await describe(client, def.name);
    }
    row.schema = verifySchema(def, table);
    console.log(`表 ${def.name} 已存在,schema 驗證:${row.schema}`);
  }

  // 本批 def.ttlAttr 皆 null → 一律驗「TTL 未啟用」。
  row.ttl = await verifyTtlDisabled(client, def);
  summary.push(row);

  // 保留擴充:若未來某表要開 TTL,在此依 def.ttlAttr 呼叫 UpdateTimeToLiveCommand。
  void UpdateTimeToLiveCommand;
}

function printSummary () {
  console.log('\n=== 結果彙總 ===');
  for (const r of summary) {
    console.log(`  ${r.table.padEnd(32)} create=${r.create.padEnd(8)} schema=${String(r.schema).padEnd(9)} ttl=${r.ttl}`);
  }
}

async function main () {
  const client = new DynamoDBClient({ region: REGION });
  console.log(`=== 甜甜神社 7 表建表 @ ${REGION} ===`);
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
  console.error('神社建表失敗:', err);
  process.exit(1);
});
