# 試煉之門 10 層難度重算 + L10 魅魔 — 設計規格 v1（2026-07-13）

Claude 設計，交 Codex 做數值反解 + 實作 + 自驗。**不部署**（使用者先實玩）。

改動檔案：
- `/opt/sml/sweetbot-next/const/trialGateLayers.js`（每層 HP / attack / name / 台詞 / increase）
- `/opt/sml/sweetbot-next/model/RPG/TrialGate.js`（魅魔奪魂機制、砍狂暴 bug）

維持 **10 層**（不走 6 層改版）。

---

## 1. 戰鬥機制事實（Claude 已從程式讀出，Codex 實作/模擬前務必吃進去）

玩家 `initPlayer`（line 45）：`hp=100, attack=100, attackAdd=0, attackIncrease=0`。
有效傷害 `getPlayerAttack`（line 75）：`(attack + attackAdd) * (1 + attackIncrease/100)`。**起手乾淨一擊 = 100**。

作答流程（`action` line ~582）：
- 單張答案 = 求提示：`thisPlayer.attack -= showCardPay`（random 2~4），露一張牌，**不觸發反擊**。
- 多張答案（真攻擊）：對→`boss.hp -= 有效攻擊`；然後 `checkBossAlive`，**只要王還活著就 `bossAttack`**。錯→不扣王血，**但一樣觸發 `bossAttack`**。

`bossAttack`（line 623）：
- 目標**永遠先 P1**，P1 死了才 P2（line 625-626）。**不會同時打兩人。**
- `target.hp -= boss.attack`，夾 0。

女神祝福 `playerIncrease`（line 84，每層擊敗後**只有補刀那人**拿一次；可被 `boss.increase[]` 限制池）：
1:+20 攻擊加點 / 2:+10 / 3:+5 / 4:+20% 增幅 / 5:+10% / 6:+20 血。

治療/道具：礦泉水 +50 血（上限 100，可重複買，`rpgTgBuy*`）；復活道具把死者拉回 50 血（line 783）。

### ⚠️ 核心平衡張力（這是整個重算的命門，務必在模擬裡處理）
**王每被攻擊一次就反擊一次，且永遠打 P1。** 一隻王要 2~3 次有效攻擊打死 → **P1 每層要吃 2~3 下反擊**（答錯還更多）。10 層累積 = P1 要吃 **25~40 下**。P1 血池只有 100 + 治療。
→ 所以 attack curve 若不夠低 / 治療經濟若沒算進去，**前段就會團滅**。這正是要 Monte-Carlo 反解的原因，不是拍腦袋填數字。
→ 設計意圖（使用者已同意）：前中段兩人靠治療都能撐；**後段致命**、坦克 P1 開始倒；**L10 P1 必死、carry P2 殘血收頭**。

---

## 2. 設計目標（模擬要達標的量化指標）

以「稱職隊伍」為基準：答對率 ~85%、偶爾用提示、會買礦泉水補血、分工＝P1 坦(被打)/P2 carry(補刀拿祝福)。

- **G1 每隻王 2~3 次有效攻擊擊殺**：`P(該層有效攻擊數 ≤3) ≥ 0.9` 且 `P(=1 擊秒殺) ≤ 0.15`（不能太脆）。
- **G2 全程通關率**：稱職隊伍打完 10 層成功率落在 **55~70%**（有挑戰但非勸退）。
- **G3 前段容錯**：L1~L5 對稱職隊伍**不應單層團滅**（給犯錯空間）。
- **G4 恐懼曲線**：L7 起單擊逼近「半血以上」，L8~L9 單擊接近秒殺，讓玩家真的怕。
- **G5 L10 魅魔**：P1 **100% 死亡**（不管疊多少血）；survivor P2 若打得好則以 **HP>0 且通常 <40** 過關；打不好則團滅。

---

## 3. 數值表 v0（**起始錨點，Codex 用模擬微調**，別當定案）

`hits` 欄 = 設計上預期擊殺所需有效攻擊數。

| 層 | boss HP (v0) | boss attack (v0) | 目標 hits | 備註 |
|---|---|---|---|---|
| 1 | 220 | 8  | 2~3 | 教學層，attack 極低 |
| 2 | 250 | 12 | 2~3 | |
| 3 | 285 | 16 | 2~3 | |
| 4 | 325 | 22 | 3   | 3 變體共用，數值取平均帶 |
| 5 | 370 | 30 | 3   | |
| 6 | 420 | 40 | 3   | |
| 7 | 470 | 55 | 3   | 恐懼起點：單擊過半 |
| 8 | 520 | 72 | 3   | 3 變體共用 |
| 9 | 570 | 95 | 3   | 近乎秒殺 |
| 10 | 640 | 見 §4 魅魔 | 3 | 最終王，奪魂機制 |

**HP 隨層升**是因為玩家有效攻擊隨祝福滾大（carry 到後段約 170~200）。Codex 反解時 HP 要對齊「該層玩家實際攜帶的有效攻擊分佈」，不是照抄上表。
**attack curve** 是 Claude 依「P1 累積承傷 + 治療經濟」手estimate 的恐懼曲線；務必用模擬驗證前段不團滅（G3）、後段夠痛（G4），再微調。

去掉每層多變體之間 HP/attack 的雜亂（現況 L4/L7/L8 三隻數值亂跳）——同層變體可保留「台詞不同」，但 HP/attack 對齊該層設計值。

---

## 4. L10 魅魔（succubus）— 奪魂機制（要寫程式）

改名：`十三么業龍` → **魅魔**。台詞全部改魅惑/致命/恐懼調性（Claude 另給文案，見 §6）。

機制（在 `TrialGate.js` 的 `bossAttack` 加分支，靠 boss 設定旗標驅動，資料驅動不寫死層號）：

- 在 `trialGateLayers.js` L10 boss 加欄位 `soulDrain: true`（或 `mechanic: "soulDrain"`）。
- `bossAttack` 內：若 `boss.soulDrain` 且本場尚未奪魂過（用 `gameInfo.data.soulDrained` 之類旗標）＋當前 target 是「第一個被鎖定的玩家」→ **直接 `target.hp = 0`（無視血量、無視加點）**，播奪魂台詞＋死亡圖。設 `gameInfo.data.soulDrained = true`。
  - 這保證 **P1 必死、無論如何**（純數字會被疊血/礦泉水破解，故用腳本）。
- 奪魂後魅魔轉打 survivor：改用**一般高傷（v0 約 65/擊，Codex 調）**，讓 survivor 能吃 1~2 下但不即死 → 逼 survivor 在 2~3 擊內把魅魔（HP v0 640，Codex 調）磨死，**殘血過關**（達 G5）。
- 邊界：若 survivor 也被磨死 → 正常團滅（可接受）。若奪魂當下另一人已死（極端）→ 退化為一般攻擊即可，別 crash。

**驗收**：模擬 L10 單獨開，確認 (a) P1 死亡率 100%；(b) survivor 通關時 HP 分佈落在 (0, ~40] 為主；(c) 不會 undefined/crash（target 為 null 的情況要守）。

---

## 5. 砍掉 ×100 狂暴 bug

`bossAttack` line 629：`if (P1.attack<=0 || P2.attack<=0) boss.attack *= 100;` — **移除**。
改為：任何會降 `player.attack` 的地方（求提示 line 585）扣完**夾下限 5**（`if (thisPlayer.attack < 5) thisPlayer.attack = 5;`）。
理由：狂暴是複利永久 ×100，等於用提示用到攻擊歸零就瞬間團滅，是地雷不是設計。下限 5 讓「狂用提示」只是變慢，不會被秒團滅。

---

## 6. 台詞（魅魔，Codex 貼進 L10 boss 各欄位）
- `appearanceTxt`：呵…終於有活祭品自己走進來了♡ 別急著逃，我會讓你們死得很甜。
- `attackTxt`：乖乖把靈魂交出來～這一下，可是會讓你上癮的哦♡
- `beAttackedTxt`：唔♡…痛得這麼溫柔，是想討我歡心嗎？
- `diedTxt`：怎麼會…被獵物…反過來品嚐了…可惡…下次…換我先動口…
- `killPlayerTxt`（奪魂擊殺）：噓——別掙扎了 {player}，你的靈魂，我收下了♡

> `{player}` 佔位符沿用現有機制（killPlayer 時代入死者），見 L10 舊 killPlayerTxt 用法。

---

## 7. Codex 任務清單
1. **Monte-Carlo 反解**（N≥20000，複刻本檔 §1 機制 + 治療/祝福/提示隨機）：解出每層 HP 與 attack，達 G1~G5。回報最終數值表 + 各 G 的命中率。
2. **實作**：更新 `trialGateLayers.js`（HP/attack/name/increase/台詞）＋ `TrialGate.js`（奪魂分支、砍狂暴、下限 5）。
3. **自驗**：跑一次模擬回歸 + 讀程式確認無 crash 路徑（target null、soulDrain 旗標、下限夾值）。回 diff。
4. **不部署**、不重啟 bot。使用者先實玩再決定上線。
5. 圖：L10 魅魔立繪 Claude 這邊處理（生圖中），與本數值改動獨立、不阻塞。

## 8. 注意
- `noAttackTime` / `topic.time` 是死碼（沒限時），別依賴。
- 結束會 bulkDelete 清戰鬥頻道；`givePoint` 是 fire-and-forget。
- 別在 sweetbot-next 留未提交臨時編輯（併行 AI 自動快照會吃進 commit）；改完即提交或明確標記。
