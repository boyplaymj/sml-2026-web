// 俯瞰斜角(無天空)審圖:上=7 張 8-bit sprite 接觸表;下=整片 iso 地面場站景面板。
// 用法: PW_PATH=... FONTCONFIG_FILE=... node compose_td.js
const { chromium } = require(process.env.PW_PATH);
const fs = require('fs');
const D = process.env.TD_DIR || '/tmp/train-td';
const b64 = f => fs.readFileSync(`${D}/${f}`).toString('base64');
const img = f => `data:image/png;base64,${b64(f)}`;

const sheet = [
  ['loco_d51_px.png', '🚂 D51 蒸汽'],
  ['loco_ef210_px.png', '🚃 EF210 桃太郎'],
  ['loco_n700s_px.png', '🚄 N700S 新幹線'],
  ['car_koki_px.png', 'コキ 貨櫃車'],
  ['sta_t1_px.png', '🏚️ Tier1 小站'],
  ['sta_t3_px.png', '🏬 Tier3 都市駅'],
  ['tile_grass_px.png', '⬧ 地面 tile']
];
const cells = sheet.map(([f, label]) => `
  <div class="cell"><img src="${img(f)}"><div class="lb">${label}</div></div>`).join('');

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Noto Sans CJK TC',sans-serif}
body{padding:22px;background:#2b2d31}
.wrap{width:940px}
.h{color:#fff;font-size:19px;font-weight:900;margin:4px 2px 12px}
.h small{color:#b9bbbe;font-weight:400;font-size:13px;margin-left:8px}
.sheet{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:22px}
.cell{background:#1e1f22;border-radius:10px;padding:8px;text-align:center}
.cell img{width:100%;image-rendering:pixelated;background:
  repeating-conic-gradient(#2a2b2e 0% 25%,#242528 0% 50%) 0/22px 22px;border-radius:6px}
.lb{color:#dcddde;font-size:12px;font-weight:700;margin-top:6px}
.embed{width:900px;background:#313338;border-radius:10px;border-left:5px solid #f2b6d0;overflow:hidden}
.hdr{display:flex;align-items:center;gap:14px;padding:16px 20px 12px}
.title{color:#fff;font-size:22px;font-weight:900}.sub{color:#b9bbbe;font-size:14px;margin-top:2px}
.teeth{margin-left:auto;background:#f2b6d0;color:#5c1c38;font-weight:900;font-size:18px;padding:6px 14px;border-radius:20px}
/* 俯瞰:整片 iso 地面場,無天空。底色草綠 + 菱形格線 */
.scene{position:relative;height:440px;overflow:hidden;image-rendering:pixelated;background:#6faa5c;
  background-image:
    repeating-linear-gradient(26.57deg,#0000 0 38px,#00000016 38px 40px),
    repeating-linear-gradient(-26.57deg,#0000 0 38px,#00000016 38px 40px),
    repeating-linear-gradient(26.57deg,#ffffff0c 0 76px,#0000 76px 80px),
    repeating-linear-gradient(-26.57deg,#ffffff0c 0 76px,#0000 76px 80px)}
/* 斜向軌道帶(俯瞰) */
.rail{position:absolute;left:-40px;right:-40px;top:250px;height:56px;transform:rotate(26.57deg);
  transform-origin:center;background:
    linear-gradient(#0000 0 12px,#5b4636 12px 16px,#0000 16px 40px,#5b4636 40px 44px,#0000 44px),
    #8a8f7a55}
.spr{position:absolute;image-rendering:pixelated;filter:drop-shadow(0 3px 2px #0004)}
.station{width:190px;left:120px;top:70px}
.loco{width:150px;left:560px;top:220px}
.foot{display:flex;gap:10px;padding:12px 18px 16px;flex-wrap:wrap}
.btn{background:#4e5058;color:#fff;font-size:15px;font-weight:700;padding:9px 16px;border-radius:8px}
.btn.pri{background:#5865f2}.btn.acc{background:#3ba55d}
</style></head><body><div class="wrap">
  <div class="h">① 8-bit 俯瞰斜角素材（48px · 16 色 · 看不到天空的鳥瞰角度）<small>更粗像素、車頂/屋頂可見</small></div>
  <div class="sheet">${cells}</div>
  <div class="h">② 俯瞰站景面板預覽<small>整片 iso 地面場,無天空 · Tier3 都市駅 + EF210</small></div>
  <div class="embed">
    <div class="hdr"><div style="font-size:32px">🚉</div>
      <div><div class="title">さくら中央 駅</div><div class="sub">Tier 3・地方都市駅　│　月台 3　│　在途 2 班</div></div>
      <div class="teeth">🦷 58,700</div></div>
    <div class="scene">
      <div class="rail"></div>
      <img class="spr station" src="${img('sta_t3_px.png')}">
      <img class="spr loco" src="${img('loco_ef210_px.png')}">
    </div>
    <div class="foot"><div class="btn pri">🚂 派車送貨</div><div class="btn">🛒 購車編組</div>
      <div class="btn acc">🏗️ 車站擴建</div><div class="btn">📋 路線</div><div class="btn">📦 在途看板</div></div>
  </div>
</div></body></html>`;

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 984, height: 1200 }, deviceScaleFactor: 2 });
  await p.setContent(html, { waitUntil: 'load' }); await p.waitForTimeout(300);
  await (await p.$('.wrap')).screenshot({ path: `${D}/td_review.png` });
  console.log('ok'); await b.close();
})();
