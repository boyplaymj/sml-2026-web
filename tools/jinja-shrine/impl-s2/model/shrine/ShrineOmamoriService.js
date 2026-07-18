// 甜甜神社 — 請御守 service(S2-2)。
// grant(discordId, type) = 授與所請御守:驗 type → 先查餘額 → 扣牙齒 → 寫 omamori 表(失敗退款)。
// 🛡️ 鐵律:餘額不足不扣不寫;put 失敗必退款;絕不 throw 給呼叫端,一律回 {ok, reason}。
// axis/boost/fee 一律來自 config(getMain 可能 null/缺欄 → fallback DEFAULT_SHRINE_CONFIG)。
const crypto = require('crypto');
const { DEFAULT_SHRINE_CONFIG } = require('./defaults');

class ShrineOmamoriService {
  // deps 可注入:{ viewerDetailDAO, omamoriDAO, configDAO, fortuneDAO }(測試用 stub)
  constructor (deps = {}) {
    this._deps = deps;
  }

  _daos () {
    if (this._resolved) return this._resolved;
    const d = this._deps;
    const OmamoriDAO = require('../../DAO/DDB/ShrineOmamoriDAO.js');
    const ConfigDAO = require('../../DAO/DDB/ShrineConfigDAO.js');
    const ViewerDetailDAO = require('../../DAO/DDB/ViewerDetailDAO.js');
    const FortuneDAO = require('../../DAO/DDB/ShrineFortuneDAO.js');
    this._resolved = {
      viewerDetailDAO: d.viewerDetailDAO || new ViewerDetailDAO(),
      omamoriDAO: d.omamoriDAO || new OmamoriDAO(),
      configDAO: d.configDAO || new ConfigDAO(),
      fortuneDAO: d.fortuneDAO || new FortuneDAO()
    };
    return this._resolved;
  }

  // grant(discordId, type, nowEpoch?) → { ok:true, omamori } | { ok:false, reason, need?, have? }
  async grant (discordId, type, nowEpoch = Math.floor(Date.now() / 1000)) {
    try {
      const { viewerDetailDAO, omamoriDAO, configDAO } = this._daos();

      // 1) config(deep-merge DEFAULT:getMain 可能 null/缺欄/拋錯)
      let cfg = null;
      try { cfg = await configDAO.getMain(); } catch (_) { cfg = null; }
      cfg = cfg || {};
      // 真正 deep-merge:後台若只留部分 type(partial map),其餘 type 仍由 DEFAULT 補齊
      // (原淺 fallback「整包取代」會讓後台刪一種→其餘變 unknown_type;Codex S2-2 Non-blocking)。
      const omamoriTypes = { ...DEFAULT_SHRINE_CONFIG.omamoriTypes, ...(cfg.omamoriTypes || {}) };
      const ttlDays = (cfg.omamoriTtlDays != null) ? cfg.omamoriTtlDays : DEFAULT_SHRINE_CONFIG.omamoriTtlDays;

      // 驗 type 合法
      const typeDef = omamoriTypes ? omamoriTypes[type] : null;
      if (!typeDef) return { ok: false, reason: 'unknown_type' };

      // 2) fee/axis/boost 缺欄 → 逐欄 fallback DEFAULT(不硬寫數值)
      const defDef = DEFAULT_SHRINE_CONFIG.omamoriTypes[type] || {};
      const fee = (typeDef.fee != null) ? typeDef.fee
        : (defDef.fee != null) ? defDef.fee
          : DEFAULT_SHRINE_CONFIG.fees.omamori;
      const axis = (typeDef.axis != null) ? typeDef.axis : defDef.axis;
      const boost = (typeDef.boost != null) ? typeDef.boost : defDef.boost;

      // 3) 先查餘額(givePoint 用 ADD 不擋負餘額、內部吞錯 → 必先查)。不足=不扣不寫。
      const viewer = await viewerDetailDAO.selectOne({ discordId: String(discordId) });
      const balance = (viewer && typeof viewer.point === 'number') ? viewer.point : 0;
      if (balance < fee) return { ok: false, reason: 'insufficient', need: fee, have: balance };

      // 4) 扣款
      await viewerDetailDAO.givePoint([String(discordId)], -fee, 'point', `請御守:${type}`);

      // 5) 建 item(§2 schema)
      const item = {
        discordId: String(discordId),
        sk: 'omamori#' + crypto.randomUUID(),
        type,
        axis,
        boost,
        acquiredAt: nowEpoch,
        expireAt: nowEpoch + ttlDays * 86400,
        recycled: false,
        source: 'juyosho'
      };

      // 6) 寫表;put 失敗 → 退款(金額相同、reason 標明退款)
      try {
        await omamoriDAO.put(item);
      } catch (err) {
        console.warn(`[ShrineOmamori] put failed for ${discordId} type=${type}, refunding:`, err && err.message);
        try {
          await viewerDetailDAO.givePoint([String(discordId)], fee, 'point', `請御守退款:${type}`);
        } catch (refundErr) {
          console.warn(`[ShrineOmamori] REFUND FAILED for ${discordId} fee=${fee}:`, refundErr && refundErr.message);
        }
        return { ok: false, reason: 'write_failed' };
      }

      // 7) 成功
      return { ok: true, omamori: item };
    } catch (err) {
      console.warn(`[ShrineOmamori] grant unexpected error for ${discordId}:`, err && err.message);
      return { ok: false, reason: 'error' };
    }
  }

  // recycle(discordId, sk) → { ok:true, merit } | { ok:false, reason }
  // 古札納所回收:御守標 recycled=true(引擎即不再算穢れ)→ 給功德值。
  // 🛡️ 鐵律:先條件寫回收成功、才給功德(冪等,功德只給一次);絕不 throw。
  async recycle (discordId, sk) {
    try {
      const { omamoriDAO, fortuneDAO, configDAO } = this._daos();
      // 1) config deep-merge → meritOnRecycle(缺→DEFAULT.meritOnRecycle=50)
      let cfg = null;
      try { cfg = await configDAO.getMain(); } catch (_) { cfg = null; }
      cfg = cfg || {};
      const merit = (cfg.meritOnRecycle != null) ? cfg.meritOnRecycle : DEFAULT_SHRINE_CONFIG.meritOnRecycle;

      // 2) 條件寫回收(原子);false=已回收/不存在 → 冪等不給功德
      const done = await omamoriDAO.recycle(discordId, sk);
      if (!done) return { ok: false, reason: 'already_recycled_or_missing' };

      // 3) 成功回收才給功德(原子累加)。若 addMerit 罕見失敗:御守已回收但功德沒入
      //    → 落 catch 記 warn(S3 可補償;本格不做補償交易)。
      await fortuneDAO.addMerit(discordId, merit);
      return { ok: true, merit };
    } catch (err) {
      console.warn(`[ShrineOmamori] recycle error for ${discordId} sk=${sk}:`, err && err.message);
      return { ok: false, reason: 'error' };
    }
  }
}

module.exports = ShrineOmamoriService;
