// 甜甜神社 — 御祈禱受付所 厄年除厄 service(S2-4)。
// harai(discordId, gender) = 依生日算数え年厄年,逢厄年才收費除厄,記 yakuHaraiYear 接引擎 B。
// 🛡️ 鐵律:年份一律用引擎同源 taipeiYear(不得自算);非厄年/同年已除 → 不收費;
//         先驗後扣款;寫失敗退款;絕不 throw,一律回 {ok, reason}。
const { computeYaku, taipeiYear } = require('./ShrineLuck');
const { DEFAULT_SHRINE_CONFIG } = require('./defaults');

class ShrineHaraiService {
  // deps 可注入:{ fortuneDAO, viewerDAO, viewerDetailDAO, configDAO }(測試用 stub)
  constructor (deps = {}) {
    this._deps = deps;
  }

  _daos () {
    if (this._resolved) return this._resolved;
    const d = this._deps;
    const FortuneDAO = require('../../DAO/DDB/ShrineFortuneDAO.js');
    const ViewerDAO = require('../../DAO/DDB/ViewerDAO.js');
    const ViewerDetailDAO = require('../../DAO/DDB/ViewerDetailDAO.js');
    const ConfigDAO = require('../../DAO/DDB/ShrineConfigDAO.js');
    this._resolved = {
      fortuneDAO: d.fortuneDAO || new FortuneDAO(),
      viewerDAO: d.viewerDAO || new ViewerDAO(),
      viewerDetailDAO: d.viewerDetailDAO || new ViewerDetailDAO(),
      configDAO: d.configDAO || new ConfigDAO()
    };
    return this._resolved;
  }

  // harai(discordId, gender, nowEpoch?) → { ok:true, yakuLevel, year, fee } | { ok:false, reason }
  // 御祈禱除厄:驗 gender+生日→算厄年→在厄年才收費除厄→記 yakuHaraiYear(接引擎 B)。
  async harai (discordId, gender, nowEpoch = Math.floor(Date.now() / 1000)) {
    try {
      const { fortuneDAO, viewerDAO, viewerDetailDAO, configDAO } = this._daos();

      // 1) gender 必填且合法
      if (gender !== 'male' && gender !== 'female') return { ok: false, reason: 'gender_required' };

      // 2) config(缺→DEFAULT):fee=fees.gokitou、rechargeable=yakuHaraiRechargeable
      let cfg = null;
      try { cfg = await configDAO.getMain(); } catch (_) { cfg = null; }
      cfg = cfg || {};
      const fee = (cfg.fees && cfg.fees.gokitou != null) ? cfg.fees.gokitou : DEFAULT_SHRINE_CONFIG.fees.gokitou;
      const rechargeable = (cfg.yakuHaraiRechargeable != null) ? cfg.yakuHaraiRechargeable : DEFAULT_SHRINE_CONFIG.yakuHaraiRechargeable;

      // 3) 生日(ViewerDAO；YYYY-MM-DD → yyyymmdd),缺/非 8 碼 → birthday_required
      const viewer = await viewerDAO.getByDcID(String(discordId));
      const birthday = (viewer && viewer.birthday) ? String(viewer.birthday).replace(/-/g, '') : null;
      if (!birthday || !/^\d{8}$/.test(birthday)) return { ok: false, reason: 'birthday_required' };

      // 4) 算厄年(用引擎同源 taipeiYear + computeYaku);非厄年 → 不收費
      const year = taipeiYear(nowEpoch);
      const kazoe = year - parseInt(birthday.slice(0, 4), 10) + 1;
      const yk = computeYaku(kazoe, gender);
      if (yk.level === 'none') return { ok: false, reason: 'not_in_yakudoshi' };

      // 5) 同年冪等:本年已除厄且不可重複 → already_haraied(不收費)
      const fortune = await fortuneDAO.getByPlayer(discordId);
      if (fortune && fortune.yakuHaraiYear === year && !rechargeable) return { ok: false, reason: 'already_haraied' };

      // 6) 先查餘額(不足不扣不寫)
      const detail = await viewerDetailDAO.selectOne({ discordId: String(discordId) });
      const balance = (detail && typeof detail.point === 'number') ? detail.point : 0;
      if (balance < fee) return { ok: false, reason: 'insufficient', need: fee, have: balance };

      // 7) 扣款
      await viewerDetailDAO.givePoint([String(discordId)], -fee, 'point', '御祈禱除厄');

      // 8) 寫 yakuHaraiYear(+gender);失敗退款
      try {
        await fortuneDAO.setYakuHarai(discordId, year, gender);
      } catch (err) {
        console.warn(`[ShrineHarai] setYakuHarai failed for ${discordId}, refunding:`, err && err.message);
        try { await viewerDetailDAO.givePoint([String(discordId)], fee, 'point', '御祈禱除厄退款'); }
        catch (re) { console.warn(`[ShrineHarai] REFUND FAILED ${discordId} fee=${fee}:`, re && re.message); }
        return { ok: false, reason: 'write_failed' };
      }

      return { ok: true, yakuLevel: yk.level, year, fee };
    } catch (err) {
      console.warn(`[ShrineHarai] harai error for ${discordId}:`, err && err.message);
      return { ok: false, reason: 'error' };
    }
  }
}

module.exports = ShrineHaraiService;
