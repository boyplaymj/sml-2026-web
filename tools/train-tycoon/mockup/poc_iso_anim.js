// POC:16-bit 斜角像素動圖 — 小車站 + 冒煙火車開過 + 循環
// 程式手繪像素(route ③)驗管線;產 frames → ffmpeg 組 GIF。
const { chromium } = require(process.env.PW_PATH);
const fs = require('fs');
const OUT = '/tmp/train-poc';
fs.mkdirSync(OUT, { recursive: true });

const LW = 220, LH = 150, SCALE = 5;       // 邏輯畫布 + 放大倍率(像素風)
const FRAMES = 24;

const page_html = `<!doctype html><html><head><meta charset="utf-8"><style>
  html,body{margin:0;background:#0b0f14}
  #c{image-rendering:pixelated;display:block}
</style></head><body>
<canvas id="c" width="${LW*SCALE}" height="${LH*SCALE}"></canvas>
<script>
const LW=${LW}, LH=${LH}, S=${SCALE}, FRAMES=${FRAMES};
const TW=28, TH=14;                          // 等距 tile 2:1
const OX=70, OY=40;
const cv=document.getElementById('c'), g=cv.getContext('2d');
g.scale(S,S); g.imageSmoothingEnabled=false;
function px(x,y,w,h,c){ g.fillStyle=c; g.fillRect(x|0,y|0,w|0,h|0); }
function iso(c,r){ return { x: OX+(c-r)*(TW/2), y: OY+(c+r)*(TH/2) }; }
// 菱形 tile(掃描線),topCol 面 + 邊緣暗色,dither 兩色格
function tile(c,r,ca,cb,edge){
  const {x,y}=iso(c,r), cx=x, cy=y;
  for(let iy=0; iy<TH; iy++){
    const dy=iy-TH/2, half=(1-Math.abs(dy)/(TH/2))*(TW/2);
    const x0=Math.round(cx-half), x1=Math.round(cx+half);
    for(let ix=x0; ix<x1; ix++){
      const col=((ix+iy)&1)? ca:cb;
      g.fillStyle=col; g.fillRect(ix, Math.round(cy+dy), 1,1);
    }
  }
  if(edge){ // 前兩邊暗一點做厚度
    for(let iy=0; iy<TH; iy++){
      const dy=iy-TH/2, half=(1-Math.abs(dy)/(TH/2))*(TW/2);
      px(Math.round(cx-half),Math.round(cy+dy),1,1,edge);
      px(Math.round(cx+half)-1,Math.round(cy+dy),1,1,edge);
    }
  }
}
// 軌道 tile(沿 c 軸方向)= 草底 + 枕木 + 兩條銀軌
function railTile(c,r){
  tile(c,r,'#4f9e42','#469439');
  const {x,y}=iso(c,r);
  // 沿 c 方向:每 tile 位移(+TW/2,+TH/2)。畫枕木(垂直於軌)
  for(let t=-1;t<=1;t+=1){
    const bx=x+t*7, by=y+t*3.5;
    px(bx-4,by-1,8,2,'#6b4a2f');
  }
  // 兩條軌
  for(let s=-2;s<=2;s++){
    const ax=x+s*(TW/2)/2, ay=y+s*(TH/2)/2;
    px(ax-3,ay-2,2,1,'#c8c8d0'); px(ax+2,ay+1,2,1,'#c8c8d0');
  }
}
// 等距方塊建物:左牆(W→S 邊)+ 右牆(S→E 邊)垂直拉高 h,再蓋 top 菱形
function isoBox(c,r,h,top,left,right){
  const {x,y}=iso(c,r);
  // 左牆:x 從 x-TW/2 → x,底緣 y 由 y → y+TH/2,整條往上拉 h
  for(let ix=Math.round(x-TW/2); ix<Math.round(x); ix++){
    const frac=(ix-(x-TW/2))/(TW/2), by=y+frac*(TH/2);
    px(ix, Math.round(by-h), 1, Math.round(h), left);
  }
  // 右牆:x 從 x → x+TW/2,底緣 y 由 y+TH/2 → y
  for(let ix=Math.round(x); ix<Math.round(x+TW/2); ix++){
    const frac=(ix-x)/(TW/2), by=(y+TH/2)-frac*(TH/2);
    px(ix, Math.round(by-h), 1, Math.round(h), right);
  }
  // top 菱形(抬高 h)
  for(let iy=0; iy<TH; iy++){
    const dy=iy-TH/2, half=(1-Math.abs(dy)/(TH/2))*(TW/2);
    for(let ix=Math.round(x-half); ix<Math.round(x+half); ix++){
      px(ix, Math.round(y+dy-h),1,1, top);
    }
  }
}
// 火車車廂:畫在軌道 param tc(float c, 固定 r=RAIL_R)上,body 顏色
const RAIL_R=3;
function car(tc, body, trim, isLoco, frame){
  const {x,y}=iso(tc, RAIL_R);
  const bx=Math.round(x), by=Math.round(y);
  // 陰影
  g.globalAlpha=0.25; px(bx-9,by+2,18,3,'#000'); g.globalAlpha=1;
  // 車體(略作等距斜)
  px(bx-9, by-9, 18, 9, body);
  px(bx-9, by-9, 18, 2, trim);          // 頂緣
  px(bx-9, by-1, 18, 2, '#1c1c22');     // 底盤
  // 窗
  for(let w=-6; w<=4; w+=5) px(bx+w, by-7, 3, 3, '#bfe6ff');
  // 車輪(交替)
  const wy=by+1, wof=(frame%2)?0:1;
  px(bx-7+wof, wy, 2,2,'#111'); px(bx+5-wof, wy, 2,2,'#111');
  if(isLoco){
    px(bx-9,by-9,5,9,'#26262e');        // 車頭較深
    px(bx-2, by-13, 3, 4, '#1a1a1f');   // 煙囪
    px(bx+6, by-4, 3, 3, trim);         // 車燈
  }
}
function smoke(cx, cy, age){
  const a=Math.max(0, 1-age/9);
  if(a<=0) return;
  g.globalAlpha=a;
  const sz=2+Math.floor(age/2);
  const col = age<3? '#f2f2f2' : (age<6?'#d8d8d8':'#c2c2c2');
  px(Math.round(cx-sz/2), Math.round(cy-age*2.2), sz, sz, col);
  g.globalAlpha=1;
}
function tree(c,r){
  const {x,y}=iso(c,r);
  px(x-1,y-6,2,6,'#5a3a22');
  px(x-4,y-12,8,7,'#2f7d3a'); px(x-3,y-14,6,3,'#37913f');
}
window.draw=function(frame){
  // 天空
  g.fillStyle='#8fd0ff'; g.fillRect(0,0,LW,LH);
  g.fillStyle='#b9e6c9'; g.fillRect(0,LH*0.55,LW,LH*0.45);
  // 地面草 tile
  for(let r=0;r<6;r++)for(let c=0;c<8;c++){
    if(r===RAIL_R){ railTile(c,r); continue; }
    if(r===RAIL_R-1 && c>=1 && c<=6){ tile(c,r,'#c2c7cd','#b3b8bf','#8f949b'); continue; } // 月台
    tile(c,r,'#54a648','#4b9c3f','#3c7d33');
  }
  // 樹
  tree(0,0); tree(7,0); tree(0,5); tree(6,5);
  // 站房(月台旁)
  isoBox(2, 1, 16, '#a8443a', '#d9c48a', '#b89a5e');
  px(iso(2,1).x-3, iso(2,1).y-12, 3,4,'#6fb7d6');  // 窗
  px(iso(2,1).x+2, iso(2,1).y-12, 3,4,'#6fb7d6');
  px(iso(2,1).x-1, iso(2,1).y-6, 3,6,'#5a3a22');   // 門
  // 號誌閃爍
  px(iso(6,2).x, iso(6,2).y-10, 2,10,'#444');
  px(iso(6,2).x-1, iso(6,2).y-12, 4,3, (frame%8<4)?'#e53a3a':'#5a1a1a');
  // 火車:tc 從 -3 → 10 掃過(頭尾都在畫面外 → 循環無縫)
  const span=13, headTc = -3 + span*(frame/FRAMES);
  // 車序:loco 在最前(tc 最大),後面掛 2 節
  const cars=[ {off:0, loco:true, body:'#2b2b33', trim:'#d24'},
               {off:-1.1, body:'#c94f4f', trim:'#7a2b2b'},
               {off:-2.2, body:'#4f86c9', trim:'#2b4f7a'} ];
  // 由後往前畫(深度)
  for(let i=cars.length-1;i>=0;i--){
    const tc=headTc+cars[i].off;
    if(tc<-2||tc>9) continue;
    car(tc, cars[i].body, cars[i].trim, cars[i].loco, frame);
  }
  // 冒煙:loco 煙囪世界位置,每 2 frame 生一朵,往上飄
  const {x:lx,y:ly}=iso(headTc, RAIL_R);
  for(let bf=frame-16; bf<=frame; bf++){
    if(bf<0) continue; if(bf%2!==0) continue;
    const btc=-3+span*((bf%FRAMES)/FRAMES);
    if(btc<-2||btc>9) continue;
    const {x:px0,y:py0}=iso(btc, RAIL_R);
    smoke(px0-2, py0-14, frame-bf);
  }
};
</script></body></html>`;

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: LW*SCALE, height: LH*SCALE }, deviceScaleFactor: 1 });
  await p.setContent(page_html, { waitUntil: 'load' });
  const c = await p.$('#c');
  for (let f = 0; f < FRAMES; f++) {
    await p.evaluate((f) => window.draw(f), f);
    await c.screenshot({ path: `${OUT}/frame_${String(f).padStart(2,'0')}.png` });
  }
  await b.close();
  console.log(`✅ ${FRAMES} frames → ${OUT}`);
})();
