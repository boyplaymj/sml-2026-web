#!/usr/bin/env python3
# 火車大亨 iso 像素引擎 — pixel8 精神:程式一格一格擺像素、鎖 SWEETIE-16、格子精確對齊。
# 對照 proof:證明「程式畫 iso」組合起來格子完美貼合(擴散生圖做不到)。
# 用法: python3 iso8.py  → out/proof.png
import sys, os, math
sys.path.insert(0, '/opt/sml/repo/tools/pixel8')
from engine import PALETTE, render, blank  # 共用鎖定調色盤 + 渲染

TW, TH = 32, 16          # iso tile 2:1(像素)
HZ = TH                  # 每 1 格高 = 一個 tile 高

def screen(gc, gr, z=0.0):
    return (gc - gr) * (TW / 2), (gc + gr) * (TH / 2) - z * HZ

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

def diamond(gc, gr, ox, oy, top):
    x, y = screen(gc, gr); x += ox; y += oy
    return [(x, y + TH / 2), (x + TW / 2, y), (x + TW, y + TH / 2), (x + TW / 2, y + TH)]
    # 註:screen 回傳為 tile 左角? 這裡用左上角基準,見 place_tile

# 用「格子左頂點」為基準的菱形四角(top,right,bottom,left)
def tile_poly(px, py):
    return [(px + TW / 2, py), (px + TW, py + TH / 2), (px + TW / 2, py + TH), (px, py + TH / 2)]

def box_polys(gc, gr, fx, fy, h, ox, oy):
    # 立體塊三面(右前、左前、頂),回 [(pts,ch)...] 已含 z 提升 h
    def g(c, r, z):
        x, y = screen(c, r); return (x + ox, y + oy - z * HZ)
    b10, b11, b01 = g(gc + fx, gr, 0), g(gc + fx, gr + fy, 0), g(gc, gr + fy, 0)
    t00, t10, t11, t01 = g(gc, gr, h), g(gc + fx, gr, h), g(gc + fx, gr + fy, h), g(gc, gr + fy, h)
    return [b10, b11, t11, t10], [b01, b11, t11, t01], [t00, t10, t11, t01]

def render_scene():
    CW, CH = 260, 210
    ox, oy = 120, 30            # 讓所有座標為正
    rows = [list('.' * CW) for _ in range(CH)]

    # ── 地面 5×4 草地(雙色格紋)+ 軌道列 r=2 ──
    def tile_left_top(gc, gr):
        x, y = screen(gc, gr); return x + ox, y + oy
    order = sorted([(c, r) for r in range(4) for c in range(5)], key=lambda t: t[0] + t[1])
    for c, r in order:
        px, py = tile_left_top(c, r)
        if r == 2:                      # 軌道列 = 碎石道床色
            fill_poly(rows, tile_poly(px, py), 'f')
        else:
            fill_poly(rows, tile_poly(px, py), '6' if (c + r) % 2 else '5')

    # 立體塊繪製器(先定義,好按深度 back→front 依序畫)
    def draw_box(gc, gr, fx, fy, h, ctop, cleft, cright, window=None):
        r_p, l_p, t_p = box_polys(gc, gr, fx, fy, h, ox, oy)
        fill_poly(rows, r_p, cright)
        fill_poly(rows, l_p, cleft)
        fill_poly(rows, t_p, ctop)
        if window:
            x, y = screen(gc, gr + fy); x += ox; y += oy
            x2, y2 = screen(gc + fx, gr + fy); x2 += ox; y2 += oy
            for t in range(2, fx * 8 - 2):
                f = t / (fx * 8.0)
                cx = x + (x2 - x) * f; cy = y + (y2 - y) * f - h * HZ * 0.55
                for wy in range(-2, 2):
                    yy, xx = int(cy + wy), int(cx)
                    if 0 <= yy < CH and 0 <= xx < CW and t % 4 != 0: rows[yy][xx] = window

    # ── 站房(r=0,最後方 → 先畫,會被前方火車正確遮擋)──
    draw_box(2, 0, 2, 1, 0.9, ctop='4', cleft='3', cright='2')
    draw_box(2, 0, 2, 1, 0.95, ctop='2', cleft='2', cright='1')  # 屋頂帶

    # ── 鐵軌:沿 r=2 中心線,枕木(先)+兩條鋼軌(後),全用格子座標→精確對齊 ──
    def cline(gr):   # r=gr 這條線在 tile 中心的兩端點(螢幕)
        ax, ay = screen(0, gr); bx, by = screen(5, gr)
        return (ox + ax + TW / 2, oy + ay + TH / 2), (ox + bx + TW / 2, oy + by + TH / 2)
    (ax, ay), (bx, by) = cline(2)
    L = int(math.hypot(bx - ax, by - ay))
    # 枕木:沿中心線每隔幾像素畫一根(沿 r 軸方向的短段)
    for i in range(0, L, 5):
        f = i / L
        cx, cy = ax + (bx - ax) * f, ay + (by - ay) * f
        for k in range(-5, 6):                        # 枕木沿 r 軸(螢幕 (−TW/2,+TH/2) 方向)
            xx, yy = int(cx - k), int(cy + k * 0.5)
            if 0 <= yy < CH and 0 <= xx < CW: rows[yy][xx] = 'f'
    # 兩條鋼軌:r=1.78 / r=2.22 各一條白線
    for rr in (1.80, 2.20):
        (px0, py0), (px1, py1) = cline(rr)
        for i in range(L):
            f = i / L
            xx, yy = int(px0 + (px1 - px0) * f), int(py0 + (py1 - py0) * f)
            if 0 <= yy < CH and 0 <= xx < CW: rows[yy][xx] = 'c'

    # ── 火車(r=2,前方 → 後畫,坐在剛畫好的鐵軌上)──
    draw_box(1, 2, 3, 1, 0.55, ctop='3', cleft='2', cright='1', window='b')

    grid = [''.join(r) for r in rows]
    os.makedirs('/opt/sml/repo/tools/train-tycoon/pixel/out', exist_ok=True)
    render(grid, 5, '/opt/sml/repo/tools/train-tycoon/pixel/out/proof.png')
    print('ok out/proof.png', CW, CH)

if __name__ == '__main__':
    render_scene()
