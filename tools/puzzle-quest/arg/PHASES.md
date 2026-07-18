# ARG 兔子洞 — 未完成任務拆解（每階段交 Codex 驗）

> 引擎與 50 頁世界圖已建好、我方自審全通過（`python3 audit.py`）。以下把「剩下的事」切成有
> Codex 驗收關卡的階段。分工：**Fable5 子代理＝寫／擴內容**，**我＝整合＋自審＋出 VERIFY 單**，
> **Codex＝每階段獨立複驗**（逐條對照該階段 VERIFY 單）。一階段驗過才進下一階段。

| 階段 | 內容 | 誰做 | Codex 驗收單 | 狀態 |
|---|---|---|---|---|
| **A** | ARG 產生器引擎正確性 | 我（已自審） | `VERIFY-engine.md` | ✅ 自審過 → **待 Codex** |
| **B** | 埋深／keystone 洩漏稽核 | 我（已自審） | `VERIFY-depth.md` | ✅ 自審過 → **待 Codex** |
| **C** | ~40 氛圍／紅鯡魚節點內容加厚 | Fable5×N 平行 → 我合併校時間軸 | `VERIFY-content.md`（產出時寫） | ⬜ 未開始 |
| **D** | 動線／可玩性（BFS 連通、階段節奏、手機檢視原始檔） | 我 Playwright 實測 | `VERIFY-flow.md`（產出時寫） | ⬜ 未開始 |
| **E** | 埋深機制沉澱進 `DESIGN_DIRECTION.md §9` | 我 | Codex 覆核與 §1–8 不衝突 | ⬜ 未開始 |
| **F** | 部署圖床 `pq/case13/` ＋ 接線 case JSON | 我（**對外，先確認**） | 部署前檢查清單 | ⬜ 未開始 |
| **G** | 原案素材補齊（3 頁筆記本實拍＋3 段語音） | 使用者側 | — | ⬜ 非 blocking |

## 相依關係
- A、B 可並行交 Codex（各自獨立）。
- C 依賴 A/B 過（不然內容改了要重驗埋深）；C 完成後 B 要**回歸重跑**（新內容可能洩漏 keystone）。
- D 依賴 C（內容定稿才測動線）。
- E 可隨時做（純文件），但建議 A–D 定案後再沉澱，免規範追著改。
- F 依賴 A–D 全過（上線品質門檻）。
- G 與 A–F 解耦，缺了 panel 會優雅略過。

## Codex 驗收怎麼跑
每階段的 `VERIFY-*.md` 都內含①我方自審結果（audit.py 輸出）②Codex 要逐條獨立確認的清單③已知風險點。
把該檔＋對應程式碼交 Codex，請它**獨立重跑稽核、逐條回 pass/fail＋findings**。findings 收斂後該階段才算過。

## 快速指令
```bash
cd tools/puzzle-quest/arg
python3 build.py mingyan-world.json   # 重建(自動清舊檔)
python3 audit.py                      # 自動稽核(A+B),全綠才交Codex
```
