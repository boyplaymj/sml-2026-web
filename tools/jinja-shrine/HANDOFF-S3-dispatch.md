# 🗂️ 神社 S3 調度單：御神籤 + 御朱印（一起交 Codex）

> 兩系統一併施工（會動到同幾個檔，分開做會撞車）。權威樹＝`/opt/sml/sweetbot-next`。
> 讀這張 → 再讀 `HANDOFF-S3-omikuji.md`、`HANDOFF-S3-goshuin.md`（細規格）。

---

## 0. 兩張施工單
| 單 | 系統 | 設施 | 檔 |
|---|---|---|---|
| S3-omikuji | 抽御神籤（每抽100🦷、只首抽計運、凶籤強制結ぶ） | 授與所 | `HANDOFF-S3-omikuji.md` |
| S3-goshuin | 御朱印（月度500🦷、六軸長效buff隨枚數成長） | 御朱印受付所 | `HANDOFF-S3-goshuin.md` |

兩者互相獨立，但**共用下列前置 → 先做一次、兩邊共用，別各寫一份**。

---

## 1. 共用前置（先做，避免重工/撞車）
1. **`ShrineFortuneDAO.replaceBuffsBySource(discordId, source, newBuffs)`** — 濾掉 `buffs[]` 內指定 source 的舊筆、append 新筆（單次 Update 覆寫 `buffs`）。
   - omikuji 用 `source:'omikuji'`、goshuin 用 `source:'goshuin'`。兩單都要「覆蓋制」→ 這支是唯一實作。
   - omikuji 另需 `clearKyo`（REMOVE pendingKyo + 濾掉 `source==='omikuji' && delta<0`）。
2. **時間閘 helper `isOpen(facility, now)`** — 純比較台北小時對 `config.hours`（`sanpai:[9,17]`、`goshuin:[9,15]`）；**fail-safe：缺 hours → 全日開放**。omikuji 授與所預設全日、goshuin 受付 09–15。
3. **config 區塊**：`defaults.js` + `seed_shrine_config.js` 同時加 `omikuji{}`（HANDOFF-S3-omikuji §7）與 `goshuin{}`（S3-goshuin §4）+ `hours`。
4. **Shrine.js 面板**：兩系統各加設施操作鈕（授與所+「抽御神籤」、御朱印受付所+「蓋御朱印」「御朱印帳」），一起改一次 `facilityActionRow`/`handleAction`/handler 表。

---

## 2. 建議建置順序
1. **共用前置**（§1：replaceBuffsBySource / isOpen / config / 面板骨架）。
2. **御神籤**：ShrineOmikujiPoolDAO + `seed_omikuji_pool.js`（讀 `omikuji_pool.json` 33 筆）+ ShrineOmikujiService（draw/musubu）+ **ShrineLuck 加 pendingKyo drain（保既有 20 test 綠）** + 卡片。
3. **御朱印**：ShrineGoshuinDAO（SK=`goshuin#<YYYY-MM>` 條件寫入）+ ShrineGoshuinService（stamp/book）+ 卡片。
4. 各自 `node --test` 全綠 → **Opus 覆核** → 同步 `tools/jinja-shrine/impl-s3/` → **Codex 二驗**。

---

## 3. 殘留待定項（已鎖預設值，Codex 照做、後台可調，別卡）
- **御神籤凶籤比例＝21%**（`omikuji.weights` 現值；使用者留了「要不要 30%」但未拍板 → 先 21%，一行 config 可改）。
- **御神籤籤紙圖**：33 張在圖床**預覽路徑** `omikuji-preview/pool/<id>.png`。`omikuji.imageBaseUrl` 先指這、**上線前搬穩定路徑**（如 `shrine/omikuji/`）並改 config。
- **御朱印圖**：尚未生（Claude 另做，同御神籤程式合成管線）。Codex 先接 `goshuin.imageBaseUrl` config + placeholder，圖後補。
- **御朱印「季節×奧社」window**：待活動排程 → 先 `requireOkumiya:true` 不設 window（或整條先不放），不影響其他款。

---

## 4. 驗收共通
- 全 `PAY_PER_REQUEST`；**無 LLM／無付費 API → 免成本四件套**（兩單皆牙齒 sink）。
- givePoint 先查餘額再扣、失敗退款；config deep-merge fallback；Scan/Query 必分頁；不碰 PvP 勝率（§1.2 鐵律）。
- buff 全走 `fortune.buffs[]`（引擎 `computeLuck` 已會讀）；唯一引擎改動＝omikuji 的 pendingKyo drain（加法、保既有測試綠）。
