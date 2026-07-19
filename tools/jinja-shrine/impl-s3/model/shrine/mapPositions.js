// 甜甜神社 — 境內地圖定點資料(S3-0a)。
// 內容內嵌自 repo tools/jinja-shrine/map/positions.json(bot 端自帶,不跨 repo require)。
// 地圖釘+側欄小釘已烤進 CDN 圖;程式端只需 key→image/name/sidebarRow 對照。
// 素材上 CDN 不進 git;改圖 → 重跑 repo 端 render.js 再同步本檔。

module.exports = {
  _note: '神社境內地圖 S3 面板素材定位。地圖釘+側欄小釘合成;正式圖無文字。座標由使用者親手綠標定位。素材上CDN不進git(產圖用 render.js;原始地圖art另存)。',
  cdnBase: 'https://image.boyplaymj.link/shrine/map/',
  mapSize: [1024, 637],
  sidebarWidth: 192,
  sidebarRows: { okusha: 0, gokitou: 1, honden: 2, goshuin: 3, juyosho: 4, temizu: 5, kosatsu: 6, ichiba: 7, torii: 8 },
  locations: [
    { key: 'okusha_top', facility: 'okusha', name: '奧社', sidebarRow: 0, pin: [639, 110], image: 'okusha_top.png', note: '通過試煉後到達的內殿' },
    { key: 'okusha_stair', facility: 'okusha', name: '奧社への石段', sidebarRow: 0, pin: [370, 243], image: 'okusha_stair.png', note: '試煉起點(聽牌試煉10關)' },
    { key: 'gokitou', facility: 'gokitou', name: '御祈禱受付所', sidebarRow: 1, pin: [447, 346], image: 'gokitou.png' },
    { key: 'honden', facility: 'honden', name: '本殿', sidebarRow: 2, pin: [650, 362], image: 'honden.png' },
    { key: 'goshuin', facility: 'goshuin', name: '御朱印受付所', sidebarRow: 3, pin: [806, 332], image: 'goshuin.png' },
    { key: 'juyosho', facility: 'juyosho', name: '授與所', sidebarRow: 4, pin: [901, 352], image: 'juyosho.png' },
    { key: 'temizu', facility: 'temizu', name: '手水舍', sidebarRow: 5, pin: [373, 435], image: 'temizu.png' },
    { key: 'kosatsu', facility: 'kosatsu', name: '古札納所', sidebarRow: 6, pin: [466, 522], image: 'kosatsu.png' },
    { key: 'ichiba', facility: 'ichiba', name: '表參道の市集', sidebarRow: 7, pin: [603, 474], image: 'ichiba.png' },
    { key: 'torii', facility: 'torii', name: '鳥居', sidebarRow: 8, pin: [645, 601], image: 'torii.png' }
  ],
  entry: 'torii',
  okusha: { gateFrom: 'okusha_stair', arriveAt: 'okusha_top', requires: 'tenpai_trial_10', note: '起程站okusha_stair→過10關聽牌試煉→切到okusha_top參拜內殿' }
};
