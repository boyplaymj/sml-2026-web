# 牙菌斑怪獸 · DDB 資料模型 — 階段7b:`sweetbot-yajunban-world` 棋盤空間表

> 交接文件 · 產出日期 2026-07-17 · 承接 [STAGE2-schema-decision.md](./STAGE2-schema-decision.md) 決策⑧ + [STAGE6-battle-DRAFT.md](./STAGE6-battle-DRAFT.md)(重生挑格/相鄰格佔用「依賴階段7」)
> 狀態:**草稿**(Claude 出提案,待 signoff / Codex 二驗)。
> 語義來源:設計冊 §section-board(菌氣 Khui 移動/相鄰格 PvP/剩菜殘渣/賽季地圖重生)。型別/TTL 慣例延續 STAGE6(TTL 秒級 10 位、其餘時間戳 ms、一表兩制 DAO 封裝)。
> 用途:解 STAGE6 兩個掛帳——**「誰在我旁邊」相鄰查詢** + **重生挑格讀格佔用**——這兩者無法靠 `PK=userId` 的 monster 表回答,需空間索引表。

---

## 🧭 為什麼非要一張獨立空間表(問題定義)
- 怪獸座標 `pos{x,y}` 是 **M#CORE 屬性**(STAGE1 §1-3 / STAGE6 決策)。「查我自己在哪」= `GetItem M#CORE`,不需要本表。
- 但兩個查詢是**反向**的——給座標問「這附近有誰/有什麼」:
  1. **PvP 相遇 / 偷菜**:相鄰格(8 鄰域)有沒有別的怪。
  2. **敗北重生挑格**:擊敗者座標半徑內(≥8 格外)哪些格空著、哪裡偏 🪨。
  3. **剩菜殘渣 / 糖晶**:某格上有沒有可吃的動態元素、時間到自動消失。
- 這些**不可能靠 monster 表**(pos 是屬性不是 key,只能全表 scan)。→ 需要以**座標分桶**當 PK 的空間索引表。這正是 STAGE2 P1-6 / 決策⑧。

---

## ✅ 決策 ⑫:表結構 `PK=zone#gridBucket`,SK 型別 overloading

**`sweetbot-yajunban-world`** · PAY_PER_REQUEST · ap-southeast-1 · **開 TTL**(屬性 `ttl`,秒)。

| 欄位 | 值 |
|---|---|
| **PK** | `<zone>#<gridBucket>`,例 `S2026#12,7` |
| **SK** | 型別前綴 overloading(見下) |

- **`zone`** = 賽季 id(`seasonId`,如 `S2026`)。**賽季換季 = 換 zone 前綴** → 舊季桶再也不被查、靠 TTL 自然排乾(見決策⑮),**免批次刪地圖**。對齊 STAGE1 §1-4「賽季軟重置:世界/地圖歸檔、位置重生」。
- **`gridBucket`** = `floor(x/B)","floor(y/B)`,`B`=桶邊長(格),**旋鈕常數,建議 `B=16`**。把連續座標分成粗桶,一次 Query 一個桶拿到桶內全部佔用/元素。

### SK 型別(同桶內三類 item)
| SK | 別名 | 內容 | 一致性 | TTL |
|---|---|---|---|---|
| `OCC#<userId>` | 佔用 | 誰站在此桶哪一格(spatial 鏡射 M#CORE.pos) | 最終一致(讀時複驗) | **滾動 idle 過期**(見⑭) |
| `LOOT#<ulid>` | 殘渣/糖晶 | 動態地圖元素,吃掉/沖刷消失 | 最終一致 | **壽命到自動消失**(見⑬) |
| `META#TERRAIN`(可選) | 地形快取 | 見決策⑯:預設**不存**,地形由 seed 決定式生成 | — | — |

---

## ✅ 決策 ⑬:`OCC#` 佔用 item schema + 移動寫入路徑

```
PK  = "<zone>#<bucket>"          e.g. "S2026#0,0"
SK  = "OCC#<userId>"
attrs:
  userId     : S   玩家(= Discord id)
  pos        : M   { x:N, y:N }     精確格座標(桶內定位、複驗用)
  race       : S   種族(相剋/渲染,免再讀對手 monster 就能篩)
  stage      : N   階段(新手保護/聲望門檻預篩)
  posVersion : N   移動序號(單調遞增,複驗防 stale,見⑭)
  updatedAt  : N   ms,最後移動時間(顯示/idle 判定)
  ttl        : N   秒,= floor(updatedAt/1000) + IDLE_TTL_SEC(滾動)
```

### 移動 = **跨表 TransactWrite**(atomic 搬桶)
高頻(STAGE1 §1-3「移動 高頻/強一致防超支」)。一次原子完成三件事,不留半搬狀態:
- **同桶內移動**(`oldBucket == newBucket`):`Update M#CORE`(pos/khui_last_ts、扣菌氣條件寫)+ `Put OCC#`(同 PK/SK 覆寫新 pos/posVersion+1/ttl)。
- **跨桶移動**(`oldBucket != newBucket`):`Update M#CORE` + `Delete OCC#@oldBucket` + `Put OCC#@newBucket`。三動作、跨 monster+world 表、單一 TransactWrite。
- **posVersion 單調遞增**:每次移動 +1,寫進 M#CORE 與 OCC# 兩邊,當複驗指紋(⑭)。
- 佔用 item **極小(~0.2KB)**,高頻移動 WRU 主成本仍在 M#CORE ~2,OCC# 可忽略。

> 🔁 **回饋 STAGE6**:敗北**重生**在結算把 `pos` 寫進 M#CORE(STAGE6 決策)→ 重生落點也是一次「移動」,故 **STAGE6 結算的 M#CORE UpdateItem 需升級為含 world OCC 搬桶的 TransactWrite**(重生 = Update M#CORE 結算 + Delete 舊 OCC + Put 新 OCC)。STAGE6 已標「重生挑格依賴階段7」,此處把接法補明:**所有改 pos 的路徑(走一格 / 吃殘渣位移 / 重生落點 / 賽季重生)一律走同一個 DAO `moveTo()`,別讓任何路徑只改 M#CORE.pos 不同步 world**。

---

## ✅ 決策 ⑭:一致性模型——world 是「鏡射索引」,pos 真相在 M#CORE(lazy 複驗 + prune)

world 佔用是 M#CORE.pos 的**空間鏡射**。即使移動用 TransactWrite,仍有殘影來源(崩潰於交易外的邊角、未來新增改 pos 路徑漏接、TTL 尚未刪到期的閒置佔用)。故:

1. **真相唯一 = M#CORE.pos**。world OCC# 只用來「縮小候選集」,不當權威。
2. **讀相鄰 = 兩段**:先 Query 桶拿候選 OCC#(便宜、粗);對**真的要互動**的候選(PvP 相遇 / 偷菜前),`GetItem` 該玩家 `M#CORE` **複驗** `pos + posVersion` 一致再動手。這與 STAGE6 `PVP#` 的 **lazy-prune 玻璃箱**同一手法(記憶 [[project_yajunban_ddb_impl]] 「lazy零背景job」)。
3. **複驗不過 = best-effort prune**:發現 OCC# 的 posVersion < M#CORE 現值,或該怪其實已不在此格 → 標記/刪掉這顆 stale OCC(非阻斷,失敗略過)。閒置未刪的靠 TTL 收尾。
4. **posVersion 單調**:複驗只信「OCC.posVersion == M#CORE.posVersion」,避免 ABA。

> 這套讓「移動偶發不同步」不會製造假戰鬥/假偷菜——最壞情況是候選集多一顆立刻被複驗剔除,而不是打到一個早就走掉的影子。

---

## ✅ 決策 ⑮:`LOOT#` 殘渣/糖晶 schema + 生成/消失/拾取

```
PK  = "<zone>#<bucket>"
SK  = "LOOT#<ulid>"          ulid=生成序,天然時間排序
attrs:
  pos      : M   { x:N, y:N }   落在哪一格
  kind     : S   殘渣/糖晶/食材…(決定拾取產出)
  amount   : N   量
  spawnAt  : N   ms,生成時間
  ttl      : N   秒,= floor(spawnAt/1000) + LOOT_LIFESPAN_SEC(「沖刷消失」)
```

- **生成**:系統/事件驅動 `Put`(戰鬥掉落、糖潮、隨機刷新)。落點桶 = `pos` 算出。
- **消失**:靠 **TTL 自動刪**(殘渣沖刷),不需背景 job(對齊「lazy 零背景 job」)。讀取端額外比 `ttl > now` 濾掉「到期未刪」的殘影(TTL 刪除有延遲)。
- **拾取(恰好一次)**:`Delete OCC 目標 LOOT#` 帶 `ConditionExpression attribute_exists(SK)` + 同交易 `Update` 拾取者(背包/菌氣)。條件 Delete 保證兩人搶同一顆只有一人成功——與 STAGE6 raid `LOOTED` 恰好一次同模式。跨表(world+monster)用 TransactWrite。

---

## ✅ 決策 ⑯:地形(🪨 等)= 決定式生成,**不存 world 表**

重生挑格要「偏 🪨 地形」。兩條路:存地形 vs 算地形。**選算**:
- 賽季地圖地形由 **`(seasonSeed, x, y)` 決定式函式**生成(引擎純函式,無隨機落庫)→ 任何時刻任何格的地形都可即時算出,**零儲存、零一致性問題、賽季換季換 seed 即換圖**。
- world 表因此**只存「會變的東西」**(佔用 + 動態元素),地形這種「整季不變」的不進表。符合 STAGE1 §1-3「地形快取」可有可無——快取是效能選項不是真相來源。
- 若未來要「可破壞地形/動態改地貌」再引入 `META#TERRAIN` 覆蓋層(疊在生成值上),現階段不需要。

---

## 🗺️ 相鄰查詢演算法(引擎用,schema 支撐驗證)
給座標 `(x,y)` 與半徑 `R`,要覆蓋 `[x−R, x+R] × [y−R, y+R]`:
- 涉及的桶 = `floor((x±R)/B)` × `floor((y±R)/B)` 的笛卡兒積。
- **相鄰 PvP/偷菜 R=1**:`B=16` 時多數落**單桶**,貼桶邊最壞 **2×2=4 桶**。
- **重生挑格 R=8**:`B=16` 時最壞 **2×2=4 桶**。
- 每個涉及桶 `Query PK=zone#bucket AND begins_with(SK,"OCC#")`(挑格另查 `LOOT#` 可略),合併後在記憶體用 `pos` 精確過濾 Chebyshev 距離。
- **`B` 是唯一旋鈕**:桶大 → 查詢桶數少但每桶 item 多;桶小 → 反之。小規模怪少,`B=16` 佳;真變密再調(改 `B` 需重建佔用鍵→放賽季邊界換)。

---

## ⏱️ 一表兩制時間(延續 STAGE6 鐵律)
- `ttl`(OCC 滾動 / LOOT 壽命)= **秒級 10 位**(`Math.floor(ms/1000)+窗口`),供 DDB TTL。
- `updatedAt` / `spawnAt` / `pos.snapAt` = **ms**(顯示/複驗/排序)。
- **DAO 封裝**,呼叫端只碰 ms;單測斷言「寫進 `ttl` 的是秒級」。TTL **只做 GC 絕不當鎖/當存活判定**(存活看 M#CORE + posVersion,STAGE6 同律)。

---

## 💰 成本控管(連回正典 [tools/COST_CONTROL.md](../COST_CONTROL.md))
- 新增 1 張 DDB 表 `sweetbot-yajunban-world`,**PAY_PER_REQUEST**、**無 GSI**(決策7a⑨)、**無 LLM/付費 API**。
- 主成本 = 高頻**移動**多寫一顆 ~0.2KB OCC(併入 M#CORE 的 TransactWrite,增量 WRU 極小)。殘渣/佔用靠 **TTL 自清**,**零背景 job、零排程 Lambda**。
- 賽季換 zone + 全表 TTL → **免批次刪除**歷史地圖(否則季末大量 delete 會噴 WCU)。
- 屬「純機制表、無外部付費來源」→ 不需帳本/月封頂四件套,但仍連回正典留痕。

---

## ➡️ 交給 Codex 二驗的收口點
1. **決策⑬ 跨表移動 TransactWrite**:monster+world 兩表放同一 TransactWrite 的**分區/大小上限**(≤100 item/4MB,穩過);同桶 vs 跨桶分支判斷正確;**回饋 STAGE6**——重生結算升級成含 world 搬桶的交易,確認不破壞 STAGE6 冪等(version/action_id)。
2. **決策⑭ 一致性**:lazy 複驗 + posVersion 防 ABA 是否夠;有沒有「不複驗就動手」的高頻路徑會被殘影咬(尤其偷菜)。
3. **決策⑮ 恰好一次拾取**:條件 Delete + 跨表 Update 的競態(兩人同格搶同顆殘渣)確實只一人成功。
4. **決策⑯ 地形不落庫**:決定式生成能否支撐「重生挑格偏🪨」與未來需求;要不要現在就留 `META#TERRAIN` 位。
5. **桶邊界 R=8 覆蓋**:`B=16` 對重生 R=8 的最壞桶數(4)確認;`B` 改動只能在賽季邊界的限制寫清楚。
6. **TTL 語義**:OCC 滾動 TTL 的 `IDLE_TTL_SEC`(建議 48h,同 STAGE6 租約 GC 級距)不會把「還在線但久沒移動」的玩家從地圖上抹掉導致他被跳過相遇——確認「讀時比 M#CORE 為準、TTL 只清殘影」這條防得住。
