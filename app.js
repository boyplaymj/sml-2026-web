/* ====================================================================
   SML 個人賽 2026 ・ 資料區
   ── 要更新選手數據 / 積分,只改下面這兩個物件就好,畫面會自動重繪 ──
   radar / career 六軸順序(對應 HUD #lbl-0~5): [效率, 攻擊力, 防守力, 技術, 爆發力, 穩定度] (0~100 裝甲值)
   標準賽季數據: pts 賽季積分 / games 出賽 / tsumo 自摸 / hu 胡牌 / deal 放槍
   color 為選手專屬色(對應計分後台 team_color)
   ==================================================================== */
const RADAR_AXES = ['效率','攻擊力','防守力','技術','爆發力','穩定度'];
const WINDS = ['東','南','西','北'];

// p(組別, 主題色, 雷達, 生涯雷達, 賽季數據)
function p(grp,color,radar,career,st){return {grp,color,radar,career,...st};}
const PLAYERS = {
  // ── 男生組 ──
  '老許':  p('men','#a312f0',[55,78,62,60,70,58],[52,74,60,57,66,55],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '賊恩':  p('men','#15d6c7',[70,65,55,72,60,63],[66,62,53,68,57,60],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '杯尼':  p('men','#1577ff',[60,58,75,55,50,80],[57,55,72,53,48,76],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '李晟':  p('men','#ff73c8',[80,68,60,65,72,55],[76,64,57,62,68,52],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '田亞霍':p('men','#ffb81a',[58,82,50,70,78,52],[55,78,48,66,74,50],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '家聲':  p('men','#ffb81a',[65,60,70,58,55,74],[62,57,67,55,52,70],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '肯尼':  p('men','#ff1e2d',[72,70,68,66,64,70],[70,68,66,64,62,68],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '小于':  p('men','#2bff88',[50,62,58,80,68,60],[48,59,55,76,64,57],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  // ── 女生組 ──
  '涵涵':  p('women','#9aa1aa',[68,72,60,64,66,62],[65,69,57,61,63,59],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '黃黃':  p('women','#a312f0',[75,60,70,55,52,78],[72,57,67,53,50,75],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '湘湘':  p('women','#ff4fa0',[60,78,55,72,74,54],[57,74,52,68,70,52],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '令兒':  p('women','#15d6c7',[82,65,62,60,58,72],[78,62,59,57,55,69],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '宜臻':  p('women','#1577ff',[58,68,76,62,60,66],[55,65,73,59,57,63],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '肉肉':  p('women','#c2651c',[70,74,66,68,70,68],[68,72,64,66,68,66],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '歐歐':  p('women','#2bff88',[64,58,72,76,55,60],[61,55,69,72,52,57],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
  '李泥':  p('women','#ff86d5',[55,80,52,66,82,50],[52,76,50,63,78,48],{pts:0,games:0,tsumo:0,hu:0,deal:0}),
};

/* 選手 HUD 詳細數據(依 SML 數據規格)。賽季未開打 → 全部預設值(0 或 '-')。
   日後有資料時,把該選手的欄位覆蓋進 PLAYER_STATS['名字'] 即可。 */
// 欄位代碼=SML HUD 規格;由後台 Firebase 直接送同名欄位即可顯示
const DEFAULT_STATS = {
  // Page1 整體綜合與機率
  total_hanchan:0, avg_rank:0, win_rate:0, tsumo_rate:0, deal_in_rate:0,
  // Page2 攻擊火力與連莊
  total_points_won:0, avg_points_won:0, max_points_won:0, scoring_count:0, scoring_interval:0, max_renchan:0, avg_renchan:0,
  // Page3 防守失血與同分判定
  total_points_lost:0, loss_interval:0, tsumo_count:0, win_count:0, deal_in_count:0,
  // 最常胡牌 Top3: [{tile:'6p', rate:18.5}, ...]
  favorite_tiles:[],
};
const PLAYER_STATS = {};                                   // 由 applyLiveData 從 Firebase 灌入
const statOf = n => ({...DEFAULT_STATS, ...(PLAYER_STATS[n]||{})});

/* 選手簡介(約 100 字內,先放範例文字,日後直接覆蓋即可) */
const BIOS = {
  '老許':'攻守兼備的全能型選手，讀牌精準、節奏沉穩，擅長在中盤後段一口氣翻盤。場上表情管理一流，是對手最難捉摸的存在。（範例簡介，待填）',
  '賊恩':'速度型快攻好手，前段聽牌速度極快，靠高頻率的胡牌累積優勢。膽大心細，敢在關鍵局放手一搏。（範例簡介，待填）',
  '杯尼':'以防守見長的鐵壁型選手，極少放槍，總能在劣勢局穩住失分。擅長讀危險牌，把牌局拖進自己的節奏。（範例簡介，待填）',
  '李晟':'運氣與爆發兼具的莊家殺手，連莊壓制力強，一旦坐莊往往能滾出大量分數。進攻火力是全場焦點。（範例簡介，待填）',
  '田亞霍':'重砲型打點王，主攻大牌與混清一色，單把打點驚人。寧可慢一點也要追求高分，是場上的得分爆點。（範例簡介，待填）',
  '家聲':'穩健派代表，攻守平衡、失誤極少，靠紮實的基本功累積穩定積分。長線作戰能力強，後勁十足。（範例簡介，待填）',
  '肯尼':'經驗老到的全能型選手，六維數值均衡，臨場判斷成熟。身兼賽評視角，對局勢的掌握格外細膩。（範例簡介，待填）',
  '小于':'靈活的速攻型選手，腳步輕快、轉守為攻迅速，常以連續小胡擾亂對手節奏。新生代潛力股。（範例簡介，待填）',
  '涵涵':'攻守俱佳的均衡型選手，讀牌細膩、出牌果決，擅長在亂局中找到最佳解。穩定輸出的女子組主力。（範例簡介，待填）',
  '黃黃':'防守型穩健好手，放槍率極低，靠耐心與止血能力消耗對手。越到後段越冷靜，是難纏的對手。（範例簡介，待填）',
  '湘湘':'進攻慾望旺盛的爆發型選手，敢衝敢拚，常以高打點一舉拉開差距。場上氣勢十足，極具觀賞性。（範例簡介，待填）',
  '令兒':'運氣與手感俱佳的自摸型選手，獨立得分能力強，不依賴對手放槍。節奏掌控細膩，後勁可期。（範例簡介，待填）',
  '宜臻':'防守反擊型選手，前期蟄伏、後期發力，擅長抓對手的危險牌。冷靜理性，是典型的技術流。（範例簡介，待填）',
  '肉肉':'全能型核心選手，六維數值全面，攻守轉換流暢。兼任賽評，對牌局節奏與心理戰的理解極深。（範例簡介，待填）',
  '歐歐':'速度與防守兼具的均衡型選手，腳步快、失分少，擅長穩中求勝。臨場應變能力出色。（範例簡介，待填）',
  '李泥':'極致進攻的重砲手，爆發力全場頂尖，主打大牌一發逆轉。高風險高報酬，是場上的不定時炸彈。（範例簡介，待填）',
};
const bioOf = n => BIOS[n] || '（選手簡介待補）';

// 賽程: {g 場次, date 'M/D', cast 賽評, players 出賽四人(東南西北順序)}
const SCHEDULE = {
  men:[
    {g:1, date:'6/23', cast:'肯尼', players:['老許','賊恩','杯尼','李晟']},
    {g:2, date:'6/30', cast:'肉肉', players:['田亞霍','家聲','肯尼','小于']},
    {g:3, date:'7/7',  cast:'肉肉', players:['老許','賊恩','田亞霍','家聲']},
    {g:4, date:'7/14', cast:'肉肉', players:['杯尼','李晟','肯尼','小于']},
    {g:5, date:'7/21', cast:'肉肉', players:['老許','杯尼','田亞霍','肯尼']},
    {g:6, date:'7/28', cast:'肉肉', players:['賊恩','李晟','家聲','小于']},
    {g:7, date:'8/4',  cast:'肉肉', players:['老許','李晟','家聲','肯尼']},
    {g:8, date:'8/11', cast:'肉肉', players:['賊恩','杯尼','田亞霍','小于']},
    {g:9, date:'8/18', cast:'肉肉', players:['老許','杯尼','家聲','小于']},
    {g:10,date:'8/25', cast:'肉肉', players:['賊恩','李晟','田亞霍','肯尼']},
  ],
  women:[
    {g:1, date:'6/29', cast:'肯尼', players:['涵涵','黃黃','湘湘','令兒']},
    {g:2, date:'7/6',  cast:'肯尼', players:['宜臻','肉肉','歐歐','李泥']},
    {g:3, date:'7/13', cast:'肯尼', players:['涵涵','黃黃','宜臻','肉肉']},
    {g:4, date:'7/20', cast:'肯尼', players:['湘湘','令兒','歐歐','李泥']},
    {g:5, date:'7/27', cast:'肉肉', players:['涵涵','湘湘','宜臻','歐歐']},
    {g:6, date:'8/3',  cast:'肯尼', players:['黃黃','令兒','肉肉','李泥']},
    {g:7, date:'8/10', cast:'肯尼', players:['涵涵','令兒','肉肉','歐歐']},
    {g:8, date:'8/17', cast:'肯尼', players:['黃黃','湘湘','宜臻','李泥']},
    {g:9, date:'8/24', cast:'肯尼', players:['涵涵','湘湘','肉肉','李泥']},
    {g:10,date:'8/31', cast:'肯尼', players:['黃黃','令兒','宜臻','歐歐']},
  ],
};

const TODAY = '2026-6-23';                 // 今天(用於月曆標示)
const grpName = g => g==='men' ? '男生組' : '女生組';
const photo   = n => `assets/players/${n}.png`;
const fmtPts  = v => v>0 ? '+'+v : (v<0 ? ''+v : '0');
const avaHTML = (n,p) => `<div class="ava" style="--c:${p.color}">${n[0]}<img src="${photo(n)}" alt="${n}" onerror="this.remove()"></div>`;

const DEFAULT_HOST = '伯夷';                      // 主播 (預設,可在各場 SCHEDULE 加 host 覆蓋)

/* 選手圖片:各用途有專屬資料夾,載入失敗時依序退回 full/ → 大頭照,全失敗才隱藏。
   matchup=本週對戰 / grid=選手一覽方塊 / profile=雷達面板大圖 / calendar=月曆 */
const imgCands = (n,folder) => {
  if(folder==='grid')   // 方塊縮圖:直接用方形大頭照(沒用 grid/ 資料夾,免得 404)
    return [`assets/players/${n}.png`,`assets/players/full/${n}.png`];
  if(folder==='matchup' || folder==='calendar')   // NEXT GAME / 月曆:優先 webp，找不到再 fallback png
    return [`assets/players/${folder}/${n}.webp`,`assets/players/${folder}/${n}.png`,`assets/players/profile/${n}.png`,`assets/players/full/${n}.png`,`assets/players/${n}.png`];
  return [`assets/players/${folder}/${n}.png`,`assets/players/full/${n}.png`,`assets/players/${n}.png`];
};
function stepImg(el){
  const c=(el.getAttribute('data-cands')||'').split('|').filter(Boolean);
  if(c.length){ el.setAttribute('data-cands',c.slice(1).join('|')); el.src=c[0]; }
  else { el.onerror=null; el.style.display='none'; }
}
// innerHTML 用:回傳 img 的屬性字串(自帶退回鏈)
const imgAttrs = (n,folder,cls) => { const c=imgCands(n,folder);
  return `${cls?`class="${cls}" `:''}src="${c[0]}" data-cands="${c.slice(1).join('|')}" onerror="stepImg(this)" alt="${n}"`; };
// JS 設定 .src 用(雷達面板、選手一覽左側大圖)
function loadImg(elId,name,folder){ const el=document.getElementById(elId),c=imgCands(name,folder);
  el.setAttribute('data-cands',c.slice(1).join('|')); el.onerror=()=>stepImg(el); el.style.display=''; el.src=c[0]; }
function autoFeatured(){
  const now = new Date(), yr = now.getFullYear();
  const all = [
    ...(SCHEDULE.men   ||[]).map((g,i)=>({grp:'men',  i,...g})),
    ...(SCHEDULE.women ||[]).map((g,i)=>({grp:'women',i,...g}))
  ];
  let best=null, bestDt=null;
  for(const g of all){
    const [m,d]=(g.date||'').split('/').map(Number);
    if(!m||!d) continue;
    const dt=new Date(yr,m-1,d,23,59,59);           // 當天 23:59 前都算「即將」
    if(dt>=now && (!bestDt||dt<bestDt)){best=g; bestDt=dt;}
  }
  return best ? {grp:best.grp,i:best.i} : {grp:'men',i:(SCHEDULE.men||[]).length-1};
}
const FEATURED = autoFeatured();                    // 首頁「本週對戰」自動抓最近場次

/* ---------- 本週對戰 ・ 選角卡 ---------- */
function renderFeatured(){
  const gm = SCHEDULE[FEATURED.grp][FEATURED.i];
  const cells = gm.players.map(n=>{const pl=PLAYERS[n];return `
    <div class="vs-cell" style="--c:${pl.color}" onclick="openPlayer('${n}')" title="${n} ・ 查看戰力">
      <img ${imgAttrs(n,'matchup','vs-img')}>
      <div class="vs-tint"></div><div class="vs-bar"></div><div class="vs-sheen"></div>
      <div class="vs-name">${n}</div>
    </div>`;}).join('');
  document.getElementById('live').innerHTML = `
    <div class="matchup-head" onclick="gotoFeaturedGame()" style="cursor:pointer" title="展開本場賽程">
      <span class="tag"><span class="dot"></span>NEXT GAME ・ ${grpName(FEATURED.grp)} Game ${gm.g}</span>
      <time>${gm.date} ↓</time>
    </div>
    <div class="vs-stage">${cells}</div>
    <div class="matchup-foot">
      <span>主播 ${gm.host||DEFAULT_HOST}　|　賽評 ${gm.cast}</span>
      <a href="#schedule" onclick="event.preventDefault();gotoFeaturedGame()">本季賽程 →</a>
    </div>
    <div class="waves"><i class="wave-back"></i><i class="wave-front"></i></div>`;
}

/* ---------- 賽事精華 ・ Reels / Shorts ---------- */
const ytThumb = id => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;   // 與後台 reels_manager 同邏輯
function renderReels(reels){
  const sec  = document.getElementById('reels');
  const grid = document.getElementById('reelsGrid');
  if(!grid) return;
  // 顯示順序 = 後台排序(第 1 則在最左);後台新增插最前、可用 ↑/↓ 自訂
  const items = (Array.isArray(reels) ? reels : []).filter(r => r && r.enabled !== false);
  if(!items.length){ if(sec) sec.hidden = true; grid.innerHTML = ''; return; }   // 沒有精華就整段收起,不留空標題
  if(sec) sec.hidden = false;
  const esc = s => String(s==null?'':s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  grid.innerHTML = items.map(it=>{
    const thumb = it.thumb || (it.yt ? ytThumb(it.yt) : '');   // YouTube 自動抓,其餘用後台存的封面
    const plat  = it.yt ? 'YouTube' : 'Instagram';
    const img   = thumb ? `<img src="${esc(thumb)}" alt="" loading="lazy" onerror="this.style.display='none'">` : '';
    return `<a class="reel" href="${esc(it.url)}" target="_blank" rel="noopener" title="觀看完整片段">
      <div class="reel-thumb">${img}
        <span class="reel-plat">${plat}</span>
        <span class="reel-play">▶</span>
      </div>
    </a>`;
  }).join('');
}

/* ---------- 選手一覽 (hover 預覽 + 點擊展開) ---------- */
let previewChar = null;
function renderCharSelect(){
  const grid = grp => Object.entries(PLAYERS).filter(([,p])=>p.grp===grp).map(([n,p])=>`
    <button class="cs-portrait" data-name="${n}" style="--c:${p.color}"
      onmouseenter="selectChar('${n}')" onfocus="selectChar('${n}')" onclick="selectChar('${n}');openPlayer('${n}')">
      <img ${imgAttrs(n,'grid')}><div class="cs-wave"></div><div class="cs-wave"></div><span class="cs-pn">${n}</span>
    </button>`).join('');
  document.getElementById('charSelect').innerHTML = `
    <div class="cs-splash" id="csSplash" style="--c:#fbbf24" onclick="previewChar&&openPlayer(previewChar)" title="點擊展開完整數據">
      <img class="cs-img" id="cs-img" alt="">
      <div class="cs-grad"></div><div class="cs-edge"></div>
      <div class="cs-info">
        <div class="cs-grp" id="cs-grp"></div>
        <div class="cs-name" id="cs-name"></div>
        <button class="cs-btn" id="cs-btn">展開完整數據 →</button>
      </div>
    </div>
    <div class="cs-side">
      <div><div class="cs-glabel"><i style="background:#38bdf8"></i>男生組</div><div class="cs-grid">${grid('men')}</div></div>
      <div><div class="cs-glabel"><i style="background:#f472b6"></i>女生組</div><div class="cs-grid">${grid('women')}</div></div>
    </div>`;
  selectChar(Object.keys(PLAYERS)[0]);
}
function selectChar(name){
  const pl = PLAYERS[name]; if(!pl) return;
  previewChar = name;
  document.getElementById('csSplash').style.setProperty('--c', pl.color);
  loadImg('cs-img', name, 'profile');
  document.getElementById('cs-grp').innerText = grpName(pl.grp);
  document.getElementById('cs-name').innerText = name;
  document.querySelectorAll('.cs-portrait').forEach(b=>b.classList.toggle('sel', b.dataset.name===name));
}

/* ---------- 積分榜 (動態排行榜) ---------- */
const rankSuffix = r => r===1?'st':r===2?'nd':r===3?'rd':'th';
const rankColor  = r => r===1?'#fbbf24':r===2?'#e2e8f0':r===3?'#f59e0b':'rgba(255,255,255,.42)';
function renderStandings(){
  const head = `<div class="lb-head"><span class="l">#</span><span class="l">選手</span>
    <span>出賽</span><span>自摸</span><span>胡牌</span><span>放槍</span><span>賽季積分</span></div>`;
  for(const grp of ['men','women']){
    const rows = Object.entries(PLAYERS).filter(([,p])=>p.grp===grp)
      .sort((a,b)=> b[1].pts-a[1].pts || a[1].games-b[1].games || b[1].tsumo-a[1].tsumo || b[1].hu-a[1].hu || a[1].deal-b[1].deal);
    document.getElementById('board-'+grp).innerHTML = `<div class="lb">` + head + rows.map(([n,p],i)=>{
      const r=i+1;
      return `<div class="lb-row" style="--c:${p.color};opacity:0" onclick="openPlayer('${n}')">
        <div class="lb-bg"><div class="lb-grad"></div><i class="lb-wave lb-w1"></i><i class="lb-wave lb-w2"></i><div class="lb-dust"></div></div>
        <div class="lb-grid">
          <div class="lb-rank" style="color:${rankColor(r)}">${r}<small>${rankSuffix(r)}</small></div>
          <div class="lb-who"><div class="lb-ava ava" style="--c:${p.color}">${n[0]}<img src="${photo(n)}" alt="${n}" onerror="this.remove()"></div>
            <div class="lb-name">${n}<small>${grpName(grp)}</small></div></div>
          <div class="lb-num">${p.games}</div><div class="lb-num g">${p.tsumo}</div>
          <div class="lb-num">${p.hu}</div><div class="lb-num r">${p.deal}</div>
          <div class="lb-total"><div class="lb-totbox"><div class="lb-totval" data-v="${p.pts}">${fmtScore(p.pts)}</div></div></div>
        </div></div>`;}).join('') + `</div>`;
  }
}
function animateBoard(grp){
  const root = document.getElementById('board-'+grp); if(!root) return;
  const rows = root.querySelectorAll('.lb-row');
  const reduceM = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(reduceM || !window.gsap){ rows.forEach(r=>{r.style.opacity=1;r.style.transform='none';}); return; }
  gsap.killTweensOf(rows);
  gsap.fromTo(rows,{opacity:0,x:-80},{opacity:1,x:0,duration:.7,stagger:.09,ease:'back.out(1.2)'});
  root.querySelectorAll('.lb-totval').forEach(el=>{
    const end=parseFloat(el.dataset.v)||0, o={v:0};
    gsap.to(o,{v:end,duration:1.1,ease:'power2.out',onUpdate:()=>el.innerText=o.v.toFixed(2)});
  });
}

/* ---------- 月曆 ---------- */
function renderCalendar(){
  const byKey = {};
  for(const grp of ['men','women'])
    SCHEDULE[grp].forEach((gm,i)=>{ byKey[gm.date.replace('/','-')] = {grp,i,...gm}; });

  const months = [[2026,6,'六月'],[2026,7,'七月'],[2026,8,'八月']];
  const dow = ['日','一','二','三','四','五','六'].map(x=>`<div class="cal-dow">${x}</div>`).join('');
  let html='';
  for(const [y,m,name] of months){
    const first = new Date(y,m-1,1).getDay();
    const days  = new Date(y,m,0).getDate();
    let cells='';
    for(let i=0;i<first;i++) cells+='<div class="cal-cell empty"></div>';
    for(let d=1;d<=days;d++){
      const gm = byKey[`${m}-${d}`];
      const isToday = (`${y}-${m}-${d}`===TODAY);
      if(gm){
        const gc = gm.grp==='men' ? '#38bdf8' : '#f472b6';
        cells+=`<button class="cal-cell game ${isToday?'today':''}" style="--gc:${gc}" onclick="openGame('${gm.grp}',${gm.i})">
          <span class="cal-num">${d}</span><span class="cal-pill">${gm.grp==='men'?'男':'女'}G${gm.g}</span></button>`;
      }else{
        cells+=`<div class="cal-cell ${isToday?'today':''}"><span class="cal-num">${d}</span></div>`;
      }
    }
    html+=`<div class="cal-month"><div class="cal-title">${name} ${y}</div><div class="cal-grid">${dow}${cells}</div></div>`;
  }
  document.getElementById('calendar').innerHTML = html;
}

/* ---------- 對戰展開 ---------- */
function openGame(grp,i,scroll){
  const gm = SCHEDULE[grp][i];
  const gc = grp==='men' ? '#38bdf8' : '#f472b6';
  const el = document.getElementById('gameDetail');
  el.hidden=false;
  el.innerHTML = `
    <div class="gd-head">
      <div><span class="gd-grp" style="color:${gc}">${grpName(grp)} ・ Game ${gm.g}</span>
        <div class="gd-date">${gm.date}　・　主播 ${gm.host||DEFAULT_HOST}　|　賽評 ${gm.cast}</div></div>
      <button class="gd-close" onclick="document.getElementById('gameDetail').hidden=true" aria-label="關閉">✕</button>
    </div>
    <div class="gd-players">${gm.players.map((n)=>{const pl=PLAYERS[n];return `
      <button class="gd-card" style="--c:${pl.color}" onclick="openPlayer('${n}')">
        <div class="gd-photo"><img ${imgAttrs(n,'calendar')}>${n[0]}</div>
        <div class="gd-name">${n}</div>
        <div class="gd-pts">積分 ${fmtPts(pl.pts)}</div></button>`;}).join('')}</div>`;
  if(scroll!==false) el.scrollIntoView({behavior:'smooth',block:'nearest'});
}
// 首頁本週對戰卡 → 捲到月曆並展開該場
function gotoFeaturedGame(){
  openGame(FEATURED.grp, FEATURED.i, false);
  const sec = document.getElementById('schedule');
  if(sec) sec.scrollIntoView({behavior:'smooth'});
}

/* ---------- 選手 HUD 數據卡 ---------- */
const fmtScore = v => (typeof v==='number' ? v.toFixed(2) : v);
// 同組排名:積分→自摸→胡牌→放槍(少者優先),與賽事規章比序一致
function rankOf(name){
  const pl = PLAYERS[name];
  const g = Object.entries(PLAYERS).filter(([,p])=>p.grp===pl.grp)
    .sort((a,b)=> b[1].pts-a[1].pts || a[1].games-b[1].games || b[1].tsumo-a[1].tsumo || b[1].hu-a[1].hu || a[1].deal-b[1].deal);
  return g.findIndex(([n])=>n===name)+1;
}
// [顯示名稱, 欄位代碼, 格式] 格式:int / f1 / f2 / pct(Float2 %)
const PD_PAGES = [
  {rows:[['出場雀數','total_hanchan','int'],['平均順位','avg_rank','f2'],['胡牌率','win_rate','pct'],['自摸率','tsumo_rate','pct'],['放槍率','deal_in_rate','pct']]},
  {rows:[['累計打點','total_points_won','int'],['平均打點','avg_points_won','f2'],['最高打點','max_points_won','int'],['得分次數','scoring_count','int'],['得分頻率','scoring_interval','f1'],['最高連莊','max_renchan','int'],['平均連莊','avg_renchan','f2']]},
  {rows:[['累計失分','total_points_lost','int'],['失分頻率','loss_interval','f1'],['自摸數','tsumo_count','int'],['胡牌數','win_count','int'],['放槍數','deal_in_count','int']]},
];
function fmtField(v, fmt){
  const n = +v || 0;
  if(fmt==='pct') return n.toFixed(2)+'%';
  if(fmt==='f2')  return n.toFixed(2);
  if(fmt==='f1')  return n.toFixed(1);
  return String(Math.round(n));   // int
}
function renderStatPage(name, pg){
  const s = statOf(name);
  document.getElementById('pm-page').innerHTML = PD_PAGES[pg].rows.map(([l,k,fmt])=>`
    <div class="pd-row"><span class="pd-l">${l}</span><span class="pd-v">${fmtField(s[k],fmt)}</span></div>`).join('');
}
function openPlayer(name){
  const pl = PLAYERS[name]; if(!pl) return;
  const rank = rankOf(name), s = statOf(name);
  loadImg('pm-photo', name, 'profile');
  document.getElementById('pm-name').innerText = name;
  document.getElementById('pm-grp').innerText  = grpName(pl.grp);
  document.getElementById('pm-rankline').innerHTML = `第 <b>${rank}</b> 名　|　賽季積分 <b>${fmtScore(pl.pts)}</b>`;
  document.documentElement.style.setProperty('--player-color', pl.color);
  document.querySelector('.pd-card').style.setProperty('--c', pl.color);

  const tiles = s.favorite_tiles || [];
  document.getElementById('pm-tiles').innerHTML = `<div class="pd-tiles-h">最常胡牌 TOP3</div>` + (tiles.length
    ? tiles.slice(0,3).map(t=>`<span class="pd-tile">${t.tile}<small>${(+t.rate||0).toFixed(1)}%</small></span>`).join('')
    : `<span class="pd-tile empty">尚無資料</span>`);

  document.getElementById('pm-anchor').innerHTML = `
    <div class="pd-akey"><div class="l">賽季排名</div><div class="v">#${rank}</div></div>
    <div class="pd-akey"><div class="l">賽季積分</div><div class="v gold">${fmtScore(pl.pts)}</div></div>`;

  const tabs = document.querySelectorAll('.pd-tab');
  tabs.forEach((b,i)=>{ b.classList.toggle('active', i===0); b.onclick=()=>{
    tabs.forEach(x=>x.classList.remove('active')); b.classList.add('active'); renderStatPage(name, +b.dataset.pg);
  };});
  renderStatPage(name, 0);

  const modal = document.getElementById('playerModal');
  modal.hidden = false; document.body.style.overflow='hidden';
  // CSS 動畫做進場(獨立於 GSAP,不會被雷達的 killTweensOf 清掉);重觸發動畫
  const card = modal.querySelector('.pd-card');
  card.style.animation='none'; void card.offsetWidth; card.style.animation='';
  // 雙 rAF:等瀏覽器完成 layout 後才跑 GSAP 動畫,避免手機上 modal 未渲染完就算座標
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    if(window.playSMLRadarAnimation)
      playSMLRadarAnimation({color:pl.color, data:pl.radar, careerData:pl.career});
  }));
}
function closePlayer(){
  document.getElementById('playerModal').hidden = true;
  document.body.style.overflow='';
  if(window.gsap) gsap.killTweensOf('*');
}
document.querySelectorAll('#playerModal [data-close]').forEach(el=>el.addEventListener('click',closePlayer));
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closePlayer(); });

/* 六軸標題點擊 → 切換公式說明面板 */
const RADAR_FORMULAS = [
  {title:'效率・計算公式', lines:[
    {lbl:'和牌效率',expr:'有效和牌 / 總局數 × 55 分'},
    {lbl:'均得分',expr:'場均得點標準化 × 30 分'},
    {lbl:'廢牌控制',expr:'無謂摸切比例逆算 × 15 分'},
  ]},
  {title:'攻擊力・計算公式', lines:[
    {lbl:'和牌率',expr:'胡牌局數 / 總局數 × 45 分'},
    {lbl:'自摸比',expr:'自摸次數 / 胡牌次數 × 35 分'},
    {lbl:'均番加乘',expr:'平均番數標準化 × 20 分'},
  ]},
  {title:'防守力・計算公式', lines:[
    {lbl:'放槍逃脫',expr:'(1 − 放槍率) × 50 分'},
    {lbl:'危牌處理',expr:'危牌正確處置率 × 30 分'},
    {lbl:'守備局控',expr:'未放槍被攻擊比率 × 20 分'},
  ]},
  {title:'技術・計算公式', lines:[
    {lbl:'讀牌精度',expr:'危牌預判成功率 × 40 分'},
    {lbl:'手牌效率',expr:'理論最快進度達成率 × 35 分'},
    {lbl:'鳴牌時機',expr:'有效鳴牌率 × 25 分'},
  ]},
  {title:'爆發力・計算公式', lines:[
    {lbl:'高番和牌',expr:'滿貫以上和牌率 × 45 分'},
    {lbl:'逆轉能力',expr:'落後翻轉場次比率 × 35 分'},
    {lbl:'單局最高',expr:'生涯最高點折算加成 × 20 分'},
  ]},
  {title:'穩定度・計算公式', lines:[
    {lbl:'放槍控制',expr:'(1 − 放槍率) × 40 分'},
    {lbl:'順位穩定',expr:'順位標準差逆算 × 35 分'},
    {lbl:'一致性',expr:'場次加權分方差修正 × 25 分'},
  ]},
];
(function(){
  const fp=document.getElementById('formulaPanel');
  const fpT=document.getElementById('formulaPanelTitle');
  const fpB=document.getElementById('formulaPanelBody');
  if(!fp||!fpT||!fpB) return;
  let activeIdx=-1;
  for(let i=0;i<6;i++){
    const t=document.getElementById(`title-${i}`); if(!t) continue;
    t.addEventListener('click',()=>{
      if(activeIdx===i && fp.classList.contains('open')){
        fp.classList.remove('open'); t.classList.remove('active'); activeIdx=-1; return;
      }
      document.querySelectorAll('.pd-radarcol .label-title').forEach(el=>el.classList.remove('active'));
      t.classList.add('active'); activeIdx=i;
      const f=RADAR_FORMULAS[i];
      fpT.textContent=f.title;
      fpB.innerHTML=f.lines.map(l=>`<div class="formula-line"><span class="formula-lbl">${l.lbl}</span><span class="formula-expr">${l.expr}</span></div>`).join('')
        +`<div class="formula-eq">合計折算至 0–100 裝甲值</div>`;
      fp.classList.add('open');
    });
  }
})();

/* ---------- 頁籤切換 ---------- */
function setupTabs(barId, prefix, onShow){
  const bar = document.getElementById(barId); if(!bar) return;
  bar.querySelectorAll('.stab').forEach(btn=>btn.addEventListener('click',()=>{
    bar.querySelectorAll('.stab').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    ['men','women'].forEach(g=>{ document.getElementById(prefix+g).hidden = (g!==btn.dataset.grp); });
    if(onShow) onShow(btn.dataset.grp);
  }));
}

/* ---------- 建立全部畫面 ---------- */
renderFeatured();
renderCharSelect();
renderStandings();
renderCalendar();
renderReels([]);                                    // 先收起空板位,等 Firestore reels 到位再展開
setupTabs('tabs-standings','board-', animateBoard);

/* ====================================================================
   Firebase 即時數據:讀取直播後台寫入的 sml_public/season_2026
   players[name] 可同時帶「榜單欄位」與「HUD 規格欄位」(欄位代碼見下方)
   ==================================================================== */
const HUD_FIELDS = ['total_hanchan','avg_rank','win_rate','tsumo_rate','deal_in_rate',
  'total_points_won','avg_points_won','max_points_won','scoring_count','scoring_interval','max_renchan','avg_renchan',
  'total_points_lost','loss_interval','tsumo_count','win_count','deal_in_count'];
function applyLiveData(live){
  if(!live) return;
  const num = (...vs)=>{ for(const v of vs){ if(v!==undefined && v!==null && v!=='') return +v||0; } return 0; };
  const isArr6 = a => Array.isArray(a) && a.length===6;  // Firebase 有送陣列就用（含全零）
  for(const name in live){
    const d = live[name] || {};
    // ── 榜單 + 雷達 → PLAYERS ──
    const base = PLAYERS[name] || {grp:'men',color:'#94a3b8',radar:[0,0,0,0,0,0],career:[0,0,0,0,0,0],pts:0,games:0,tsumo:0,hu:0,deal:0};
    PLAYERS[name] = {
      ...base,
      grp:    d.grp || base.grp,
      color:  (d.color && d.color!=='#ffffff') ? d.color : base.color,
      radar:  isArr6(d.radar) ? d.radar.map(v=>+v||0) : (isArr6(d.radar_current) ? d.radar_current.map(v=>+v||0) : base.radar),
      career: isArr6(d.career)? d.career.map(v=>+v||0): (isArr6(d.radar_career)  ? d.radar_career.map(v=>+v||0)  : base.career),
      pts:   num(d.pts, d.season_score),
      games: num(d.games, d.matches),
      tsumo: num(d.tsumo, d.tsumo_count),
      hu:    num(d.hu,    d.win_count),
      deal:  num(d.deal,  d.deal_in_count),
    };
    // ── HUD 三頁明細 → PLAYER_STATS ──
    const st = {};
    HUD_FIELDS.forEach(k=> st[k] = num(d[k]));
    st.tsumo_count   = num(d.tsumo_count, d.tsumo);   // 與榜單共用絕對數
    st.win_count     = num(d.win_count,   d.hu);
    st.deal_in_count = num(d.deal_in_count, d.deal);
    st.favorite_tiles = Array.isArray(d.favorite_tiles) ? d.favorite_tiles : [];
    PLAYER_STATS[name] = st;
  }
  // 重繪所有用到選手數據的區塊
  renderFeatured();
  const sel = previewChar;                       // 記住目前預覽的選手
  renderCharSelect();
  if(sel && PLAYERS[sel]) selectChar(sel);
  renderStandings();
  renderCalendar();
  ['men','women'].forEach(animateBoard);          // 重新揭示兩組榜單
}

(function(){
  if(typeof firebase==='undefined'){ console.warn('Firebase SDK 未載入,維持靜態資料'); return; }
  const firebaseConfig = {
    apiKey: "AIzaSyAZaa_yHu7gsRaj71YL8x3REHfL_V5Tq4w",
    authDomain: "sml2026newscore.firebaseapp.com",
    projectId: "sml2026newscore",
    storageBucket: "sml2026newscore.firebasestorage.app",
    messagingSenderId: "248732232049",
    appId: "1:248732232049:web:98ed0cbf3990977661eed0"
  };
  try{
    if(!firebase.apps.length) firebase.initializeApp(firebaseConfig);
    firebase.firestore().collection("sml_public").doc("season_2026")
      .onSnapshot(snap=>{                          // 即時:後台一按更新,官網自動跟著變
        const data = snap.data();
        if(data && data.players) applyLiveData(data.players);
        applyLiveStream(data && data.liveStream ? data.liveStream : LIVE_STREAM_DEFAULT);
        renderReels(data && data.reels);            // 賽事精華:後台一存,官網即時重繪
      }, err=>console.warn('官網數據讀取失敗(可能是 Firestore 讀取權限):', err));
  }catch(e){ console.warn('Firebase 初始化失敗:', e); }
})();

/* ====================================================================
   直播狀態:後台控制 liveStream.isLive / url,官網即時切換按鈕
   後台(Firestore)有送 liveStream 時以後台為準;沒送則用下方手動連結。
   ==================================================================== */
const LIVE_STREAM_DEFAULT = {
  isLive: true,
  url: 'https://youtube.com/live/YcC4n9Mm2bM?feature=share'  // 2026/06/28 直播
};
function applyLiveStream(ls){
  const btn = document.querySelector('a.live-btn');
  const badge = document.querySelector('.announce-live');
  const watch = document.querySelector('a.btn-gold');   // 「▶ 觀看直播」按鈕
  const isLive = ls && ls.isLive && ls.url;
  const url = (ls && ls.url) || LIVE_STREAM_DEFAULT.url; // 後台有送就用後台,否則用手動連結

  // 「▶ 觀看直播」永遠開新視窗轉跳直播連結
  if(watch){
    watch.href = url;
    watch.target = '_blank';
    watch.rel = 'noopener';
  }

  // 跑馬燈左側 badge
  if(badge) badge.style.display = isLive ? '' : 'none';

  if(!btn) return;
  // 上方狀態按鈕:直播中或下次直播,點下去都開新視窗到直播連結
  btn.href = url;
  btn.target = '_blank';
  btn.rel = 'noopener';
  if(isLive){
    btn.innerHTML = '<span class="dot"></span>直播中';
    btn.style.display = '';
  } else {
    const next = getNextMatch();
    if(next){
      btn.innerHTML = `下次直播 ${next}`;
      btn.style.display = '';
    } else {
      btn.style.display = 'none';
    }
  }
}

function getNextMatch(){
  const now = new Date();
  const year = now.getFullYear();
  const all = [
    ...( SCHEDULE.men   || []).map(g=>({...g, grp:'men'})),
    ...( SCHEDULE.women || []).map(g=>({...g, grp:'women'}))
  ];
  let nearest = null, nearestDate = null;
  for(const g of all){
    const [m,d] = (g.date||'').split('/').map(Number);
    if(!m||!d) continue;
    const dt = new Date(year, m-1, d, 20, 0, 0); // 預設晚上8點
    if(dt > now && (!nearestDate || dt < nearestDate)){ nearest = g; nearestDate = dt; }
  }
  if(!nearest) return null;
  const [m,d] = nearest.date.split('/');
  return `${m}/${d}`;
}
applyLiveStream(LIVE_STREAM_DEFAULT);  // 先套手動連結,Firestore 有資料再覆蓋

/* ====================================================================
   賽程自動同步:讀取 EventBridge+Lambda 每小時從 Google Sheet 產生的
   data/schedule.json。抓不到或格式異常 -> 維持上方內建賽程當後備,確保不會壞。
   (依 max-age=300 走瀏覽器快取,不額外增加請求)
   ==================================================================== */
(function(){
  const ok = g => Array.isArray(g) && g.length && g.every(x => x && Array.isArray(x.players) && x.players.length);
  fetch('data/schedule.json')
    .then(r => r.ok ? r.json() : Promise.reject('HTTP '+r.status))
    .then(d => {
      if(!d || !ok(d.men) || !ok(d.women)) throw '格式異常';
      SCHEDULE.men = d.men; SCHEDULE.women = d.women;   // 以線上賽程覆蓋內建
      renderFeatured(); renderCalendar();               // 重繪賽程相關區塊
    })
    .catch(e => console.warn('賽程線上同步未套用,沿用內建賽程:', e));
})();

/* 積分榜進場:捲到才播一次 */
(function(){
  const men = document.getElementById('board-men');
  if(!men) return;
  const io = new IntersectionObserver((es)=>{
    es.forEach(e=>{ if(e.isIntersecting){ animateBoard('men'); io.disconnect(); } });
  },{threshold:.18});
  io.observe(men);
})();

/* ---------- 手機下拉選單 ---------- */
(function(){
  const nav = document.querySelector('header.nav'), burger = document.querySelector('.nav-burger');
  if(!nav || !burger) return;
  const setIcon = ()=>{ burger.textContent = nav.classList.contains('open') ? '✕' : '☰'; };
  burger.addEventListener('click', ()=>{ nav.classList.toggle('open'); burger.setAttribute('aria-expanded', nav.classList.contains('open')); setIcon(); });
  nav.querySelectorAll('.nav-links a').forEach(a=>a.addEventListener('click', ()=>{ nav.classList.remove('open'); setIcon(); }));
})();

/* ---------- 背景波浪視差 (跟著捲動但較慢) ---------- */
if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches){
  const bg1 = document.querySelector('.bgfx-1'), bg2 = document.querySelector('.bgfx-2');
  let ticking=false;
  function bgfxUpdate(){
    const y = window.scrollY || window.pageYOffset;
    if(bg1) bg1.style.backgroundPositionY = `${(-y*0.40).toFixed(1)}px`;  // 內容 1.0、波浪 0.40 → 較慢
    if(bg2) bg2.style.backgroundPositionY = `${(-y*0.22).toFixed(1)}px`;  // 更深一層,更慢
    ticking=false;
  }
  window.addEventListener('scroll',()=>{ if(!ticking){ticking=true; requestAnimationFrame(bgfxUpdate);} },{passive:true});
  bgfxUpdate();
}


/* ---------- 進場 + 捲動揭示 (尊重 reduced-motion) ---------- */
const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
if(!reduce && window.gsap){
  gsap.from('.hero-copy > *',{y:30,opacity:0,duration:.8,stagger:.1,ease:'power3.out'});
  gsap.from('.matchup',{y:50,opacity:0,duration:.9,delay:.3,ease:'back.out(1.1)'});
  const io=new IntersectionObserver((es)=>{
    es.forEach(e=>{ if(e.isIntersecting){ gsap.to(e.target,{y:0,opacity:1,duration:.7,ease:'power3.out'}); io.unobserve(e.target);} });
  },{threshold:.12});
  document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
}else{
  document.querySelectorAll('.reveal').forEach(el=>{el.style.opacity=1;el.style.transform='none';});
}

/* ====================================================================
   選手雷達圖引擎 (改編自 Ryo-Jan SML 轉播版)
   ==================================================================== */
const CENTER = 200, MAX_RADIUS = 135, LEVELS = 5, CRIT_THRESHOLD = 75;
const radarAngles = [];
for(let i=0;i<6;i++) radarAngles.push((Math.PI*2*i/6)-(Math.PI/2));
const getPoint = (r,a) => ({x:CENTER+r*Math.cos(a), y:CENTER+r*Math.sin(a)});

const gridGroup = document.getElementById('grid-group');
if(gridGroup){
  for(let level=1;level<=LEVELS;level++){
    const r = MAX_RADIUS*(level/LEVELS);
    const pts = radarAngles.map(a=>{const q=getPoint(r,a);return `${q.x},${q.y}`;}).join(' ');
    const poly = document.createElementNS('http://www.w3.org/2000/svg','polygon');
    poly.setAttribute('points',pts); poly.setAttribute('class','grid-line'); poly.style.opacity=0;
    gridGroup.appendChild(poly);
  }
  radarAngles.forEach(a=>{
    const q = getPoint(MAX_RADIUS,a);
    const line = document.createElementNS('http://www.w3.org/2000/svg','line');
    line.setAttribute('x1',CENTER); line.setAttribute('y1',CENTER);
    line.setAttribute('x2',q.x);    line.setAttribute('y2',q.y);
    line.setAttribute('class','axis-line'); line.style.opacity=0;
    gridGroup.appendChild(line);
  });
}

const polygonNode = document.getElementById('poly');
const polygonCareerNode = document.getElementById('poly-career');
const radarLabels = window.gsap ? gsap.utils.toArray('.label-container') : [];
const radarDots = window.gsap ? gsap.utils.toArray('.data-dot') : [];

function resetRadarState(){
  gsap.killTweensOf('*');
  document.querySelectorAll('.grid-line,.axis-line,.data-polygon,.data-polygon-career,.data-dot,.label-container,.label-title,.label-value,.label-sub')
    .forEach(el=>el.removeAttribute('style'));
  radarDots.forEach(dot=>{dot.setAttribute('cx',CENTER);dot.setAttribute('cy',CENTER);dot.setAttribute('r',5);});
  gsap.set([polygonNode,polygonCareerNode],{svgOrigin:'200 200',scale:0});
  gsap.set(radarLabels,{xPercent:-50,yPercent:-50,scale:0,opacity:0,x:0,y:0});
  for(let i=0;i<6;i++){ document.getElementById(`val-${i}`).innerText='0'; document.getElementById(`subval-${i}`).innerText='生涯 0'; }
}

window.playSMLRadarAnimation = function(payload){
  if(!window.gsap || !payload || !payload.data || payload.data.length!==6 || !payload.careerData || payload.careerData.length!==6) return;
  resetRadarState();
  const D = payload.data, C = payload.careerData;
  const maxValue = Math.max(...D), maxIndex = D.indexOf(maxValue);
  document.documentElement.style.setProperty('--player-color', payload.color);

  const targetPositions=[], finalPts=[], finalCareer=[];
  for(let i=0;i<6;i++){
    const q = getPoint(Math.max(MAX_RADIUS*(D[i]/100), 4), radarAngles[i]); targetPositions.push(q); finalPts.push(`${q.x},${q.y}`);
    const cp = getPoint(Math.max(MAX_RADIUS*(C[i]/100), 4), radarAngles[i]); finalCareer.push(`${cp.x},${cp.y}`);
  }
  polygonNode.setAttribute('points',finalPts.join(' '));
  polygonCareerNode.setAttribute('points',finalCareer.join(' '));

  const pT={v0:0,v1:0,v2:0,v3:0,v4:0,v5:0}, pC={v0:0,v1:0,v2:0,v3:0,v4:0,v5:0};
  const tl = gsap.timeline();
  tl.fromTo(gsap.utils.toArray('.grid-line,.axis-line'),{opacity:0},{opacity:1,duration:.5,stagger:.05,ease:'power2.out'},0);
  tl.fromTo(radarDots,{scale:0,opacity:0,attr:{cx:CENTER,cy:CENTER}},
    {duration:.8,scale:1,opacity:1,stagger:.05,ease:'back.out(1.5)',attr:{cx:i=>targetPositions[i].x,cy:i=>targetPositions[i].y}},0.4);
  tl.fromTo([polygonCareerNode,polygonNode],{scale:0},{scale:1,duration:1.0,ease:'power3.out'},1.0);
  tl.fromTo(radarLabels,{scale:0,opacity:0},{scale:1,opacity:1,duration:.6,stagger:.08,ease:'back.out(2.5)'},1.6);
  tl.to(pT,{v0:D[0],v1:D[1],v2:D[2],v3:D[3],v4:D[4],v5:D[5],duration:.8,ease:'power2.out',roundProps:'v0,v1,v2,v3,v4,v5',
    onUpdate:()=>{for(let i=0;i<6;i++) document.getElementById(`val-${i}`).innerText=pT[`v${i}`];}},2.0);
  tl.to(pC,{v0:C[0],v1:C[1],v2:C[2],v3:C[3],v4:C[4],v5:C[5],duration:.8,ease:'power2.out',roundProps:'v0,v1,v2,v3,v4,v5',
    onUpdate:()=>{for(let i=0;i<6;i++) document.getElementById(`subval-${i}`).innerText=`生涯 ${pC[`v${i}`]}`;}},2.0);
  tl.add(()=>{ D.forEach((val,i)=>{ if(val>=CRIT_THRESHOLD){
    const lblNode=document.getElementById(`lbl-${i}`), valNode=document.getElementById(`val-${i}`), dotNode=document.getElementById(`dot-${i}`);
    gsap.to(lblNode,{x:'+=6',y:'+=6',rotation:4,duration:.04,repeat:5,yoyo:true,ease:'none',onComplete:()=>gsap.set(lblNode,{x:0,y:0,rotation:0})});
    gsap.fromTo(valNode,{color:'#ef4444',textShadow:'0 0 25px rgba(239,68,68,1)',scale:1.4},{color:'#f8fafc',textShadow:'0 0 10px rgba(255,255,255,.3)',scale:1,duration:.7,ease:'power2.out'});
    gsap.fromTo(dotNode,{attr:{r:10},fill:'#ef4444',filter:'drop-shadow(0 0 15px rgba(239,68,68,1))'},{attr:{r:5},fill:payload.color,filter:`drop-shadow(0 0 5px ${payload.color})`,duration:.7,ease:'power2.out'});
  }}); },2.8);
  if(maxValue > 0) tl.add(()=>{
    const L=document.getElementById(`lbl-${maxIndex}`), V=document.getElementById(`val-${maxIndex}`), T=document.getElementById(`title-${maxIndex}`), Dt=document.getElementById(`dot-${maxIndex}`);
    gsap.fromTo(L,{scale:1},{scale:1.07,duration:.8,repeat:-1,yoyo:true,ease:'sine.inOut'});
    gsap.fromTo([V,T],{color:'#f8fafc',textShadow:'none'},{color:'#fbbf24',textShadow:'0 0 9px rgba(251,191,36,.55)',duration:.8,repeat:-1,yoyo:true,ease:'sine.inOut'});
    gsap.fromTo(Dt,{fill:payload.color,stroke:payload.color,attr:{r:5}},{fill:'#fbbf24',stroke:'#fbbf24',attr:{r:6.5},filter:'drop-shadow(0 0 7px rgba(251,191,36,.8))',duration:.8,repeat:-1,yoyo:true,ease:'sine.inOut'});
  },3.7);
};
