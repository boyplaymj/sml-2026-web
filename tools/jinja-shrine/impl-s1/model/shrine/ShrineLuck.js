// 甜甜神社 — 運氣引擎（S1 命門，純函式，不碰 DDB，可離線單測）。
// 規格見 repo tools/jinja-shrine/STAGE1.md。對齊報稅 TaxCalculator 純函式模式。
//
// 六軸有效值 = base(50) + 有效 buff + 穢れ(過期未回收御守) + 厄年 penalty，夾 [0,100]。
// nowEpoch 一律由呼叫端注入（不在此取現在時間），確保可測、可重現。

const { AXES, DEFAULT_SHRINE_CONFIG } = require('./defaults');

const SEC_PER_DAY = 86400;
const TAIPEI_OFFSET_SEC = 8 * 3600; // 厄年以台北曆年判定

function clamp (v, lo, hi) {
  return v < lo ? lo : (v > hi ? hi : v);
}

function baseAxes () {
  const o = {};
  for (const a of AXES) o[a] = 50;
  return o;
}

// nowEpoch(秒) → 台北曆年
function taipeiYear (nowEpoch) {
  return new Date((nowEpoch + TAIPEI_OFFSET_SEC) * 1000).getUTCFullYear();
}

// ── 厄年（数え年）─────────────────────────────────────────────
// 男 本厄 25/42(大厄)/61；女 本厄 19/33(大厄)/37/61。前厄=本厄-1、後厄=本厄+1。
const YAKU_HONYAKU = {
  male: [25, 42, 61],
  female: [19, 33, 37, 61]
};
const YAKU_TAIYAKU = { male: 42, female: 33 };

// kazoe(数え年) + gender → { level:'none'|'maeyaku'|'honyaku'|'atoyaku', isTaiyaku }
function computeYaku (kazoe, gender) {
  const honyakuAges = YAKU_HONYAKU[gender];
  if (!honyakuAges || !Number.isFinite(kazoe)) return { level: 'none', isTaiyaku: false };
  // 本厄優先
  for (const h of honyakuAges) {
    if (kazoe === h) return { level: 'honyaku', isTaiyaku: h === YAKU_TAIYAKU[gender] };
  }
  for (const h of honyakuAges) {
    if (kazoe === h - 1) return { level: 'maeyaku', isTaiyaku: false };
    if (kazoe === h + 1) return { level: 'atoyaku', isTaiyaku: false };
  }
  return { level: 'none', isTaiyaku: false };
}

// ── 主引擎 ───────────────────────────────────────────────────
// input: { fortune|null, omamori[]|[], nowEpoch, config?, birthday?('yyyymmdd'), gender?('male'|'female') }
// output: { axes{6軸}, sougou, breakdown }
function computeLuck (input) {
  const {
    fortune = null,
    omamori = [],
    nowEpoch,
    config = DEFAULT_SHRINE_CONFIG,
    birthday = null,
    gender = null
  } = input || {};

  // 1) base
  const axes = baseAxes();
  if (fortune && fortune.base) {
    for (const a of AXES) {
      if (typeof fortune.base[a] === 'number') axes[a] = fortune.base[a];
    }
  }

  // 2) 有效 buff（過期忽略、未知 axis 跳過）
  const buffDelta = {};
  for (const a of AXES) buffDelta[a] = 0;
  const buffs = (fortune && Array.isArray(fortune.buffs)) ? fortune.buffs : [];
  for (const b of buffs) {
    if (!b || !AXES.includes(b.axis) || typeof b.delta !== 'number') continue;
    if (typeof b.expireAt === 'number' && b.expireAt <= nowEpoch) continue; // 過期
    axes[b.axis] += b.delta;
    buffDelta[b.axis] += b.delta;
  }

  // 3) 穢れ：過期(expireAt<=now)且未回收的御守，按天扣 body
  const decay = (config.kegareDailyDecay != null) ? config.kegareDailyDecay : DEFAULT_SHRINE_CONFIG.kegareDailyDecay;
  let kegarePenalty = 0;
  for (const o of (omamori || [])) {
    if (!o || o.recycled) continue;
    if (typeof o.expireAt !== 'number' || o.expireAt > nowEpoch) continue; // 未到期
    const daysExpired = Math.floor((nowEpoch - o.expireAt) / SEC_PER_DAY);
    if (daysExpired > 0) kegarePenalty += daysExpired * decay;
  }
  axes.body -= kegarePenalty;

  // 4) 厄年 penalty（缺 gender 或 birthday → 不扣，保守）
  let yakuLevel = 'none';
  let yakuPenalty = 0;
  if (birthday && /^\d{8}$/.test(String(birthday)) && (gender === 'male' || gender === 'female')) {
    const birthYear = parseInt(String(birthday).slice(0, 4), 10);
    const kazoe = taipeiYear(nowEpoch) - birthYear + 1;
    const yk = computeYaku(kazoe, gender);
    yakuLevel = yk.level;
    if (yk.level !== 'none') {
      const yp = config.yakuPenalty || DEFAULT_SHRINE_CONFIG.yakuPenalty;
      yakuPenalty += (yp[yk.level] || 0);
      if (yk.isTaiyaku && yk.level === 'honyaku') yakuPenalty += (yp.taiyakuExtra || 0);
      axes.body += yakuPenalty; // penalty 為負值
    }
  }

  // 5) clamp [0,100]
  for (const a of AXES) axes[a] = clamp(axes[a], 0, 100);

  // 6) 綜合運 = 六軸均值（整數）
  const sougou = Math.round(AXES.reduce((s, a) => s + axes[a], 0) / AXES.length);

  return {
    axes,
    sougou,
    breakdown: { base: fortune && fortune.base ? { ...fortune.base } : baseAxes(), buffDelta, kegarePenalty, yakuLevel, yakuPenalty }
  };
}

// ── 公式 helper（純，export 供 S4 各遊戲；PvP 不動勝率鐵律見 STAGE1 §3）─────
function revenueMultiplier (v, div) {
  const d = div || DEFAULT_SHRINE_CONFIG.luckCoef.revenueDiv;
  return 1 + (v - 50) / d;
}
function probWeight (w, v, div) {
  const d = div || DEFAULT_SHRINE_CONFIG.luckCoef.probDiv;
  return Math.max(0, w * (1 + (v - 50) / d));
}
function resistFactor (v, div) {
  const d = div || DEFAULT_SHRINE_CONFIG.luckCoef.resistDiv;
  return 1 - (v - 50) / d;
}

module.exports = {
  AXES,
  baseAxes,
  computeYaku,
  computeLuck,
  revenueMultiplier,
  probWeight,
  resistFactor,
  clamp
};
