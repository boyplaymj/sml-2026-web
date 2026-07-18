#!/usr/bin/env node
/* 影片製作進度 — 任務前 1 小時 Web Push 推播器
 * 由 systemd timer 每 15 分鐘跑一次。無 LLM、無付費 API。
 *
 * 邏輯：掃 sml-video-projects 所有專案 → 每個「未完成且有日期」的任務算出開始時間
 *  （台灣時間；沒填 time 預設當天 09:00）→ 若「現在」落在 [開始前 60 分, 開始時刻)
 *   且尚未提醒過(remindedAt 空) → 對所有訂閱裝置發 Web Push，並在該任務寫 remindedAt。
 *
 * 用法：
 *   node send.js            正常跑一輪
 *   node send.js --dry      只印不送、不寫 remindedAt
 *   node send.js --test     立刻對所有訂閱送一則測試推播（驗證管線）
 */
const webpush = require('web-push');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, QueryCommand, UpdateCommand, DeleteCommand } = require('@aws-sdk/lib-dynamodb');
const { SSMClient, GetParametersCommand } = require('@aws-sdk/client-ssm');

const REGION = process.env.AWS_REGION || 'ap-southeast-1';
const TABLE = process.env.TABLE || 'sml-video-projects';
const GSI = 'type-updatedAt-index';
const SITE_URL = 'https://image.boyplaymj.link/vproj/';
const DEFAULT_TIME = '09:00';      // 沒填時間的任務，當天這個時刻提醒
const LEAD_MIN = 60;               // 開始前幾分鐘提醒
const DRY = process.argv.includes('--dry');
const TEST = process.argv.includes('--test');

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }));
const ssm = new SSMClient({ region: REGION });
const nowIso = () => new Date().toISOString().replace(/\.\d+Z$/, 'Z');
const CAT = [
  [/拍攝|補拍|開拍|拍片|攝影|空景|棚拍|外拍|側拍|收音|實拍/, '🎥'],
  [/企劃|腳本|分鏡|劇本|提案|定稿|發想|規劃|構思/, '📝'],
  [/文案|copy|標題|字幕|上字|翻譯|逐字|校稿/i, '🔤'],
  [/剪輯|粗剪|精剪|後製|調色|特效|轉場|剪片/, '✂️'],
  [/配樂|選曲|音樂|配音|旁白|音效|混音|bgm/i, '🎵'],
  [/發布|發佈|上架|上片|上線|publish|po文|排程發|投稿/i, '🚀']
];
const emojiOf = (s) => { for (const [re, e] of CAT) if (re.test(s)) return e; return '📌'; };

async function loadVapid() {
  const r = await ssm.send(new GetParametersCommand({
    Names: ['/sml/vproj-push/vapid-public', '/sml/vproj-push/vapid-private', '/sml/vproj-push/vapid-subject'],
    WithDecryption: true
  }));
  const m = {}; (r.Parameters || []).forEach(p => { m[p.Name.split('/').pop()] = p.Value; });
  const pub = m['vapid-public'], priv = m['vapid-private'], subj = m['vapid-subject'] || 'mailto:admin@example.com';
  if (!pub || !priv) throw new Error('VAPID keys missing in SSM');
  webpush.setVapidDetails(subj, pub, priv);
}

async function queryType(type) {
  const out = []; let ek;
  do {
    const r = await ddb.send(new QueryCommand({
      TableName: TABLE, IndexName: GSI,
      KeyConditionExpression: '#t = :t', ExpressionAttributeNames: { '#t': 'type' },
      ExpressionAttributeValues: { ':t': type }, ExclusiveStartKey: ek
    }));
    out.push(...(r.Items || [])); ek = r.LastEvaluatedKey;
  } while (ek);
  return out;
}

async function sendToAll(subs, payloadObj) {
  const payload = JSON.stringify(payloadObj);
  let ok = 0, gone = 0, fail = 0;
  for (const s of subs) {
    const subscription = { endpoint: s.endpoint, keys: { p256dh: s.p256dh, auth: s.auth } };
    try {
      await webpush.sendNotification(subscription, payload);
      ok++;
    } catch (e) {
      const code = e.statusCode;
      if (code === 404 || code === 410) { // 訂閱已失效 → 清掉
        gone++;
        if (!DRY) await ddb.send(new DeleteCommand({ TableName: TABLE, Key: { id: s.id } })).catch(() => {});
      } else { fail++; console.error('push fail', code, e.body || e.message); }
    }
  }
  return { ok, gone, fail };
}

async function markReminded(project, tid) {
  const tasks = (project.tasks || []).map(t => t.tid === tid ? { ...t, remindedAt: nowIso() } : t);
  await ddb.send(new UpdateCommand({
    TableName: TABLE, Key: { id: project.id },
    UpdateExpression: 'SET #tasks = :t',
    ExpressionAttributeNames: { '#tasks': 'tasks' },
    ExpressionAttributeValues: { ':t': tasks }
  }));
}

(async () => {
  await loadVapid();
  const subs = await queryType('pushsub');

  if (TEST) {
    if (!subs.length) { console.log('沒有任何訂閱裝置'); return; }
    const r = await sendToAll(subs, { title: '🎬 測試推播', body: '推播管線正常 ✅ 之後任務前 1 小時會像這樣提醒你', url: SITE_URL, tag: 'vproj-test' });
    console.log('TEST 送出', r); return;
  }

  if (!subs.length) { console.log('沒有訂閱裝置，略過'); return; }

  const projects = await queryType('vproj');
  const now = Date.now();
  let fired = 0;
  for (const p of projects) {
    for (const t of (p.tasks || [])) {
      if ((t.status || 'todo') === 'done') continue;
      if (!t.date || !/^\d{4}-\d{2}-\d{2}$/.test(t.date)) continue;
      if (t.remindedAt) continue;
      const time = (t.time && /^([01]\d|2[0-3]):[0-5]\d$/.test(t.time)) ? t.time : DEFAULT_TIME;
      const target = new Date(`${t.date}T${time}:00+08:00`).getTime(); // 任務為台灣時間
      if (isNaN(target)) continue;
      const leadStart = target - LEAD_MIN * 60000;
      if (now < leadStart || now >= target) continue; // 只在「開始前 <=60 分」這個窗口內、且還沒過開始時刻

      const em = emojiOf(`${t.tag || ''} ${t.title || ''} ${p.title || ''}`);
      const mins = Math.max(1, Math.round((target - now) / 60000));
      const body = `${time}｜${em} ${t.title || ''}${t.tag ? '（' + t.tag + '）' : ''}` + (t.note ? `\n${t.note}` : '');
      const payload = { title: `⏰ ${mins} 分鐘後：${p.title}`, body, url: SITE_URL, tag: `vproj-${p.id}-${t.tid}` };
      console.log(`FIRE ${p.title} / ${t.title} @ ${t.date} ${time}  (${mins}分後)`);
      if (!DRY) {
        const r = await sendToAll(subs, payload);
        console.log('  sent', r);
        await markReminded(p, t.tid);
      }
      fired++;
    }
  }
  console.log(`done. fired=${fired}, subs=${subs.length}${DRY ? ' (dry)' : ''}`);
})().catch(e => { console.error(e); process.exit(1); });
