// 甜甜火車大亨 — 在途/待抵達列車 DAO(PK=userId, SK=sk='<arriveAt zero-pad>#<dispatchId>')。
// SK 前綴 arriveAt(補零字串)→ 可用 range query 一次撈「已抵達(sk <= now#~)」的所有列車做惰性結算。
// 放到 sweetbot-next/DAO/DDB/。dispatch item:
//   { userId, sk, dispatchId, lineId, destId, departAt, arriveAt,
//     locoId, cars[], cargo{}, kind:'freight'|'passenger', settled:false }
const DDBBaseDAO = require('./DDBBaseDAO');
const { PutCommand, QueryCommand, DeleteCommand } = require('@aws-sdk/lib-dynamodb');

const TABLE_NAME = 'train-tycoon-transit';
const PAD = 15; // arriveAt(ms)補零位數,確保字典序 == 時間序

const skFor = (arriveAt, dispatchId) => `${String(arriveAt).padStart(PAD, '0')}#${dispatchId}`;

class TrainTycoonTransitDAO extends DDBBaseDAO {
  constructor () {
    super(TABLE_NAME);
  }

  static skFor (arriveAt, dispatchId) { return skFor(arriveAt, dispatchId); }

  async addDispatch (item) {
    const sk = skFor(item.arriveAt, item.dispatchId);
    const full = { ...item, userId: String(item.userId), sk };
    await this.ddb.send(new PutCommand({ TableName: this.tableName, Item: full }));
    return full;
  }

  // 撈某玩家「已在 nowTs 前抵達」的所有在途列車(惰性結算對象)。
  async listArrivedBefore (userId, nowTs) {
    const res = await this.ddb.send(new QueryCommand({
      TableName: this.tableName,
      KeyConditionExpression: 'userId = :u AND sk <= :hi',
      ExpressionAttributeValues: {
        ':u': String(userId),
        ':hi': `${String(nowTs).padStart(PAD, '0')}#￿`
      }
    }));
    return res.Items || [];
  }

  // 全部在途(含未抵達)—給「在途看板」分頁。
  async listAll (userId) {
    const res = await this.ddb.send(new QueryCommand({
      TableName: this.tableName,
      KeyConditionExpression: 'userId = :u',
      ExpressionAttributeValues: { ':u': String(userId) }
    }));
    return res.Items || [];
  }

  // 結算完刪除該趟(惰性結算後回收)。
  async remove (userId, sk) {
    await this.ddb.send(new DeleteCommand({
      TableName: this.tableName,
      Key: { userId: String(userId), sk }
    }));
  }
}

module.exports = TrainTycoonTransitDAO;
