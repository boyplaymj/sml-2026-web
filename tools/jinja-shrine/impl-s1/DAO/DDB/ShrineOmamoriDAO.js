// 甜甜神社 — 御守持有 DAO(sweetbot-shrine-omamori, PK=discordId, SK=sk)。
// hot-path 用 Query(非 scan);必分頁(對齊全站鐵律)。
const BaseDAO = require('./DDBCompatibleBaseDAO.js');
const { QueryCommand, PutCommand } = require('@aws-sdk/lib-dynamodb');

class ShrineOmamoriDAO extends BaseDAO {
  constructor () {
    super('sweetbot-shrine-omamori');
  }

  // 取玩家全部御守(含過期未回收者,穢れ結算需要)。分頁抓完。
  async listByPlayer (discordId) {
    const items = [];
    let lastKey;
    do {
      const res = await this.ddb.send(new QueryCommand({
        TableName: this.tableName,
        KeyConditionExpression: '#d = :d',
        ExpressionAttributeNames: { '#d': 'discordId' },
        ExpressionAttributeValues: { ':d': String(discordId) },
        ExclusiveStartKey: lastKey
      }));
      if (res.Items) items.push(...res.Items);
      lastKey = res.LastEvaluatedKey;
    } while (lastKey);
    return items;
  }

  async put (item) {
    await this.ddb.send(new PutCommand({ TableName: this.tableName, Item: item }));
    return item;
  }
}

module.exports = ShrineOmamoriDAO;
