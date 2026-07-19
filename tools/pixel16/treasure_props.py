"""
pixel16 寶物道具組 —— 獎盃 / 鑰匙 / 王冠(精緻金屬 + 寶石)。

用 parts/metal.py 的 shade() 把任意輪廓上成金屬光影,gem() 點寶石。
先畫佔位輪廓('#')→ shade(ramp) → gem 點綴 → add_outline。
展示:精緻技法能套在不規則造型,且 shift_ramp 仍可換材質。
"""
import os
from engine16 import add_outline, overlay, blank, make_sheet, render, shift_ramp
from parts.metal import shade, gem

OUT = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT, exist_ok=True)
SZ = 30
F = "#"   # 佔位:任意非 '.' 字元,交給 shade 上色


def cv():
    return [["."] * SZ for _ in range(SZ)]


def gr(c):
    return ["".join(r) for r in c]


def hspan(c, y, x0, x1, ch=F):
    for x in range(x0, x1 + 1):
        if 0 <= y < SZ and 0 <= x < SZ:
            c[y][x] = ch


def disc(c, cxp, cyp, r, ch=F):
    for y in range(cyp - r, cyp + r + 1):
        for x in range(cxp - r, cxp + r + 1):
            if (x - cxp) ** 2 + (y - cyp) ** 2 <= r * r:
                if 0 <= y < SZ and 0 <= x < SZ:
                    c[y][x] = ch


def ring(c, cxp, cyp, ro, ri, ch=F):
    for y in range(cyp - ro, cyp + ro + 1):
        for x in range(cxp - ro, cxp + ro + 1):
            d = (x - cxp) ** 2 + (y - cyp) ** 2
            if ri * ri <= d <= ro * ro and 0 <= y < SZ and 0 <= x < SZ:
                c[y][x] = ch


# ── 獎盃 ─────────────────────────────────────────────────────
def trophy():
    c = cv()
    bowl = [(4, 7, 22), (5, 7, 22), (6, 8, 21), (7, 8, 21), (8, 9, 20),
            (9, 9, 20), (10, 10, 19), (11, 11, 18), (12, 12, 17), (13, 13, 16)]
    for y, a, b in bowl:
        hspan(c, y, a, b)
    ring(c, 6, 8, 4, 2)          # 左把手
    ring(c, 23, 8, 4, 2)         # 右把手
    for y in range(14, 18):      # 柄
        hspan(c, y, 14, 15)
    hspan(c, 18, 12, 17)         # 底座
    hspan(c, 19, 10, 19)
    hspan(c, 20, 9, 20)
    g = shade(gr(c), "gold", sheen=0.28)
    g = gem(g, 14, 9, 2, "coral")   # 盃面紅寶
    return g


# ── 鑰匙 ─────────────────────────────────────────────────────
def key():
    c = cv()
    ring(c, 15, 7, 6, 3)         # 匙頭環
    for y in range(12, 25):      # 匙桿
        hspan(c, y, 14, 16)
    hspan(c, 21, 17, 20)         # 匙齒
    hspan(c, 22, 17, 20)
    hspan(c, 24, 17, 19)
    g = shade(gr(c), "gold", sheen=0.30)
    g = gem(g, 15, 7, 2, "azure")   # 匙頭藍寶
    return g


# ── 王冠 ─────────────────────────────────────────────────────
def crown():
    c = cv()
    for y in range(18, 24):      # 冠帶
        hspan(c, y, 6, 25)
    tips = [(7, 12), (11, 9), (16, 6), (21, 9), (25, 12)]   # 五尖(中最高)
    for xt, yt in tips:
        for y in range(yt, 19):
            half = round(2.6 * (y - yt) / (18 - yt))
            hspan(c, y, xt - half, xt + half)
    g = shade(gr(c), "gold", sheen=0.30)
    gem_ramp = ["coral", "azure", "mint", "coral", "azure"]  # 尖端寶石
    for (xt, yt), rp in zip(tips, gem_ramp):
        g = gem(g, xt, yt + 1, 1, rp)
    for gx in range(9, 24, 4):   # 冠帶寶石列
        g = gem(g, gx, 21, 1, "mint")
    return g


def build():
    props = [("trophy", trophy()), ("key", key()), ("crown", crown())]
    frames = []
    for name, g in props:
        out = add_outline(g, diagonal=True)
        render(out, scale=12, path=os.path.join(OUT, "prop_%s.png" % name))
        frames.append(add_outline(overlay(blank(SZ, SZ), g, 0, 0), diagonal=True))
    sheet = make_sheet(frames, cols=3, gap=3)
    render(sheet, scale=9, path=os.path.join(OUT, "props_sheet.png"))
    print("寫出: prop_{trophy,key,crown}.png + props_sheet.png")


if __name__ == "__main__":
    build()
