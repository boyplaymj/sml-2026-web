const { chromium } = require(process.env.PW_PATH);
const fs = require('fs');
const b64 = f => fs.readFileSync(f).toString('base64');
const loco = b64('/tmp/train-px/loco_px.png');
const station = b64('/tmp/train-px/station_px.png');
const html = `<!doctype html><html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Noto Sans CJK TC',sans-serif}
body{padding:24px;background:#2b2d31}
.embed{width:840px;background:#313338;border-radius:10px;border-left:5px solid #f2b6d0;overflow:hidden}
.hdr{display:flex;align-items:center;gap:14px;padding:16px 20px 12px}
.title{color:#fff;font-size:22px;font-weight:900}.sub{color:#b9bbbe;font-size:14px;margin-top:2px}
.teeth{margin-left:auto;background:#f2b6d0;color:#5c1c38;font-weight:900;font-size:18px;padding:6px 14px;border-radius:20px}
.scene{position:relative;height:420px;overflow:hidden;image-rendering:pixelated;
  background:linear-gradient(#8fd0ff 0%,#bfe6f5 46%,#7bbf63 46%,#5c9e48 100%)}
.spr{position:absolute;image-rendering:pixelated;filter:drop-shadow(0 6px 4px #0004)}
.station{width:320px;left:60px;top:56px}
.loco{width:300px;left:430px;top:150px}
.foot{display:flex;gap:10px;padding:12px 18px 16px;flex-wrap:wrap}
.btn{background:#4e5058;color:#fff;font-size:15px;font-weight:700;padding:9px 16px;border-radius:8px}
.btn.pri{background:#5865f2}.btn.acc{background:#3ba55d}
</style></head><body>
<div class="embed">
  <div class="hdr"><div style="font-size:32px">🚉</div>
    <div><div class="title">さくら中央 駅</div><div class="sub">Tier 3・地方都市駅　│　月台 3　│　在途 2 班</div></div>
    <div class="teeth">🦷 58,700</div></div>
  <div class="scene">
    <img class="spr station" src="data:image/png;base64,${station}">
    <img class="spr loco" src="data:image/png;base64,${loco}">
  </div>
  <div class="foot"><div class="btn pri">🚂 派車送貨</div><div class="btn">🛒 購車編組</div>
    <div class="btn acc">🏗️ 車站擴建</div><div class="btn">📋 路線</div><div class="btn">📦 在途看板</div></div>
</div></body></html>`;
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 900, height: 580 }, deviceScaleFactor: 2 });
  await p.setContent(html, { waitUntil: 'load' }); await p.waitForTimeout(300);
  await (await p.$('.embed')).screenshot({ path: '/tmp/train-px/panel_px.png' });
  console.log('ok'); await b.close();
})();
