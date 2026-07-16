// 拆解圖:展示「一堆 emoji 零件 → 合成一張車站圖」
const { chromium } = require(process.env.PW_PATH);
const fs = require('fs');
const OUT = '/tmp/train-mockup';
fs.mkdirSync(OUT, { recursive: true });

const parts = [
  ['☁️', '雲'], ['🏔️', '遠山'], ['🌲', '樹'], ['🏚️', '木造小站'],
  ['🚂', '蒸汽 D51'], ['🚉', '月台'], ['🧍', '乘客'], ['🪧', '站牌'],
];

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Noto Sans CJK TC','Noto Color Emoji',sans-serif}
body{background:#2b2d31;color:#fff;padding:26px;width:760px}
h2{font-size:20px;margin-bottom:12px;color:#f2b6d0}
.tray{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:8px}
.chip{background:#3a3c42;border:2px dashed #6b6e76;border-radius:12px;padding:10px 8px;text-align:center;width:88px}
.chip .g{font-size:44px;line-height:1}
.chip .l{font-size:12px;color:#c8cad0;margin-top:6px}
.arrow{text-align:center;font-size:30px;color:#f2b6d0;margin:6px 0}
.diorama{position:relative;width:708px;height:280px;border-radius:12px;overflow:hidden;
  background:linear-gradient(#bfe3ff,#eaf7ff 72%,#cdeccb 72%,#bfe0bd 100%)}
.e{position:absolute;transform:translateX(-50%);line-height:1;filter:drop-shadow(0 3px 3px #0003)}
.rail{position:absolute;left:0;right:0;bottom:15%;height:7px;
  background:repeating-linear-gradient(90deg,#6b5136 0 10px,#8a6a48 10px 20px);border-top:3px solid #9a9a9a}
.cap{color:#b9bbbe;font-size:13px;margin-top:10px}
</style></head><body>
  <h2>① 零件:每個都是一顆 emoji 字元</h2>
  <div class="tray">
    ${parts.map(([g, l]) => `<div class="chip"><div class="g">${g}</div><div class="l">${l}</div></div>`).join('')}
    <div class="chip"><div class="g" style="font-size:30px;color:#9a9a9a">▬▬</div><div class="l">鐵軌(CSS)</div></div>
  </div>
  <div class="arrow">▼ 程式貼到畫布上、分層疊出來 ▼</div>
  <h2>② 組裝:合成一張 PNG</h2>
  <div class="diorama">
    <div class="e" style="left:16%;top:10%;font-size:40px">☁️</div>
    <div class="e" style="left:64%;top:8%;font-size:34px">☁️</div>
    <div class="e" style="left:72%;bottom:30%;font-size:70px;opacity:.5">🏔️</div>
    <div class="e" style="left:7%;bottom:16%;font-size:56px">🌲</div>
    <div class="e" style="left:90%;bottom:15%;font-size:50px">🌲</div>
    <div class="e" style="left:42%;bottom:20%;font-size:88px">🏚️</div>
    <div class="rail"></div>
    <div class="e" style="left:22%;bottom:15%;font-size:38px">🚉</div>
    <div class="e" style="left:32%;bottom:15%;font-size:68px">🚂</div>
    <div class="e" style="left:20%;bottom:9%;font-size:32px">🧍</div>
    <div class="e" style="left:52%;bottom:9%;font-size:28px">🪧</div>
  </div>
  <div class="cap">↑ 完全同一批 emoji,換位置/尺寸/加背景 → 就是車站場景。升級只是換更氣派的 emoji + 加更多顆。</div>
</body></html>`;

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 760, height: 620 }, deviceScaleFactor: 2 });
  await p.setContent(html, { waitUntil: 'load' });
  await p.waitForTimeout(400);
  await p.screenshot({ path: `${OUT}/breakdown.png` });
  console.log('✅ breakdown → ' + OUT + '/breakdown.png');
  await b.close();
})();
