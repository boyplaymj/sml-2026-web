# 捍衛路權（西裝蛙過馬路）── 階段化改造設計稿 v0.1

> 目標：把目前「無盡連續難度」的跑法，疊上**離散階段（stage）**——玩家前進到里程碑會「進入下一階段」，關卡樣貌與獎勵隨階段變化。
> 原則：**純加法、不動現有骨架**。距離排行榜、檢查點落袋、每日上限全部保留；stage 只是無盡跑道上的「主題帶＋里程碑」，不是關門結束。
>
> 程式位置：`/opt/sml/sweetbot-next/model/miniGame/CrossingRoad.js`（單檔）
> 相關常數：`STRIDE = 11`（每 11 格一個檢查點🟫安全島）、`COLS = 9`、`ENTRY_FEE = 200`、`DAILY_TEETH_CAP = 10000`、`DAILY_XP_CAP = 20`

---

## 0. 為什麼不是「每走 100」（數據依據）

掃 `sweetbot-viewer` 表 30 位有成績玩家的 `crossroadBest`（截至 2026-07-14）：

| 指標 | 值 |
|---|---|
| 最高距離 | **117**（唯一破百，1 人） |
| 中位數 | **17** |
| 平均 | 23.8 |
| 30+ | 8 人（27%） |
| 50+ | 2 人（7%） |
| 100+ | **1 人（3%）** |

**結論**：若門檻設 100，全服只有 1 人能進入第 2 階段，97% 玩家永遠卡階段 1 → 分階段等於沒做。
→ 門檻必須拉近，並對齊檢查點（過階段時人站在安全島，體感乾淨）。

---

## 1. 階段界線（對齊檢查點，STRIDE=11）

檢查點落在距離 11、22、33…。階段界線全部踩在檢查點上：

| 階段 | 名稱 | 距離區間 | 進階檢查點 | 預估觸及率 |
|---|---|---|---|---|
| **1** | ☀️ 白天市區 | 0 – 21 | — | 100% |
| **2** | 🌆 黃昏車潮 | 22 – 43 | CP@22（=2×11） | ~30% |
| **3** | 🌃 霓虹夜晚 | 44 – 87 | CP@44（=4×11） | ~10% |
| **4** | 🌧️ 暴雨高速 | 88 – 153 | CP@88（=8×11） | ~3%（含現任榜一） |
| **5** | 🔥 極限地獄 | 154+ | CP@154（=14×11） | 目前無人（給高手刷） |

界線上界（exclusive）：`STAGE_BOUNDS = [22, 44, 88, 154]`

```js
// 距離 → 階段序號(1..5)。純函數，不需存 DB（stage 可由 best 距離推回）
const STAGE_BOUNDS = [22, 44, 88, 154];
const stageOf = (dist) => STAGE_BOUNDS.filter((b) => dist >= b).length + 1;
```

> 曲線設計刻意「先密後疏」：階段 1 短（讓 100% 玩家很快嘗到進階的爽感），越後面越長（頂尖玩家有得刷）。
> 界線間距 22→22→44→66，倍率遞增。

---

## 2. 每階段旋鈕（STAGES 設定表）

**鐵律：階段 1 的所有數值＝現行值，一字不改。** 只在玩家往後推進時才加難度／加獎勵，避免動到 97% 玩家的入門體驗。

```js
const STAGES = [
  // n  名稱        theme    densityBonus  fastBias  restRowChance  teethMul  xpMul  clearBonus
  { n: 1, name: '白天市區', theme: 'day',   densityBonus: 0, fastBias: 0.0, restRowChance: 0.05, teethMul: 1.0,  xpMul: 1.0, clearBonus: 0    },
  { n: 2, name: '黃昏車潮', theme: 'dusk',  densityBonus: 1, fastBias: 0.3, restRowChance: 0.05, teethMul: 1.15, xpMul: 1.1, clearBonus: 80   },
  { n: 3, name: '霓虹夜晚', theme: 'night', densityBonus: 1, fastBias: 0.6, restRowChance: 0.04, teethMul: 1.35, xpMul: 1.25, clearBonus: 200  },
  { n: 4, name: '暴雨高速', theme: 'rain',  densityBonus: 2, fastBias: 1.0, restRowChance: 0.02, teethMul: 1.6,  xpMul: 1.5, clearBonus: 450  },
  { n: 5, name: '極限地獄', theme: 'hell',  densityBonus: 2, fastBias: 1.5, restRowChance: 0.00, teethMul: 2.0,  xpMul: 1.8, clearBonus: 900  }
];
const stageCfg = (dist) => STAGES[stageOf(dist) - 1];
```

### 旋鈕語意（對應現有程式）

1. **densityBonus** — 車流密度加成。改 `spawnVehicles()`：
   ```js
   // 現行：const target = Math.min(2 + (Math.random() < 0.4 ? 1 : 0) + Math.floor(lvl / 2), COLS - 4);
   // 改為：  ... + Math.floor(lvl / 2) + stageCfg(i).densityBonus, COLS - 4);
   ```
   `COLS-4 = 5` 的硬上限保留（9 寬至少留 4 格活路）→ densityBonus 效果是「更快逼近密度上限」，不會爆成無解。

2. **fastBias** — 快車偏壓。改 `pickVehType()` 的權重：`speed >= 2` 的車種（機車等）權重 ×`(1 + stage.fastBias)`，再正規化。這是**繞過密度上限**、讓高階段真正變難的主旋鈕（車更快＝反應窗更短）。

3. **restRowChance** — 喘息列（整排淨空）機率。現行寫死 `Math.random() < 0.05`，改讀 `stageCfg(i).restRowChance`。高階段趨近 0＝沒有免費喘息列。

4. **teethMul / xpMul** — 撿取道具的牙齒／EXP 倍率。改 `ensure()` 放道具處：
   ```js
   // 現行：{ kind: 'teeth', val: this.rint(15, 45) + lvl * 10 }
   //       { kind: 'xp',    val: this.rint(5, 15)  + lvl * 2  }
   // 改為乘上 stageCfg(i).teethMul / xpMul（四捨五入取整）
   ```
   （`lvl` 已在階段內持續遞增，再乘 stageMul → 獎勵隨深入自然放大。）

5. **clearBonus** — **一次性通關獎金**（本設計新增的「里程碑爽感」核心）。玩家在單局中**首次踏上某階段界線檢查點**時，發一筆 clearBonus 牙齒。詳見 §3。

---

## 3. 通關獎金 clearBonus（里程碑機制）

- 觸發：`move()` 前進成功後，若 `g.frogAbs` 正好等於某個 `STAGE_BOUNDS` 值（=界線檢查點）、且該階段未在本局領過 → 發獎。
- 發放方式：**加進 `g.carriedTeeth`**（不是直接入帳）。因為界線本身就是檢查點🟫，踏上去的同一步會走落袋邏輯 → 這筆獎金當場落袋、之後死掉也保得住。（跟現有「檢查點落袋」語意天然一致，不必另寫入帳路徑。）
- 防重複：`g.stageBonusPaid = g.stageBonusPaid || new Set()`；發過的 bound 加進 set。
- 每日上限：clearBonus 走 `carriedTeeth → bankedTeeth → settle()` 既有流程，自動吃 `DAILY_TEETH_CAP` 封頂，不需另外處理。
- UI：發獎當回合 `lastEvent` 顯示「🎉 抵達 🌆黃昏車潮！通關獎金 +150🦷（已落袋）」。

```js
// move() 內、g.frogAbs += 1 且 g.best 更新之後：
if (STAGE_BOUNDS.includes(g.frogAbs) && !g.stageBonusPaid.has(g.frogAbs)) {
  g.stageBonusPaid.add(g.frogAbs);
  const cfg = stageCfg(g.frogAbs);          // 剛跨進的新階段
  if (cfg.clearBonus > 0) {
    g.carriedTeeth += cfg.clearBonus;        // 站在界線檢查點→同步落袋
    ev += `　🎉 抵達 ${STAGE_ICON[cfg.n]}${cfg.name}！通關獎金 +${cfg.clearBonus}${emoji.teeth}`;
  }
}
```

---

## 4. HUD / 玩家可見的「階段感」

無需新美術即可先上線的視覺回饋：

1. **statusLine（每回合面板）**：加階段標籤＋距下一階段還差幾格。
   ```js
   // 現行：`🏁 距離 ${g.best}　${emoji.teeth} 身上 ${g.carriedTeeth}${bank}　|　回合 ${g.turn}`
   // 前面插一行：
   const cfg = stageCfg(g.best);
   const nextB = STAGE_BOUNDS.find((b) => b > g.best);
   const stageLine = `${STAGE_ICON[cfg.n]} 階段${cfg.n} ${cfg.name}` +
     (nextB ? `　🔜 再 ${nextB - g.best} 格進階` : '　（已達最終階段）');
   ```
   `const STAGE_ICON = { 1:'☀️', 2:'🌆', 3:'🌃', 4:'🌧️', 5:'🔥' };`

2. **settle 結算訊息**：距離後補「最遠抵達 🌃階段3 霓虹夜晚」。

3. **排行榜（leaderboardFull）**：距離欄後加階段徽章。stage 由 `stageOf(distance)` 現算，**不需新 DB 欄位**。

---

## 5. 視覺換色（時段/天氣主題）── Phase 2 生圖計畫

Phase 1 靠 §4 的階段 emoji 徽章＋文字給足「我進到新區了」；**Phase 2 才做整套換皮**。`theme` 欄位已預留（render 依 `stageCfg(i).theme` 選 tile 變體）。本節是給使用者「照著生圖」的清單。

### 5.0 先讀：渲染事實與約束（決定哪些能 AI 生、哪些不能）

- tile ＝ **128×128 的 Discord 自製 emoji**，在每列 **9 欄橫向鋪滿**當背景（`tw_lane_*`／`tw_island`／`tw_crosswalk*` 都是「整列同 tile 重複」）。
- ⇒ **左右邊緣必須無縫**（第 9 格右緣接第 1 格左緣）。AI 生圖幾乎做不到逐像素無縫拼接，且 tile 在聊天視窗只有指甲大，細節會糊。
- ⇒ **鐵律：會整列重複的路面/斑馬線/安全島 tile，走「程式重染」路線，不要 AI 生圖。** AI 生圖留給「不重複、單點出現、或只看一次」的美術（見 5.2）。

### 5.1 路線 A：路面 tile 程式重染（不是生圖工，但要先排）

`genTerrainTW.js` 目前所有色都是常數（瀝青基色 `[72,71,78]`、雙黃 `#…`、紅線 `#…`、磚島 `#8a3f30`）。Phase 2 把這些抽成「主題調色盤」，一個 theme 參數就烤出一整套：

```
node genTerrainTW.js --theme dusk  --out assets/terrains/dusk
node genTerrainTW.js --theme night --out assets/terrains/night
node genTerrainTW.js --theme rain  --out assets/terrains/rain
node genTerrainTW.js --theme hell  --out assets/terrains/hell
```

每主題要重染的 tile（沿用現有 key，加 theme 尾碼，如 `tw_lane_plain_dusk`）：
`tw_lane_plain / tw_lane_dash / tw_lane_yellow / tw_lane_red / tw_crosswalk / tw_crosswalk_green / tw_crosswalk_yw / tw_island`，以及「車底連續背景」variants。

各主題調色方向（給實作者，非生圖）：

| theme | 瀝青基色 | 標線 | 額外程式效果 |
|---|---|---|---|
| dusk 黃昏 | 暖灰偏褐 `~[86,74,70]` | 標線加暖色偏 | 全 tile 疊 8% 橘色 overlay（夕照） |
| night 霓虹 | 深藍黑 `~[40,42,54]` | 標線提亮＋青/粉點光反射 | 疊 10% 藍、隨機 2~3 點霓虹反光斑 |
| rain 暴雨 | 濕灰去飽和 `~[60,62,66]` | 標線半透（積水蓋住） | 隨機積水橢圓＋細斜雨絲線（程式畫，會動更好但先靜態） |
| hell 地獄 | 焦黑 `~[34,30,32]` | 裂縫透出岩漿橘 | 隨機龜裂線＋發光 ember 點 |

> 這條是最省事、且唯一能保證無縫的路。建議 **Phase 2 主體就是這個**，工作量＝把常數抽參數＋調 4 組色盤，交 Codex。

### 5.2 路線 B：使用者 AI 生圖清單（不需無縫、加分用）

以下是**真正適合你生圖**的項目——單點出現或只看一次、不用橫向拼接：

**B-1　階段進場立繪（最高優先，爽感核心）**
- 每次踏上界線檢查點（§3 通關獎金那一刻）發一張「歡迎進入新區」大圖到頻道。
- 4 張（dusk／night／rain／hell），西裝蛙站在該主題街景前的**單張情境圖**（非 tile，不用無縫）。
- 規格：1024×1024 或 1024×576 橫幅，Bedrock SD3.5，主角＝現有西裝蛙一致性（用甜甜設定圖當風格錨）。
- ⚠️ 遵守 i18n：**圖內不要放任何文字**，「通關獎金 +80🦷」等字走 Discord embed。

**B-2　主題點綴 emoji（單格、不整列重複 → 可生圖）**
- 現有 `CELL_ACCENTS` 機制支援「某格疊一個裝飾」。每主題 2~3 個氛圍小物，各 128×128、**透明背景 PNG**、單獨出現不拼接：
  - dusk：路燈暖光暈、下班車陣尾燈
  - night：霓虹招牌、地面光斑
  - rain：水漥反光、傘
  - hell：地裂岩漿口、火星
- 規格：Bedrock SD3.5，透明底，深色瀝青上要看得清（避免純黑）。

**B-3（選配）主題車輛皮膚**
- 車是單一 sprite、不拼接 → 可生圖。但車種多、且有速度碼綁定，成本高。**建議延後**，先用現有車。

### 5.3 生圖規格總表（B 類）

| 項目 | 張數 | 尺寸 | 背景 | 無縫? | 圖內文字 |
|---|---|---|---|---|---|
| B-1 進場立繪 | 4 | 1024²／1024×576 | 情境 | 否 | 禁 |
| B-2 點綴 emoji | ~10（4主題×2~3） | 128² | 透明 | 否 | 禁 |
| B-3 車皮（選配） | 視需要 | 各車原尺寸 | 透明 | 否 | 禁 |

- 生圖引擎：**AWS Bedrock Stability SD3.5（us-west-2）**（唯一可用，見記憶 reference_bedrock_image_gen）。
- 一致性：西裝蛙用甜甜角色設定圖當風格錨，避免每張長不一樣。

### 5.4 上線掛接（生圖完成後）

- B-2 emoji：走既有 `tools/emoji/upload.js` → 14 台金庫 guild → registry → `em()` 取用；render 依 `stageCfg(i).theme` 選對應點綴。
- B-1 立繪：存自控圖床（`boyplaymj-image`），§3 發通關獎金訊息時附該主題圖。
- 路面 tile（路線 A）：Codex 烤圖 → upload.js 上傳 `_<theme>` 尾碼 → render 的 `laneTile()/checkpoint()` 依 theme 加尾碼取 key（對不到就 fallback 現有 day 版，漸進上線不會破圖）。

### 5.5 建議節奏

1. **先只做 dusk 一整套**（路線 A 4 tile 重染 + B-1 一張立繪 + B-2 兩顆點綴），把「生圖→上傳→render 依 theme 切換」整條管線打通、Discord 實看一次。
2. 管線驗證 OK 再一次補齊 night／rain／hell。
3. hell 最後做（目前無人到達，投資報酬最低）。

---

## 6. 存檔 / 資料層

- **不需要新增 DDB 欄位。** stage 全由 `crossroadBest` 距離推導。
- 現有 `crossroadBest / crossroadBestTurns / crossroadTeeth / crossroadDaily*` 全部沿用。
- run-state 新增（僅記憶體、不落 DB）：`g.stageBonusPaid`（Set）。

---

## 7. 平衡備註（給實作者留意）

- **牙齒通膨**：階段 4/5 的 `teethMul` 1.6~2.0 疊上 `lvl*10` 的道具值，單局理論產出仍可能逼近 `DAILY_TEETH_CAP=10000`——由每日上限兜底，不會失控（且能到階段 4 的目前僅 1 人）。**本版已把獎勵整體調瘦**（乘率壓縮＋clearBonus 約砍半），若日後仍嫌肥，續調 teethMul／clearBonus，勿動上限。
- **階段 1 零改動**：確認上線後 stage 1 的密度、車速、喘息列、道具值與現版逐項相等（見驗收 §8-1）。
- **界線落點**：`STAGE_BOUNDS` 每個值都必須是 `STRIDE(11)` 的倍數（22/44/88/154 ✔）→ 確保界線＝安全檢查點，通關獎金當步落袋。

---

## 8. 驗收點（交 Codex）

1. **階段 1 不變**：距離 0–21 的密度公式、車速權重、喘息列機率(0.05)、道具值公式與現版**逐項相等**（可對照 diff 確認 stage1 cfg 全中性）。
2. **stageOf 正確**：dist 21→階段1、22→階段2、43→2、44→3、87→3、88→4、153→4、154→5。
3. **通關獎金**：單局首次踏 22 得 +150🦷 並「當場落袋」（死亡後仍保留）；同局重複踏 22（若有退回再前進）不重複發；踏 44/88/154 各發對應獎金一次。
4. **密度上限**：任何階段單列車輛數 ≤ `COLS-4 (=5)`，青蛙恆有活路（跑 200 回合不出現整列塞死）。
5. **每日上限**：高階段大量牙齒仍被 `DAILY_TEETH_CAP` 封頂，達標後當日後續局歸零邏輯不變。
6. **HUD**：面板顯示正確階段徽章＋「再 N 格進階」；到階段 5 顯示「已達最終階段」；結算與排行榜顯示最遠階段。
7. **無回歸**：檢查點落袋、掛機沒收、放棄結算、車輛碰撞判定不受影響。

---

## 9. 分工

- 設計：Claude（本文件）
- 實作＋驗證：Codex（單檔 `CrossingRoad.js`，改動集中在 `spawnVehicles / pickVehType / ensure / move / statusLine / settle / leaderboardFull` 七處 + 頂部常數區）
- 部署：改完 Codex 自驗 → 回報 → 使用者 Discord 實測階段 2 進階與獎金 → `./restart.sh`

---

## 10. Phase 2 路線 A：地形主題重染（正式交 Codex）

> 目標：`genTerrainTW.js` 目前所有顏色寫死＝只有 day 一套。把顏色抽成「主題調色盤」，`--theme <name>` 就烤出整套同幾何、只換色的 tile；render 依 `stageCfg(i).theme` 選對應 tile。**幾何/標線/補丁/無縫邏輯一律不動**，只換色 + 疊氛圍 overlay。
> 使用者已看預覽（測試頻道 1526446545514270760）拍板方向 OK。以下色值＝預覽用的基準，Codex 可微調但別偏離主題方向。

### 10.1 檔案與現況（`sweetbot-next/tools/emoji/genTerrainTW.js`）

寫死的顏色常數（要抽成 theme 參數）：
| 位置 | 現值(day) | 語意 |
|---|---|---|
| L137 | `W='#d8d5d0' Y='#c0a060' R='#8a3c38'` | 白/黃/紅標線 |
| L160 | `ASPHALT_MIX = [7×[r,g,b]]` | 瀝青底 7 色階 |
| L264-268 `island()` | 路緣 `#9aa0a6`／草 `#3f7d43`／灌木 `#4f944f` | 安全島(檢查點) |

（`busLane` 的 `[96,44,40]`、磚島 `#8a3f30/#b2543f/#a84e3b` 屬紅磚類，非本輪核心；有餘力再一起，否則保持 day。）

### 10.2 作法：抽一張 `THEME_PALETTES`

```js
// 頂部常數區新增。day 必須＝現行值（回歸鐵律）。
const THEME_PALETTES = {
  day:   { asphalt:[66,65,70], W:'#d8d5d0', Y:'#c0a060', R:'#8a3c38',
           island:{ curb:'#9aa0a6', grass:'#3f7d43', bush:'#4f944f' }, overlay:null },
  dusk:  { asphalt:[86,74,70], W:'#e6d8c4', Y:'#d2a850', R:'#94443a',
           island:{ curb:'#9a8f80', grass:'#5c6e38', bush:'#6e7d42' }, overlay:{ tint:'#ff8a3d', alpha:0.08 } },
  night: { asphalt:[40,42,54], W:'#c6ccda', Y:'#a89050', R:'#7a3450',
           island:{ curb:'#5a5f72', grass:'#2c4a34', bush:'#365a3e' }, overlay:{ tint:'#2a3ea0', alpha:0.10, neon:true } },
  rain:  { asphalt:[60,62,66], W:'#b6bcc2', Y:'#9a8a58', R:'#6e3a40',
           island:{ curb:'#6a7076', grass:'#3a5a42', bush:'#456a4c' }, overlay:{ tint:'#3a4650', alpha:0.10, rain:true } },
  hell:  { asphalt:[34,30,32], W:'#a89890', Y:'#c85a20', R:'#a02818',
           island:{ curb:'#4a3a38', grass:'#3a2420', bush:'#5a2e22' }, overlay:{ tint:'#000000', alpha:0.12, ember:true } },
};
const THEME = opt('--theme', 'day');              // CLI 旗標
const PAL = THEME_PALETTES[THEME] || THEME_PALETTES.day;
```

- `ASPHALT_MIX` 由 `PAL.asphalt` 程式產 7 色階（預覽用的位移法即可：`const D=[[0,0,0],[-3,-2,-3],[2,1,1],[-2,0,-1],[1,-1,-3],[-4,2,1],[3,3,2]]; ASPHALT_MIX = D.map(o=>PAL.asphalt.map((v,k)=>v+o[k]))`）。這樣色差收窄邏輯與 day 一致（不會出現接縫色塊）。
- `W/Y/R` 改讀 `PAL.*`。
- `island()` 三個色改讀 `PAL.island.*`。
- **輸出檔名加主題尾碼**（day 不加，維持現檔名＝零回歸）：`--theme dusk` → `tw_lane_plain_dusk.png`、`tw_island_dusk.png`…。變體尾碼順序：`tw_lane_plain_dusk_v3`（theme 在 v 之前）。

### 10.3 氛圍 overlay（render 疊，非只換常數）

`renderTile()` / `island()` 產圖最後一步，依 `PAL.overlay` 疊一層（左右無縫）：
- `tint/alpha`：整格罩半透明色（夕照橘、夜藍、雨灰、hell 黑）。**必做**，換色感主要靠這。
- `neon`(night)：隨機 2~3 個青/粉小光斑（`radialGradient`，seed 決定位置→同格固定）。
- `rain`(rain)：細斜雨絲線（週期整除 128→無縫）＋ 2~3 積水橢圓半透明反光。
- `ember`(hell)：龜裂線（透出 `Y` 岩漿橘）＋ 3~5 個發光點。
- 都吃 tile 的 seed（同格永遠同圖、不閃爍），且不跨左右邊或用滿版橫貫（維持無縫）。

### 10.4 render 端掛接（`CrossingRoad.js`）

- 現行 `emc('tw_lane_plain_v2', ...)`、`emc('tw_island', ...)`、`laneTile()` 回傳的 key，改成依當前列所屬 stage 的 `theme` 加尾碼：`key + (theme==='day' ? '' : '_'+theme)`。
- theme 由 `stageCfg(i).theme`（i＝該列絕對距離）決定。
- **fallback**：`em()` 對不到 `_<theme>` key 時回退 day 原 key → 主題 tile 還沒上傳也不破圖，可漸進上線（先 dusk）。

### 10.5 產出與上傳

- `buildSet`／`upload.js` 增加對 4 個 theme 目錄的迴圈（沿用現有 registry 機制；注意 `emoji stale-hash` 雷：新增 key 要真的觸發重傳）。
- 14 台金庫 guild emoji 容量要確認：新增 4 主題 ×(約 8 tile × 變體) 是否超額；超了就只上 in-game 真正用到的 key，別全上。

### 10.6 驗收點（route A）

1. **day 零回歸**：`--theme day`（或不帶）產出與現版逐檔 byte 對照無差（或視覺全等）。
2. **無縫**：每個主題的 `tw_lane_*`／`tw_crosswalk*`／`tw_island` 橫向鋪 9 格、縱向鋪，接縫處無色塊/無斷線（斑馬線上下無縫、雙黃線端點吻合）。
3. **主題辨識度**：dusk 暖褐、night 深藍、rain 灰、hell 焦黑+岩漿橘，四者一眼可分；overlay 有疊上。
4. **安全島換色**：檢查點島的草/路緣隨主題變（不再五主題同一片綠）。
5. **render fallback**：某主題 key 尚未上傳時，該列自動用 day 版、不破圖。
6. **命名**：day 檔名不變；其餘 `_<theme>` 尾碼；變體 `_<theme>_vN` 順序一致。
7. **建議節奏**：先只做 `dusk` 一套走完「烤→upload→render 依 theme 切」全鏈、Discord 實看，OK 再補 night/rain/hell（hell 最後）。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：唯一成本＝**Bedrock Stability SD3.5（us-west-2）生素材立繪／地磚**（§10）。這是**一次性素材製作**，非玩家 runtime 逐次呼叫——烤好即存自控圖床 `boyplaymj-image` 快取，遊戲改讀圖床貼圖，之後零 LLM 成本。
- **無新增 DDB 欄位**（stage 全由 `crossroadBest` 距離推導，§8）；emoji 走既有 14 台金庫（guild emoji 免費）。
- 生圖屬一次性、可控批量：**逐主題烤（dusk→night→rain→hell），每批人工檢視再續**，避免一次大量燒 Bedrock。
- **runtime 無 LLM／無付費 API／無新表**，故免「帳本表＋月度封頂」四件套。
