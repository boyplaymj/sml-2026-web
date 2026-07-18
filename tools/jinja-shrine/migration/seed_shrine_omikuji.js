// Seed:甜甜神社籤詩池(sweetbot-shrine-omikuji-pool)。
//   Stage 0 佔位版:11 個常規籤階各 1 張 + 大大吉彩蛋,結構完整(六軸 items),供引擎/後台驗收。
//   11 常規階(對齊 config.omikujiWeights):大吉/吉/中吉/小吉/末吉/末小吉/凶/小凶/半凶/末凶/大凶。
//   正式豐富籤池(數十張、和歌講究)為獨立內容批次補上。
//   冪等:PutCommand 覆寫同 omikujiId。用法:node migration/seed_shrine_omikuji.js
//
//   分項→子軸對照(items 內每項都帶 axis,引擎照 axis 給對應 buff):
//     商賣/金運/相場 → zaiun(財)   爭事/勝負 → shengun(勝)   學問/仕事 → zhiun(智)
//     健康/病氣 → body(厄除)        戀愛/縁談/待人 → renyuan(人緣)   旅行/失物/轉居 → xingyun(行)
//   score 正負依籤階:大吉全正且大,大凶全負。引擎抽到籤→把各 item.score 加成到對應軸(帶時效)。
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, PutCommand } = require('@aws-sdk/lib-dynamodb');

const REGION = 'ap-southeast-1';
const TABLE = 'sweetbot-shrine-omikuji-pool';
const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }));

// 佔位籤:每階一張,items 覆蓋六軸。text 為簡短示意,正式版再潤。
const POOL = [
  { omikujiId: 'ok-daikichi-01', rank: '大吉', waka: '朝日さす　峰の白雲　晴れわたり　千代のさかえを　なほ祈るかな',
    sougou: '雲開月出,萬事如願。誠心所向,福澤自來。',
    items: {
      商賣: { axis: 'zaiun', score: 12, text: '財源廣進,買賣大利。' },
      勝負: { axis: 'shengun', score: 10, text: '勝運極旺,先手必得。' },
      學問: { axis: 'zhiun', score: 9, text: '文思泉湧,金榜題名。' },
      健康: { axis: 'body', score: 8, text: '身心康泰,百病不侵。' },
      戀愛: { axis: 'renyuan', score: 10, text: '良緣天成,兩情相悅。' },
      旅行: { axis: 'xingyun', score: 9, text: '出行大吉,一路平安。' }
    } },
  { omikujiId: 'ok-kichi-01', rank: '吉', waka: '池水の　ふかき心を　くみてこそ　人のなさけも　しらるなりけれ',
    sougou: '穩中有進,守正得吉。急則生亂,緩則有成。',
    items: {
      金運: { axis: 'zaiun', score: 7, text: '財氣平順,積少成多。' },
      爭事: { axis: 'shengun', score: 6, text: '爭執可勝,宜以和為貴。' },
      仕事: { axis: 'zhiun', score: 6, text: '事業有成,貴人相助。' },
      健康: { axis: 'body', score: 5, text: '調養得宜,無大礙。' },
      縁談: { axis: 'renyuan', score: 6, text: '姻緣漸近,水到渠成。' },
      旅行: { axis: 'xingyun', score: 5, text: '旅途順遂。' }
    } },
  { omikujiId: 'ok-chukichi-01', rank: '中吉', waka: '曇りなき　心の月を　さきだてて　うき世の中を　照らしてぞゆく',
    sougou: '運勢中上,持恆則吉。莫因小挫而退。',
    items: {
      商賣: { axis: 'zaiun', score: 6, text: '生意見好,勿貪則安。' },
      勝負: { axis: 'shengun', score: 5, text: '勝負在己,穩紮穩打。' },
      學問: { axis: 'zhiun', score: 5, text: '勤學有得。' },
      病氣: { axis: 'body', score: 4, text: '小恙將癒。' },
      戀愛: { axis: 'renyuan', score: 5, text: '感情升溫。' },
      失物: { axis: 'xingyun', score: 4, text: '失物可尋回。' }
    } },
  { omikujiId: 'ok-shokichi-01', rank: '小吉', waka: '待つ人は　來らぬさきに　いそがれて　こころのどけき　春の日ぞなき',
    sougou: '小有喜氣,循序漸進。',
    items: {
      相場: { axis: 'zaiun', score: 4, text: '小財可得。' },
      爭事: { axis: 'shengun', score: 3, text: '爭事宜退一步。' },
      仕事: { axis: 'zhiun', score: 4, text: '工作穩定。' },
      健康: { axis: 'body', score: 3, text: '注意飲食即安。' },
      待人: { axis: 'renyuan', score: 4, text: '所待之人將至。' },
      旅行: { axis: 'xingyun', score: 3, text: '近遊為宜。' }
    } },
  { omikujiId: 'ok-suekichi-01', rank: '末吉', waka: '風さそふ　花のゆくへは　知らねども　惜しむ心は　身にとまりけり',
    sougou: '先抑後揚,末有吉兆。宜守成待時。',
    items: {
      金運: { axis: 'zaiun', score: 3, text: '財運後半見好。' },
      勝負: { axis: 'shengun', score: 2, text: '初挫後勝。' },
      學問: { axis: 'zhiun', score: 3, text: '持之以恆終有成。' },
      健康: { axis: 'body', score: 2, text: '漸入佳境。' },
      縁談: { axis: 'renyuan', score: 3, text: '緣分尚需等待。' },
      轉居: { axis: 'xingyun', score: 2, text: '遷居宜緩。' }
    } },
  { omikujiId: 'ok-sueshokichi-01', rank: '末小吉', waka: '露の身の　消えなば消えね　いかにせん　げにこそ人の　なさけをば知れ',
    sougou: '微吉將顯,耐心守候。',
    items: {
      商賣: { axis: 'zaiun', score: 2, text: '薄利可圖。' },
      爭事: { axis: 'shengun', score: 1, text: '爭事平息中。' },
      仕事: { axis: 'zhiun', score: 2, text: '慢工出細活。' },
      病氣: { axis: 'body', score: 1, text: '調養漸安。' },
      戀愛: { axis: 'renyuan', score: 2, text: '緣淺情長。' },
      失物: { axis: 'xingyun', score: 1, text: '失物或現。' }
    } },
  { omikujiId: 'ok-kyou-01', rank: '凶', waka: '思ふこと　などかなはぬと　うらむれど　まことは道の　なほ遠きかな',
    sougou: '運勢受阻,退守為吉。綁凶結緣可化。',
    items: {
      金運: { axis: 'zaiun', score: -4, text: '破財之虞,慎理財。' },
      勝負: { axis: 'shengun', score: -5, text: '爭則必敗,宜忍。' },
      學問: { axis: 'zhiun', score: -3, text: '心浮難進。' },
      健康: { axis: 'body', score: -4, text: '注意身體,勿勞。' },
      戀愛: { axis: 'renyuan', score: -3, text: '感情生波。' },
      旅行: { axis: 'xingyun', score: -4, text: '遠行不利。' }
    } },
  { omikujiId: 'ok-shokyou-01', rank: '小凶', waka: '山ふかみ　春とも知らぬ　松の戸に　たえだえかかる　雪の玉水',
    sougou: '小有不順,謹慎自保。',
    items: {
      相場: { axis: 'zaiun', score: -3, text: '投機宜止。' },
      爭事: { axis: 'shengun', score: -3, text: '避免衝突。' },
      仕事: { axis: 'zhiun', score: -2, text: '事多阻滯。' },
      病氣: { axis: 'body', score: -3, text: '小病纏身,早療。' },
      待人: { axis: 'renyuan', score: -2, text: '所待之人遲。' },
      失物: { axis: 'xingyun', score: -3, text: '失物難尋。' }
    } },
  { omikujiId: 'ok-hankyou-01', rank: '半凶', waka: '世の中は　むかしよりやは　うかりける　わが身ひとつの　ためになれるか',
    sougou: '吉凶參半,如履薄冰。',
    items: {
      金運: { axis: 'zaiun', score: -4, text: '收支需節制。' },
      勝負: { axis: 'shengun', score: -4, text: '勝算不明,勿冒進。' },
      學問: { axis: 'zhiun', score: -3, text: '學業停滯。' },
      健康: { axis: 'body', score: -4, text: '體弱宜補。' },
      縁談: { axis: 'renyuan', score: -3, text: '婚談生變。' },
      轉居: { axis: 'xingyun', score: -4, text: '遷移不吉。' }
    } },
  { omikujiId: 'ok-suekyou-01', rank: '末凶', waka: '数ならぬ　身をも心の　もりたてて　かかる憂き世に　ながらへぬべし',
    sougou: '凶氣漸退,苦盡待甘。切勿妄動。',
    items: {
      商賣: { axis: 'zaiun', score: -5, text: '買賣大損之兆。' },
      爭事: { axis: 'shengun', score: -5, text: '爭端不休。' },
      仕事: { axis: 'zhiun', score: -4, text: '諸事不成。' },
      病氣: { axis: 'body', score: -5, text: '健康拉警報。' },
      戀愛: { axis: 'renyuan', score: -4, text: '情路坎坷。' },
      旅行: { axis: 'xingyun', score: -5, text: '出行招災。' }
    } },
  { omikujiId: 'ok-daikyou-01', rank: '大凶', waka: '限りあれば　松も緑を　あらためて　ふりゆくものは　人の心か',
    sougou: '大凶臨身,萬事宜守不宜進。誠心參拜、綁凶結緣、消災解厄以轉運。',
    items: {
      金運: { axis: 'zaiun', score: -8, text: '大破財,遠離投機借貸。' },
      勝負: { axis: 'shengun', score: -9, text: '逢賭必輸,逢爭必敗。' },
      學問: { axis: 'zhiun', score: -7, text: '心神大亂。' },
      健康: { axis: 'body', score: -8, text: '健康大忌,速就醫防患。' },
      戀愛: { axis: 'renyuan', score: -7, text: '情感決裂之危。' },
      旅行: { axis: 'xingyun', score: -8, text: '遠行大凶,能免則免。' }
    } },
  // 超稀有彩蛋(權重由後台另設,預設不在 omikujiWeights 內=抽不到,留給活動觸發)
  { omikujiId: 'ok-daidaikichi-01', rank: '大大吉', waka: '天地の　ひらけはじめし　ときよりも　いや栄えゆく　わがきみの代',
    sougou: '百年一遇,神恩浩蕩。六運齊揚,心願皆成。',
    items: {
      商賣: { axis: 'zaiun', score: 15, text: '富貴逼人。' },
      勝負: { axis: 'shengun', score: 15, text: '戰無不勝。' },
      學問: { axis: 'zhiun', score: 15, text: '文曲高照。' },
      健康: { axis: 'body', score: 15, text: '龍馬精神。' },
      戀愛: { axis: 'renyuan', score: 15, text: '天賜良緣。' },
      旅行: { axis: 'xingyun', score: 15, text: '所至皆福。' }
    } }
];

async function main () {
  let ok = 0;
  for (const o of POOL) {
    await ddb.send(new PutCommand({ TableName: TABLE, Item: { ...o, enabled: true } }));
    ok++;
  }
  console.log(`已寫入 ${ok} 張佔位籤詩(11 常規階各 1 + 大大吉彩蛋)。`);
}

main().catch((err) => { console.error('seed omikuji 失敗:', err); process.exit(1); });
