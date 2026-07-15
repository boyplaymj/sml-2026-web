# 両雀後台中樞 — 架構與治理

> 這是 **両雀 (Ryōjaku) web app 的專屬後台**。目標：**未來所有功能設計文件都集中在這裡管理**。
> 現階段（原始碼未交、無後端存取權）= **設計/文件中樞**；取得工程師 API 權限後，逐模組長出「實際資料管理面板」。
> 最後更新：2026-07-15

---

## 1. 定位

| 階段 | 後台形態 | 依賴 |
|---|---|---|
| **v0（現在）** | 文件中樞：集中管理各模組設計冊，cyberpunk 風單頁 | 純前端，零成本 |
| v1 | 加入「唯讀」資料檢視（打工程師 API GET） | 需 API base + 讀取權/token |
| v2 | 加入實際管理操作（建賽季、上架館家、發遊戲…） | 需寫入權 + 各模組後端 |

現在做 v0，把地基打好；v1/v2 待原始碼與權限。

---

## 2. 結構

```
tools/ryojaku-webapp/
├─ SPEC.md            現有架構還原規格（登入/揪團/社群/評分/記帳/聊天/推播）
├─ ARCHITECTURE.md    ← 本檔
├─ admin/
│  ├─ index.html      後台中樞（讀 modules.json → 側欄 → 渲染 md）
│  └─ modules.json    模組清單（單一事實來源；新增功能只改這裡 + 丟 md）
└─ modules/
   ├─ ladder.md       賽事天梯
   ├─ ingame.md       APP 內遊戲
   ├─ parlor.md       麻將館專區
   └─ training.md     訓練工具
```

**新增一個功能文件的流程**：`modules/` 放一支 `.md` → `modules.json` 加一列 → 後台自動出現在側欄。

---

## 3. 模組總覽

### 現有架構（已上線，見 SPEC.md）
帳號系統 / 揪團找場 / 社群貼文 / 信譽評分 / 記帳財務 / 聊天訊息 / 推播獎勵

### 新專區（本輪新增，設計草案）
| 模組 | 一句話 | 成本敏感度 |
|---|---|---|
| **賽事天梯** `ladder` | 對局結果進積分天梯、分賽季、天梯榜與晉降級獎勵 | DDB/Lambda（精簡成本段） |
| **APP 內遊戲** `ingame` | App 內建小遊戲（每日挑戰/練習賽/轉蛋），點數經濟 | DDB＋可能 LLM |
| **麻將館專區** `parlor` | 實體麻將館/俱樂部名錄、優惠、包桌預約、打卡 | DDB＋S3（精簡成本段） |
| **訓練工具** `training` | 練習工具集：算台/聽牌/牌效/語音判台 | 可能 LLM＋ASR（四件套） |

---

## 4. 設計系統（沿用 App，見 SPEC §3）

後台視覺與 App 一致：深色 cyberpunk。底 `#050b14` / slate `#0f172a`，霓虹 cyan `#06b6d4`、pink `#d946ef`、yellow `#facc15`、purple `#8b5cf6`，玻璃擬態卡、neon 陰影、mono 字體標題。

---

## 5. 成本控管

- **後台中樞本身**：純前端靜態頁，**免成本規範**（見 tools/COST_CONTROL.md §0「不算額外成本」）。
- **各新模組**：實際實作若吃 LLM/DDB/S3/付費 API，其 `modules/*.md` 設計冊**必須**含「💰 成本控管」段並連回 `tools/COST_CONTROL.md`（燒 LLM 者備齊帳本/月封頂/後台卡/kill switch 四件套）。

---

## 6. 本機預覽

```bash
cd tools/ryojaku-webapp && python3 -m http.server 8899
# 開 http://localhost:8899/admin/
```
（因後台用 fetch 讀本地 md，需經 http server，不能直接 file:// 開）
