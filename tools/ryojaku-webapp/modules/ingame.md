# 🎮 APP 內遊戲 (In-app Games)

> **狀態**：設計草案 🔶（Claude 提案，待 gameboy 拍板）
> 一句話：**App 內建的輕量小遊戲，養成黏著度與點數經濟，等直播/社群時有得玩。**

---

## 1. 定位與價值

在「找場之外」給玩家**每天打開 App 的理由**。參考 SML 既有甜甜遊戲館的成功模式（每日挑戰、轉蛋、練習賽），但主題聚焦麻將。
- 產出**點數/貨幣**，回流到 `/profile` 兌換與獎勵系統、天梯裝飾、館家優惠。
- 低成本、可快速上新，當社群活動載體。

---

## 2. 遊戲清單（草案，先做 MVP 2–3 款）🔶

| 遊戲 | 玩法 | 成本敏感 |
|---|---|---|
| **每日一牌 / 猜番** | 給牌面猜台/番，累積連勝 | 純規則，題庫靜態 → 零 LLM |
| **聽牌挑戰** | 給 13 張，限時選聽哪張、算台 | 純規則（可與訓練工具共用引擎） |
| **牌桌轉蛋** | 消點數抽頭銜/邊框/表情 | DDB 機率表 |
| **每日簽到 streak** | 連續登入領點數 | DDB |
| **（進階）AI 出題** | LLM 動態生情境題/講解 | ⚠️ 燒 LLM → 需四件套 |

**Claude 傾向**：MVP 先做「每日一牌 + 聽牌挑戰 + 簽到」——**全走靜態題庫/規則引擎，零 LLM**，把成本壓到只有 DDB。AI 出題留 v2 再評估。

## 3. 資料模型草案 🔶
```
GamePlay    { userId, gameKey, date, score, streak, rewardClaimed }
GachaPool   { poolId, items[], weights[] }
PointLedger { userId, delta, reason, ts }   // 點數流水（可沿用既有點數體系）
```

## 4. API 草案 🔶
`GET /ingame-daily` · `POST /ingame-submit` · `POST /ingame-gacha` · `POST /ingame-claim` · `GET /ingame-leaderboard`

## 5. 後台管理面板（v2）
題庫 CRUD、轉蛋機率表、每日獎勵設定、上下架遊戲、點數發放稽核、（若上 AI）用量卡。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **MVP（無 AI）**：成本來源僅 DDB 新表 `ingame-play` / `gacha-pool` / 點數流水，PAY_PER_REQUEST，量級小（預估 < $2/月）。無 LLM／無付費 API → 免帳本封頂。
- **若啟用「AI 出題」**：走 Bedrock `global.anthropic.claude-opus-4-8` + prompt caching，沿用 EC2 role `sml-claude-ec2` 的 `bedrock:InvokeModel`，無 key；並備齊四件套：
  - 帳本表 `ingame-ai-usage`（PAY_PER_REQUEST + TTL 90 天，costMicros 整數）+ `rollup#month` 原子彙總
  - 月度封頂 env `INGAME_AI_MONTHLY_CAP_USD`（預設 15），呼叫前守門超額降級
  - kill switch `INGAME_AI_DISABLED=1`，無憑證預設 stub 不計費
  - 後台用量卡 + admin Lambda `aiUsage` action

## 6. 待你拍板
- [ ] MVP 先上哪 2–3 款？要不要一開始就上 AI 出題（會進成本控管）？
- [ ] 點數與天梯/館家優惠/牙齒經濟是否共用同一貨幣？
- [ ] 是否綁直播（像甜甜賓果盤那樣配合 Daily）？
