// 端上麻將牌辨識：onnxruntime-web 跑 YOLOv8(自訓, Jon Chan 台灣牌資料集 v83) → 台灣牌 id 陣列。
// 解碼(letterbox / argmax / NMS / label→id)＝Python 驗證版逐行 port，實測真牌桌照片準確。
// 模型類別(42)：1-9C萬 / 1-9B索 / 1-9D筒 / EW東 SW南 WW西 NW北 RD中 GD發 WD白 / 1-4F+1-4S 八花
//   NAMES 順序＝模型 metadata 內嵌 names（0..41），labelToId 吃字串故與順序無關。
(function (root) {
  'use strict';
  var MODEL_URL = 'mahjong-tw-yolov8.onnx';
  var SIZE = 640, CONF = 0.35, IOU = 0.45;
  var NAMES = ['1B','1C','1D','1F','1S','2B','2C','2D','2F','2S','3B','3C','3D','3F','3S',
    '4B','4C','4D','4F','4S','5B','5C','5D','6B','6C','6D','7B','7C','7D','8B','8C','8D',
    '9B','9C','9D','EW','GD','NW','RD','SW','WD','WW'];

  // Jon Chan 台灣牌短碼 → 台灣牌 id（萬1-9 / 索11-19 / 筒21-29 / 字牌百位；花牌回 null）
  //   C=萬(character) B=索(bamboo) D=筒(dot)；F/S=八花，判聽挑掉但 dets 仍留 label 供顯示
  //   ⚠ 字牌須先攔：RD中/GD發/WD白 尾字亦為 D，會被筒子 s==='D' 分支誤判成 NaN
  var HONORS = { EW:101, SW:201, WW:301, NW:401, RD:501, GD:601, WD:701 };
  function labelToId (l) {
    if (HONORS[l] != null) return HONORS[l];       // 東南西北中發白（先判，避免 *D 撞筒子）
    var n = +l[0], s = l[1];                        // '5C' → n=5, s='C'
    if (s === 'C') return n;                        // 萬 1-9
    if (s === 'B') return n + 10;                   // 索 11-19
    if (s === 'D') return n + 20;                   // 筒 21-29
    return null;                                    // 花牌 1-4F / 1-4S：判聽不計
  }

  var _session = null;
  async function getSession (onProgress) {
    if (_session) return _session;
    if (onProgress) onProgress('載入辨識模型…（首次約 12MB）');
    // 單執行緒 wasm → 免 SharedArrayBuffer / COOP-COEP 標頭，任何靜態站可跑
    root.ort.env.wasm.numThreads = 1;
    // ort 由 index.html 的 <script> 提供；wasm 自 CDN 解析
    _session = await root.ort.InferenceSession.create(MODEL_URL, { executionProviders: ['wasm'] });
    return _session;
  }

  // 影像 → 640×640 letterbox → Float32 CHW [1,3,640,640]，回傳 tensor + 還原參數
  function preprocess (img) {
    var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
    var r = Math.min(SIZE / w, SIZE / h);
    var nw = Math.round(w * r), nh = Math.round(h * r);
    var dx = (SIZE - nw) >> 1, dy = (SIZE - nh) >> 1;
    var cv = document.createElement('canvas'); cv.width = SIZE; cv.height = SIZE;
    var ctx = cv.getContext('2d');
    ctx.fillStyle = 'rgb(114,114,114)'; ctx.fillRect(0, 0, SIZE, SIZE);
    ctx.drawImage(img, dx, dy, nw, nh);
    var d = ctx.getImageData(0, 0, SIZE, SIZE).data; // RGBA
    var arr = new Float32Array(3 * SIZE * SIZE), plane = SIZE * SIZE;
    for (var i = 0; i < plane; i++) {
      arr[i]             = d[i * 4]     / 255; // R
      arr[i + plane]     = d[i * 4 + 1] / 255; // G
      arr[i + 2 * plane] = d[i * 4 + 2] / 255; // B
    }
    return { tensor: new root.ort.Tensor('float32', arr, [1, 3, SIZE, SIZE]), r: r, dx: dx, dy: dy };
  }

  function iou (a, b) {
    var x1 = Math.max(a[0], b[0]), y1 = Math.max(a[1], b[1]);
    var x2 = Math.min(a[2], b[2]), y2 = Math.min(a[3], b[3]);
    var inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
    var a1 = (a[2] - a[0]) * (a[3] - a[1]), a2 = (b[2] - b[0]) * (b[3] - b[1]);
    return inter / (a1 + a2 - inter + 1e-6);
  }
  function nms (dets) { // dets: [{box,score,cid}] 已按 score 降冪
    var keep = [];
    for (var i = 0; i < dets.length; i++) {
      var ok = true;
      for (var j = 0; j < keep.length; j++) if (iou(dets[i].box, keep[j].box) > IOU) { ok = false; break; }
      if (ok) keep.push(dets[i]);
    }
    return keep;
  }

  // 解碼 YOLOv8 輸出 (1,46,8400)：4 框 + 42 類（numCls 由 dims 動態算，換模型免改）
  function decode (out, r, dx, dy) {
    var data = out.data, dims = out.dims;          // dims = [1,46,8400]
    var nc = dims[1], na = dims[2], numCls = nc - 4;
    var dets = [];
    for (var a = 0; a < na; a++) {
      var best = 0, bestk = 0;
      for (var k = 0; k < numCls; k++) {
        var sc = data[(4 + k) * na + a];
        if (sc > best) { best = sc; bestk = k; }
      }
      if (best < CONF) continue;
      var cx = data[a], cy = data[na + a], ww = data[2 * na + a], hh = data[3 * na + a];
      var x1 = (cx - ww / 2 - dx) / r, y1 = (cy - hh / 2 - dy) / r;
      var x2 = (cx + ww / 2 - dx) / r, y2 = (cy + hh / 2 - dy) / r;
      dets.push({ box: [x1, y1, x2, y2], score: best, cid: bestk });
    }
    dets.sort(function (p, q) { return q.score - p.score; });
    return nms(dets);
  }

  // 對外：影像元素 → { ids:[台灣牌id...], dets:[{box,score,label,id}...] }
  async function detectTiles (img, onProgress) {
    var sess = await getSession(onProgress);
    if (onProgress) onProgress('辨識中…');
    var pre = preprocess(img);
    var feeds = {}; feeds[sess.inputNames[0]] = pre.tensor;
    var res = await sess.run(feeds);
    var out = res[sess.outputNames[0]];
    var keep = decode(out, pre.r, pre.dx, pre.dy);
    // 由上而下、左而右排序（依牌框中心）
    keep.sort(function (p, q) {
      var py = (p.box[1] + p.box[3]) / 2, qy = (q.box[1] + q.box[3]) / 2;
      if (Math.abs(py - qy) > 60) return py - qy;
      return p.box[0] - q.box[0];
    });
    var dets = keep.map(function (d) {
      var label = NAMES[d.cid], id = labelToId(label);
      return { box: d.box, score: d.score, label: label, id: id };
    });
    var ids = dets.map(function (d) { return d.id; }).filter(function (x) { return x != null; });
    return { ids: ids, dets: dets };
  }

  root.MahjongDetect = { detectTiles: detectTiles, labelToId: labelToId, NAMES: NAMES };
})(typeof window !== 'undefined' ? window : this);
