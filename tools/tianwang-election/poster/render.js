const { chromium } = require(process.env.PW_PATH);
const jobs = [
  ['A','/tmp/poster/poster_A.html',600,820],
  ['B','/tmp/poster/poster_B.html',600,820],
  ['C','/tmp/poster/poster_C.html',600,820],
  ['M','/tmp/poster/poster_M.html',720,720],
];
async function overlaps(p){
  return await p.evaluate(() => {
    const els=[...document.querySelectorAll('*')].filter(el=>{
      const t=[...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim().length);
      if(!t) return false; const s=getComputedStyle(el);
      if(s.display==='none'||s.visibility==='hidden'||+s.opacity===0) return false;
      const r=el.getBoundingClientRect(); return r.width>2&&r.height>2;
    });
    const B=els.map(el=>{const r=el.getBoundingClientRect();
      return{el,x:r.left,y:r.top,r:r.right,b:r.bottom,t:(el.textContent||'').trim().slice(0,10)};});
    const out=[];
    for(let i=0;i<B.length;i++)for(let j=i+1;j<B.length;j++){const a=B[i],c=B[j];
      if(a.el.contains(c.el)||c.el.contains(a.el))continue;
      const ox=Math.min(a.r,c.r)-Math.max(a.x,c.x),oy=Math.min(a.b,c.b)-Math.max(a.y,c.y);
      if(ox>2&&oy>2)out.push(`${a.t}×${c.t}(${Math.round(ox*oy)}px²)`);}
    return out;
  });
}
(async()=>{
  const b=await chromium.launch(); let fail=0;
  for(const [name,file,w,h] of jobs){
    const p=await b.newPage({viewport:{width:w,height:h},deviceScaleFactor:2});
    await p.goto('file://'+file); await p.waitForTimeout(450);
    await p.screenshot({path:`/tmp/poster/out_${name}.png`});
    const ov=await overlaps(p);
    if(ov.length){fail++;console.log(`❌ ${name}: ${ov.join(', ')}`);}
    else console.log(`✅ ${name}: 無重疊`);
    await p.close();
  }
  await b.close();
  process.exit(fail?1:0);
})();
