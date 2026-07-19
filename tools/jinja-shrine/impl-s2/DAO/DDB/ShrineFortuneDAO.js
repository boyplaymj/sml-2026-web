// 甜甜神社 — 玩家運氣狀態 DAO(sweetbot-shrine-fortune, PK=discordId)。
// base DAO 的 get/update 寫死 PK=id,本表 PK=discordId,故用 doc client + 正確 key 自寫。
const BaseDAO = require('./DDBCompatibleBaseDAO.js');
const { GetCommand, PutCommand, UpdateCommand } = require('@aws-sdk/lib-dynamodb');

class ShrineFortuneDAO extends BaseDAO {
  constructor () {
    super('sweetbot-shrine-fortune');
  }

  async getByPlayer (discordId) {
    const res = await this.ddb.send(new GetCommand({
      TableName: this.tableName,
      Key: { discordId: String(discordId) }
    }));
    return res.Item || null;
  }

  // 整包覆寫(S1 只讀;此 put 供 S2 授與/參拜寫回用)。
  async put (item) {
    await this.ddb.send(new PutCommand({ TableName: this.tableName, Item: item }));
    return item;
  }

  // 原子累加功德值(ADD;merit 不存在時自動從 0 起)。避免 read-modify-write 競態。
  async addMerit (discordId, n) {
    await this.ddb.send(new UpdateCommand({
      TableName: this.tableName,
      Key: { discordId: String(discordId) },
      UpdateExpression: 'ADD merit :n',
      ExpressionAttributeValues: { ':n': n }
    }));
    return true;
  }

  // 持久化性別(SET #g;gender 是 DDB 保留字 → #g alias)。御祈禱驗證通過即寫,與付費無關。
  async setGender (discordId, gender) {
    await this.ddb.send(new UpdateCommand({
      TableName: this.tableName,
      Key: { discordId: String(discordId) },
      UpdateExpression: 'SET #g = :g',
      ExpressionAttributeNames: { '#g': 'gender' },
      ExpressionAttributeValues: { ':g': gender }
    }));
    return true;
  }

  // 記錄除厄:一次 UpdateCommand 原子寫 yakuHaraiYear(+可選 gender)。
  // gender 傳入(male/female)才寫;否則只寫年。gender 是 DDB 保留字 → #g alias。
  async setYakuHarai (discordId, year, gender) {
    const values = { ':y': year };
    let expr = 'SET yakuHaraiYear = :y';
    const names = {};
    if (gender === 'male' || gender === 'female') {
      expr += ', #g = :g';
      names['#g'] = 'gender';
      values[':g'] = gender;
    }
    await this.ddb.send(new UpdateCommand({
      TableName: this.tableName,
      Key: { discordId: String(discordId) },
      UpdateExpression: expr,
      ...(Object.keys(names).length ? { ExpressionAttributeNames: names } : {}),
      ExpressionAttributeValues: values
    }));
    return true;
  }
}

module.exports = ShrineFortuneDAO;
