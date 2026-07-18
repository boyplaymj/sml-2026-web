# 交 Codex 複驗 — ARG 兔子洞（明硯案）A/B/C 三關

Neku，這是「偽文件解謎」新做的 **ARG 兔子洞產生器＋明硯案 50 頁文件迷宮**，請你獨立複驗。
起因：使用者嫌解謎「答案太好找」，要求網站埋深到「數十次點擊、甚至改網址、刪除的文件要從
檢視原始檔反貼網址」才找得到。我方三關（A 引擎 / B 埋深 / C 內容）都已自審通過，請你**獨立重跑
稽核＋逐條回 pass/fail＋findings（標嚴重度）**，收斂後才進 D（動線實測）。

## 一分鐘看懂這套怎麼埋深
- **資料驅動**：`mingyan-world.json`（世界圖，50 節點）→ `build.py` 編譯成 `dist/mingyan/` 50 個獨立 HTML。
- **四個 URL 埋深機制**（細節見 `WALKTHROUGH-mingyan.md`）：
  1. 每頁獨立檔＋隱藏頁 hash 檔名＋S3 無目錄列表 → 看 A 頁源碼不洩漏 B 頁、無法枚舉。
  2. **刪檔還原 ×4**：`del-*` 顯示「已刪除」，真實網址藏在該頁 HTML 註解裡（每頁自帶「檢視原始檔」鈕，手機可用）→ 貼回網址列才到隱藏 keystone 頁。
  3. **改網址遞增 ×1**：`uploads-0416/0418` 有連結、缺 `0417` 不放連結，靠玩家把號碼 +1 猜到。
  4. **公平麵包屑**：`n-webmaster`/`n-archive-notice` 先教「按鈕怎麼用、檔名連號、備份寫在註解」，不通靈。
- **埋深鐵律**（因玩家會用檢視原始檔，比一般更嚴）：keystone 只准出現在 stage≥4 節點，**任何 stage<4 頁的『源碼』grep keystone 必須零命中**。

## 怎麼跑稽核（請你獨立重跑）
```bash
cd tools/puzzle-quest/arg
python3 build.py mingyan-world.json     # 重建(自動清舊檔) → dist/mingyan/ 50 頁
python3 audit.py                        # A1–A4 + B1–B5 自動稽核,應全綠
# 用「真 core.any」再掃一次早階段洩漏(勿只信我的詞表):
python3 - <<'PY'
import json,glob
core=json.load(open('../CASE-13-mingyan.json'))['solution']['core']  # method/culprit/motive
words=[w for c in core if c['id'] in ('method','motive') for w in c['any']]  # 兇手名可早伏筆,不掃
m={x['file']:x for x in json.load(open('dist/mingyan/_manifest.json'))}
import os
hit=[(f,w) for f in glob.glob('dist/mingyan/*.html') if m[os.path.basename(f)]['stage']<4 for w in words if w in open(f,encoding='utf-8').read()]
print('早階段 method/motive keystone 洩漏:', hit or '零命中 ✅')
PY
```

## 三關驗收單（逐條對照，各檔內含我方自審結果＋你要複驗的清單＋風險點）
- **A 引擎正確性** → `VERIFY-engine.md`：hash 檔名穩定、階段閘門（離線 fallback 該鎖不該洩）、檢視原始檔逃逸/XSS、連結 fail-fast、清舊檔、`note.rawHtml` 是唯一信任欄位。
- **B 埋深/洩漏** → `VERIFY-depth.md`：早階段 keystone 零洩漏、早階段湊不齊 core、四還原鏈＋數字鏈公平、紅鯡魚公平、時間軸一致。
- **C 內容加厚（Fable5）** → `VERIFY-content.md`：27 節點加厚後回歸沒把真相講白、兇手僅中性伏筆、結構未被動（`mingyan-world.json.bak` 是加厚前版可 diff）。

## 重點風險點（請特別盯這幾個）
1. **階段閘門離線行為**：Firestore fetch 失敗時 fallback 為 stage1（最保守）——確認 stage4 隱藏頁在 fetch 失敗時是「鎖住」不是「洩漏」。
2. **檢視原始檔逃逸**：所有作者輸入走 `html.escape(quote=True)`；確認沒有任一渲染路徑把作者字串未逃逸塞進 HTML。`note.rawHtml` 是唯一信任原始 HTML 的欄位、僅作者用——確認世界圖沒濫用。
3. **改 node id 會讓 hash 檔名漂**：確認這點在 README/WALKTHROUGH 有標；目前 world.json 重算檔名 == 產物檔名（audit A2 已驗）。
4. **Fable5 在求職串（stage2）加了高董「深夜獨自來館」伏筆**——屬 culprit 中性伏筆、不構成 win（§5 分野），但請確認語氣沒滑成「暗示他犯案」。
5. **清舊檔**：`build.py` 產出前刪 out 目錄 `*.html`/`_manifest.json`；確認 `--out` 指非預期目錄不會誤刪其他檔。

## 埋深正典依據
- `../DESIGN_DIRECTION.md` §1（埋深）/§5（驗收 checklist）/§5 keystone vs 兇手名分野。
- 真 core.any／partial／reveal／storyboard 見 `../CASE-13-mingyan.json`。

## 檔案清單（tools/puzzle-quest/arg/）
| 檔 | 用途 |
|---|---|
| `build.py` | 產生器（世界圖→50 頁靜態 HTML） |
| `mingyan-world.json` | 世界圖（50 節點，含 Fable5 加厚） |
| `mingyan-world.json.bak` | 加厚前版本（C 關 diff 用） |
| `audit.py` | 自動稽核（A+B） |
| `enrich_prep.py` / `enrich_merge.py` | C 關：分批抽取 / 雙閘合併驗證 |
| `README.md` | 引擎 schema／開新案步驟／部署 |
| `WALKTHROUGH-mingyan.md` | 破關動線＋四 URL 關卡表 |
| `PHASES.md` | 未完成任務拆解（A–G） |
| `VERIFY-engine/depth/content.md` | 三關驗收單（← 你逐條回覆這些） |
| `dist/mingyan/` | 產物 50 頁（可自行重建；`_manifest.json` 部署時不上傳） |

## 回報格式（拜託）
每關逐條 `pass / fail / n/a` ＋ findings（`[Bug] / [埋深] / [公平性] / [nit]` ＋ 一句描述 ＋ 建議）。
blocking findings 收斂後回「A/B/C 可放行」。

---

# 修正回覆 · round 1（回應 Codex 兩個 blocking）

## Finding 1（High/A：`?stage` 公開繞過）— 已修
- `build.py` 加 `--dev` 旗標：**正式產出（無 `--dev`）不再注入 `?stage` 覆寫**，階段一律以 Firestore 為準；`?stage` 只在 `python3 build.py world.json --dev`（授權/測試）注入。
- 驗證：正式版 `grep "location.search).get('stage')" dist/mingyan/*.html` → **0 頁**；`--dev` 版 → 50 頁。
- 產出結尾會標 `[正式版:無?stage覆寫]` / `[--dev:含?stage覆寫,勿部署]`。

## Finding 2（High/B：早階段命中真 core.any、可提前 SOLVED）— 已修
- `audit.py` B1 **改讀真 `CASE-13-mingyan.json` 的 `core.any`（method+motive）**，不再維護第二份手寫詞表（culprit 名依 §5 允許早階段伏筆，不掃）。
- 早階段 5 處命中全部改寫成非 core 詞：
  - `電死`→`出人命/要人命`（t-blackout s1、d-safety-check s3）
  - `託名`→`傳為/傳稱作者/畫上款識年代`（d-appraisal s2、t-auction s3、img-painting s3）
- 提前破案模擬（真 core.any、stage<4 全文 includes）：`method 湊不到 ✅｜motive 湊不到 ✅｜culprit 湊得到(允許的兇手名伏筆)` → **早階段無法 SOLVED**。
- `audit.py` 全綠（A1–A4 + B1–B5）。

## ⚠️ 殘留限制（Finding 1 的更底層，請 Codex 一起裁）
純靜態 S3 無法做伺服器端階段閘門：**keystone 頁的完整 HTML 無論階段都被送達瀏覽器**，
`del-*` 存根的還原註解也一樣。被教會看原始碼的玩家，理論上可從 `t-main` 源碼看到 `del-*` 檔名 →
view-source `del-*` 讀還原註解 → view-source 隱藏 keystone 頁讀內文，**繞過階段節奏**（客戶端 lock 只換 DOM、不改原始檔）。
- 移除 `?stage` 已把「一鍵繞過」堵掉；但要**完全堵死階段節奏**，需 keystone 頁的內文改成 **stage≥4 才向 Firestore 抓**（不烘進靜態檔）＝Phase 2 加固（多一點 Firestore 讀）。
- 取捨：這遊戲的訴求是「答案很難找」，沿源碼一路走其實就是在做 ARG 苦工；是否要到「階段節奏不可繞」的等級，交使用者決定。請 Codex 就「以現況放行 A/B」或「要求併 Phase 2 才放行」給意見。

## 重新驗證指令
```bash
cd tools/puzzle-quest/arg
python3 build.py mingyan-world.json   # 正式版(無?stage)
python3 audit.py                       # 全綠(B1已讀真core.any)
```
