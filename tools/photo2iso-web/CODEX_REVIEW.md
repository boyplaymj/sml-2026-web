# Codex 複驗清單 — photo2iso 管線 + iso 車輛庫

作者:Claude(Fable/Opus 混用)。狀態:**全部未 commit**。這是「照片→統一 iso 角度 16bit」工具鏈 + 火車大亨 iso 車輛庫。
請獨立複驗以下內容,分「🔴阻斷 / 🟡應修 / 🟢確認即可」回報,並標出我漏掉的。

---

## 0. 範圍與檔案

**主角 = photo2iso 互動網頁(本次重點)**
- `tools/photo2iso-web/index.html` — 單頁前端工具(純 JS/canvas,零後端零成本)。
- `tools/photo2iso-web/sample.png` — 測試素材(合成木箱)。

**支援 = Python 原型 / iso 車輛庫**
- `tools/pixel16/photo2iso.py` — homography + PALETTE16 量化原型。
- `tools/pixel16/build_jr_iso.py` — 真實 JR 側視照 → iso 實測。
- `tools/train-tycoon/pixel/iso_cars16.py`(Iso 類別+斜面貼片器+轉向架,6 車廂)
- `tools/train-tycoon/pixel/shape_demo16.py`(cyl_h 水平圓柱=罐車/弧頂)
- `tools/train-tycoon/pixel/loco_iso16.py`(cyl_v 垂直圓柱+drive_wheel+蒸汽機車頭)
- `tools/train-tycoon/pixel/couple_train.py`(編組整列同軌)
- 共用底:`tools/pixel16/engine16.py`(已於 7fd04ed 進庫)、`tools/pixel8/engine.py`。

---

## 1. Claude 已修(請覆驗修法是否正確、有無副作用)

> 以下 4 項 Codex 前一輪已確認為真;Claude 已修並用 Playwright 實測(退化不再 NaN/崩、bands 已接上、taint 有 try/catch、autoColor 改多點中位)。請覆驗。

1. ✅ **`solve()` 加 epsilon(1e-9)pivot guard**,近奇異回 `null`;`out.every(Number.isFinite)` 再保一層。`render()` 遇 `cf===null` 的照片面 **直接 skip 並設 `degenerate` 旗標**,在輸出畫布顯示紅字警告「錨點退化…已跳過該面」,其他面照畫。像素迴圈另加 `|wv|<1e-6` 與 `!isFinite(sx,sy)` 跳過。**驗:退化四邊形不再吐 NaN(已測 top 面壓成一點 → 無 error、有警告)。**
2. ✅ **`rampSnap()` 讓 `bands` 生效**:`nb=max(2,min(bands,ramp長))`,先把亮度量化成 `nb` 階再映射 ramp index。注意 wood ramp 只有 3 階,故 bands 3 vs 5 對木頭無差=正常;鋼(6階)才看得出。**驗:數學是否合理、會不會有階數 off-by-one。**
3. ✅ **`loadImage()` 的 `getImageData()` 包 try/catch**:taint 失敗時 `srcData=null` + `drawMsg()` 提示改用 file-input 或部署,不卡 UI。**驗:部署(http 同源)後正常、失敗路徑提示正確。**
4. ✅ **`autoColor()` 改面內 3×3 多點取樣 → 逐通道中位**,避開單點白背景。**驗:側視照 top/right=auto 取色是否合理。**

## 1b. 🟡 仍待查(Claude 未動)

5. **效能**:每面對「超取樣後畫布」逐像素反扭正(SS=3 + 高像素密度 + 大盒)可能慢/卡。請量最壞情況互動延遲,必要時建議設上限或降級。

---

## 2. 🟢 請獨立查驗(我認為 OK,但要你背書)

- **homography 正確性**:`coeffs(dst,src)` 解的是「輸出→來源」映射;`render()` 內對每個輸出像素用 `(cf[0]*x+cf[1]*y+cf[2])/(cf[6]*x+cf[7]*y+1)` 反查來源。驗證數學與邊界(w 分母趨 0)。
- **iso 角度統一性**:所有幾何都走 `screen(c,r)=((c-r)*TW/2,(c+r)*TH/2)`(web 與 python 同式,TW=28/TH=14)。驗證 web 版與車輛庫的角度真的一致(這是整個專案的賣點)。
- **`inQuad()`**:凸四邊形內測試(cross product 同號)。凹/反向 winding 會誤判 → 面畫錯。驗證錨點亂拖時的行為。
- **PALETTE16 / RAMPS** 在 index.html 內嵌值與 `engine16.py` 完全一致(手抄,請比對有無漏字或錯值)。
- **loco 圖層順序**(`loco_iso16.draw_loco`):已修「駕駛室穿幫」為嚴格由遠到近繪製(底架→駕駛室→鍋爐→配件→煙箱→動輪→排障器→煙)。請確認無殘留前後穿幫。
- **couple_train 編組**:四車同軌 `dc` 位移,鐵軌連貫。驗證接縫與深度排序。

---

## 3. 已知決策 / 非問題(不用當 bug 報)

- **無成本控管段**:photo2iso 與車輛庫皆「純前端 / 純 Python 本機出圖」,**不燒 LLM、不建 DDB、不打付費 API、無 runtime 成本**,依 `tools/COST_CONTROL.md` 免「💰成本控管」段。請確認我這判斷正確。
- **不用擴散生圖**:全程 deterministic(homography + 調色盤量化 + 程式擺像素),刻意不走 Bedrock,符合 pixel8/pixel16 鐵律。
- **絕對路徑 `sys.path.insert('/opt/sml/repo/...')`**:本機出圖工具,非部署程式,暫可接受(如要 CI 化再改相對路徑)。
- **產物 `out/`、`shot_*.png`、`sample.png`**:圖不入庫(pixel8/16 慣例 .gitignore),但 `sample.png` 是工具範例需隨檔走——請判斷該不該納入 git。

---

## 4. 品質面(非程式 bug,但想聽你判斷)

- photo2iso 對**方正物件**(貨櫃/建築/道具)輸出乾淨可用;對**複雜曲面**(火車頭/角色)單張照片只能得「平板立牌」,真 3D 仍需手工幾何。請確認這個定位在 UI 提示中有講清楚、不會誤導使用者。
- `ramp吸附` vs `直接量化`:ramp 吸附把雜色收進材質 ramp,對純色/線稿來源效果好;對高紋理真實照片仍偏草稿。

---

## 5. 如何跑

```bash
# 網頁(需 http,勿用 file://):
cd tools/photo2iso-web && python3 -m http.server 8777   # 開 http://localhost:8777/
# Python 原型 / 實測：
cd tools/pixel16 && python3 photo2iso.py && python3 build_jr_iso.py
# iso 車輛庫：
cd tools/train-tycoon/pixel && python3 iso_cars16.py && python3 loco_iso16.py && python3 couple_train.py
```

回報格式:每項標 🔴/🟡/🟢 + 檔案:行號 + 具體修法建議。謝謝。
