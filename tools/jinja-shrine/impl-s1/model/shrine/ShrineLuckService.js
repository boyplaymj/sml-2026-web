// 甜甜神社 — getLuck 存取器（S1 薄包：DAO → computeLuck → 快取 60s → fail-safe 50）。
// 供跨遊戲（S4）呼叫。DAO 可注入以利單測。
// 🛡️ fail-safe 鐵律：任何錯/查無/未知 axis → 回 50，絕不 throw 給呼叫端遊戲。
const { AXES, computeLuck } = require('./ShrineLuck');
const { DEFAULT_SHRINE_CONFIG } = require('./defaults');

const CACHE_TTL_MS = 60 * 1000;
const BASELINE = 50;

class ShrineLuckService {
  // deps 可注入：{ fortuneDAO, omamoriDAO, configDAO, viewerDAO }（測試用 stub）
  constructor (deps = {}) {
    this._deps = deps;
    this._cache = new Map(); // discordId -> { at, result }
  }

  _daos () {
    if (this._resolved) return this._resolved;
    const d = this._deps;
    const FortuneDAO = require('../../DAO/DDB/ShrineFortuneDAO.js');
    const OmamoriDAO = require('../../DAO/DDB/ShrineOmamoriDAO.js');
    const ConfigDAO = require('../../DAO/DDB/ShrineConfigDAO.js');
    const ViewerDAO = require('../../DAO/DDB/ViewerDAO.js');
    this._resolved = {
      fortuneDAO: d.fortuneDAO || new FortuneDAO(),
      omamoriDAO: d.omamoriDAO || new OmamoriDAO(),
      configDAO: d.configDAO || new ConfigDAO(),
      viewerDAO: d.viewerDAO || new ViewerDAO()
    };
    return this._resolved;
  }

  // 取整包（後台/多軸一次用）。永不 throw：出錯回 base 50 包。
  async getLuckAll (discordId, nowMs = Date.now(), nowEpoch = Math.floor(Date.now() / 1000)) {
    const cached = this._cache.get(String(discordId));
    if (cached && (nowMs - cached.at) < CACHE_TTL_MS) return cached.result;
    let result;
    try {
      const { fortuneDAO, omamoriDAO, configDAO, viewerDAO } = this._daos();
      const [fortune, omamori, config, viewer] = await Promise.all([
        fortuneDAO.getByPlayer(discordId),
        omamoriDAO.listByPlayer(discordId),
        configDAO.getMain(),
        viewerDAO.getByDcID(String(discordId)).catch(() => null)
      ]);
      const birthday = viewer && viewer.birthday ? String(viewer.birthday).replace(/-/g, '') : null;
      const gender = (fortune && fortune.gender) || null; // gender 由 S2 御祈禱補收
      result = computeLuck({
        fortune,
        omamori: omamori || [],
        nowEpoch,
        config: config || DEFAULT_SHRINE_CONFIG,
        birthday,
        gender
      });
    } catch (err) {
      console.warn(`[ShrineLuck] getLuckAll fail-safe for ${discordId}:`, err && err.message);
      result = this._baseResult();
    }
    this._cache.set(String(discordId), { at: nowMs, result });
    return result;
  }

  // 取單軸有效值。未知 axis 或任何問題 → 50。
  async getLuck (discordId, axis, nowMs = Date.now(), nowEpoch = Math.floor(Date.now() / 1000)) {
    if (!AXES.includes(axis)) return BASELINE;
    try {
      const r = await this.getLuckAll(discordId, nowMs, nowEpoch);
      const v = r && r.axes ? r.axes[axis] : undefined;
      return (typeof v === 'number') ? v : BASELINE;
    } catch (_) {
      return BASELINE;
    }
  }

  invalidate (discordId) { this._cache.delete(String(discordId)); }

  _baseResult () {
    const axes = {};
    for (const a of AXES) axes[a] = BASELINE;
    return { axes, sougou: BASELINE, breakdown: { base: { ...axes }, buffDelta: {}, kegarePenalty: 0, yakuLevel: 'none', yakuPenalty: 0 } };
  }
}

module.exports = ShrineLuckService;
