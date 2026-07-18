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
}

module.exports = ShrineFortuneDAO;
