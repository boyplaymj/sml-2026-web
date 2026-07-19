const sharp=require("/opt/sml/sweetbot-next/node_modules/sharp");
const W=1024,H=637,SIDE_W=192;
const POS=[
 {key:'okusha_top',name:'奧社',row:0,x:639,y:110},
 {key:'okusha_stair',name:'奧社樓梯',row:0,x:370,y:243},
 {key:'gokitou',name:'御祈禱',row:1,x:447,y:346},
 {key:'honden',name:'本殿',row:2,x:650,y:362},
 {key:'goshuin',name:'御朱印',row:3,x:806,y:332},
 {key:'juyosho',name:'授與所',row:4,x:901,y:352},
 {key:'temizu',name:'手水舍',row:5,x:373,y:435},
 {key:'kosatsu',name:'古札納所',row:6,x:466,y:522},
 {key:'ichiba',name:'市集',row:7,x:603,y:474},
 {key:'torii',name:'鳥居',row:8,x:645,y:601},
];
const labelY=i=>Math.round((0.06+i*0.108)*H);
function pin(size){const s=size,w=Math.round(s*0.78);return Buffer.from(`
 <svg width="${w}" height="${s}" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
  <ellipse cx="${w/2}" cy="${s-2}" rx="${w*0.28}" ry="${s*0.05}" fill="#000" opacity="0.30"/>
  <path d="M${w/2} ${s} L${w*0.18} ${s*0.42} L${w*0.82} ${s*0.42} Z" fill="#c0392b" stroke="#5a0f14" stroke-width="${s*0.05}"/>
  <rect x="${w*0.12}" y="${s*0.06}" width="${w*0.76}" height="${s*0.42}" rx="${w*0.14}" fill="#e63946" stroke="#5a0f14" stroke-width="${s*0.05}"/>
  <rect x="${w*0.32}" y="${s*0.16}" width="${w*0.36}" height="${s*0.22}" rx="${w*0.06}" fill="#fff3c4" stroke="#5a0f14" stroke-width="${s*0.035}"/>
 </svg>`);}
async function one(p,out){ // 單一位置圖:地圖釘 + 側欄小釘
  const mp=await sharp(pin(48)).png().toBuffer(); const mm=await sharp(mp).metadata();
  const sp=await sharp(pin(26)).png().toBuffer(); const sm=await sharp(sp).metadata();
  const ly=labelY(p.row);
  await sharp("/tmp/shrine_base.png").composite([
    {input:sp,left:SIDE_W-sm.width-10,top:ly-Math.round(sm.height/2)},
    {input:mp,left:p.x-Math.round(mm.width/2),top:p.y-mm.height}
  ]).png().toFile(out);
}
async function allPins(out){ // 驗證圖:全部釘一次+名稱
  const comp=[]; let labels="";
  for(const p of POS){const mp=await sharp(pin(42)).png().toBuffer();const mm=await sharp(mp).metadata();
    comp.push({input:mp,left:p.x-Math.round(mm.width/2),top:p.y-mm.height});
    labels+=`<text x="${p.x}" y="${p.y+13}" font-size="13" font-family="sans-serif" font-weight="bold" fill="#fff" stroke="#000" stroke-width="0.6" text-anchor="middle">${p.name}</text>`;}
  comp.push({input:Buffer.from(`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">${labels}</svg>`),left:0,top:0});
  await sharp("/tmp/shrine_base.png").composite(comp).png().toFile(out);
}
module.exports={POS,one,allPins};
