# CASE-13 明硯 · ARG 兔子洞破關動線（QA / 作者用）

50 個節點裡，**關鍵路徑約 8 步**，其餘 ~40 頁是氛圍／紅鯡魚／麵包屑（挖得深是沉浸，不是必經）。
玩家不必看完 50 頁才破案；但最深的三顆 keystone **一定要動用「檢視原始檔／改網址」才拿得到**。

## 入口
`forum.html`（城中大小事討論版首頁）。線上由甜甜 panel 給的連結進來。

## 關鍵路徑（三 core 各自的證物鏈）

### ① 手法 keystone — 人為破壞觸電（非意外）
- S1：主串 `t-main` →「檢方不當單純意外、有份電路鑑識報告被刪」（只指路、不明講）。
- S4：主串該樓連到 **`del-electrical`（已刪除存根）** →
- 點右下「⟨/⟩ 檢視原始檔」→ 源碼註解 `備份位置： ./_ca9558ea.html` →
- **把 `_ca9558ea.html` 貼回網址列** → `d-electrical`（隱藏 keystone）：接地被剪＋火線接外殼＋8/20 檢查合格＝人為破壞。
- 佐證（另一條還原鏈）：跳電串 `t-blackout` → `del-safety` → 檢視原始檔 → `_53796fa6.html`＝安檢合格時間鎖。

### ② 兇手 — 負責人高博彥（機會鎖）
- S3：主串「知情人」樓 → `d-access-log`（門禁log）：卓 19:40 早退無權限、深夜 `M-001·董事長級` 22:51 進修復室（**未具名**）。
- S3 佐證（改網址遞增）：保全老陳 `p-guard` → `uploads-index`（監視器上傳）→ 相簿只有 `uploads-0416`、`uploads-0418`，缺 0417 →
  **把網址 0418 改成 0417** → `uploads-0417.html`：22:51 符合高博彥身形的人獨自進修復室。
- S4：`d-access-log` 的「相關連結」→ `d-access-named`：M-001 實名＝高博彥＋機會鎖（唯一同時有門禁＋碰得到電路＋保全代碼）。

### ③ 動機 — 掩蓋贗品／洗錢滅口
- S3：拍賣串 `t-auction` → `al-auction` → `img-painting-detail` →「相關連結」→ `d-pigment`（S4）：鈦白時代錯置＝贗品。
- S4：主串「嚇到」樓 → **`del-ledger`（已刪除存根）** → 檢視原始檔 → `備份位置： ./_624caea4.html` →
  **貼回網址列** → `d-ledger`（隱藏 keystone）：人頭買家＋海外空殼對敲＝洗錢，高博彥主導，郭崇德為被利用人頭。

### 收束
`d-timeline`（S4 檢方時序，多處「相關連結」可達）把三 core 串成一條線。

## 紅鯡魚（公平、事後都能被 S4 證物解釋）
- **助理卓文瀚**（`t-artgossip`/`p-zhuo`/`d-hr`/`del-zhuo-comment`→`_dde24f5d`筆記本）：職場恨＋筆記像預謀 → 被 `d-access-log`（19:40 早退、無修復室權限）洗清。
- **藏家郭崇德**（`t-collector`/`p-guo`/`d-buyer-alibi`）：撂狠話、錢 → 被外地不在場＋`d-ledger`（他是人頭、被利用）洗清。

## 教學鋪陳（讓玩家先學會機制再面對 keystone）
- **檢視原始檔還原**先在 S2 低風險教學：`del-zhuo-comment` → `_dde24f5d.html`（卓的筆記本第二頁，紅鯡魚），
  站務公告 `n-webmaster`＋`n-archive-notice` 明說「按鈕怎麼用、備份位置寫在註解裡」。
- **改網址遞增**在 S3 由 `uploads-0418` 頁面文案＋EXIF 明講「試試把 0418 改成 0417」。

## 四個 URL-manipulation 關卡總表
| 關卡 | 入口（有連結） | 手段 | 目的地（無連結） | 內容 |
|---|---|---|---|---|
| 還原·電路 | `del-electrical` | 檢視原始檔→貼網址 | `_ca9558ea.html` | ① 人為破壞（keystone） |
| 還原·對帳 | `del-ledger` | 檢視原始檔→貼網址 | `_624caea4.html` | ③ 洗錢（keystone） |
| 還原·安檢 | `del-safety` | 檢視原始檔→貼網址 | `_53796fa6.html` | ① 時間鎖佐證 |
| 還原·教學 | `del-zhuo-comment` | 檢視原始檔→貼網址 | `_dde24f5d.html` | 紅鯡魚·筆記本（教學） |
| 遞增·監視器 | `uploads-0418` | 網址 0418→0417 | `uploads-0417.html` | ② 高博彥進修復室 |

（隱藏頁 hash 每次 build 依 node id 固定不變；若改了 node id/salt，hash 會變，記得同步。）
