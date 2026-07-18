// Patch:把 S2 新增的 config 欄位補進既有 sweetbot-shrine-config key='main'。
//   為什麼要另寫:seed_shrine_config.js 用 attribute_not_exists(key) → main 已存在時整列跳過,
//   不會補這些新欄。本 patch 用 UpdateExpression + if_not_exists 逐欄補,
//   **只補「缺的」欄、絕不覆蓋後台已調的值**(冪等、可重跑)。
//   值取自 model/shrine/defaults.js(單一真理)。用法:node migration/patch_shrine_config_s2.js
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, UpdateCommand, GetCommand } = require('@aws-sdk/lib-dynamodb');
const { DEFAULT_SHRINE_CONFIG } = require('../model/shrine/defaults.js');

const REGION = 'ap-southeast-1';
const TABLE = 'sweetbot-shrine-config';
const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }));

// 本次要補的 S2 欄位(→ 取 defaults 的權威值)
const FIELDS = {
  omamoriTypes: DEFAULT_SHRINE_CONFIG.omamoriTypes,
  yakuHaraiMode: DEFAULT_SHRINE_CONFIG.yakuHaraiMode,
  yakuHaraiRechargeable: DEFAULT_SHRINE_CONFIG.yakuHaraiRechargeable
};

async function main () {
  const names = { '#key': 'key' };
  const values = {};
  const sets = [];
  for (const [k, v] of Object.entries(FIELDS)) {
    names['#' + k] = k;
    values[':' + k] = v;
    sets.push(`#${k} = if_not_exists(#${k}, :${k})`); // 只在缺該欄時才寫入
  }

  try {
    await ddb.send(new UpdateCommand({
      TableName: TABLE,
      Key: { key: 'main' },
      UpdateExpression: 'SET ' + sets.join(', '),
      ExpressionAttributeNames: names,
      ExpressionAttributeValues: values,
      ConditionExpression: 'attribute_exists(#key)' // main 必須已存在(S0 已建);否則請先跑 seed
    }));
  } catch (err) {
    if (err.name === 'ConditionalCheckFailedException') {
      throw new Error('config main 不存在,請先跑 seed_shrine_config.js 建立再 patch');
    }
    throw err;
  }

  // 讀回驗證
  const { Item } = await ddb.send(new GetCommand({ TableName: TABLE, Key: { key: 'main' } }));
  const missing = Object.keys(FIELDS).filter(k => Item[k] === undefined);
  const axes = new Set(['zaiun', 'shengun', 'zhiun', 'body', 'renyuan', 'xingyun']);
  const badAxis = Object.entries(Item.omamoriTypes || {}).filter(([, v]) => !axes.has(v.axis)).map(([k]) => k);

  console.log('讀回 key=main:');
  console.log('  omamoriTypes 型別數:', Object.keys(Item.omamoriTypes || {}).length, '(應 6)');
  console.log('  yakuHaraiMode:', Item.yakuHaraiMode, '| yakuHaraiRechargeable:', Item.yakuHaraiRechargeable);
  if (missing.length) { console.error('❌ 仍缺欄:', missing.join(',')); process.exit(1); }
  if (badAxis.length) { console.error('❌ omamoriTypes 非法軸:', badAxis.join(',')); process.exit(1); }
  console.log('✅ S2 config 欄位齊備、六軸合法(既有欄未被覆蓋)。');
}

main().catch(e => { console.error(e); process.exit(1); });
