// 甜甜神社 — 後台設定 DAO(sweetbot-shrine-config, PK=key, 單列 key='main')。
// 60s 記憶體快取(後台改設定最多 60s 後生效,可接受)。讀失敗 → 回 null,由呼叫端 fallback DEFAULT。
const BaseDAO = require('./DDBCompatibleBaseDAO.js');
const { GetCommand, PutCommand } = require('@aws-sdk/lib-dynamodb');

const CACHE_TTL_MS = 60 * 1000;

class ShrineConfigDAO extends BaseDAO {
  constructor () {
    super('sweetbot-shrine-config');
    this._cache = null;
    this._cacheAt = 0;
  }

  async getMain (nowMs = Date.now()) {
    if (this._cache && (nowMs - this._cacheAt) < CACHE_TTL_MS) return this._cache;
    const res = await this.ddb.send(new GetCommand({
      TableName: this.tableName,
      Key: { key: 'main' }
    }));
    this._cache = res.Item || null;
    this._cacheAt = nowMs;
    return this._cache;
  }

  async put (item) {
    await this.ddb.send(new PutCommand({ TableName: this.tableName, Item: { ...item, key: 'main' } }));
    this._cache = null; // 失效快取
    return item;
  }
}

module.exports = ShrineConfigDAO;
