// 甜甜神社 — 境內面板模組(S3-0a:純核心 + 面板互動)。
// 純邏輯(可離線單測):定點解析/導覽選項/面板 embed/失礼判定/component 組裝。
// 互動 handler(S3-0a-ii):!神社 公開入口 → shrenter 開 ephemeral 面板(lazy 失礼結算+openVisit)
// → shrbow-in 一礼硬門解鎖導覽 → shrnav 移動換圖 → shrbow-out 退場礼(closeVisit)。
// 鐵律:純方法絕不 throw 給呼叫端(未知 key → null / fallback torii);handler 絕不讓例外炸掉互動。
const { EmbedBuilder, ActionRowBuilder, ButtonBuilder, StringSelectMenuBuilder } = require('discord.js');
const DiscordButtonHelper = require('../../helper/DiscordButtonHelper.js');
const buttonStyle = require('../../const/buttonStyle.js');
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

    // S3-0a-ii:面板互動接線(discord.js 端依 key 派發)。
    // criminalAccess:'block'=在押不得參拜;bind 檢查走框架預設(未綁定者自動擋)。
    this.commands = [
      { key: '神社', criminalAccess: 'block', usePermission: 0, func: this.openEntrance.bind(this) }
    ];
    this.buttons = [
      { key: 'shrenter', usePermission: 0, func: this.enter.bind(this) },
      { key: 'shrbow', usePermission: 0, func: this.bow.bind(this) }
    ];
    this.selects = [
      { key: 'shrnav', usePermission: 0, func: this.navigate.bind(this) }
    ];
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

  // ── component 組裝(純、可單測;不碰 interaction)──────────────

  // 公開入口訊息的單一按鈕 [⛩️ 甜甜神社へ](shrenter)。
  _entranceRow () {
    return new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(DiscordButtonHelper.getCustomID('shrenter', []))
        .setLabel('⛩️ 甜甜神社へ')
        .setStyle(buttonStyle.red)
    );
  }

  // 鳥居前硬門:唯一按鈕 [🙇 一礼して入る](shrbow-in);未一礼不給導覽。
  _bowInRow () {
    return new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(DiscordButtonHelper.getCustomID('shrbow', ['in']))
        .setLabel('🙇 一礼して入る')
        .setStyle(buttonStyle.blue)
    );
  }

  // 入境後面板的兩個 ActionRow:[導覽下拉(shrnav,9 設施), 退場礼鈕(shrbow-out)]。
  _navComponents () {
    const menu = new StringSelectMenuBuilder()
      .setCustomId(DiscordButtonHelper.getCustomID('shrnav', []))
      .setPlaceholder('⛩️ どちらへ參りますか')
      .addOptions(this.navFacilities());
    const exitRow = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(DiscordButtonHelper.getCustomID('shrbow', ['out']))
        .setLabel('🙇 一礼して退く')
        .setStyle(buttonStyle.grey)
    );
    return [new ActionRowBuilder().addComponents(menu), exitRow];
  }

  // ── 互動 handler(薄殼;絕不讓例外炸掉互動)──────────────────

  // !神社(公開一行入口 + 進場按鈕)。
  async openEntrance (client, message) {
    await message.msg.reply({
      content: '⛩️ 甜甜神社の鳥居が見える。',
      components: [this._entranceRow()]
    }).catch(() => {});
  }

  // [⛩️ 甜甜神社へ]:lazy 失礼結算 → 開新 visit → ephemeral 鳥居面板(硬門:只給一礼鈕)。
  async enter (client, struct) {
    try {
      const discordId = String(struct.user.id);
      const nowEpoch = Math.floor(Date.now() / 1000);
      const { fortuneDAO } = this._daos();
      const old = await fortuneDAO.openVisit(discordId, nowEpoch);
      const shitsurei = this._shitsureiOnEnter(old, nowEpoch);
      if (shitsurei) await fortuneDAO.appendBuff(discordId, shitsurei);
      const obj = {
        embeds: [this._panel('torii')],
        components: [this._bowInRow()],
        ephemeral: true
      };
      // 失礼:只給神職斥責文字,不顯數字(運氣黑箱)。
      if (shitsurei) obj.content = '「前回は礼を欠いたようですね…」神職がじっとこちらを見ている。';
      await struct.interaction.reply(obj).catch(() => {});
    } catch (e) {
      console.error('[Shrine.enter]', e && e.message);
      await struct.interaction.reply({ content: '⛩️ 境內が少し混み合っているようだ…また後で。', ephemeral: true }).catch(() => {});
    }
  }

  // [🙇 一礼](shrbow):in=硬門解鎖導覽(純 UI,不寫 DB);out=標記乾淨退場(closeVisit)+收面板。
  async bow (client, struct) {
    try {
      if (struct.args[0] === 'in') {
        await struct.interaction.update({
          embeds: [this._panel('torii')],
          components: this._navComponents()
        }).catch(() => {});
        return;
      }
      // out:closeVisit 是巢狀路徑更新,只會在 openVisit(進場)之後被按到 → 安全。
      await this._daos().fortuneDAO.closeVisit(String(struct.user.id));
      await struct.interaction.update({
        embeds: [
          new EmbedBuilder()
            .setTitle('⛩️ 甜甜神社')
            .setDescription('またのお參りを。')
            .setColor(0xC0392B)
        ],
        components: []
      }).catch(() => {});
    } catch (e) {
      console.error('[Shrine.bow]', e && e.message);
      await struct.interaction.update({ embeds: [this._panel('torii')], components: this._navComponents() }).catch(() => {});
    }
  }

  // 導覽下拉(shrnav):移動到選中設施(未知值 _panel 自帶 fallback torii)。
  async navigate (client, struct) {
    try {
      const locKey = struct.values && struct.values[0];
      await struct.interaction.update({
        embeds: [this._panel(locKey)],
        components: this._navComponents()
      }).catch(() => {});
    } catch (e) {
      console.error('[Shrine.navigate]', e && e.message);
      await struct.interaction.update({ embeds: [this._panel('torii')], components: this._navComponents() }).catch(() => {});
    }
  }
}

module.exports = Shrine;
module.exports.FLAVOR = FLAVOR;
module.exports.SHITSUREI = SHITSUREI;
