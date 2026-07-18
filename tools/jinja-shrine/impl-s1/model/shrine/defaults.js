// 甜甜神社 — 引擎預設值(鏡射 migration/seed_shrine_config.js 的 config#main)。
// 用於:純引擎單測、config 讀取失敗時 fail-safe fallback。
// 若後台改了 config,執行時以 DDB config 為準;這裡只是骨架與測試錨。

// 六軸英文 key(正典;順序固定供彙總)
const AXES = ['zaiun', 'shengun', 'zhiun', 'body', 'renyuan', 'xingyun'];

const DEFAULT_SHRINE_CONFIG = {
  key: 'main',
  version: 1,
  fees: {
    harai: 0, honden: 200, okumiya: 500, goshuin: 150, omamori: 300,
    ofuda: 250, taima: 200, ema: 100, gokitou: 800, pillarMin: 1000
  },
  omikujiWeights: {
    大吉: 6, 吉: 14, 中吉: 16, 小吉: 16, 末吉: 12, 末小吉: 8,
    凶: 12, 小凶: 6, 半凶: 4, 末凶: 4, 大凶: 2
  },
  buff: {
    baseTtlSec: 86400,
    rankTtlMultiplier: { 大吉: 3, 吉: 2, 中吉: 1.5, 小吉: 1.2, 末吉: 1, 末小吉: 1, 凶: 1, 小凶: 1, 半凶: 1, 末凶: 1, 大凶: 1 }
  },
  omamoriTtlDays: 365,
  kegareDailyDecay: 1,
  meritOnRecycle: 50,
  yakuPenalty: { maeyaku: -3, honyaku: -6, atoyaku: -3, taiyakuExtra: -4 },
  luckCoef: { revenueDiv: 500, probDiv: 250, resistDiv: 200 },
  market: { enabled: false, note: '' }
};

module.exports = { AXES, DEFAULT_SHRINE_CONFIG };
