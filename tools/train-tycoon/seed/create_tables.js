// 建表腳本:甜甜火車大亨 5 張表(對應 DESIGN.md §9),全 PAY_PER_REQUEST,region ap-southeast-1。
// 冪等:逐表 DescribeTable,已存在跳過;不存在才 CreateTable 並等到 ACTIVE。
// 用法:node create_tables.js   (需 AWS 憑證 + @aws-sdk/client-dynamodb)
// 放到 sweetbot-next/migration/ 執行亦可(相依同 SDK)。
const {
  DynamoDBClient,
  DescribeTableCommand,
  CreateTableCommand,
  waitUntilTableExists
} = require('@aws-sdk/client-dynamodb');

const REGION = 'ap-southeast-1';

// 每表 key schema。config=section(HASH)+state(RANGE);transit=userId(HASH)+sk(RANGE);
// events=userId(HASH)+ts(RANGE,Number);stations/world 單 HASH。
const TABLES = [
  {
    name: 'train-tycoon-config',
    attrs: [{ AttributeName: 'section', AttributeType: 'S' }, { AttributeName: 'state', AttributeType: 'S' }],
    keys: [{ AttributeName: 'section', KeyType: 'HASH' }, { AttributeName: 'state', KeyType: 'RANGE' }]
  },
  {
    name: 'train-tycoon-stations',
    attrs: [{ AttributeName: 'userId', AttributeType: 'S' }],
    keys: [{ AttributeName: 'userId', KeyType: 'HASH' }]
  },
  {
    name: 'train-tycoon-transit',
    attrs: [{ AttributeName: 'userId', AttributeType: 'S' }, { AttributeName: 'sk', AttributeType: 'S' }],
    keys: [{ AttributeName: 'userId', KeyType: 'HASH' }, { AttributeName: 'sk', KeyType: 'RANGE' }]
  },
  {
    name: 'train-tycoon-world',
    attrs: [{ AttributeName: 'nodeId', AttributeType: 'S' }],
    keys: [{ AttributeName: 'nodeId', KeyType: 'HASH' }]
  },
  {
    name: 'train-tycoon-events',
    attrs: [{ AttributeName: 'userId', AttributeType: 'S' }, { AttributeName: 'ts', AttributeType: 'N' }],
    keys: [{ AttributeName: 'userId', KeyType: 'HASH' }, { AttributeName: 'ts', KeyType: 'RANGE' }]
  }
];

async function ensureTable (client, t) {
  try {
    const res = await client.send(new DescribeTableCommand({ TableName: t.name }));
    console.log(`表 ${t.name} 已存在(狀態: ${res.Table.TableStatus}),跳過。`);
    return;
  } catch (err) {
    if (err.name !== 'ResourceNotFoundException') throw err;
  }
  console.log(`表 ${t.name} 不存在,建立中...`);
  await client.send(new CreateTableCommand({
    TableName: t.name,
    AttributeDefinitions: t.attrs,
    KeySchema: t.keys,
    BillingMode: 'PAY_PER_REQUEST'
  }));
  await waitUntilTableExists({ client, maxWaitTime: 120 }, { TableName: t.name });
  console.log(`表 ${t.name} 建立完成。`);
}

async function main () {
  const client = new DynamoDBClient({ region: REGION });
  for (const t of TABLES) await ensureTable(client, t);
  console.log('全部 5 表就緒。');
}

main().catch((err) => { console.error('建表失敗:', err); process.exit(1); });
