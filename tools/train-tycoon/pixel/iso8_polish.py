#!/usr/bin/env python3
# 火車大亨 iso 像素 — polish 版:三面明暗 + 黑描邊(cel outline) + 乾淨鐵軌 + 地磚格線。
# 承 proof(iso8.py):幾何對齊已證,這裡補「好看」= 描邊/陰影/紋理(參考麻將桌 iso)。
# pixel8 精神:程式擺像素、鎖 SWEETIE-16、渲染後 Read 看、不對就改。
import sys, os, math
sys.path.insert(0, '/opt/sml/repo/tools/pixel8')
from engine import PALETTE, render

# ⚠ LEGACY/PROOF:早期驗證檔,非統一角度正典(正典=iso_cars16/loco/couple/web,TW/TH=28/14)。
TW, TH = 32, 16          # iso tile 2:1(legacy 32/16)
HZ = TH                  # 每 1 格高 = 一個 tile 高

def screen(gc, gr):
    return (gc - gr) * (TW / 2), (gc + gr) * (TH / 2)

def fill_poly(rows, pts, ch):
    H, W = len(rows), len(rows[0])
    ys = [p[1] for p in pts]
    for y in range(max(0, int(math.floor(min(ys)))), min(H, int(math.ceil(max(ys))) + 1)):
        yc = y + 0.5
        xs = []
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
            if (y1 <= yc < y2) or (y2 <= yc < y1):
                xs.append(x1 + (yc - y1) / (y2 - y1) * (x2 - x1))
        xs.sort()
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
        if 0 <= y0 < H and 0 <= x0 < W:
            rows[y0][x0] = ch
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy: err -= dy; x0 += sx
        if e2 < dx:  err += dx; y0 += sy

def dither(rows, pts, ch, step=2):
    # 在多邊形內灑點狀高光 → 表面紋理(仿麻將桌面 dither)
    H, W = len(rows), len(rows[0])
    ys = [p[1] for p in pts]
    for y in range(max(0, int(math.floor(min(ys)))), min(H, int(math.ceil(max(ys))) + 1)):
        yc = y + 0.5
        xs = []
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
            if (y1 <= yc < y2) or (y2 <= yc < y1):
                xs.append(x1 + (yc - y1) / (y2 - y1) * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(round(xs[k]))), min(W, int(round(xs[k + 1])))):
                if (x + y) % step == 0 and (x * 3 + y) % 3 == 0:
                    rows[y][x] = ch

def tile_poly(px, py):
    # 菱形四角 top,right,bottom,left(以格子左頂點 px,py 為基準)
    return [(px + TW / 2, py), (px + TW, py + TH / 2), (px + TW / 2, py + TH), (px, py + TH / 2)]

def render_scene():
    CW, CH = 182, 132
    ox, oy = 54, 44
    rows = [list('.' * CW) for _ in range(CH)]

    def lt(gc, gr):           # 格子左頂點(螢幕)
        x, y = screen(gc, gr); return x + ox, y + oy

    # ── 地面 5×4:雙色草地 + 每格淺格線,r=2 為道床 ──
    order = sorted([(c, r) for r in range(4) for c in range(5)], key=lambda t: t[0] + t[1])
    for c, r in order:
        px, py = lt(c, r)
        poly = tile_poly(px, py)
        if r == 2:
            fill_poly(rows, poly, 'f')        # 道床底(深灰礫石)
            dither(rows, poly, 'e', step=2)   # 礫石顆粒
        else:
            base = '6' if (c + r) % 2 else '5'
            fill_poly(rows, poly, base)
            dither(rows, poly, '5' if base == '6' else '6', step=3)  # 草地雜色
        # 格線:菱形四邊用比草稍深的線,讓每格看得出來
        edge = 'f' if r == 2 else '7'
        for i in range(4):
            line(rows, poly[i], poly[(i + 1) % 4], edge)

    # ── 立體塊:三面明暗 + 黑描邊 + 可選開窗 ──
    def box(gc, gr, fx, fy, h, ctop, cleft, cright, window=None, wrow=0.5, z0=0.0):
        def g(c, r, z):
            x, y = screen(c, r); return (x + ox, y + oy - z * HZ)
        z1 = z0 + h
        # 8 角(底面在 z0、頂面在 z1)
        b10, b11, b01 = g(gc + fx, gr, z0), g(gc + fx, gr + fy, z0), g(gc, gr + fy, z0)
        t00, t10, t11, t01 = g(gc, gr, z1), g(gc + fx, gr, z1), g(gc + fx, gr + fy, z1), g(gc, gr + fy, z1)
        rface = [b10, b11, t11, t10]   # 右前面(受光最少 → 最暗)
        lface = [b01, b11, t11, t01]   # 左前面(中間調)
        tface = [t00, t10, t11, t01]   # 頂面(最亮)
        fill_poly(rows, rface, cright)
        fill_poly(rows, lface, cleft)
        fill_poly(rows, tface, ctop)
        # 頂面沿受光邊補一條高光
        line(rows, t00, t10, ctop)
        # 開窗(左前面一排)
        if window:
            n_win = max(1, int(fx))
            for t in range(1, n_win + 1):
                f = t / (n_win + 1)
                wx = b01[0] + (b11[0] - b01[0]) * f
                wy = b01[1] + (b11[1] - b01[1]) * f
                for k in range(3):
                    yy = int(wy - (h * HZ * wrow) - k * 3)
                    xx = int(wx)
                    for dxx in (0, 1):
                        if 0 <= yy < CH and 0 <= xx + dxx < CW:
                            rows[yy][xx + dxx] = window
        # 黑描邊:頂面四邊 + 三條可見垂直棱 + 前底兩邊
        ink = '0'
        for a, b in [(t00, t10), (t10, t11), (t11, t01), (t01, t00)]:
            line(rows, a, b, ink)
        line(rows, t10, b10, ink); line(rows, t11, b11, ink); line(rows, t01, b01, ink)
        line(rows, b10, b11, ink); line(rows, b11, b01, ink)

    # 站房(r=0,後方先畫)：灰牆 + 疊在牆頂的紅屋頂
    box(2, 0.4, 1.9, 1.1, 1.0, ctop='d', cleft='c', cright='e', window='a')      # 牆體(灰白,開窗)
    box(1.85, 0.28, 2.2, 1.35, 0.34, ctop='2', cleft='2', cright='1', z0=1.0)    # 紅屋頂(墊高、微出簷)

    # ── 鐵軌(r=2 中心線)：枕木(深) → 兩鋼軌(亮) ──
    def cline(gr, c0=0.35, c1=4.65):
        ax, ay = screen(c0, gr); bx, by = screen(c1, gr)
        return (ox + ax + TW / 2, oy + ay + TH / 2), (ox + bx + TW / 2, oy + by + TH / 2)
    (ax, ay), (bx, by) = cline(2)
    L = int(math.hypot(bx - ax, by - ay))
    for i in range(0, L, 6):                       # 枕木:沿 r 軸的短段,均勻
        f = i / L
        cx, cy = ax + (bx - ax) * f, ay + (by - ay) * f
        for k in range(-5, 6):
            xx, yy = int(cx - k), int(cy + k * 0.5)
            if 0 <= yy < CH and 0 <= xx < CW: rows[yy][xx] = '0'
    for rr, hi in ((1.78, False), (2.22, False)):  # 兩鋼軌:主體亮灰 + 上緣白高光
        (px0, py0), (px1, py1) = cline(rr)
        for i in range(L):
            f = i / L
            xx = int(px0 + (px1 - px0) * f); yy = int(py0 + (py1 - py0) * f)
            if 0 <= yy < CH and 0 <= xx < CW:
                rows[yy][xx] = 'd'
                if 0 <= yy - 1 < CH: rows[yy - 1][xx] = 'c'

    # 火車(r=2,前方後畫,坐在鋼軌上):車身 + 前端駕駛室
    box(1.0, 1.78, 2.5, 0.44, 0.5, ctop='a', cleft='9', cright='8', window='b', wrow=0.5)   # 車身(藍)
    box(3.5, 1.78, 0.7, 0.44, 0.7, ctop='4', cleft='3', cright='2')                          # 駕駛室(前端、較高)

    grid = [''.join(r) for r in rows]
    out = '/opt/sml/repo/tools/train-tycoon/pixel/out'
    os.makedirs(out, exist_ok=True)
    render(grid, 5, out + '/proof_polish.png')
    print('ok proof_polish.png', CW, CH)

if __name__ == '__main__':
    render_scene()
