// Seed:甜甜神社後台設定(sweetbot-shrine-config, key='main')。
//   規格見 repo tools/jinja-shrine/STAGE0.md / DESIGN.md。所有數值後台可即時調(煞車)。
//   冪等:僅在 main 列「不存在」時寫入,避免重跑覆蓋後台已改的值。
//   要強制重置預設值:node migration/seed_shrine_config.js --force
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, PutCommand } = require('@aws-sdk/lib-dynamodb');

const REGION = 'ap-southeast-1';
const TABLE = 'sweetbot-shrine-config';
const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }));
const FORCE = process.argv.includes('--force');

const DEFAULT_CONFIG = {
  key: 'main',
  version: 1,
  // 各設施牙齒費用(手水免費)
  fees: {
    harai: 0,       // 手水舍(洗手,免費)
    honden: 200,    // 參拜主殿(抽籤)
    okumiya: 500,   // 奧社(高階深參拜)
    goshuin: 150,   // 御朱印
    omamori: 300,   // 御守授與
    ofuda: 250,     // 神札
    taima: 200,     // 大麻(祓串)
    ema: 100,       // 繪馬
    gokitou: 800,   // 御祈禱(消災解厄)
    pillarMin: 1000 // 石柱最低捐獻
  },
  // 籤階權重(抽 rank 用,總和不必=100,程式按比例)
  omikujiWeights: {
    大吉: 6, 吉: 14, 中吉: 16, 小吉: 16, 末吉: 12, 末小吉: 8,
    凶: 12, 小凶: 6, 半凶: 4, 末凶: 4, 大凶: 2
  },
  // 祝福 buff 時效(秒)。基礎 24h;籤階越高時效越長(倍率)。
  buff: {
    baseTtlSec: 86400,
    rankTtlMultiplier: { 大吉: 3, 吉: 2, 中吉: 1.5, 小吉: 1.2, 末吉: 1, 末小吉: 1, 凶: 1, 小凶: 1, 半凶: 1, 末凶: 1, 大凶: 1 }
  },
  omamoriTtlDays: 365,     // 御守效期一年
  kegareDailyDecay: 1,     // 每張過期未回收御守,每日扣 body/綜合運
  meritOnRecycle: 50,      // 回收一張御守給的功德值
  // 厄年 body penalty(数え年;男25/42/61 女19/33/37/61,大厄=42/33 額外加重)
  yakuPenalty: { maeyaku: -3, honyaku: -6, atoyaku: -3, taiyakuExtra: -4 },
  // §1.2 運氣→遊戲修正係數(除數越大影響越小,後台可調緊煞車)
  luckCoef: { revenueDiv: 500, probDiv: 250, resistDiv: 200 },
  // 市集活動(Phase 擴充點)
  market: { enabled: false, note: '' },
  // ── S2：御守型別(型→軸+持有加成 boost+費) 與 除厄模式 ──
  omamoriTypes: {
    kinunmori: { axis: 'zaiun', boost: 6, fee: 300 }, // 金運守
    shoumori: { axis: 'shengun', boost: 6, fee: 300 }, // 勝守
    gakugyomori: { axis: 'zhiun', boost: 6, fee: 300 }, // 學業守
    kenkoumori: { axis: 'body', boost: 6, fee: 300 }, // 健康守
    enmusubi: { axis: 'renyuan', boost: 6, fee: 300 }, // 縁結守
    koutsuu: { axis: 'xingyun', boost: 6, fee: 300 } // 交通安全守
  },
  yakuHaraiMode: 'clear', // clear=本年歸零 | half=減半
  yakuHaraiRechargeable: false, // 同台北年可否重複除厄收費
  updatedAt: Math.floor(Date.now() / 1000)
};

async function main () {
  const params = {
    TableName: TABLE,
    Item: DEFAULT_CONFIG
  };
  if (!FORCE) {
    params.ConditionExpression = 'attribute_not_exists(#k)';
    params.ExpressionAttributeNames = { '#k': 'key' };
  }
  try {
    await ddb.send(new PutCommand(params));
    console.log(`已寫入 shrine config main(${FORCE ? '強制覆蓋' : '初次建立'})。`);
  } catch (err) {
    if (err.name === 'ConditionalCheckFailedException') {
      console.log('shrine config main 已存在,跳過(用 --force 覆蓋)。');
      return;
    }
    throw err;
  }
}

main().catch((err) => { console.error('seed config 失敗:', err); process.exit(1); });
