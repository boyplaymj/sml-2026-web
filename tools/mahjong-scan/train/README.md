# 訓練台灣牌辨識模型（走 A：自訓）

把日麻(riichi)模型換成台灣牌模型，用 [Jon Chan 公開資料集](https://universe.roboflow.com/jon-chan-gnsoa/mahjong-baq4s)（3503 張、**已標註好**，42 類 = 34 基本牌 + 8 花牌）。

## 為什麼要換
現行 `demo/mahjong-yolov8.onnx` 是拿**日本牌**訓的（DrCheeseFace, MIT）。台灣牌牌面（字牌字體、數字牌字型）長得不一樣，可能誤讀；且它沒有花牌。自訓一版台灣牌模型可修掉這兩點。**判聽本身花牌會挑掉不算**，換模型的真正價值是牌面辨識準度。

## 成本
- **$0**：資料集下載免費、Colab T4 GPU 免費。
- **零人工標註**：資料集已標好，只是拿現成標籤訓練。
- 時間：Colab 掛著跑約 1–2 小時。

## 步驟
1. 開 [Google Colab](https://colab.research.google.com/) → 上傳 `train_taiwan_mahjong.ipynb`。
2. 右上 `連線` → `變更執行階段類型` → **T4 GPU**。
3. 登入 [roboflow.com](https://roboflow.com)（免費）→ Settings → API Keys → 複製 Private API Key。
4. Cell 2 貼上 key + 版本號（Universe 頁左側 Versions 看最新版）。
5. `執行階段` → `全部執行`，等跑完會自動下載 `best.onnx`。
6. **把 `best.onnx` 和 Cell 3/7 印出的 `NAMES = [...]` 清單丟回給 Claude。**

## Claude 接回來要做的（拿到檔案後）
- `best.onnx` → 改名 `demo/mahjong-tw-yolov8.onnx`，改 `detect.js` 的 `MODEL_URL`。
- 依回傳的 `NAMES`（Cell 7 印的順序）更新 `detect.js` 的 `NAMES` 陣列（38→42）。
- 換上 `labelToId()`（見下，已按此資料集短碼命名規則預寫好）。
- `decode()` **不用改**（已用 `dims[1]` 動態算類別數，42 類自動相容）。
- 私頻 903327108451950692 實測後上線。

## 類別命名規則（2026-07-19 用 API 抓 42 類確認）
資料集短碼 → 台灣牌 id（沿用既有 `mahjongHand.js` 慣例：萬1-9 / 索11-19 / 筒21-29 / 字牌百位）：

| 短碼 | 牌 | id |
|---|---|---|
| `1C`–`9C` | 萬 (character) | 1–9 |
| `1B`–`9B` | 索 (bamboo) | 11–19 |
| `1D`–`9D` | 筒 (circle/dot) | 21–29 |
| `EW` | 東 | 101 |
| `SW` | 南 | 201 |
| `WW` | 西 | 301 |
| `NW` | 北 | 401 |
| `RD` | 中 (red dragon) | 501 |
| `GD` | 發 (green dragon) | 601 |
| `WD` | 白 (white dragon) | 701 |
| `1F`–`4F` | 花：梅蘭菊竹 | **null**（判聽挑掉，dets 仍留 label 供顯示） |
| `1S`–`4S` | 花：春夏秋冬 | **null**（同上） |

預寫的對照函式（等 NAMES 順序回來即可直接換進 `detect.js`）：

```js
// Jon Chan 台灣牌短碼 → 台灣牌 id
//   ⚠ 字牌須先攔：RD中/GD發/WD白 尾字亦為 D，否則會被 s==='D' 筒子分支吃成 NaN
var HONORS = { EW:101, SW:201, WW:301, NW:401, RD:501, GD:601, WD:701 };
function labelToId (l) {
  if (HONORS[l] != null) return HONORS[l];  // 東南西北中發白（先判）
  var n = +l[0], s = l[1];                  // '5C' → n=5, s='C'
  if (s === 'C') return n;                   // 萬 1-9
  if (s === 'B') return n + 10;              // 索 11-19
  if (s === 'D') return n + 20;              // 筒 21-29
  return null;                               // 花牌 1-4F / 1-4S：判聽不計（label 仍在 dets）
}
```

> 花牌回 `null` → 會被 `ids` 過濾掉、不進聽牌結構，但 `dets` 仍保留 label，之後要在 UI 顯示「摸到花牌」可直接用。
