# 火車大亨 V1-c-4 go-live runbook(客運上線)

> V1-a/b/c-1/c-2/c-3a/c-3b 全完成 + Codex 驗過(最後 commit sweetbot-next 211e47c)。本步是**真正 go-live**:碰 DDB + restart(清 session)+ 私頻實測。**執行要 gameboy 定時機**。
> preflight(2026-07-18)已確認:DDB published catalogs **已含**客車廂 px_normal/green/tour + 客運車頭 n700s/e5/l0 → **不動 catalog**;balance **缺** 3 新欄 → 補。

## ⚠️ 執行前協調點
1. **restart 會部署整個工作樹**:sweetbot-next 工作樹目前有**他 session 的 DailyQuest 未提交 WIP** → restart 會讓它一起上線。**restart 前要與 DailyQuest owner 協調**(commit 乾淨 or 確認可上)。restart.sh 走 systemd,查未提交可能擋。
2. **restart 清所有頻道 session**(含 SML_Claude bridge 對話)→ 挑離峰、先預告。
3. 私頻實測需**至少 2 座玩家站**(自己 + 一個測試帳號/既有玩家),客運才有目的地可送。

## 步驟(照順序;前 2 步可先做,restart 才是不可逆點)

### Step 1 — 補 3 個 balance 欄到 DDB published + draft(targeted,不 re-seed)
```bash
for st in published draft; do
  aws dynamodb update-item --table-name train-tycoon-config --region ap-southeast-1 \
    --key "{\"section\":{\"S\":\"balance\"},\"state\":{\"S\":\"$st\"}}" \
    --update-expression "SET #d.#wm.#b = :b, #d.#aa.#stf.#tu = :tu, #d.#pax = :pax" \
    --expression-attribute-names '{"#d":"data","#wm":"worldMap","#b":"bounds","#aa":"antiAbuse","#stf":"shortTripFatigue","#tu":"thresholdUnits","#pax":"passenger"}' \
    --expression-attribute-values '{":b":{"M":{"w":{"N":"120"},"h":{"N":"120"}}},":tu":{"N":"40"},":pax":{"M":{"flowRate":{"N":"0.15"}}}}'
done
```
- ⚠️ 前置:worldMap / antiAbuse.shortTripFatigue 這兩個 map 在 published/draft **已存在**(preflight 確認 balance 有這些 map,只缺葉欄)→ nested SET 不會 abort。若哪個父 map 不存在會 ValidationException,改先補父 map。
- **副作用**:thresholdUnits 進 published → 舊 live 貨運的短程疲勞門檻從百分位改成 40。貨運面板 restart 後就停用,影響窗口 = Step1→restart 之間(建議相鄰做)。bounds/flowRate 舊碼不讀 → 無副作用。
- 驗:`get-item` 讀回 3 欄確認。

### Step 2 — 對現有站補 world 座標(人工放行 backfill,冪等)
```bash
cd /opt/sml/sweetbot-next && NODE_PATH=$PWD/node_modules node model/miniGame/trainTycoon/backfill_world.js
```
- 冪等:已有 node 的站 skip、決定性座標(spawnCoordForId,與開站同源)。
- 驗:輸出「新增 N、跳過 M」;`aws dynamodb scan train-tycoon-world --select COUNT` 對照 stations 數。
- backfill 讀 config bounds(Step1 後為 120);config 讀失敗也退 DEFAULT_BOUNDS=120。

### Step 3 — restart(不可逆點;先預告 + 協調 DailyQuest WIP)
```bash
cd /opt/sml/sweetbot-next && ./restart.sh   # systemd sweetbot-next.service;30 秒預告→重啟→resume 通知
```
- 開機檢查:NRestarts=0 / Logged in tenten#5083 / 無 error。
- restart 後遊戲讀新碼:`!火車` 派車面板 = 客運到別的玩家站。

### Step 4 — 私頻 903327108451950692 E2E 實測
1. `!火車` → 開站(自己若已有站則跳過;新站會落 world 座標)。
2. 需第 2 座站存在(測試帳號開站 or 既有玩家)。
3. 派車分頁:選客運車頭 → 客車廂 → 節數 → **目的地=別的玩家站**(暱稱純文字)→ preview(票收/來回時間)→ 確認。
4. 等來回時間到 → 開面板(惰性結算):**寄件人金庫 += 票收**、**收件人客流點 += round(座位收×0.15)**。
5. 驗 DDB:寄件人 stations.treasury、收件人 stations.flowPoints、transit 已刪(月台釋放)。

## Rollback(若 restart 後客運壞)
- 還原遊戲碼:`git -C /opt/sml/sweetbot-next revert 211e47c ef57455 d423774 6cd3322 a351715 aa90114 e55b85f`(或 checkout 舊 TrainTycoon.js)→ restart → 回舊貨運單程模型。
- 3 個 balance 新欄 additive、舊碼幾乎不讀(僅 thresholdUnits 影響貨運短程疲勞)→ 可留;要淨可 `REMOVE` 那 3 欄。
- world 表座標留著無害(舊碼不讀)。

## 完成後
- V1 客運 MVP live → 進 V2(貨運收貨閘 + 逾時 + 疲勞全套 + 客流點花用/設施改造)。
- 待校準(真玩後調 config,免改碼):thresholdUnits 40 / flowRate 0.15 / bounds 120 / 客運票收常數。
