// 灌 config seed:把 config_seed.json 的每個 section 寫成 train-tycoon-config 的 published item。
// item 形狀對齊 MahjongConfigDAO 慣例:{ section, state:'published', data, updatedAt }。
// 冪等:純 Put 覆蓋 published(不動 draft)。用法:node seed_config.js
const fs = require('fs');
const path = require('path');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, PutCommand } = require('@aws-sdk/lib-dynamodb');

const REGION = 'ap-southeast-1';
const TABLE_NAME = 'train-tycoon-config';
const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }));

async function main () {
  const seed = JSON.parse(fs.readFileSync(path.join(__dirname, 'config_seed.json'), 'utf8'));
  const sections = seed.sections;
  const now = Date.now();
  for (const [section, data] of Object.entries(sections)) {
    await ddb.send(new PutCommand({
      TableName: TABLE_NAME,
      Item: { section, state: 'published', data, updatedAt: now }
    }));
    // 同步鋪一份 draft,後台載入時有底可改
    await ddb.send(new PutCommand({
      TableName: TABLE_NAME,
      Item: { section, state: 'draft', data, updatedAt: now }
    }));
    console.log(`灌好 section=${section}(published + draft)`);
  }
  console.log('config seed 完成。');
}

main().catch((err) => { console.error('seed 失敗:', err); process.exit(1); });
