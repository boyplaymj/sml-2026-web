# 火車大亨 Block A — Codex 交接（建 5 表 + DAO + config seed）

> 目標:把玩法資料層立起來(表/DAO/型錄),與素材線並行。對齊 DESIGN.md §9/§13。
> 分工:Claude 起草(本批檔案),Codex 驗證 + 落地到 sweetbot-next + 執行建表/灌種。

## 產出檔案(本 repo `tools/train-tycoon/`)
- `seed/create_tables.js` — 冪等建 5 表(全 PAY_PER_REQUEST,ap-southeast-1)。
- `seed/config_seed.json` — JR 型錄 + 目的地 + 平衡 的 seed 資料(§13)。
- `seed/seed_config.js` — 把 seed 灌成 `train-tycoon-config` 的 published + draft item。
- `dao/TrainTycoonConfigDAO.js` — 讀 published 型錄/目的地/平衡,惰性快取 + fallback。
- `dao/TrainTycoonStationDAO.js` — 車站狀態(建站/存檔/提款/回沖/結算游標,原子操作)。
- `dao/TrainTycoonTransitDAO.js` — 在途列車(SK=arriveAt 補零#dispatchId,range query 撈已抵達)。

## 5 張表 key schema
| 表 | HASH | RANGE | 用途 |
|---|---|---|---|
| `train-tycoon-config`   | section (S) | state (S) | 後台 draft/published 型錄設定 |
| `train-tycoon-stations` | userId (S)  | —         | 玩家車站狀態(§14.4 渲染欄位) |
| `train-tycoon-transit`  | userId (S)  | sk (S)    | 在途/待抵達列車(sk 字典序==時間序) |
| `train-tycoon-world`    | nodeId (S)  | —         | 全服共用目的地世界狀態(需求/報價/熱度) |
| `train-tycoon-events`   | userId (S)  | ts (N)    | 事件流水/待回應事件 |

## 落地步驟(Codex)
1. 複製 3 個 DAO 到 `sweetbot-next/DAO/DDB/`(相依既有 `DDBBaseDAO.js`,已對齊)。
2. 建表:`node create_tables.js`(或搬到 `sweetbot-next/migration/`)。冪等,重跑安全。
3. 灌種:`node seed_config.js`(讀同目錄 `config_seed.json`)。
4. 驗:`TrainTycoonConfigDAO.getGameConfig()` 應回傳 8 動力車 / 8 車廂 / 5 設備 / 4 人員 / 4 目的地。

## 驗收點
- [ ] 5 表皆 ACTIVE、PAY_PER_REQUEST、key schema 如上。
- [ ] config 三 section(catalogs/destinations/balance)published + draft 皆在。
- [ ] DAO fallback:清空 config 表時 `getGameConfig()` 仍回最小可玩集、不丟例外。
- [ ] transit `listArrivedBefore(u, now)` 只回 arriveAt<=now 的趟次(補零字典序正確)。
- [ ] station `withdraw` 餘額不足 / 非 active 時 ConditionalCheckFailed,不扣款。

## 尚未含(後續 Block)
- 玩法主程式 `sweetbot-next/model/miniGame/TrainTycoon.js`(!火車 單指令 + rrt: 按鈕面板 + 惰性結算引擎)。
- 後台 `sweetbot-site/public/train_tycoon_admin.html`(照 mahjong_tycoon_admin.html)。
- `train-tycoon-world` 世界 tick 需求波動、events 事件系統(Phase 3/4)。
- 車站渲染器 renderStation()(接素材線;素材風格鎖定審圖中)。

## 💰 成本
新 5 表全 PAY_PER_REQUEST;無 LLM/付費 API(惰性結算純程式);預估 <$1~2/月。見 DESIGN.md 成本控管段。
