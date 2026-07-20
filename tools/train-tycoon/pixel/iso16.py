#!/usr/bin/env python3
# 火車大亨 iso 像素 — 16bit 版(pixel16)。
# 承 iso8_polish.py 的幾何(格子對齊已證),但改用 pixel16:
#   - PALETTE16 多階漸層盤 + 具名 ramp(steel/enamel/coral/azure/gold/mint)。
#   - 每個面沿 ramp 上「垂直漸層」(頂面亮、左面亮→中、右面中→暗)+ 頂緣鏡面高光。
#   → 8bit 是平塗色塊,16bit 是有份量的明暗梯度、金屬反光。
import sys, os, math
sys.path.insert(0, '/opt/sml/repo/tools/pixel16')
from engine16 import PALETTE16, RAMPS, render

# ⚠ LEGACY/PROOF:早期 16bit 驗證檔,非統一角度正典(正典=iso_cars16/loco/couple/web,TW/TH=28/14)。
TW, TH = 32, 16          # (legacy 32/16)
HZ = TH

def screen(gc, gr):
    return (gc - gr) * (TW / 2), (gc + gr) * (TH / 2)

def _spans(pts, y):
    yc = y + 0.5
    xs = []
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        if (y1 <= yc < y2) or (y2 <= yc < y1):
            xs.append(x1 + (yc - y1) / (y2 - y1) * (x2 - x1))
    xs.sort()
    return xs

def fill_poly(rows, pts, ch):
    H, W = len(rows), len(rows[0])
    ys = [p[1] for p in pts]
    for y in range(max(0, int(math.floor(min(ys)))), min(H, int(math.ceil(max(ys))) + 1)):
        xs = _spans(pts, y)
        for k in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(round(xs[k]))), min(W, int(round(xs[k + 1])))):
                rows[y][x] = ch

def fill_grad(rows, pts, ramp_chars):
    """沿多邊形 y 範圍上垂直漸層:ramp_chars[0]=最上(亮)…[-1]=最下(暗)。"""
    H, W = len(rows), len(rows[0])
    ys = [p[1] for p in pts]
    y0, y1 = int(math.floor(min(ys))), int(math.ceil(max(ys)))
    span = max(1, y1 - y0)
    for y in range(max(0, y0), min(H, y1 + 1)):
        f = (y - y0) / span
        ch = ramp_chars[min(len(ramp_chars) - 1, int(f * len(ramp_chars)))]
        xs = _spans(pts, y)
        for k in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(round(xs[k]))), min(W, int(round(xs[k + 1])))):
                rows[y][x] = ch

def line(rows, p0, p1, ch):
    H, W = len(rows), len(rows[0])
    x0, y0 = int(round(p0[0])), int(round(p0[1]))
    x1, y1 = int(round(p1[0])), int(round(p1[1]))
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        if 0 <= y0 < H and 0 <= x0 < W: rows[y0][x0] = ch
        if x0 == x1 and y0 == y1: break
        e2 = 2 * err
        if e2 > -dy: err -= dy; x0 += sx
        if e2 < dx:  err += dx; y0 += sy

def tile_poly(px, py):
    return [(px + TW / 2, py), (px + TW, py + TH / 2), (px + TW / 2, py + TH), (px, py + TH / 2)]

def render_scene():
    CW, CH = 182, 132
    ox, oy = 54, 44
    rows = [list('.' * CW) for _ in range(CH)]

    def lt(gc, gr):
        x, y = screen(gc, gr); return x + ox, y + oy

    mint = RAMPS['mint']      # fghi 暗→亮
    steel = RAMPS['steel']    # 012345

    # ── 地面 5×4:草地(mint 兩階棋盤 + dither)、r=2 道床(steel 暗) ──
    order = sorted([(c, r) for r in range(4) for c in range(5)], key=lambda t: t[0] + t[1])
    for c, r in order:
        px, py = lt(c, r)
        poly = tile_poly(px, py)
        if r == 2:
            fill_poly(rows, poly, steel[1])            # 道床底
            # 礫石顆粒(亮暗兩色點)
            _dither(rows, poly, steel[2], steel[0])
        else:
            base = mint[2] if (c + r) % 2 else mint[1]  # 兩階綠棋盤
            fill_poly(rows, poly, base)
            up = mint[3] if base == mint[2] else mint[2]  # 只提亮一階,低對比
            _dither(rows, poly, up, base, step=4)         # 稀疏草點
        edge = steel[0] if r == 2 else mint[0]
        for i in range(4):
            line(rows, poly[i], poly[(i + 1) % 4], edge)

    # ── 立體塊:三面沿 ramp 上漸層 + 頂緣鏡面高光 + 黑描邊 ──
    def box(gc, gr, fx, fy, h, ramp, window=None, wrow=0.5, z0=0.0):
        R = RAMPS[ramp]
        lo, mid, hi = R[0], R[len(R) // 2], R[-1]
        def g(c, r, z):
            x, y = screen(c, r); return (x + ox, y + oy - z * HZ)
        z1 = z0 + h
        b10, b11, b01 = g(gc + fx, gr, z0), g(gc + fx, gr + fy, z0), g(gc, gr + fy, z0)
        t00, t10, t11, t01 = g(gc, gr, z1), g(gc + fx, gr, z1), g(gc + fx, gr + fy, z1), g(gc, gr + fy, z1)
        rface = [b10, b11, t11, t10]   # 右前(最暗)
        lface = [b01, b11, t11, t01]   # 左前(中)
        tface = [t00, t10, t11, t01]   # 頂(最亮)
        # 右面:中→暗漸層;左面:亮→中漸層;頂面:近全亮微層
        fill_grad(rows, rface, [R[max(0, len(R)-2)], mid, lo])
        fill_grad(rows, lface, [hi, R[max(0, len(R)-2)], mid])
        fill_grad(rows, tface, [hi, hi, R[max(0, len(R)-2)]])
        # 頂受光棱鏡面高光(用鋼盤最亮或自身最亮)
        line(rows, t00, t10, hi)
        line(rows, t00, t01, hi)
        # 開窗(左前面一排,用青色玻璃)
        if window:
            n_win = max(1, int(fx))
            for t in range(1, n_win + 1):
                f = t / (n_win + 1)
                wx = b01[0] + (b11[0] - b01[0]) * f
                wy = b01[1] + (b11[1] - b01[1]) * f
                for k in range(3):
                    yy = int(wy - (h * HZ * wrow) - k * 3); xx = int(wx)
                    for dxx in (0, 1):
                        if 0 <= yy < CH and 0 <= xx + dxx < CW:
                            rows[yy][xx + dxx] = window
        # 黑描邊
        ink = '0'
        for a, b in [(t00, t10), (t10, t11), (t11, t01), (t01, t00)]:
            line(rows, a, b, ink)
        line(rows, t10, b10, ink); line(rows, t11, b11, ink); line(rows, t01, b01, ink)
        line(rows, b10, b11, ink); line(rows, b11, b01, ink)

    # 站房:琺瑯白牆(開青窗) + 珊瑚紅屋頂(墊高出簷)
    box(2, 0.4, 1.9, 1.1, 1.0, 'enamel', window='p')
    box(1.85, 0.28, 2.2, 1.35, 0.34, 'coral', z0=1.0)

    # ── 鐵軌:枕木(木紋暗) + 兩鋼軌(steel 亮 + 鏡面高光) ──
    def cline(gr, c0=0.35, c1=4.65):
        ax, ay = screen(c0, gr); bx, by = screen(c1, gr)
        return (ox + ax + TW / 2, oy + ay + TH / 2), (ox + bx + TW / 2, oy + by + TH / 2)
    (ax, ay), (bx, by) = cline(2)
    L = int(math.hypot(bx - ax, by - ay))
    wood = RAMPS['wood']
    for i in range(0, L, 6):
        f = i / L; cx, cy = ax + (bx - ax) * f, ay + (by - ay) * f
        for k in range(-5, 6):
            xx, yy = int(cx - k), int(cy + k * 0.5)
            if 0 <= yy < CH and 0 <= xx < CW:
                rows[yy][xx] = wood[0] if k % 3 else wood[1]
    for rr in (1.78, 2.22):
        (px0, py0), (px1, py1) = cline(rr)
        for i in range(L):
            f = i / L
            xx = int(px0 + (px1 - px0) * f); yy = int(py0 + (py1 - py0) * f)
            if 0 <= yy < CH and 0 <= xx < CW:
                rows[yy][xx] = steel[4]                 # 鋼軌主體亮灰
                if 0 <= yy - 1 < CH: rows[yy - 1][xx] = steel[5]  # 鏡面高光

    # 火車:天藍車身(青窗) + 金色駕駛室
    box(1.0, 1.78, 2.5, 0.44, 0.5, 'azure', window='q', wrow=0.5)
    box(3.5, 1.78, 0.7, 0.44, 0.7, 'gold')

    grid = [''.join(r) for r in rows]
    out = '/opt/sml/repo/tools/train-tycoon/pixel/out'
    os.makedirs(out, exist_ok=True)
    render(grid, 5, out + '/proof16.png')
    print('ok proof16.png', CW, CH)

def _dither(rows, pts, ch, bg, step=2):
    H, W = len(rows), len(rows[0])
    ys = [p[1] for p in pts]
    for y in range(max(0, int(math.floor(min(ys)))), min(H, int(math.ceil(max(ys))) + 1)):
        xs = _spans(pts, y)
        for k in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(round(xs[k]))), min(W, int(round(xs[k + 1])))):
                if (x + y) % step == 0 and (x * 3 + y) % 3 == 0:
                    rows[y][x] = ch

if __name__ == '__main__':
    render_scene()
