// 甜甜火車大亨 — 型錄/目的地/平衡 config DAO(讀 published,惰性快取,fallback 保底)。
// 對齊 MahjongConfigDAO 慣例。放到 sweetbot-next/DAO/DDB/。
const DDBBaseDAO = require('./DDBBaseDAO');
const { GetCommand } = require('@aws-sdk/lib-dynamodb');

const TABLE_NAME = 'train-tycoon-config';
const CACHE_MS = 60 * 1000;

// 最小可玩 fallback(DDB 空/未 seed 也能跑;正式值由 config_seed.json 灌入覆蓋)。
const FALLBACK = {
  catalogs: {
    locomotives: [
      { id: 'd51', emoji: '🚂', name: 'D51', kind: 'freight', traction: 2, speed: 45, fuelEff: 0.45, priceTeeth: 1200, fuelPerTrip: 120, unlockTier: 1 },
      { id: 'kiha40', emoji: '🚉', name: 'キハ40', kind: 'both', traction: 3, speed: 60, fuelEff: 0.6, priceTeeth: 2200, fuelPerTrip: 100, unlockTier: 1 }
    ],
    cars: [
      { id: 'chi', kigo: 'チ', name: '平板車', kind: 'freight', capacity: 20, weight: 3, priceTeeth: 400, special: null },
      { id: 'koki', kigo: 'コキ', name: '貨櫃車', kind: 'freight', capacity: 34, weight: 5, priceTeeth: 1300, special: { goods: 'container' } }
    ],
    equipment: [],
    staff: []
  },
  destinations: [
    { id: 'npc_minato', name: 'みなと港町', emoji: '⚓', kind: 'npc', distance: 30, unlockTier: 1, freightDemand: { container: { qty: 40, priceRange: [80, 130] } }, passengerDemand: 60, heat: 1.0 }
  ],
  balance: {
    openCostTeeth: 500,
    reviveCostTeeth: 300,
    worldTickMinutes: 10,
    fuelUnitPrice: 1.0,
    fareBase: 12,
    fareElasticity: 0.9,
    distanceToMinutes: 1.2,
    onTimeBonus: 0.15,
    latePenalty: 0.25,
    eventProb: { delay: 0.1, breakdown: 0.06, weather: 0.05, surge: 0.08, vip: 0.03 },
    tierUpgradeCostTeeth: [0, 3000, 12000, 40000, 120000, 350000],
    tierPlatformCap: [1, 2, 3, 4, 5, 7],
    bankruptcy: { deficitTicksToClose: 8, minReserve: 0 }
  }
};

const clone = (o) => JSON.parse(JSON.stringify(o));

class TrainTycoonConfigDAO extends DDBBaseDAO {
  constructor () {
    super(TABLE_NAME);
    this.cache = { at: 0, config: null };
  }

  async getPublished (section) {
    const res = await this.ddb.send(new GetCommand({
      TableName: this.tableName,
      Key: { section: String(section), state: 'published' }
    }));
    return res.Item?.data || null;
  }

  async getGameConfig () {
    if (this.cache.config && Date.now() - this.cache.at < CACHE_MS) return clone(this.cache.config);
    const [catalogs, destinations, balance] = await Promise.all([
      this.getPublished('catalogs').catch(() => null),
      this.getPublished('destinations').catch(() => null),
      this.getPublished('balance').catch(() => null)
    ]);
    const config = {
      catalogs: (catalogs && typeof catalogs === 'object') ? { ...clone(FALLBACK.catalogs), ...catalogs } : clone(FALLBACK.catalogs),
      destinations: (Array.isArray(destinations) && destinations.length) ? destinations : clone(FALLBACK.destinations),
      balance: (balance && typeof balance === 'object') ? { ...clone(FALLBACK.balance), ...balance } : clone(FALLBACK.balance)
    };
    config.balance.bankruptcy = { ...clone(FALLBACK.balance.bankruptcy), ...(config.balance.bankruptcy || {}) };
    this.cache = { at: Date.now(), config: clone(config) };
    return config;
  }
}

module.exports = TrainTycoonConfigDAO;
