// 甜甜火車大亨 — 玩家車站狀態 DAO(PK=userId)。對齊 MahjongTycoonParlorDAO 慣例。
// 放到 sweetbot-next/DAO/DDB/。station item 形狀見 DESIGN.md §9/§14.4:
//   { userId, status, tier, treasury, platforms, yard, waitingHall,
//     equipment[], staff[], fleet[], lines[], decor[], theme,
//     lastSettledAt, renderSig, imageUrl, stats{}, createdAt, updatedAt }
const DDBBaseDAO = require('./DDBBaseDAO');
const { GetCommand, PutCommand, UpdateCommand } = require('@aws-sdk/lib-dynamodb');

const TABLE_NAME = 'train-tycoon-stations';

class TrainTycoonStationDAO extends DDBBaseDAO {
  constructor () {
    super(TABLE_NAME);
  }

  async get (userId) {
    const res = await this.ddb.send(new GetCommand({
      TableName: this.tableName,
      Key: { userId: String(userId) },
      ConsistentRead: true
    }));
    return res.Item || null;
  }

  // 建站 / 縮編求生後重開(closed→active);已 active 則擋掉(不覆蓋在營車站)。
  async createOrReopen (item) {
    await this.ddb.send(new PutCommand({
      TableName: this.tableName,
      Item: { ...item, userId: String(item.userId) },
      ConditionExpression: 'attribute_not_exists(userId) OR #status = :closed',
      ExpressionAttributeNames: { '#status': 'status' },
      ExpressionAttributeValues: { ':closed': 'closed' }
    }));
    return item;
  }

  async save (item) {
    await this.ddb.send(new PutCommand({
      TableName: this.tableName,
      Item: { ...item, userId: String(item.userId) }
    }));
    return item;
  }

  // 提款到金庫(僅在營 + 餘額足夠;原子扣款,防並發雙花)。
  async withdraw (userId, amount, now) {
    const res = await this.ddb.send(new UpdateCommand({
      TableName: this.tableName,
      Key: { userId: String(userId) },
      ConditionExpression: '#status = :active AND #treasury >= :amount',
      UpdateExpression: [
        'SET #treasury = #treasury - :amount',
        '#stats.#totalWithdrawn = if_not_exists(#stats.#totalWithdrawn, :zero) + :amount',
        '#updatedAt = :now'
      ].join(', '),
      ExpressionAttributeNames: {
        '#status': 'status', '#treasury': 'treasury',
        '#stats': 'stats', '#totalWithdrawn': 'totalWithdrawn', '#updatedAt': 'updatedAt'
      },
      ExpressionAttributeValues: { ':active': 'active', ':amount': Number(amount), ':zero': 0, ':now': Number(now) },
      ReturnValues: 'ALL_NEW'
    }));
    return res.Attributes;
  }

  // 惰性結算把抵達收益回沖車站金庫。
  async addTreasury (userId, amount, now) {
    const res = await this.ddb.send(new UpdateCommand({
      TableName: this.tableName,
      Key: { userId: String(userId) },
      UpdateExpression: 'SET #treasury = if_not_exists(#treasury, :zero) + :amount, #updatedAt = :now',
      ExpressionAttributeNames: { '#treasury': 'treasury', '#updatedAt': 'updatedAt' },
      ExpressionAttributeValues: { ':amount': Number(amount), ':zero': 0, ':now': Number(now) },
      ReturnValues: 'ALL_NEW'
    }));
    return res.Attributes;
  }

  // 惰性結算游標推進(下次只補算 lastSettledAt 之後)。
  async setLastSettled (userId, ts) {
    const res = await this.ddb.send(new UpdateCommand({
      TableName: this.tableName,
      Key: { userId: String(userId) },
      UpdateExpression: 'SET #l = :ts, #updatedAt = :ts',
      ExpressionAttributeNames: { '#l': 'lastSettledAt', '#updatedAt': 'updatedAt' },
      ExpressionAttributeValues: { ':ts': Number(ts) },
      ReturnValues: 'ALL_NEW'
    }));
    return res.Attributes;
  }
}

module.exports = TrainTycoonStationDAO;
