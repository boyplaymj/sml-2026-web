#!/usr/bin/env python3
# 編組:機車頭 + 多節車廂掛在「同一條 c 軸軌道」上(共用畫布)。
# 這是「每節角度一樣」的終極證明:全用同一條 screen(c,r) 投影,
# 車與車若角度有一絲差就接不攏;接得天衣無縫 = 角度數學統一。
import sys, os
sys.path.insert(0, '/opt/sml/repo/tools/pixel16')
sys.path.insert(0, '/opt/sml/repo/tools/train-tycoon/pixel')
from engine16 import RAMPS, add_outline, render
from iso_cars16 import Iso, new_canvas, grid, screen, HZ, disc, line, _container
from shape_demo16 import cyl_h
from loco_iso16 import draw_loco

D = 1.1
rc = D / 2

def draw_passenger(rows, ox, oy, c0, color, L=4.2):
    iso = Iso(rows, ox, oy, L, D, 1.2, dc=c0)
    iso.wheels([0.22, 0.80]); iso.faces(color); R = RAMPS[color]
    iso.long_panel(0.03, 0.97, 0.10, 0.145, R[1])
    for i in range(6):
        fa = 0.07 + i*(0.88/6); fb = fa + 0.62/6; iso.win(fa, fb)
    iso.long_panel(0.03, 0.97, 0.36, 0.395, RAMPS['gold'][3])
    iso.clerestory(); iso.end_panel(0.30, 0.70, 0.1, 0.72, R[1]); iso.outline()

def draw_tank(rows, ox, oy, c0, L=3.7):
    base = Iso(rows, ox, oy, L, D, 0.34, dc=c0)
    base.wheels([0.23, 0.77]); base.faces('steel')
    base.roof_panel(0, 1, 0, 1, RAMPS['steel'][2]); base.outline()
    zc = 0.34 + 0.62
    cyl_h(rows, ox, oy, c0 + 0.35, c0 + L - 0.35, rc, zc, 0.6, 'steel')
    for i in range(int((L-0.8)/0.05)):                 # 頂高光縱脊
        c = c0 + 0.4 + i*0.05; x, y = screen(c, rc)
        xx, yy = int(x + ox), int(y + oy - (zc + 0.6) * HZ)
        if 0 <= yy < len(rows) and 0 <= xx < len(rows[0]): rows[yy][xx] = RAMPS['steel'][5]
    cyl_h(rows, ox, oy, c0 + L*0.45, c0 + L*0.55, rc, zc + 0.53, 0.15, 'gold', endcap=False)
    for cc in (c0 + L*0.3, c0 + L*0.7):                # 金箍
        import math
        for a in range(-38, 210, 3):
            th = math.radians(a); dr, dz = math.cos(th), math.sin(th)
            x, y = screen(cc, rc)
            px = x + ox + 0.6*dr*screen(0,1)[0]
            py = y + oy - zc*HZ + 0.6*(dr*screen(0,1)[1] + dz*(-HZ))
            if 0 <= int(py) < len(rows) and 0 <= int(px) < len(rows[0]): rows[int(py)][int(px)] = RAMPS['gold'][3]

def draw_container(rows, ox, oy, c0, L=3.7):
    flat = Iso(rows, ox, oy, L, D, 0.34, dc=c0)
    flat.wheels([0.23, 0.77]); flat.faces('steel')
    flat.roof_panel(0, 1, 0, 1, RAMPS['steel'][2]); flat.outline()
    _container(rows, ox, oy, 'coral', c0 + 0.1)
    _container(rows, ox, oy, 'azure', c0 + 1.95)

def build():
    W, HH, ox, oy = 300, 200, 30, 56
    rows = new_canvas(W, HH)
    # 鐵軌:沿 c 軸一整條(枕木 + 雙鋼軌),先畫(在車底)
    import math
    steel = RAMPS['steel']; wood = RAMPS['wood']
    def cpt(c, r, z=0.0):
        x, y = screen(c, r); return (x + ox, y + oy - z*HZ)
    c_lo, c_hi = -0.6, 17.6
    n = int((c_hi - c_lo) / 0.02)
    for i in range(n):                                  # 枕木
        c = c_lo + (c_hi - c_lo)*i/n
        if int(c/0.28) % 2 == 0: continue
        p = cpt(c, rc)
        for k in range(-7, 8):
            xx, yy = int(p[0] - k), int(p[1] + k*0.5)
            if 0 <= yy < HH and 0 <= xx < W: rows[yy][xx] = wood[0] if k % 3 else wood[1]
    for rr in (rc - 0.32, rc + 0.32):                   # 雙鋼軌
        for i in range(n):
            c = c_lo + (c_hi - c_lo)*i/n
            x, y = cpt(c, rr)
            if 0 <= int(y) < HH and 0 <= int(x) < W:
                rows[int(y)][int(x)] = steel[4]
                if 0 <= int(y)-1 < HH: rows[int(y)-1][int(x)] = steel[5]
    # 由遠(低 c,左上)到近(高 c,右下)依序畫 → 近的自然遮遠的
    draw_container(rows, ox, oy, 0.0)
    draw_tank(rows, ox, oy, 4.05)
    draw_passenger(rows, ox, oy, 8.1, 'mint')
    draw_loco(rows, ox, oy, 12.65, D)
    return add_outline(grid(rows), ink='0', diagonal=False)

if __name__ == '__main__':
    out = '/opt/sml/repo/tools/train-tycoon/pixel/out'
    os.makedirs(out, exist_ok=True)
    render(build(), 4, out + '/train_coupled.png')
    print('ok train_coupled.png')
