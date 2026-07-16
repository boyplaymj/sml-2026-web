// 甜甜火車大亨 — 車站面板視覺樣稿產生器
// 產出 Tier 1/3/5 三張「完整面板」PNG(embed 頂欄 + 車站側視拼貼場景 + 按鈕列)
// 用法:PW_PATH=<playwright> FONTCONFIG_FILE=~/.fonts/fonts.conf node build.js
const { chromium } = require(process.env.PW_PATH);
const fs = require('fs');

const OUT = '/tmp/train-mockup';
fs.mkdirSync(OUT, { recursive: true });

// 每個 tier 的車站組成(驅動分層畫布,對應 DESIGN §14)
const TIERS = [
  {
    n: 1, name: 'こまち野 小站', tierName: '無人小站', teeth: '1,240',
    w: 720, sky: ['#bfe3ff', '#eaf7ff'],
    skyline: [{ e: '🌲', s: 60, x: 6, b: 18 }, { e: '🌲', s: 50, x: 88, b: 16 }, { e: '🏔️', s: 80, x: 70, b: 30, o: .5 }],
    building: [{ e: '🏚️', s: 96, x: 40 }],
    clock: null,
    platforms: 1,
    trains: [{ e: '🚂', s: 74, x: 30 }],
    fore: [{ e: '🧍', s: 34, x: 22 }, { e: '🪧', s: 30, x: 52 }],
    clouds: [{ x: 15, y: 12, s: 46 }, { x: 66, y: 8, s: 40 }],
    note: '起手:1 月台、木造小站、蒸汽 D51',
  },
  {
    n: 3, name: 'さくら中央 駅', tierName: '地方都市駅', teeth: '58,700',
    w: 860, sky: ['#a9dbff', '#e6f5ff'],
    skyline: [{ e: '🏪', s: 56, x: 8, b: 40 }, { e: '🏬', s: 66, x: 78, b: 42 }, { e: '🌳', s: 54, x: 2, b: 16 }, { e: '🌳', s: 50, x: 93, b: 14 }, { e: '🏢', s: 62, x: 88, b: 44 }],
    building: [{ e: '🏬', s: 104, x: 38 }],
    clock: { e: '🕐', s: 40, x: 47, b: 60 },
    platforms: 3,
    trains: [{ e: '🚆', s: 72, x: 16 }, { e: '🚃', s: 66, x: 30 }, { e: '🚋', s: 70, x: 62 }, { e: '📦', s: 30, x: 74, b: 20 }],
    fore: [{ e: '🚦', s: 40, x: 6 }, { e: '🧑‍🤝‍🧑', s: 38, x: 24 }, { e: '🚕', s: 44, x: 84 }, { e: '🏗️', s: 52, x: 70 }],
    clouds: [{ x: 10, y: 10, s: 44 }, { x: 45, y: 6, s: 38 }, { x: 80, y: 14, s: 42 }],
    note: 'Tier3:3 月台、站房+時鐘、桃太郎/金太郎貨運、貨場吊車、計程車招呼站',
  },
  {
    n: 5, name: 'あまね中央ターミナル', tierName: '大型ターミナル', teeth: '2,910,000',
    w: 1000, sky: ['#8fd0ff', '#dff1ff'],
    skyline: [{ e: '🏙️', s: 120, x: 2, b: 34 }, { e: '🗼', s: 110, x: 84, b: 34 }, { e: '🏢', s: 84, x: 20, b: 46 }, { e: '🏢', s: 78, x: 72, b: 46 }, { e: '🎆', s: 60, x: 50, b: 66 }],
    building: [{ e: '🏛️', s: 120, x: 40 }],
    clock: { e: '🕰️', s: 46, x: 49, b: 66 },
    platforms: 5,
    trains: [{ e: '🚄', s: 78, x: 10 }, { e: '🚅', s: 82, x: 30 }, { e: '🚋', s: 72, x: 60 }, { e: '📦', s: 30, x: 71, b: 20 }, { e: '📦', s: 30, x: 76, b: 20 }],
    fore: [{ e: '⛲', s: 56, x: 6 }, { e: '🌷', s: 34, x: 18 }, { e: '🌷', s: 34, x: 23 }, { e: '👥', s: 40, x: 34 }, { e: '🚕', s: 42, x: 86 }, { e: '🚕', s: 40, x: 92 }, { e: '🐕', s: 34, x: 48 }],
    clouds: [{ x: 8, y: 8, s: 46 }, { x: 40, y: 6, s: 40 }, { x: 68, y: 12, s: 44 }, { x: 90, y: 6, s: 36 }],
    note: 'Tier5:5 月台、天際線+東京鐵塔+航廈、新幹線 N700S/はやぶさ、噴水花圃、甜甜🐕客串',
  },
];

function scene(t) {
  const el = (o, extra = '') =>
    `<div class="e" style="left:${o.x}%;${o.b != null ? 'bottom:' + o.b + '%' : 'bottom:18%'};font-size:${o.s}px;${o.o != null ? 'opacity:' + o.o + ';' : ''}${extra}">${o.e}</div>`;
  const cloud = c => `<div class="cloud" style="left:${c.x}%;top:${c.y}%;font-size:${c.s}px">☁️</div>`;
  // 月台:一條軌道 + N 個月台標記
  const rail = `<div class="rail"></div>`;
  const plats = Array.from({ length: t.platforms }, (_, i) =>
    `<div class="plat" style="left:${8 + i * (84 / t.platforms)}%">🚉</div>`).join('');
  return `
  <div class="diorama" style="width:${t.w}px;background:linear-gradient(#${''}${t.sky[0].slice(1)},#${t.sky[1].slice(1)} 72%,#cdeccb 72%,#bfe0bd 100%)">
    ${t.clouds.map(cloud).join('')}
    <div class="layer skyline">${t.skyline.map(o => el(o)).join('')}</div>
    <div class="layer building">${t.building.map(o => el(o, 'bottom:20%')).join('')}${t.clock ? el(t.clock) : ''}</div>
    ${rail}
    <div class="layer plats">${plats}</div>
    <div class="layer trains">${t.trains.map(o => el(o, 'bottom:15%')).join('')}</div>
    <div class="layer fore">${t.fore.map(o => el(o, 'bottom:9%')).join('')}</div>
  </div>`;
}

function panel(t) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>
    *{margin:0;padding:0;box-sizing:border-box;font-family:'Noto Sans CJK TC','Noto Color Emoji',sans-serif}
    body{padding:26px;background:#2b2d31}
    .embed{width:${t.w}px;background:#313338;border-radius:10px;border-left:5px solid #f2b6d0;overflow:hidden;box-shadow:0 8px 30px #0007}
    .hdr{display:flex;align-items:center;gap:14px;padding:16px 20px 12px}
    .ava{font-size:34px}
    .htxt{flex:1}
    .title{color:#fff;font-size:22px;font-weight:900;letter-spacing:.5px}
    .sub{color:#b9bbbe;font-size:14px;margin-top:2px}
    .teeth{background:#f2b6d0;color:#5c1c38;font-weight:900;font-size:18px;padding:6px 14px;border-radius:20px}
    .diorama{position:relative;height:360px;overflow:hidden;margin:2px 0}
    .cloud{position:absolute;opacity:.9;filter:drop-shadow(0 2px 2px #fff6)}
    .layer{position:absolute;inset:0}
    .e{position:absolute;transform:translateX(-50%);line-height:1;filter:drop-shadow(0 3px 3px #0003)}
    .rail{position:absolute;left:0;right:0;bottom:15%;height:8px;background:repeating-linear-gradient(90deg,#6b5136 0 10px,#8a6a48 10px 20px);border-top:3px solid #9a9a9a;box-shadow:0 3px 0 #7a5a3a}
    .plat{position:absolute;bottom:15%;transform:translateX(-50%);font-size:40px;filter:drop-shadow(0 3px 3px #0003)}
    .foot{display:flex;gap:10px;padding:12px 18px 16px;flex-wrap:wrap;background:#313338}
    .btn{background:#4e5058;color:#fff;font-size:15px;font-weight:700;padding:9px 16px;border-radius:8px}
    .btn.pri{background:#5865f2}
    .btn.acc{background:#3ba55d}
    .cap{color:#f2b6d0;font-size:13px;padding:0 20px 16px;background:#313338}
  </style></head><body>
    <div class="embed">
      <div class="hdr">
        <div class="ava">🚉</div>
        <div class="htxt">
          <div class="title">${t.name}</div>
          <div class="sub">Tier ${t.n}・${t.tierName}　│　月台 ${t.platforms}　│　在途 ${t.n} 班</div>
        </div>
        <div class="teeth">🦷 ${t.teeth}</div>
      </div>
      ${scene(t)}
      <div class="foot">
        <div class="btn pri">🚂 派車送貨</div>
        <div class="btn">🛒 購車編組</div>
        <div class="btn acc">🏗️ 車站擴建</div>
        <div class="btn">📋 路線</div>
        <div class="btn">📦 在途看板</div>
        <div class="btn">🏆 排行</div>
      </div>
      <div class="cap">▶ ${t.note}</div>
    </div>
  </body></html>`;
}

(async () => {
  const b = await chromium.launch();
  for (const t of TIERS) {
    const p = await b.newPage({ viewport: { width: t.w + 52, height: 560 }, deviceScaleFactor: 2 });
    await p.setContent(panel(t), { waitUntil: 'load' });
    await p.waitForTimeout(400);
    const embed = await p.$('.embed');
    await embed.screenshot({ path: `${OUT}/tier${t.n}.png` });
    console.log(`✅ tier${t.n} → ${OUT}/tier${t.n}.png`);
    await p.close();
  }
  await b.close();
})();
