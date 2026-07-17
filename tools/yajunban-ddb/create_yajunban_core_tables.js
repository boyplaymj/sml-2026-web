// 建表腳本:牙菌斑怪獸 · DDB 核心 4 表(階段9a)
// - sweetbot-yajunban-monster : PK userId + SK sk           (無 TTL / 無 GSI)
// - sweetbot-yajunban-ledger  : PK userId + SK sk           (無 TTL / season-index 延後不建)
// - sweetbot-yajunban-battle  : PK battleId                 (TTL=leaseExpireAt 秒)
// - sweetbot-yajunban-world   : PK pk + SK sk               (TTL=ttl 秒)
// BillingMode 一律 PAY_PER_REQUEST。堡壘 5 表不在此腳本(見 STAGE9a 文末,另立 9b)。
//
// 設計依據:STAGE2/3/4/5a/6/7b/8(全定稿)。TTL 慣例對齊 migration/create_earthquake_tables.js,
// 但強化為「每次跑都 DescribeTimeToLive 驗證/補正」(落實 STAGE8 §2 P2-a:TTL attr 打錯=靜默不清殭屍)。
//
// 用法(冪等,可重跑):
//   複製到 sweetbot-next/migration/ 後 → node migration/create_yajunban_core_tables.js
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

async function tableExists (client, name) {
  try {
    const res = await client.send(new DescribeTableCommand({ TableName: name }));
    return res.Table.TableStatus;
  } catch (err) {
    if (err.name === 'ResourceNotFoundException') return null;
    throw err;
  }
}

async function ensureTable (client, def) {
  const status = await tableExists(client, def.name);
  if (status) {
    console.log(`表 ${def.name} 已存在(狀態: ${status}),跳過建表。`);
  } else {
    console.log(`表 ${def.name} 不存在,開始建立...`);
    await client.send(new CreateTableCommand({
      TableName: def.name,
      AttributeDefinitions: def.attrs,
      KeySchema: def.keys,
      BillingMode: 'PAY_PER_REQUEST'
    }));
    await waitUntilTableExists({ client, maxWaitTime: 120 }, { TableName: def.name });
    console.log(`表 ${def.name} 建立完成。`);
  }

  // TTL 冪等驗證/補正(即使表已存在也檢查;落實 STAGE8 §2 P2-a)。
  await ensureTtl(client, def);
}

async function ensureTtl (client, def) {
  const desc = await client.send(new DescribeTimeToLiveCommand({ TableName: def.name }));
  const cur = desc.TimeToLiveDescription || {};
  const curStatus = cur.TimeToLiveStatus; // ENABLED / DISABLED / ENABLING / DISABLING
  const curAttr = cur.AttributeName || null;

  if (!def.ttlAttr) {
    // 此表不該開 TTL(永久資料表)。若發現被誤開,警示(不自動關,避免誤動)。
    if (curStatus === 'ENABLED') {
      console.warn(`⚠️ 表 ${def.name} 不應開 TTL,卻偵測到 TTL ENABLED(attr=${curAttr})!請人工確認。`);
    } else {
      console.log(`表 ${def.name} 無 TTL(符合預期)。`);
    }
    return;
  }

  // 應開 TTL 的表:已用正確 attr 啟用 → 略過;否則啟用/補正。
  if (curStatus === 'ENABLED' && curAttr === def.ttlAttr) {
    console.log(`表 ${def.name} TTL 已正確啟用(${def.ttlAttr}),跳過。`);
    return;
  }
  if (curStatus === 'ENABLED' && curAttr !== def.ttlAttr) {
    console.warn(`⚠️ 表 ${def.name} TTL 啟用在錯誤 attr「${curAttr}」(應為「${def.ttlAttr}」)!需人工先關再開,腳本不自動改。`);
    return;
  }
  if (curStatus === 'ENABLING' || curStatus === 'DISABLING') {
    console.warn(`⚠️ 表 ${def.name} TTL 狀態轉換中(${curStatus}),稍後重跑本腳本補正。`);
    return;
  }
  // DISABLED / 未設 → 啟用
  await client.send(new UpdateTimeToLiveCommand({
    TableName: def.name,
    TimeToLiveSpecification: { Enabled: true, AttributeName: def.ttlAttr }
  }));
  console.log(`表 ${def.name} 已啟用 TTL(${def.ttlAttr})。`);
}

async function main () {
  const client = new DynamoDBClient({ region: REGION });
  console.log(`=== 牙菌斑核心 4 表建表 @ ${REGION} ===`);
  for (const def of TABLES) await ensureTable(client, def);
  console.log('=== 全部完成 ===');
}

main().catch((err) => {
  console.error('牙菌斑建表失敗:', err);
  process.exit(1);
});
