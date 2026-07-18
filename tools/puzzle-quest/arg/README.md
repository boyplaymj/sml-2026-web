# 偽文件解謎 — ARG 兔子洞產生器

把一份「世界圖」JSON 編譯成一整包**互相連結的靜態 HTML**（每節點一頁），做成要一層層挖的
文件迷宮。純靜態、掛圖床即可、**$0 運行成本**（不燒 LLM、不吃 DDB）。

## 為什麼要這個
原本假網站是「單頁、捲一捲讀完」，而且**所有留言寫死在同一頁的 JS 源碼**——玩家開「檢視原始碼」
一次讀光所有階段。這個引擎把答案埋深：

1. **點擊埋深**：關鍵散在幾十份文件裡，要一層層點進去、跨文件對照才拼得出。
2. **每頁一個獨立檔**：看 A 頁源碼不會洩漏 B 頁；隱藏頁用 hash 檔名、S3 無目錄列表 → 無法枚舉。
3. **刪檔還原**：`deleted` 節點顯示「已刪除」，真實網址藏在該頁「原始碼的 HTML 註解」裡；
   玩家用每頁自帶的「⟨/⟩ 檢視原始檔」按鈕（**手機也能用**）撈出網址，**貼回網址列**才進得去。
4. **數字遞增網址**：連號檔（`uploads-0416/0417/0418.html`）故意缺一號、不放連結，靠玩家把網址號碼 +1 猜到。

## 用法
```bash
python3 build.py mingyan-world.json          # 正式版 → dist/<case>/（每次自動清空重建；無 ?stage 覆寫）
python3 build.py mingyan-world.json --dev    # 測試版：注入 ?stage=N 覆寫預覽階段（勿部署）
python3 build.py mingyan-world.json --out /tmp/x
```
**只有 `--dev` 版**的頁面支援 `?stage=N`（1–9）覆寫當前案情階段（授權/測試用）；**正式版不含此覆寫**
（否則玩家加 `?stage=4` 即繞過閘門）。線上實際階段一律讀 Firestore `sml_config/puzzle_stage`
（puzzleId 對上才生效），與既有 `mingyan.html` 同機制。

## 埋深鐵律（沿用 DESIGN_DIRECTION）
- **keystone（人為破壞/接地被剪/外殼帶電/鈦白/贗品/洗錢/滅口…）只准出現在 stage≥4 的節點**。
  因為「檢視原始檔」會讀到源碼——早階段頁面（含隱藏頁）源碼裡 grep 這些詞必須零命中。
  build 後用這段自檢：
  ```bash
  cd dist/mingyan && python3 -c "import json,glob;m={x['file']:x for x in json.load(open('_manifest.json'))};bad=['人為破壞','接地被剪','外殼帶電','鈦白','贗品','洗錢','滅口','他殺'];print([(f,w) for f in glob.glob('*.html') if m[f]['stage']<4 for w in bad if w in open(f,encoding='utf-8').read()] or '零洩漏OK')"
  ```
- **後段留言只給異常感＋指向被刪文件**，不明講手法動機（同理，會被檢視原始檔讀到）。
- **公平性**：要猜的網址（連號、備份位置）一定要在別的文件先埋暗示（本案：站長雜記講「檔名連號、缺一號不代表不存在」＋「站務把備份位置寫成 HTML 註解」；`n-archive-notice` 講已刪內容有備份）。不靠通靈。

## 世界圖 schema
```jsonc
{
  "config": {
    "case": "mingyan", "entry": "forum",            // 入口節點 id
    "siteName","siteLogo","siteSub","nav","footer",  // 站台外觀
    "puzzleId","firebaseKey","firebaseProject"       // 階段閘門讀 Firestore 用
  },
  "nodes": [
    { "id","type","stage",              // stage=從第幾階段起可看（預設1）
      "title","crumb",                  // 麵包屑
      "hidden": true,                   // 不被連結、hash 檔名（只能靠還原/改網址到達）
      "file": "uploads-0417.html",      // 明指檔名（給連號數字頁用；優先於 hash）
      "clue": true,                     // 標記關鍵路徑節點（僅供統計/QA）
      "see": [["節點id","顯示文字"]],    // 通用「相關連結」欄（任何類型可用，會被階段閘門套用）
      ...類型專屬欄位 }
  ]
}
```
### 節點類型與專屬欄位
| type | 用途 | 主要欄位 |
|---|---|---|
| `forum` | 討論版首頁（板塊＋串列表） | `sections:[{board,threads:[{id,title,replies,hot}]}]` |
| `thread` | 討論串 | `op:{name,time,text}`、`comments:[{name,time,text,likes,color,stage?,deleted?,reason?,link?:{node,label,stage?}}]` |
| `profile` | 會員個人頁 | `name,handle,color,bio,meta:[[k,v]],posts:[{title,time,link?}],album?` |
| `album` | 相簿縮圖牆 | `items:[{node,label,thumb?}]` |
| `image` | 單張影像 | `src?,caption,exif:[[k,v]]` |
| `doc` | 正式文件（紙感） | `org,docTitle,meta:[[k,v]],secs:[{h,body}],stamp?` |
| `deleted` | 已刪除存根 | `reason,hintText?,recover:{node,note}` → 產生器把 `recover.node` 的隱藏網址寫進 HTML 註解 |
| `note` | 純文字頁/站務/404 | `paras:[..],links?:[[node,label]],rawHtml?` |

**留言分階段**：`comment.stage`＝該樓從第幾階段起顯示（前端隱藏未到階段者、不計入樓層數）。
`comment.link.stage` 可比留言更晚（留言先出現、連到的證物晚點才通）。

## 開新案的步驟
1. 複製 `mingyan-world.json` 改成 `<case>-world.json`，改 `config`（case/puzzleId…）與 nodes。
2. 每個 keystone 做成 stage4 的 `deleted`→`hidden doc` 還原鏈；早階段只留指路留言。
3. `python3 build.py <case>-world.json` → 跑上面的自檢 grep（零洩漏）＋確認隱藏鏈（見 `WALKTHROUGH`）。
4. 部署到圖床 `image.boyplaymj.link/pq/<case>/`（見下），把 case JSON 的 `clues.site`／`stages[].site`
   指到 `.../pq/<case>/forum.html`。

## 部署（圖床 S3 + CloudFront）
```bash
aws s3 sync dist/mingyan/ s3://<圖床bucket>/pq/case13/ --exclude "_manifest.json"
# CloudFront E2IJWN6FWT2XYG 失效 /pq/case13/*
```
> ⚠️ 部署＝對外上線，先在對話頻道確認。`_manifest.json` 是 QA 用、不要上傳（含隱藏頁清單）。
