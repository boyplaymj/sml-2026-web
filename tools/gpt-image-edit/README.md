# gpt-image-edit

用 OpenAI **GPT Image 2** 對既有圖片做「精準微調」的個人 CLI。
專治 Gemini / nano-banana 聽不懂指令、整張圖被改壞的情況。

> 這是**個人手動調圖工具**，不接甜甜 bot、不對外服務，所以不需要 `tools/COST_CONTROL.md`
> 的四件套。但 image API 是**付費**的（跟 Claude 帳號無關），請在 OpenAI 後台設**月度用量上限**。

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：外部**付費**影像 API（OpenAI GPT Image 2，**非 Bedrock**，token 計費）。跟 Claude / AWS 帳號無關，需自備 OpenAI 付費帳號 + key。
- **預估量級**：medium 1024²約 $0.053/張，edit 含參考圖高保真約 **2–3×**（~$0.15/張）；high 約 $0.21/張。
- **🚨 硬閘（COST_CONTROL.md §1.6）**：**動用 API 前一律先預估成本（單價 × 張數 → 本次/每日/每月）並經確認才可執行**；不預估不確認不准打。預設仍優先走 Bedrock SD3.5，改用本工具是因 GPT Image 2 指令遵從度 + 局部重繪較佳。
- **定位**：**個人手動 CLI**，不接 bot、不對外服務 → 免帳本/月封頂四件套。但**務必到 OpenAI 後台設「月度用量上限（hard cap）」**當總煞車。
- **工具內建**：每次呼叫後印出成本估算區間；`--quality low` 可壓成本。
- **升級門檻**：一旦要接進甜甜 bot / 對外服務，必須回本規範補齊四件套（帳本表 + 月封頂 cap + 後台用量卡 + kill switch）。

## 安裝（EC2 上）

```bash
cd tools/gpt-image-edit
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...        # 建議寫進 ~/.bashrc 或 .env，勿進 git
```

## 用法

```bash
# 整張依指令重繪（大改；沒指定的地方也可能變）
./edit.py in.png "把背景換成夜晚城市、霓虹燈" -o out.png

# 局部微調（推薦）：只改 mask 透明區，其餘鎖住
./edit.py in.png "把角色帽子改成紅色" --mask mask.png -o out.png

# 多張參考圖合成
./edit.py char.png scene.png "讓角色站進這個場景" -o out.png

# 一次出 3 張候選挑
./edit.py in.png "微調光線更柔和" -n 3 -o cand.png
```

## 座標圈選自動生 mask（免開修圖軟體，推薦）

不想手繪 mask？直接用座標圈出要改的區域，程式自動產遮罩：

```bash
# 圈一個矩形區來改（左上角原點；座標可用像素或百分比）
./edit.py in.png "把這塊招牌換成 SML logo" --region rect:60%,10%,30%,15% -o out.png

# 圈橢圓（適合臉/頭/圓形物件），邊緣羽化 12px 讓改動融合更自然
./edit.py in.png "把表情改成笑臉" --region ellipse:40%,30%,20%,20% --feather 12 -o out.png

# 多個區域一起圈（--region 可重複）
./edit.py in.png "把兩盞燈都改成暖黃光" \
  --region rect:10%,20%,15%,15% --region rect:70%,20%,15%,15% -o out.png

# 想看程式圈成什麼樣，把 mask 存出來檢查
./edit.py in.png "..." --region ellipse:50%,50%,30%,30% --save-mask mask_preview.png -o out.png
```

語法：`rect:x,y,w,h` 或 `ellipse:x,y,w,h`。圈到的區域=可編輯，其餘鎖住。
`--region` 與 `-m/--mask` 擇一使用。複雜形狀才需要下面的手繪 mask。

## 手繪 mask（複雜形狀時）

`mask` = 跟原圖**同尺寸**的 PNG，帶 alpha：
- **透明 (alpha=0) = 允許重繪**
- **不透明 = 鎖住不動**

先產一張空白 mask 起點，再用修圖軟體塗黑要保留的區域：

```bash
./edit.py --make-mask-from in.png -o mask.png   # 產全透明空白 mask
# 用 GIMP/Photopea 把「要保留」的地方塗成不透明黑，存回 mask.png
```

## 參數

| 參數 | 說明 |
|---|---|
| `-o/--output` | 輸出檔名（預設 out.png） |
| `-m/--mask` | 遮罩 PNG（透明區=可編輯） |
| `--region` | 座標圈選自動產 mask（可重複）：rect/ellipse:x,y,w,h |
| `--feather` | mask 邊緣羽化像素，改動融合更自然 |
| `--save-mask` | 把自動產生的 mask 另存供檢視 |
| `--quality` | low / medium / high（成本↑，預設 medium） |
| `--size` | 1024x1024 / 1536x1024 / 1024x1536 / auto |
| `-n` | 一次生幾張候選 |
| `--model` | 預設 gpt-image-2 |

## 成本速記（估算，非帳單）

| 品質 | ~USD/張 | edit 情境（×2–3） |
|---|---|---|
| low | $0.006 | ~$0.02 |
| medium | $0.053 | ~$0.15 |
| high | $0.211 | ~$0.6 |

Batch API 可再打對半（非同步），本 CLI 走同步即時版。
