"""
火車大亨 🚂 16-bit 貨運道具組 —— pixel16 首個實戰資產。

展示飛輪:通用形狀(bar/drum)沉澱進 parts/shapes.py,這裡「拼裝」成一組貨物。
- 金錠 / 鋼錠:同一支 bar() 畫一次,shift_ramp 換材質(gold↔steel)= 兩種礦石秒出。
- 鐵桶:drum() 直接用。
- 煤炭 / 木箱:本檔手工形狀(之後若再用就上抽 parts/)。
產物 out/cargo_*.png + cargo_sheet.png(不入庫)。
"""
import os
from engine16 import (
    add_outline, overlay, make_sheet, render, shift_ramp, RAMPS, blank,
)
from parts.shapes import bar, drum

OUT = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT, exist_ok=True)


def _canvas(w, h):
    return [["."] * w for _ in range(h)]


def _grid(c):
    return ["".join(r) for r in c]


def _pad(g, w, h, ox, oy):
    """把小網格 g 貼到 w×h 透明畫布的 (ox,oy)。"""
    return overlay(blank(w, h), g, ox, oy)


# ── 金錠堆(bar 拼三顆金字塔)──────────────────────────────────
def ingot_stack(ramp="gold"):
    b = bar(ramp, w=16, h=7)
    c = blank(26, 24)
    c = overlay(c, b, 1, 14)     # 底左
    c = overlay(c, b, 9, 14)     # 底右
    c = overlay(c, b, 5, 7)      # 頂中
    return c


# ── 煤炭堆(手工:深色礦堆 + 碎塊刻面)──────────────────────────
def coal_pile():
    S = RAMPS["steel"]  # 0..5 暗→亮(藍灰,當煤炭很搭)
    W, H = 28, 22
    c = _canvas(W, H)
    cx = 13
    for y in range(7, H):
        hw = min(13, 2 + (y - 7))
        for x in range(cx - hw, cx + hw + 1):
            if 0 <= x < W:
                c[y][x] = S[1] if (y + x) % 3 else S[2]   # 主體暗、微刻面
    # 碎塊高光(左上受光)與深縫
    facets = [(9, 11, S[4]), (16, 12, S[3]), (12, 15, S[4]),
              (19, 16, S[3]), (7, 17, S[3]), (22, 19, S[2]), (14, 19, S[4])]
    for fx, fy, hi in facets:
        for dx, dy, ch in [(0, 0, hi), (1, 0, S[2]), (0, 1, S[2]),
                           (-1, 0, S[1]), (0, -1, S[5])]:
            x, y = fx + dx, fy + dy
            if 0 <= x < W and 8 <= y < H:
                c[y][x] = ch
    return _grid(c)


# ── 木箱(手工:框 + 直板 + X 撐)──────────────────────────────
def wood_crate():
    x0, y0, x1, y1 = 4, 4, 19, 20     # 前面正方
    W, H = 24, 24
    c = _canvas(W, H)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            c[y][x] = "y"                          # 木面主色
    for x in range(x0, x1 + 1):                    # 上下框
        c[y0][x] = c[y0 + 1][x] = "z"
        c[y1][x] = c[y1 - 1][x] = "x"
    for y in range(y0, y1 + 1):                    # 左右柱
        c[y][x0] = c[y][x0 + 1] = "z"
        c[y][x1] = c[y][x1 - 1] = "x"
    for y in range(y0 + 2, y1 - 1):                # X 對角撐(受光板)
        f = (y - y0) / (y1 - y0)
        xa = round(x0 + 2 + f * (x1 - x0 - 4))
        xb = round(x1 - 2 - f * (x1 - x0 - 4))
        for xx in (xa, xa + 1, xb, xb - 1):
            if x0 < xx < x1:
                c[y][xx] = "z"
    return _grid(c)


def _finish(name, g, scale=10):
    g = add_outline(g, diagonal=True)
    render(g, scale=scale, path=os.path.join(OUT, "cargo_%s.png" % name))
    return g


def build():
    gold = ingot_stack("gold")
    steel = shift_ramp(ingot_stack("gold"), "gold", "steel")   # 同形狀→鋼錠
    barrel = _pad(drum("steel", band="gold", w=16, h=20), 22, 24, 3, 2)
    coal = coal_pile()
    crate = wood_crate()

    icons = {
        "coal": coal, "gold": gold, "steel": steel,
        "barrel": barrel, "crate": crate,
    }
    finished = {k: _finish(k, v) for k, v in icons.items()}

    # 統一成同尺寸(28×24)排精靈表
    order = ["coal", "gold", "steel", "barrel", "crate"]
    frames = []
    for k in order:
        g = icons[k]
        w, h = len(g[0]), len(g)
        canvas = blank(28, 24)
        g2 = add_outline(overlay(canvas, g, (28 - w) // 2, (24 - h)), diagonal=True)
        frames.append(g2)
    sheet = make_sheet(frames, cols=5, gap=2)
    render(sheet, scale=8, path=os.path.join(OUT, "cargo_sheet.png"))
    print("寫出:", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    build()
