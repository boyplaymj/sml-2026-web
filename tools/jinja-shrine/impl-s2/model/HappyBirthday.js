const Config = require('../config.js');
const ViewerDAO = require('../DAO/DDB/ViewerDAO.js');
const ConfigDAO = require('../DAO/DDB/ConfigDAO.js');

const BirthdayRecordDAO = require('../DAO/BirthdayRecordDAO.js');
const ViewerDetailDAO = require('../DAO/DDB/ViewerDetailDAO.js');
const ShrineFortuneDAO = require('../DAO/DDB/ShrineFortuneDAO.js'); // S2-5:生日厄年鉤子讀 gender/除厄年
const { computeYaku, taipeiYear } = require('./shrine/ShrineLuck.js'); // 厄年算法與運氣引擎同源
const CommonUtil = require('./CommonUtil.js');
const emoji = require('../const/emoji.js');
const moment = require('moment');
const momentTZ = require('moment-timezone');
const { EmbedBuilder, ActionRowBuilder, ButtonBuilder } = require('discord.js');
const DiscordButtonHelper = require('../helper/DiscordButtonHelper.js');
const buttonStyle = require('../const/buttonStyle.js');

class HappyBirthday {
  constructor (connection, redis) {
    this.gameID = 0;
    this.redis = redis; // 生日訊息冪等標記用（防每小時補跑洗版）
    this.ViewerDAO = new ViewerDAO(connection);
    this.BirthdayRecordDAO = new BirthdayRecordDAO(connection);
    this.ViewerDetailDAO = new ViewerDetailDAO(connection);
    this.ConfigDAO = new ConfigDAO();
    this.ShrineFortuneDAO = new ShrineFortuneDAO(); // S2-5 生日厄年鉤子(讀取失敗不影響生日祝賀)
    this.commands = [
      // 勞動白名單(Jail.LABOR_WHITELIST):在押可用,在押時使用計勞動點換假釋
      { key: '生日', criminalAccess: 'allow', usePermission: 0, tips: 'SetBirthday', func: this.setBirthday.bind(this) }
    ];
    this.buttons = [
      { key: 'hbc', blockCriminal: false, usePermission: 0, func: this.congratulation.bind(this) }
    ]
  }

  async showBirthday (message) {
    const stars = await this.ViewerDAO.getNextBirthdayByDate(CommonUtil.getDateFormat('MM-DD'));
    if (stars.length < 5) {
      const nextStars = await this.ViewerDAO.getNextBirthday();
      nextStars.forEach(element => {
        stars.push(element);
      });
    }
    let totalCount = 0;
    let m = parseInt(stars[0].bMonth);
    let text = '';
    let isSet = false;
    // console.log(stars);
    const self = this;
    const embed = new EmbedBuilder();
    embed.setTitle('最近生日的人');
    // 名單顯示只到 10 筆,先批次把這些人的暱稱解析成純文字(embed mention 顯示不穩,見 _displayNames 註解)。
    const nameMap = await this._displayNames(message.guild, stars.slice(0, 10).map(s => s.discordID));
    stars.forEach((item) => {
      if (totalCount < 10) {
        if (m != item.bMonth) {
          isSet = true;
          embed.addFields({ name: `${m}月壽星`, value: text, inline: false });
          m = parseInt(item.bMonth);
          text = '';
        }
        isSet = false;
        const birthday = moment(item.birthday).format('MM月DD日');
        // 計算今天是他的幾歲生日
        const c = self.dateDifference(item.birthday, CommonUtil.getDate());
        c.years++;
        const nm = nameMap[item.discordID] || `<@${item.discordID}>`;
        text += `${nm} ${birthday} 滿${c.years}歲囉！\n`;
        totalCount++;
      }
    });
    if (!isSet)embed.addFields({ name: `${m}月壽星`, value: text, inline: false });

    embed.addFields({ name: '今天還沒祝賀嗎？', value: '現在去<#863339960076599316> 祝賀吧！', inline: false });
    await message.channel.send({
      embeds: [embed]
    });
  }

  async setBirthday (client, message) {
    const userID = message.author.id;
    const birthday = message.args[0]
    const viewer = await this.ViewerDAO.getByDcID(userID);
    if (viewer == null) {
      await message.msg.reply('你確定你有綁定了嗎?');
      return;
    }
    if (viewer.birthday != null) {
      await this.showBirthday(message.msg);
      return;
    }
    if (!CommonUtil.isValidDateFormat(birthday)) {
      await message.msg.reply(`你輸入的生日格式錯誤囉！請確認格式為
\`\`\`yaml
yyyymmdd
\`\`\`
例如
\`\`\`yaml

19940807
\`\`\``);
      return;
    }
    const result = this.ViewerDAO.setBirthday(viewer.id, birthday);
    if (result) {
      await message.msg.reply(`儲存成功! 你的生日是 ${birthday}`);
    } else {
      await message.msg.reply('儲存失敗! 請聯繫系統管理員');
    }
  }

  dateDifference (date1, date2) {
    const date1Time = new Date(date1).getTime();
    const date2Time = new Date(date2).getTime();
    const diffTime = Math.abs(date1Time - date2Time);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    const years = Math.floor(diffDays / 365);
    const months = Math.floor((diffDays % 365) / 30);
    const days = Math.floor((diffDays % 365) % 30);
    return {
      years,
      months,
      days
    };
  }

  async giveRole (client) {
    // [A] NODE_ENV 可能 undefined(實機沒設)，原本 .trim() 會直接崩潰整個 giveRole → 預設 production
    const env = (process.env.NODE_ENV || 'production').trim();
    const channelSetting = await this.ConfigDAO.selectOne({
      env,
      key: 'birthdayChannel'
    });
    const channelRole = await this.ConfigDAO.selectOne({
      env,
      key: 'birthdayRole'
    });
    const roleID = channelRole.value;
    const guild = client.guilds.cache.get(channelSetting.serverID);
    const today = momentTZ().tz(Config.timeZone).format('MM-DD');
    const channel = guild.channels.cache.find(channel => channel.id === channelSetting.value);

    // 今天的壽星
    const newStars = (await this.ViewerDAO.getByBirthday(today)) || [];
    // DDB viewer 的欄位是 discordId(小寫)/id，不是 discordID(大寫)。統一取用避免 undefined。
    const starId = (s) => s.discordId || s.discordID || s.id;
    const todayIds = new Set(newStars.map(starId));
    // 可觀測：每次都記今天找到幾位壽星（掃到 0 也記，方便對照「明明有人卻掃到 0」）
    console.log(`[birthday] ${today} 找到壽星 ${newStars.length} 位:`, newStars.map(starId));

    // [B] 移除：reconcile 全量對帳。凡「目前持有生日身分組」但生日不是今天的，一律拿掉。
    //     原本只比對「昨天生日」的人 → 只有一天窗口，午夜 job 漏跑就永久卡著。
    const holders = await this._membersWithRole(guild.id, roleID);
    for (const dcID of holders) {
      if (todayIds.has(dcID)) continue;
      try {
        await guild.members.fetch(dcID);
        await guild.members.cache.get(dcID).roles.remove(roleID);
      } catch (e) {
        console.log('[birthday] remove fail', dcID, e.message);
      }
    }

    // 加上：今天壽星沒身分組就加，並發祝賀訊息
    const self = this;
    for (const item of newStars) {
      try {
        const dcId = starId(item);
        await guild.members.fetch(dcId);
        const roles = guild.members.cache.get(dcId)._roles;
        if (!roles.includes(roleID)) {
          await guild.members.cache.get(dcId).roles.add(roleID);
        }
        // 冪等：今天已發過這位壽星的祝賀訊息就跳過(只跳過發訊息，身分組上面照給)。
        // 讓 giveRole 可以「開機 + 每小時」補跑而不會洗版重發。
        const postedKey = `birthday:posted:${dcId}:${CommonUtil.getDate()}`;
        if (this.redis && await this.redis.get(postedKey)) {
          continue;
        }
        // 計算今天是他的幾歲生日
        const c = self.dateDifference(item.birthday, CommonUtil.getDate());

        // 壽星名用 bot 端解析好的暱稱純文字(上面已 fetch 過此成員);embed mention 顯示不穩故不用 <@id>。
        const starName = guild.members.cache.get(dcId)?.displayName || `<@${dcId}>`;
        const embed = new EmbedBuilder();
        embed
          .addFields(
            { name: emoji.happyBirthday, value: `伯夷今天 **${starName}** 生日~可以祝 **${starName}** 生日快樂嗎💖\n今天是 **${starName}** 的 (${c.years}) 歲生日喔喔喔喔! 🎂`, inline: true })
        // S2-5:厄年鉤子(選配、fail-safe)。逢厄年且今年未除厄才附;缺 gender/任何錯 → 不附,不影響祝賀。
        const yakuHint = await self._yakuHint(dcId, item.birthday);
        if (yakuHint) embed.addFields({ name: '⛩️ 甜甜神社・厄年提醒', value: yakuHint, inline: false });
        const row = new ActionRowBuilder()
          .addComponents(
            new ButtonBuilder()
              .setCustomId(DiscordButtonHelper.getCustomID('hbc', [dcId, CommonUtil.getDate()]))
              .setLabel('恭喜!')
              .setEmoji(emoji.congratulation)
              .setStyle(buttonStyle.red)
          )
        await channel.send({
          embeds: [embed],
          components: [row]
        });
        // 發送成功才記標記(TTL 25h，隔天自動失效不影響明年同一天)
        if (this.redis) await this.redis.set(postedKey, true, 25 * 3600, true);
      } catch (e) {
        console.log('[birthday] add/notify fail', starId(item), e.message);
      }
    }
  }

  // S2-5 厄年鉤子:壽星逢厄年且今年未除厄 → 回提示字串,否則 null。
  // 需 shrine fortune.gender(御祈禱時收集);缺 gender → 不附(保守)。
  // 🛡️ 全程 try/catch:shrine 讀取/算法任何錯 → 回 null,絕不影響生日祝賀主流程。
  // nowEpoch 可注入以利單測(預設現在)。厄年算法用引擎同源 computeYaku/taipeiYear。
  async _yakuHint (dcId, birthday, nowEpoch = Math.floor(Date.now() / 1000)) {
    try {
      const fortune = await this.ShrineFortuneDAO.getByPlayer(dcId);
      const gender = fortune && fortune.gender;
      if (gender !== 'male' && gender !== 'female') return null; // 缺 gender → 不附
      const bd = String(birthday || '').replace(/-/g, '');
      if (!/^\d{8}$/.test(bd)) return null; // 生日非 8 碼 → 不附
      const year = taipeiYear(nowEpoch);
      if (fortune.yakuHaraiYear === year) return null; // 今年已除厄 → 不嘮叨
      const kazoe = year - parseInt(bd.slice(0, 4), 10) + 1;
      const yk = computeYaku(kazoe, gender);
      if (yk.level === 'none') return null; // 非厄年 → 不附
      const label = { maeyaku: '前厄', honyaku: yk.isTaiyaku ? '大厄（本厄）' : '本厄', atoyaku: '後厄' }[yk.level] || '厄年';
      return `今年是你的 **${label}** 年喔。要不要到 ⛩️甜甜神社 的御祈禱受付所除厄呢？`;
    } catch (e) {
      console.log('[birthday] yakuHint skip:', e && e.message);
      return null;
    }
  }

  // 批次把一組 discordID 解析成「顯示名」(member.displayName=有伺服器暱稱用暱稱、否則全域名)。
  // 為什麼要在 bot 端解析成純文字:embed 裡的 <@id> mention 不會被附進訊息 payload,
  // 觀看端只能靠自己的成員快取渲染 → 沒快取就顯示不出暱稱(時好時壞)。放解析好的字串就 100% 穩定。
  // 一次 guild.members.fetch({user:[...]}) 批抓(單一請求),避免逐一 fetch 拖過互動 3 秒窗。
  async _displayNames (guild, ids) {
    const map = {};
    const uniq = [...new Set((ids || []).filter(Boolean))];
    if (!guild || !uniq.length) return map;
    try {
      const fetched = await guild.members.fetch({ user: uniq });
      fetched.forEach((m) => { map[m.id] = m.displayName; });
    } catch (e) {
      console.log('[birthday] 批次解析暱稱失敗:', e && e.message);
    }
    return map;
  }

  // 用 REST 分頁列出「持有指定身分組」的成員 id（gateway 沒開 GuildMembers intent，cache 不可靠）
  async _membersWithRole (guildID, roleID) {
    const ids = [];
    let after = '0';
    for (;;) {
      const res = await fetch(`https://discord.com/api/v10/guilds/${guildID}/members?limit=1000&after=${after}`, {
        headers: { Authorization: `Bot ${Config.loginToken}` }
      });
      if (!res.ok) { console.log('[birthday] list members fail', res.status); break; }
      const arr = await res.json();
      if (!arr.length) break;
      arr.forEach((m) => { if ((m.roles || []).includes(roleID)) ids.push(m.user.id); });
      after = arr[arr.length - 1].user.id;
      if (arr.length < 1000) break;
      await new Promise((r) => setTimeout(r, 300));
    }
    return ids;
  }

  async congratulation (client, button) {
    const userID = button.user.id;
    const birthdayStarID = button.args[0];
    const date = button.args[1] + '-' + button.args[2] + '-' + button.args[3];
    const output = {};
    if (userID == birthdayStarID) {
      await button.interaction.reply({
        content: '自己的生日自己恭喜! 是不是有點邊緣了?!',
        ephemeral: true
      });
      return;
    }
    // 隔天/非當天點舊生日按鈕：只回點擊者 ephemeral、不動原訊息(不清按鈕、不動禮金簿)。
    // 放在「已祝福過」檢查前，避免遲到點擊被導到「只能祝福一次」的不精準訊息。
    if (date !== CommonUtil.getDate()) {
      await button.interaction.reply({
        content: '這個生日已經過囉，沒辦法補領獎勵 🎂',
        ephemeral: true
      }).catch(() => {});
      return;
    }
    if (await this.BirthdayRecordDAO.checkExist(birthdayStarID, userID)) {
      await button.interaction.reply({
        content: '只能祝福一次啦! 留點機會給別人好嗎?',
        ephemeral: true
      });
      return;
    }
    // 至此保證是「生日當天」(非當天已於前面 early return)。發獎 + 記錄祝賀。
    const insertID = await this.BirthdayRecordDAO.add(birthdayStarID, userID);
    if (insertID > 0) {
      await this.ViewerDetailDAO.givePoint([userID], 50, 'point', '祝福壽星');
      await this.ViewerDetailDAO.givePoint([userID], 10, 'experience', '祝福壽星');
      await this.ViewerDetailDAO.givePoint([birthdayStarID], 100, 'point', '壽星獎勵');
    }
    // 明確保留祝賀按鈕：當天要讓多人都能繼續祝賀。
    // 部分 discord.js 版本在 interaction.update() 未帶 components 時會清掉按鈕，
    // 故從原訊息重建 row 明確帶回，避免「第一個人按完按鈕就消失」。
    if (button.msg.components && button.msg.components.length) {
      try {
        output.components = [ActionRowBuilder.from(button.msg.components[0])];
      } catch (e) {
        console.log('[birthday] 保留按鈕失敗，改沿用原 components:', e.message);
        output.components = button.msg.components;
      }
    }
    const oldField = button.msg.embeds[0].fields[0];
    const embed = new EmbedBuilder();
    const wishers = await this.BirthdayRecordDAO.getWishers(birthdayStarID);
    if (wishers == null) { return }
    // DDB 紀錄只有 wisherID(無 discordName)。embed mention 顯示不穩(見 _displayNames 註解)→
    // bot 端批次解析成暱稱純文字;抓不到(退群等)才退回 <@id>。取前 30 筆解析即可(顯示也只切 30)。
    const nameMap = await this._displayNames(button.msg.guild, wishers.slice(0, 30).map(x => x.wisherID));
    const wishersArr = wishers.map(x => nameMap[x.wisherID] || `<@${x.wisherID}>`);
    embed.addFields(
      { name: oldField.name, value: oldField.value, inline: true },
      { name: '禮金簿', value: wishersArr.slice(0, 30).join(' ') + `\n以上每人獲得 50${emoji.teeth} & 10${emoji.experience}\n壽星累積獲得 ${wishersArr.length * 100}${emoji.teeth}`, inline: false }
    );
    output.embeds = [embed];

    await button.interaction
      .update(output)
      .catch((err) => {
        console.log(err);
      });
  }
}

module.exports = HappyBirthday;
