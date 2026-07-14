// 自動偵測文字方塊重疊：載入海報 → 量測所有含文字元素的 bounding box → 兩兩比對相交
const { chromium } = require(process.env.PW_PATH);
const file = process.argv[2];
const W = +(process.argv[3]||600), H = +(process.argv[4]||820);
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport:{ width:W, height:H }, deviceScaleFactor:1 });
  await p.goto('file://'+file);
  await p.waitForTimeout(400);
  const overlaps = await p.evaluate(() => {
    const els = [...document.querySelectorAll('*')].filter(el => {
      // 只看「直接」含非空白文字的元素（葉節點文字）
      const hasText = [...el.childNodes].some(n => n.nodeType===3 && n.textContent.trim().length);
      if (!hasText) return false;
      const s = getComputedStyle(el);
      if (s.display==='none' || s.visibility==='hidden' || +s.opacity===0) return false;
      const r = el.getBoundingClientRect();
      return r.width>2 && r.height>2;
    });
    const rect = el => { const r=el.getBoundingClientRect();
      return {el, x:r.left, y:r.top, r:r.right, b:r.bottom, t:(el.textContent||'').trim().slice(0,12)}; };
    const boxes = els.map(rect);
    const inter = (a,c) => {
      const ox = Math.min(a.r,c.r)-Math.max(a.x,c.x);
      const oy = Math.min(a.b,c.b)-Math.max(a.y,c.y);
      return (ox>2 && oy>2) ? Math.round(ox*oy) : 0;
    };
    const out=[];
    for (let i=0;i<boxes.length;i++) for (let j=i+1;j<boxes.length;j++){
      const a=boxes[i], c=boxes[j];
      if (a.el.contains(c.el) || c.el.contains(a.el)) continue; // 祖孫不算
      const area = inter(a,c);
      if (area>0) out.push({a:a.t, b:c.t, area,
        ax:Math.round(a.x),ay:Math.round(a.y), cx:Math.round(c.x),cy:Math.round(c.y)});
    }
    return out;
  });
  await b.close();
  if (!overlaps.length) console.log('✅ NO OVERLAP');
  else { console.log('❌ '+overlaps.length+' 組重疊:');
    overlaps.forEach(o=>console.log(`   「${o.a}」×「${o.b}」  相交${o.area}px²  (${o.ax},${o.ay})/(${o.cx},${o.cy})`)); }
})();
