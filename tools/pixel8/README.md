# pixel8 — 8-bit 設計系統

大量 Discord 遊戲共用的**統一 8bit 風格**產線。核心哲學:**不「生成」圖,用程式「組裝」圖**。
擴散生圖(Bedrock)做不好真低解析像素(糊邊、格線不齊、每張風格漂移);這裡用確定性程式擺像素 → 秒出、像素精準、跨遊戲天生同風格,而且**跨專案複利**(第二款遊戲用拼裝而非重畫)。

## 概念
- **調色盤鎖定**:全系統共用 `SWEETIE-16`(16 色)。風格統一的源頭。
- **sprite = 字元網格** `list[str]`,每格一個調色盤字元,`.` = 透明。
- **新資產 = 鏡射 + 描邊 + 換色 + 疊圖**,不重畫。

## 元件庫 API(`engine.py`)
| 函式 | 作用 | 複利點 |
|---|---|---|
| `mirror_h(left)` | 左半 → 完整對稱圖 | 對稱物件只畫一半 |
| `add_outline(g)` | 自動描邊 | 只畫填色,邊線粗細/顏色全系統一致 |
| `recolor(g, {'c':'4'})` | 換色 | 一個底模 → 無限同風格配色變體 |
| `overlay(base, top, x, y)` | 疊圖 | 底模 + 換帽子/道具/表情零件 |
| `flip_h` / `flip_v` | 翻轉 | 面向左右/上下 |
| `make_sheet(frames, cols, gap)` | 拼精靈表 | 動畫幀 / 批次匯出 |
| `render(g, scale, path)` | 網格 → PNG | 最近鄰放大保硬邊 |

## 範例
`mascot_tooth.py` = 牙齒吉祥物 🦷(全遊戲共用貨幣,當風格錨)。
只手畫左半 8 欄 → `mirror_h` → `add_outline` = 底模;再 `recolor` 出金牙/薄荷、`overlay` 加閃光、`make_sheet` 拼表。
```
python3 mascot_tooth.py   # 產物在 out/
```

## 做新遊戲資產的流程
1. 開新檔 `<遊戲>_<物件>.py`,`from engine import ...`。
2. 手畫填色網格(對稱物件只畫左半)。
3. `add_outline` → 底模;需要變體就 `recolor`;需要零件就 `overlay`。
4. `render` 出圖;要上 Discord 就接 `tools/emoji/upload.js` 金庫管線。

## 飛輪(越做越快)
把成功的 sprite 網格 + 產生它的程式存進 `parts/`,下次當 few-shot 範例餵回。
角色底模 / 描邊風格 / 常用零件累積成庫 → 第二款遊戲拼裝,以秒計。

## 為何暫不用 Aseprite
Aseprite 只是畫布+匯出,畫圖智能仍是「Claude 擺像素」,跟本系統同源;ARM 主機要自編 Skia。
**只有等要大量逐幀動畫 / tilemap 關卡圖才值得升級**(那是它主場)。目前 icon/sprite/emoji/UI 純程式完全吃得下。
