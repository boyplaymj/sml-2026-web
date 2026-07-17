// 建表腳本:牙菌斑怪獸 · DDB 堡壘 5 表(階段9b)
// - sweetbot-yajunban-fortress            : PK playerId  | GSI level-index / guild-index      | 無 TTL
// - sweetbot-yajunban-fortress-raid       : PK raidId    | GSI attacker-index / defender-index | TTL=ttl
// - sweetbot-yajunban-sugar-pulse         : PK pulseId + SK sk                                 | TTL=ttl
// - sweetbot-yajunban-fortress-guild-pool : PK guildId                                         | 無 TTL / 無 GSI
// - sweetbot-yajunban-fortress-ledger     : PK playerId + SK sk | GSI season-index             | 無 TTL
// BillingMode 一律 PAY_PER_REQUEST。schema 依據:STAGE9b-fortress-schema.md(定稿)。
//
// 沿用 create_yajunban_core_tables.js(9a)骨架:冪等 CreateTable + 既有表驗 schema + TTL 驗證/補正,
// 擴充:CreateTable 帶 GlobalSecondaryIndexes;既有表驗 GSI(名/keySchema/projection)。
// 用法(冪等,可重跑):複製到 sweetbot-next/migration/ 後 → node migration/create_yajunban_fortress_tables.js
const {
  DynamoDBClient,
  DescribeTableCommand,
  CreateTableCommand,
  DescribeTimeToLiveCommand,
  UpdateTimeToLiveCommand,
  waitUntilTableExists
} = require('@aws-sdk/client-dynamodb');

const REGION = 'ap-southeast-1';

const TABLES = [
  {
    name: 'sweetbot-yajunban-fortress',
    attrs: [
      { AttributeName: 'playerId', AttributeType: 'S' },
      { AttributeName: 'matchableBucket', AttributeType: 'S' },
      { AttributeName: 'lastActiveAt', AttributeType: 'N' },
      { AttributeName: 'guildId', AttributeType: 'S' },
      { AttributeName: 'channelId', AttributeType: 'S' }
    ],
    keys: [{ AttributeName: 'playerId', KeyType: 'HASH' }],
    ttlAttr: null,
    gsis: [
      {
        IndexName: 'level-index', // 稀疏:只對可配對堡壘寫 matchableBucket(STAGE9b P1-1)
        keys: [
          { AttributeName: 'matchableBucket', KeyType: 'HASH' },
          { AttributeName: 'lastActiveAt', KeyType: 'RANGE' }
        ],
        projection: { ProjectionType: 'INCLUDE', NonKeyAttributes: ['level', 'shieldUntil', 'activeRaidId', 'state'] }
      },
      {
        IndexName: 'guild-index',
        keys: [
          { AttributeName: 'guildId', KeyType: 'HASH' },
          { AttributeName: 'channelId', KeyType: 'RANGE' }
        ],
        projection: { ProjectionType: 'KEYS_ONLY' }
      }
    ]
  },
  {
    name: 'sweetbot-yajunban-fortress-raid',
    attrs: [
      { AttributeName: 'raidId', AttributeType: 'S' },
      { AttributeName: 'attackerId', AttributeType: 'S' },
      { AttributeName: 'departAt', AttributeType: 'N' },
      { AttributeName: 'defenderId', AttributeType: 'S' },
      { AttributeName: 'arriveAt', AttributeType: 'N' }
    ],
    keys: [{ AttributeName: 'raidId', KeyType: 'HASH' }],
    ttlAttr: 'ttl', // = max(zombieLeaseEnd, cooldownUntil, revengeUntil, notifRetentionUntil),STAGE9b P1-2
    gsis: [
      {
        IndexName: 'attacker-index',
        keys: [
          { AttributeName: 'attackerId', KeyType: 'HASH' },
          { AttributeName: 'departAt', KeyType: 'RANGE' }
        ],
        projection: { ProjectionType: 'INCLUDE', NonKeyAttributes: ['defenderId', 'state'] }
      },
      {
        IndexName: 'defender-index',
        keys: [
          { AttributeName: 'defenderId', KeyType: 'HASH' },
          { AttributeName: 'arriveAt', KeyType: 'RANGE' }
        ],
        projection: { ProjectionType: 'INCLUDE', NonKeyAttributes: ['attackerId', 'state'] }
      }
    ]
  },
  {
    name: 'sweetbot-yajunban-sugar-pulse',
    attrs: [
      { AttributeName: 'pulseId', AttributeType: 'S' },
      { AttributeName: 'sk', AttributeType: 'S' }
    ],
    keys: [
      { AttributeName: 'pulseId', KeyType: 'HASH' },
      { AttributeName: 'sk', KeyType: 'RANGE' }
    ],
    ttlAttr: 'ttl', // 糖潮結束後 META/CLAIM 自清;claim 去重/防超賣靠條件寫非 TTL
    gsis: []
  },
  {
    name: 'sweetbot-yajunban-fortress-guild-pool',
    attrs: [{ AttributeName: 'guildId', AttributeType: 'S' }],
    keys: [{ AttributeName: 'guildId', KeyType: 'HASH' }],
    ttlAttr: null,
    gsis: []
  },
  {
    name: 'sweetbot-yajunban-fortress-ledger',
    attrs: [
      { AttributeName: 'playerId', AttributeType: 'S' },
      { AttributeName: 'sk', AttributeType: 'S' },
      { AttributeName: 'seasonId', AttributeType: 'S' },
      { AttributeName: 'ts', AttributeType: 'N' }
    ],
    keys: [
      { AttributeName: 'playerId', KeyType: 'HASH' },
      { AttributeName: 'sk', KeyType: 'RANGE' }
    ],
    ttlAttr: null,
    gsis: [
      {
        IndexName: 'season-index',
        keys: [
          { AttributeName: 'seasonId', KeyType: 'HASH' },
          { AttributeName: 'ts', KeyType: 'RANGE' }
        ],
        projection: { ProjectionType: 'INCLUDE', NonKeyAttributes: ['type', 'delta', 'refId'] }
      }
    ]
  }
];

const summary = [];
const fatals = [];

function normPairs (arr, a, b) {
  return arr.map((x) => `${x[a]}:${x[b]}`).sort();
}
function sameSet (actual, expected, a, b) {
  const x = normPairs(actual || [], a, b);
  const y = normPairs(expected || [], a, b);
  return x.length === y.length && x.every((v, i) => v === y[i]);
}
function sameStrSet (a, b) {
  const x = [...(a || [])].sort();
  const y = [...(b || [])].sort();
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

function verifySchema (def, table) {
  const problems = [];
  if (!sameSet(table.KeySchema || [], def.keys, 'AttributeName', 'KeyType')) {
    problems.push(`KeySchema 不符(實際 ${JSON.stringify(table.KeySchema)})`);
  }
  if (!sameSet(table.AttributeDefinitions || [], def.attrs, 'AttributeName', 'AttributeType')) {
    problems.push(`AttributeDefinitions 不符(實際 ${JSON.stringify(table.AttributeDefinitions)})`);
  }
  const billing = table.BillingModeSummary && table.BillingModeSummary.BillingMode;
  if (billing !== 'PAY_PER_REQUEST') problems.push(`BillingMode 應 PAY_PER_REQUEST,實際「${billing}」`);
  verifyGsis(def, table, problems);
  if (problems.length) {
    for (const p of problems) fatals.push(`[${def.name}] schema 驗證失敗:${p}`);
    return 'MISMATCH';
  }
  return 'OK';
}

function verifyGsis (def, table, problems) {
  const actual = table.GlobalSecondaryIndexes || [];
  const expected = def.gsis || [];
  if (actual.length !== expected.length) {
    problems.push(`GSI 數應 ${expected.length},實際 ${actual.length}`);
    return;
  }
  for (const eg of expected) {
    const ag = actual.find((g) => g.IndexName === eg.IndexName);
    if (!ag) { problems.push(`缺 GSI「${eg.IndexName}」`); continue; }
    if (!sameSet(ag.KeySchema || [], eg.keys, 'AttributeName', 'KeyType')) {
      problems.push(`GSI「${eg.IndexName}」KeySchema 不符`);
    }
    const ap = ag.Projection || {};
    if (ap.ProjectionType !== eg.projection.ProjectionType) {
      problems.push(`GSI「${eg.IndexName}」Projection 型別應 ${eg.projection.ProjectionType},實際 ${ap.ProjectionType}`);
    } else if (eg.projection.ProjectionType === 'INCLUDE' &&
               !sameStrSet(ap.NonKeyAttributes, eg.projection.NonKeyAttributes)) {
      problems.push(`GSI「${eg.IndexName}」NonKeyAttributes 不符(實際 ${JSON.stringify(ap.NonKeyAttributes)})`);
    }
  }
}

async function ensureTable (client, def) {
  const row = { table: def.name, create: '', schema: '-', ttl: '' };
  let table = await describe(client, def.name);

  if (!table) {
    console.log(`表 ${def.name} 不存在,開始建立...`);
    const params = {
      TableName: def.name,
      AttributeDefinitions: def.attrs,
      KeySchema: def.keys,
      BillingMode: 'PAY_PER_REQUEST'
    };
    if (def.gsis && def.gsis.length) {
      params.GlobalSecondaryIndexes = def.gsis.map((g) => ({
        IndexName: g.IndexName,
        KeySchema: g.keys,
        Projection: g.projection
      }));
    }
    await client.send(new CreateTableCommand(params));
    await waitUntilTableExists({ client, maxWaitTime: 180 }, { TableName: def.name });
    console.log(`表 ${def.name} 建立完成。`);
    row.create = 'created';
    row.schema = 'OK';
  } else {
    row.create = 'existed';
    if (table.TableStatus !== 'ACTIVE') {
      console.log(`表 ${def.name} 狀態 ${table.TableStatus},等待 ACTIVE...`);
      await waitUntilTableExists({ client, maxWaitTime: 180 }, { TableName: def.name });
      table = await describe(client, def.name);
    }
    row.schema = verifySchema(def, table);
    console.log(`表 ${def.name} 已存在,schema 驗證:${row.schema}`);
  }

  row.ttl = await ensureTtl(client, def);
  summary.push(row);
}

async function ensureTtl (client, def) {
  const desc = await client.send(new DescribeTimeToLiveCommand({ TableName: def.name }));
  const cur = desc.TimeToLiveDescription || {};
  const curStatus = cur.TimeToLiveStatus;
  const curAttr = cur.AttributeName || null;

  if (!def.ttlAttr) {
    if (curStatus === 'ENABLED' || curStatus === 'ENABLING') {
      fatals.push(`[${def.name}] 不應開 TTL,卻偵測到 TTL ${curStatus}(attr=${curAttr})。`);
      return `ERR(${curStatus})`;
    }
    if (curStatus === 'DISABLING') return 'disabling';
    return 'none';
  }
  if (curStatus === 'ENABLED' && curAttr === def.ttlAttr) return 'ok';
  if (curStatus === 'ENABLING' && curAttr === def.ttlAttr) return 'enabling';
  if ((curStatus === 'ENABLED' || curStatus === 'ENABLING') && curAttr !== def.ttlAttr) {
    fatals.push(`[${def.name}] TTL 啟用在錯誤 attr「${curAttr}」(應「${def.ttlAttr}」)。`);
    return `ERR(wrong-attr:${curAttr})`;
  }
  if (curStatus === 'DISABLING') {
    fatals.push(`[${def.name}] TTL 正在 DISABLING,待完成後重跑。`);
    return 'ERR(disabling)';
  }
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
    console.log(`  ${r.table.padEnd(38)} create=${r.create.padEnd(8)} schema=${String(r.schema).padEnd(9)} ttl=${r.ttl}`);
  }
}

async function main () {
  const client = new DynamoDBClient({ region: REGION });
  console.log(`=== 牙菌斑堡壘 5 表建表 @ ${REGION} ===`);
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
  console.error('牙菌斑堡壘建表失敗:', err);
  process.exit(1);
});
