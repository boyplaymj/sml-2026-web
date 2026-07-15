# 🏆 賽事天梯 (Ladder)

> **狀態**：設計草案 🔶（Claude 提案，待 gameboy 拍板）
> 一句話：**把玩家的對局結果轉成競技積分，分賽季排名、晉降級、發獎勵。**

---

## 1. 定位與價值

両雀是 elite community，「天梯」給認真的玩家一個**看得見的實力座標**與長期目標：
- 每場結算後，依名次/淨分變動天梯積分 → 匯總成**賽季天梯榜**。
- 分**段位**（例如 青銅→白銀→黃金→白金→鑽石→雀聖），跨段有晉降賽感。
- 賽季結束**結算獎勵**（頭銜、邊框、兌換點數），下季軟重置。

與現有模組的接點：吃 `/game-detail` 的對局結果、`/rate-*` 的信譽當防作弊佐證、獎勵接 `/profile` 兌換系統。

---

## 2. 核心機制（草案，待選型）

| 決策點 | 選項 | Claude 傾向 |
|---|---|---|
| 積分算法 | (a) ELO/Glicko 對戰評分 (b) 名次積分表（1st +X…4th −Y） (c) 淨台數加權 | **(b) 名次積分表**起步，簡單透明、好解釋；成熟後再進 (a) |
| 賽季長度 | 月賽 / 季賽 | 月賽（節奏快、話題多） |
| 段位重置 | 硬重置 / 軟重置（往中間收斂） | 軟重置 |
| 上榜門檻 | 最少對局數（防刷榜） | 需 ≥ N 場才計入榜 |
| 防作弊 | 信譽差評/黑名單影響、異常淨分偵測 | 接信譽系統 + 主揪覆核 |

---

## 3. 資料模型草案 🔶

```
LadderSeason  { seasonId, name, startAt, endAt, status(active/settled), resetRule }
LadderEntry   { seasonId, userId, points, tier(段位), games, wins,
                netScore, rank, lastGameAt }
LadderReward  { seasonId, tier, rewards[] }   // 賽季結算獎勵表
```
天梯榜 = 對 `LadderEntry` 按 `points` 排序（DDB：`seasonId` 為 PK、GSI 排 points）。

## 4. API 草案（沿用 App 命名慣例）🔶
`GET /ladder-standings?season=` · `GET /ladder-me` · `POST /ladder-apply-result`（對局結算內部觸發）· `GET /ladder-seasons` · `POST /ladder-settle-season`（後台）

## 5. 後台管理面板（v2）
建立/開關賽季、調積分表與段位門檻、看即時榜、手動修正（作弊扣分/DQ）、賽季結算按鈕、獎勵設定。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：DDB 新表 `ladder-season` / `ladder-entry` / `ladder-reward`，量級極小（PAY_PER_REQUEST，讀多寫少，預估 < $1/月）。
- 所有新表 PAY_PER_REQUEST；無 LLM / 無付費 API，故免帳本封頂。
- 若日後加「AI 賽評/戰報生成」等 LLM 功能，回本規範補齊「四件套」。

## 6. 待你拍板
- [ ] 積分算法選 (a)/(b)/(c)？段位命名與階數？
- [ ] 月賽 or 季賽？獎勵形式（頭銜/點數/實體）？
- [ ] 天梯是否只算「俱樂部團局」等特定團局種類？
