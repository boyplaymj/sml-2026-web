// 斜角(等距 isometric)結構驗證:證明菱形 tile 可照等距網格鋪 + 疊物件(軌道/月台/站體/列車)
// 這是「結構證明」用 CSS 畫的 tile,非最終美術。
const { chromium } = require(process.env.PW_PATH);
const fs = require('fs');
const OUT = '/tmp/train-mockup';
fs.mkdirSync(OUT, { recursive: true });

const TW = 96, TH = 48;          // tile 寬/高 2:1
const COLS = 9, ROWS = 7;
const ORIGIN_X = 470, ORIGIN_Y = 70;

// 地圖:0 草 / 1 軌道(橫) / 2 軌道(直) / 3 月台 / 4 道路
const G = [
  [0,0,4,4,4,4,4,0,0],
  [0,0,4,0,0,0,4,0,0],
  [1,1,1,1,1,1,1,1,1],
  [0,3,3,3,3,3,3,3,0],
  [2,2,2,2,2,2,2,2,2],
  [0,0,0,0,0,0,0,0,0],
  [0,0,0,0,0,0,0,0,0],
];
const TILE_CSS = {
  0:'linear-gradient(145deg,#7bc86b,#5fa851)',
  1:'linear-gradient(145deg,#8a6a48,#6b5136)',
  2:'linear-gradient(145deg,#8a6a48,#6b5136)',
  3:'linear-gradient(145deg,#c7ccd1,#9aa0a6)',
  4:'linear-gradient(145deg,#5a5f66,#43474d)',
};
function iso(c,r){ return { x: ORIGIN_X + (c-r)*(TW/2), y: ORIGIN_Y + (c+r)*(TH/2) }; }

let tiles = '';
for(let r=0;r<ROWS;r++)for(let c=0;c<COLS;c++){
  const {x,y}=iso(c,r); const t=G[r][c];
  // 軌道方向紋
  let rail='';
  if(t===1) rail=`<div class="rail rx"></div>`;
  if(t===2) rail=`<div class="rail ry"></div>`;
  tiles += `<div class="tile" style="left:${x}px;top:${y}px;background:${TILE_CSS[t]};z-index:${r+c}">${rail}</div>`;
}

// 物件(billboard):放在某格、往上抬,z-index 用 r+c 做深度排序
const OBJ = [
  {c:3,r:1,e:'🏢',s:104,dy:70,z:0},   // 站房後方大樓
  {c:5,r:1,e:'🏬',s:96,dy:64},
  {c:1,r:0,e:'🌳',s:56,dy:40},
  {c:7,r:0,e:'🌳',s:56,dy:40},
  {c:4,r:1,e:'🕐',s:38,dy:150},
  {c:1,r:2,e:'🚋',s:70,dy:44},         // 軌道上的貨列
  {c:3,r:2,e:'🚆',s:74,dy:46},
  {c:6,r:2,e:'🚃',s:66,dy:44},
  {c:4,r:3,e:'🧑‍🤝‍🧑',s:40,dy:30},   // 月台乘客
  {c:2,r:3,e:'🧍',s:36,dy:28},
  {c:6,r:3,e:'🪑',s:34,dy:26},
  {c:4,r:4,e:'🚄',s:80,dy:48},         // 直向軌道新幹線
  {c:2,r:0,e:'🚕',s:44,dy:36},         // 道路計程車
];
let objs='';
for(const o of OBJ){
  const {x,y}=iso(o.c,o.r);
  objs += `<div class="obj" style="left:${x}px;top:${y-o.dy}px;font-size:${o.s}px;z-index:${(o.z??(o.r+o.c))+100}">${o.e}</div>`;
}

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Noto Sans CJK TC','Noto Color Emoji',sans-serif}
body{background:linear-gradient(#9bd7f2,#cdeccb);width:940px;height:600px;position:relative;overflow:hidden}
.stage{position:absolute;inset:0}
.tile{position:absolute;width:${TW}px;height:${TH}px;transform:translate(-50%,-50%);
  clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%);border:1px solid #0002}
.rail{position:absolute;left:50%;top:50%}
.rail.rx{width:${TW}px;height:6px;transform:translate(-50%,-50%) rotate(26.57deg);
  background:repeating-linear-gradient(90deg,#bbb 0 3px,transparent 3px 9px),linear-gradient(#999,#777);border-radius:2px}
.rail.ry{width:${TW}px;height:6px;transform:translate(-50%,-50%) rotate(-26.57deg);
  background:repeating-linear-gradient(90deg,#bbb 0 3px,transparent 3px 9px),linear-gradient(#999,#777);border-radius:2px}
.obj{position:absolute;transform:translate(-50%,-50%);line-height:1;filter:drop-shadow(0 4px 3px #0004)}
.hud{position:absolute;left:20px;top:16px;background:#000a;color:#fff;padding:10px 16px;border-radius:10px;font-size:15px;font-weight:700}
.hud b{color:#f2b6d0}
.tag{position:absolute;right:18px;bottom:14px;background:#0009;color:#ffd;padding:6px 12px;border-radius:8px;font-size:13px}
</style></head><body>
  <div class="stage">${tiles}${objs}</div>
  <div class="hud">🚉 <b>斜角車站</b>　等距 ${COLS}×${ROWS} 網格　│　🦷 128,400</div>
  <div class="tag">結構驗證:菱形 tile 照等距座標鋪 + 深度排序疊物件(軌道/月台/站體/列車)</div>
</body></html>`;

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 940, height: 600 }, deviceScaleFactor: 2 });
  await p.setContent(html, { waitUntil: 'load' });
  await p.waitForTimeout(400);
  await p.screenshot({ path: `${OUT}/iso.png` });
  console.log('✅ iso → ' + OUT + '/iso.png');
  await b.close();
})();
