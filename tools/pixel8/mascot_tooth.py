"""牙齒吉祥物 🦷 — 用 pixel8 元件庫「組裝」而非「重畫」。

流程展示複利:只畫左半 → mirror_h 鏡射 → add_outline 自動描邊 → 底模;
再 recolor 秒出配色變體、overlay 疊零件、make_sheet 拼精靈表。
字元:. 透明  0 描邊  c 牙白  3 腮紅  4 黃(金)  b 青(薄荷)
"""
import os
from engine import mirror_h, add_outline, recolor, overlay, make_sheet, render

# 只畫「左半 8 欄」的填色(不含外描邊,描邊交給程式)。對稱物件工作量減半。
TOOTH_HALF = [
    "........",  # 0
    "...ccccc",  # 1  牙冠
    "..cccccc",  # 2
    ".ccccccc",  # 3
    ".ccccccc",  # 4
    ".ccc00cc",  # 5  眼
    ".ccc00cc",  # 6
    ".ccccccc",  # 7
    ".cc3cccc",  # 8  腮紅
    ".cccc0cc",  # 9  嘴角
    ".ccccc00",  # 10 嘴底
    ".ccccccc",  # 11
    "..cccc..",  # 12 牙根
    "..ccc...",  # 13
    "...cc...",  # 14
    "........",  # 15
]

# ── 組裝管線:鏡射 → 自動描邊 = 底模 ──────────────────────────
BASE = add_outline(mirror_h(TOOTH_HALF))

# ── 換色:一個底模 → 多款同風格變體(秒出、風格自動統一)──────────
GOLD = recolor(BASE, {"c": "4"})   # 金牙
MINT = recolor(BASE, {"c": "b"})   # 薄荷牙

# ── 疊圖組裝:加一顆閃光零件(示範「換帽子/道具」式拼裝)──────────
SPARKLE = [
    ".4.",
    "404",
    ".4.",
]
BLING = overlay(GOLD, SPARKLE, ox=10, oy=2)

# ── 精靈表:四款變體拼一張(= 批次匯出 / 動畫幀基礎)──────────────
SHEET = make_sheet([BASE, GOLD, MINT, BLING], cols=4, gap=1)

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "out")
    os.makedirs(out, exist_ok=True)
    render(BASE,  scale=16, path=os.path.join(out, "tooth_base.png"))
    render(GOLD,  scale=16, path=os.path.join(out, "tooth_gold.png"))
    render(MINT,  scale=16, path=os.path.join(out, "tooth_mint.png"))
    render(BLING, scale=16, path=os.path.join(out, "tooth_bling.png"))
    render(SHEET, scale=12, path=os.path.join(out, "tooth_sheet.png"))
    print("done:", out)
