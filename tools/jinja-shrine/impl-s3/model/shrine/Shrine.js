// 甜甜神社 — 境內面板模組(S3-0a-i:純核心)。
// 本檔只放「可離線單測的純邏輯」:定點解析/導覽選項/面板 embed/失礼判定。
// Discord 互動 handler(!神社 / shrenter / shrbow / shrnav)留 S3-0a-ii 再接;
// commands/buttons/selects 先留空陣列,discord.js 端接線也留下一格。
// 鐵律:純方法絕不 throw 給呼叫端(未知 key → null / fallback torii)。
const { EmbedBuilder } = require('discord.js');
const MAP = require('./mapPositions.js');

// ── 風味文字(HANDOFF-S3-0a §3;無運氣數值、純情境)──
const FLAVOR = {
  torii: '參道の入口。鳥居をくぐって境內へ。',
  ichiba: '表參道の市集。掘り出し物があるかも。',
  kosatsu: '古札納所。古いお守りやお札を納める所。',
  temizu: '手水舍。參拜の前に心身を清めよう。',
  honden: '本殿。麻雀大明神が祀られている。',
  juyosho: '授與所。お守りや神札を授かれる。',
  goshuin: '御朱印受付所。參拜の証をいただこう。',
  gokitou: '御祈禱受付所。厄を祓う場所。',
  okusha_stair: '奧社への石段。この先の試煉を越えた者だけが辿り着ける。'
};

// ── 失礼(放置未退場礼)罰則(config 可調:哪軸/幾點/幾天)──
// 綜合運=六軸衍生值 → 扣「厄除(body)」一軸當代表;computeLuck 既有 buff 路徑會吃到。
const SHITSUREI = { axis: 'body', delta: -5, days: 3, source: 'shitsurei_taijou' };

// ── 導覽選單 9 設施(HANDOFF-S3-0a §2;value=location key,奧社→okusha_stair)──
const NAV_FACILITIES = [
  { label: '鳥居', emoji: '⛩️', value: 'torii' },
  { label: '表參道の市集', emoji: '🎪', value: 'ichiba' },
  { label: '古札納所', emoji: '♻️', value: 'kosatsu' },
  { label: '手水舍', emoji: '💧', value: 'temizu' },
  { label: '本殿', emoji: '⛩️', value: 'honden' },
  { label: '授與所', emoji: '🏪', value: 'juyosho' },
  { label: '御朱印受付所', emoji: '📿', value: 'goshuin' },
  { label: '御祈禱受付所', emoji: '🙏', value: 'gokitou' },
  { label: '奧社', emoji: '⛰️', value: 'okusha_stair' }
];

class Shrine {
  // 簽名比照 DailyQuest(connection, redis);deps 可注入 stub 供測(比照 ShrineOmamoriService)。
  constructor (connection, redis, deps = {}) {
    this.connection = connection;
    this.redis = redis;
    this._deps = deps;

    // handler 留 S3-0a-ii:先空陣列,discord.js 端也還沒接線。
    this.commands = [];
    this.buttons = [];
    this.selects = [];
  }

  // lazy require DAO(比照 ShrineOmamoriService._daos();測試可注入 fortuneDAO stub)
  _daos () {
    if (this._resolved) return this._resolved;
    const d = this._deps;
    const FortuneDAO = require('../../DAO/DDB/ShrineFortuneDAO.js');
    this._resolved = {
      fortuneDAO: d.fortuneDAO || new FortuneDAO()
    };
    return this._resolved;
  }

  // ── 純方法(不碰 interaction)────────────────────────────────

  // location key → location 物件(name/image/facility/sidebarRow…);未知 → null。
  resolveLocation (key) {
    if (!key) return null;
    return MAP.locations.find((l) => l.key === key) || null;
  }

  // 導覽下拉 9 選項 [{label,emoji,value}](value=location key)。
  navFacilities () {
    return NAV_FACILITIES.map((o) => ({ ...o }));
  }

  // 設施面板 embed。未知 key → fallback torii(絕不 throw)。
  _panel (locKey) {
    const loc = this.resolveLocation(locKey) || this.resolveLocation(MAP.entry);
    const flavor = FLAVOR[loc.key] || '';
    return new EmbedBuilder()
      .setTitle('⛩️ 甜甜神社')
      .setDescription('**' + loc.name + '**\n' + flavor)
      .setColor(0xC0392B)
      .setImage(MAP.cdnBase + loc.image);
  }

  // 進場 lazy 失礼判定:上一趟 lastVisit 存在且 closed===false(放置未一礼退場)
  // → 回負 buff(扣 body、3 天過期);乾淨退場(closed:true)或無紀錄 → null(不扣)。
  _shitsureiOnEnter (oldLastVisit, nowEpoch) {
    if (oldLastVisit && oldLastVisit.closed === false) {
      return {
        axis: SHITSUREI.axis,
        delta: SHITSUREI.delta,
        expireAt: nowEpoch + SHITSUREI.days * 86400,
        source: SHITSUREI.source
      };
    }
    return null;
  }
}

module.exports = Shrine;
module.exports.FLAVOR = FLAVOR;
module.exports.SHITSUREI = SHITSUREI;
