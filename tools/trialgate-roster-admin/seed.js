#!/usr/bin/env node
process.env.NODE_PATH = [
  process.env.NODE_PATH,
  '/opt/sml/sweetbot-next/node_modules'
].filter(Boolean).join(':');
require('module').Module._initPaths();

const path = require('path');
const { DynamoDBClient, CreateTableCommand, DescribeTableCommand } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, PutCommand } = require('@aws-sdk/lib-dynamodb');

const REGION = process.env.AWS_REGION || 'ap-southeast-1';
const TABLE = process.env.TRIALGATE_LAYERS_TABLE || 'sweetbot-trialgate-layers';
const CONFIG_PATH = process.env.TRIALGATE_CONFIG ||
  '/opt/sml/sweetbot-next/const/trialGateLayers.js';
const BLESSINGS_PATH = process.env.TRIALGATE_BLESSINGS ||
  '/opt/sml/sweetbot-next/const/trialGateBlessings.js';
const TEXTS_PATH = process.env.TRIALGATE_TEXTS ||
  '/opt/sml/sweetbot-next/const/trialGateTexts.js';
const PROPS_ENUM_PATH = process.env.RPG_PROPS_ENUM ||
  '/opt/sml/sweetbot-next/const/rpgPropsEnum.js';
const EMOJI_PATH = process.env.SWEETBOT_EMOJI ||
  '/opt/sml/sweetbot-next/const/emoji.js';

const ddbRaw = new DynamoDBClient({ region: REGION });
const ddb = DynamoDBDocumentClient.from(ddbRaw);

async function ensureTable () {
  try {
    await ddbRaw.send(new DescribeTableCommand({ TableName: TABLE }));
    return;
  } catch (e) {
    if (e.name !== 'ResourceNotFoundException') throw e;
  }
  await ddbRaw.send(new CreateTableCommand({
    TableName: TABLE,
    BillingMode: 'PAY_PER_REQUEST',
    AttributeDefinitions: [{ AttributeName: 'layer', AttributeType: 'S' }],
    KeySchema: [{ AttributeName: 'layer', KeyType: 'HASH' }]
  }));
  for (let i = 0; i < 30; i++) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    const r = await ddbRaw.send(new DescribeTableCommand({ TableName: TABLE }));
    if (r.Table?.TableStatus === 'ACTIVE') return;
  }
  throw new Error(`table ${TABLE} not ACTIVE after wait`);
}

async function put (item) {
  await ddb.send(new PutCommand({ TableName: TABLE, Item: item }));
}

function buildItems (rpgPropsEnum, emoji) {
  const items = {};
  for (const [key, prop] of Object.entries(rpgPropsEnum)) {
    if (!prop || !Number.isInteger(Number(prop.id)) || Number(prop.id) <= 0) continue;
    const emojiKey = key.toUpperCase();
    items[String(prop.id)] = {
      name: prop.name || key,
      img: '',
      emoji: emoji[emojiKey] || '',
      emojiPending: false
    };
  }
  return items;
}

async function main () {
  const resolved = path.resolve(CONFIG_PATH);
  const blessingsResolved = path.resolve(BLESSINGS_PATH);
  const textsResolved = path.resolve(TEXTS_PATH);
  const propsResolved = path.resolve(PROPS_ENUM_PATH);
  const emojiResolved = path.resolve(EMOJI_PATH);
  delete require.cache[resolved];
  delete require.cache[blessingsResolved];
  delete require.cache[textsResolved];
  delete require.cache[propsResolved];
  delete require.cache[emojiResolved];
  const config = require(resolved);
  const blessings = require(blessingsResolved);
  const texts = require(textsResolved);
  const items = buildItems(require(propsResolved), require(emojiResolved));
  await ensureTable();
  await put({ layer: '__meta__', maxLayer: Number(config.maxLayer || 0), updatedAt: new Date().toISOString() });
  await put({ layer: '__blessings__', blessings, updatedAt: new Date().toISOString() });
  await put({ layer: '__texts__', texts, updatedAt: new Date().toISOString() });
  await put({ layer: '__items__', items, updatedAt: new Date().toISOString() });
  for (let i = 1; i <= Number(config.maxLayer || 0); i++) {
    const key = String(i);
    const layer = config.layers[key];
    if (!layer) throw new Error(`missing layer ${key}`);
    await put({
      layer: key,
      bosses: layer.bosses || [],
      award: layer.award || {},
      updatedAt: new Date().toISOString()
    });
  }
  console.log(`seeded ${config.maxLayer} trialgate layers, ${blessings.length} blessings, ${Object.keys(texts).length} texts, ${Object.keys(items).length} items into ${TABLE}`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
