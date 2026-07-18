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
    // 時限祝福制:buff 必須帶「有效未來到期」才算有效。缺 expireAt / 非數字 / 已過期 → 一律忽略
    // (否則無到期欄的髒 buff 會變永久加成)。
    if (typeof b.expireAt !== 'number' || b.expireAt <= nowEpoch) continue;
    axes[b.axis] += b.delta;
    buffDelta[b.axis] += b.delta;
  }

  // 3) 御守：活御守(未回收、未到期)→ 對應軸 +boost；過期未回收 → 穢れ按天扣 body（S2 擴充 A）
  const decay = (config.kegareDailyDecay != null) ? config.kegareDailyDecay : DEFAULT_SHRINE_CONFIG.kegareDailyDecay;
  const omamoriBoost = {};
  for (const a of AXES) omamoriBoost[a] = 0;
  let kegarePenalty = 0;
  for (const o of (omamori || [])) {
    if (!o || o.recycled) continue;               // 已回收 → 不計
    if (typeof o.expireAt !== 'number') continue; // 無到期欄 → 髒資料略過
    if (o.expireAt > nowEpoch) {
      // 活御守正向加成（未知 axis / boost 非數字 → 略過，比照 buff 防髒）
      if (AXES.includes(o.axis) && typeof o.boost === 'number') {
        axes[o.axis] += o.boost;
        omamoriBoost[o.axis] += o.boost;
      }
    } else {
      // 過期未回收 → 穢れ
      const daysExpired = Math.floor((nowEpoch - o.expireAt) / SEC_PER_DAY);
      if (daysExpired > 0) kegarePenalty += daysExpired * decay;
    }
  }
  axes.body -= kegarePenalty;

  // 4) 厄年 penalty（缺 gender 或 birthday → 不扣，保守）；本年已除厄 → 減免（S2 擴充 B）
  let yakuLevel = 'none';
  let yakuPenalty = 0;
  let yakuHaraied = false;
  if (birthday && /^\d{8}$/.test(String(birthday)) && (gender === 'male' || gender === 'female')) {
    const birthYear = parseInt(String(birthday).slice(0, 4), 10);
    const kazoe = taipeiYear(nowEpoch) - birthYear + 1;
    const yk = computeYaku(kazoe, gender);
    yakuLevel = yk.level;
    if (yk.level !== 'none') {
      const yp = config.yakuPenalty || DEFAULT_SHRINE_CONFIG.yakuPenalty;
      yakuPenalty += (yp[yk.level] || 0);
      if (yk.isTaiyaku && yk.level === 'honyaku') yakuPenalty += (yp.taiyakuExtra || 0);
      // 除厄：fortune.yakuHaraiYear === 本台北年 → clear 歸零 / half 減半（僅當年有效）
      if (fortune && fortune.yakuHaraiYear === taipeiYear(nowEpoch)) {
        const mode = config.yakuHaraiMode || DEFAULT_SHRINE_CONFIG.yakuHaraiMode;
        if (mode === 'half') { yakuPenalty = Math.round(yakuPenalty / 2); yakuHaraied = true; } else { yakuPenalty = 0; yakuHaraied = true; } // 預設 clear
      }
      axes.body += yakuPenalty; // penalty 為負值(除厄後可能為 0)
    }
  }

  // 5) clamp [0,100]
  for (const a of AXES) axes[a] = clamp(axes[a], 0, 100);

  // 6) 綜合運 = 六軸均值（整數）
  const sougou = Math.round(AXES.reduce((s, a) => s + axes[a], 0) / AXES.length);

  return {
    axes,
    sougou,
    breakdown: { base: fortune && fortune.base ? { ...fortune.base } : baseAxes(), buffDelta, omamoriBoost, kegarePenalty, yakuLevel, yakuPenalty, yakuHaraied }
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
  clamp,
  taipeiYear // S2-4:除厄年份與引擎同源(只加匯出,勿改邏輯)
};
