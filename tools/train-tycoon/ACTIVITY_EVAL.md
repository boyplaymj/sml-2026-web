# 火車大亨走 Discord Activity(Embedded App SDK)— 技術/成本評估

> 日期:2026-07-15　評估對象:把甜甜火車大亨做成 **Discord Activity**(iframe 內的即時互動 web app),而非傳統 bot 生 PNG 面板。
> 動機:使用者想藉這款遊戲**實試 Discord 這幾年的新機制**,並追求 OpenTTD 那種**可拖曳/縮放的即時斜角地圖**。
> 來源:Discord 官方 Activities 文件、Embedded App SDK(GitHub)、Verified/Unverified Activities 支援文。

---

## 1. 一句話結論
Activity 能給你**真・即時互動斜角地圖**(不用每次生 PNG),但它本質是**「寫一個小型網頁遊戲(前端 + 後端)並自架 host」**,工程量比 bot 版大一個級距;**上大群前必須通過認證**。建議**先以未認證 Activity 在 <25 人測試群把 MVP 蓋起來玩+學管線**,驗證好玩再走認證。

---

## 2. 架構:Activity 需要哪些零件
| 零件 | 說明 | SML 現況 |
|---|---|---|
| **前端 web app** | 跑在 Discord iframe 裡的 HTML5/Canvas 遊戲(斜角地圖引擎,如 PixiJS/Phaser) | 需新寫 |
| **Embedded App SDK** | 前端 ↔ Discord client 溝通(取得使用者身分、頻道、participants) | 接官方 SDK |
| **OAuth2 授權** | `authorize()`→ 拿 code →**後端** exchange token →`authenticate()` | 需後端一個 token endpoint |
| **後端遊戲伺服器** | SDK **不含**多人連線/狀態同步 → 遊戲狀態、路線結算、牙齒經濟全要自己的後端(HTTP + 可選 WebSocket 即時) | 可用既有 EC2/Lambda + DynamoDB |
| **Hosting + HTTPS** | 前端靜態站 + 後端 API;Discord 會把外部請求走 `/.proxy/` 代理、需設 **URL Mapping**、受 **CSP** 限制 | 可用既有 S3+CloudFront / EC2 |
| **牙齒經濟串接** | 讀寫既有 `sweetbot-player-point-log` 等 DDB,牙齒與全站共用 | 現成,直接接 |

**重點:遊戲「核心邏輯」(車站/購車/路線/在途結算/牙齒)跟 bot 版是共用的**——不會白做。差別在**呈現層**:bot=生 PNG;Activity=前端即時算圖(Canvas),還能拖曳縮放點擊。

---

## 3. 認證門檻(決定性)
- **未認證 Activity**:只能在 **<25 人的伺服器**或 **DM** 由開發者/受邀測試者啟動。→ **適合開發、內測、學習,零審核。**
- **要在 SML 主群(>25 人)給所有人玩 → 必須「認證 Verified」**,才解鎖 discoverability/monetization。認證要求:
  - App 通過 Discord 驗證流程;
  - **公開的隱私政策 + 服務條款**(Activity 可存取使用者 IP 等 → 官方要求揭露);
  - 無限制級內容、符合開發者條款/社群守則;
  - 審核需時(非即時)。
- **費用**:認證本身不收費;成本是**時間 + 要備妥法務頁(Privacy Policy/ToS)**。

> 影響:MVP 學習階段**不受影響**(小群/DM 直接玩);但「正式上線給全群」多一道**認證前置**,要排時程。

---

## 4. 成本(遵循 tools/COST_CONTROL.md)
- **成本來源**:前端靜態 hosting(S3/CloudFront，可併既有)＋後端 API/WebSocket(EC2/Lambda)＋DynamoDB(遊戲狀態表，全 PAY_PER_REQUEST)。**無 LLM、無付費 API。**
- **與 bot 版差異**:bot 版寄生在既有甜甜程序、幾乎零增量;**Activity 版多了「一個要長期運轉的 web 服務」**——若用既有 EC2 併跑,增量很小(< 幾 USD/月);若上 WebSocket 即時同步、要獨立進程,略增。
- **量級**:預估 < $3~5/月(視是否常駐 WebSocket)。仍無帳本四件套需求(無 LLM)。
- **隱含成本**:認證要備隱私政策/ToS 頁(一次性)。

---

## 5. 工程量(誠實估;比 bot 版大)
分階段,每階段仍可 <25 分小塊切:
- **P0 Hello Activity**:建 Discord App→設 Activity→URL Mapping→iframe 載入最小前端→SDK `authenticate()` 拿到使用者→在 <25 人測試群跑起來。(**學會管線的關鍵一步**)
- **P1 斜角地圖引擎**:PixiJS 等鋪等距 tile、拖曳/縮放、點 tile;先用 CC0 素材包。
- **P2 後端 + 狀態**:遊戲狀態 API(DynamoDB)、建站/購車/派車/在途結算,串牙齒經濟。
- **P3 即時感**:WebSocket 或輪詢做在途列車/多人看得到彼此(共用互連路網的社交面)。
- **P4 打磨 + 認證**:隱私政策/ToS、驗證申請、Discovery 設定 → 上主群。

> 相對照:bot 版 Phase 0~2(前面設計冊)大概是 P0~P2 的一半工，且不需前端引擎/認證。

---

## 6. 優劣對照
| 面向 | Bot + Components V2(生 PNG) | Activity(即時 web app) |
|---|---|---|
| 視覺 | 靜態圖,依狀態換圖 | **即時互動、可拖曳縮放**、最接近 OpenTTD |
| 工程量 | 小(現有架構) | **大**(前端引擎+後端服務+SDK+認證) |
| 上線門檻 | 無,直接發正式頻道 | **>25 人群要先認證** |
| 學新東西 | Components V2(小) | **Activity 全套(大,正合「想試」)** |
| 成本 | 幾乎零增量 | 小幅(多一個 web 服務) |
| 玩法邏輯 | ← 兩者**共用**,不白做 → | |

---

## 7. 建議路線(兼顧「想試」與「不燒過頭」)
**兩階段、風險遞增:**
1. **學習/原型階段(現在做,零認證)**:開一個 **<25 人的 SML 開發測試群**,把 Activity MVP(P0→P2)蓋起來自己玩。**完整學會 Activity 管線**、驗證斜角互動地圖手感與玩法是否有趣。**這步就滿足「用這遊戲試新機制」的目標。**
2. **正式化階段(玩法驗證後再投入)**:備隱私政策/ToS → 申請認證 → Discovery → 上 SML 主群。

**保險**:核心玩法邏輯與後端 DDB 從一開始就跟「可能的 bot 版」共用設計 → 萬一 Activity 太重或認證卡關,隨時能退回 bot + PNG 版呈現,玩法不浪費。

---

## 8. 待使用者拍板
1. 走 **B(Activity)** 當主線,先做 P0「Hello Activity」把管線跑通?
2. 前端引擎選型(PixiJS 輕量 2D/等距、Phaser 遊戲框架…)由 Claude 建議後定。
3. Activity 掛哪個 Discord App(新建專用 App / 沿用現有)?牽涉 [[project_sweetbot_ownership_migration]] 的身分歸屬,建議**新建一個乾淨的專用 App** 避免糾纏。
4. 測試群(<25 人)由使用者開,還是 Claude 協助建。

---

*本評估待使用者拍板路線後,P0 再細化為建 App/URL Mapping/最小前端的逐步手冊。*
