#!/usr/bin/env python3
# 證明:iso 車輛外型「不限於方盒」。加幾何原件就能做非方塊外型,角度一樣統一。
# 這裡示範水平圓柱(罐車 タキ)+ 弧形車頂客車 —— 都不是方盒。
import sys, os, math
sys.path.insert(0, '/opt/sml/repo/tools/pixel16')
sys.path.insert(0, '/opt/sml/repo/tools/train-tycoon/pixel')
from engine16 import RAMPS, add_outline, render
from iso_cars16 import (Iso, new_canvas, grid, screen, HZ, disc, line,
                        fill_poly, lerp2, vsub)

def cyl_h(rows, ox, oy, c0, c1, rc, zc, rad, ramp, endcap=True):
    """iso 水平圓柱(沿 c 軸躺):橫剖圓在 (r,z) 平面 → 投影成斜橢圓管。
    上亮下暗沿圓周漸層 = 金屬圓柱體積(方盒絕對做不出的曲面)。"""
    R = RAMPS[ramp] if isinstance(ramp, str) else ramp
    Rv = screen(0, 1); Uv = (0.0, -float(HZ))     # r 軸 / z 軸 的螢幕向量
    def base(c):
        x, y = screen(c, rc); return (x + ox, y + oy - zc * HZ)
    sc = max(2, int((c1 - c0) / 0.03))
    for i in range(sc + 1):
        c = c0 + (c1 - c0) * i / sc
        bx, by = base(c)
        for j in range(0, 260):
            th = math.radians(-38 + j * (248 / 260))   # 只掃可見的前+頂弧
            dr, dz = math.cos(th), math.sin(th)
            px = bx + rad * dr * Rv[0] + rad * dz * Uv[0]
            py = by + rad * dr * Rv[1] + rad * dz * Uv[1]
            f = (dz + 1) / 2                            # 底0→頂1
            idx = min(len(R) - 1, int(f * len(R)))
            xx, yy = int(round(px)), int(round(py))
            if 0 <= yy < len(rows) and 0 <= xx < len(rows[0]): rows[yy][xx] = R[idx]
    # 近端圓蓋(c1 端,面向右,看得到)
    if endcap:
        bx, by = base(c1)
        for a in range(0, 360, 2):
            for rr in [k * 0.06 for k in range(int(rad / 0.06) + 1)]:
                th = math.radians(a)
                dr, dz = math.cos(th) * rr, math.sin(th) * rr
                px = bx + dr * Rv[0] + dz * Uv[0]; py = by + dr * Rv[1] + dz * Uv[1]
                f = (dz / rad + 1) / 2
                idx = min(len(R) - 1, max(0, int(f * len(R)) - 1))   # 端蓋略暗一階
                xx, yy = int(round(px)), int(round(py))
                if 0 <= yy < len(rows) and 0 <= xx < len(rows[0]): rows[yy][xx] = R[idx]

def tank_car():
    W, HH = 150, 124; ox, oy = 58, 74
    rows = new_canvas(W, HH)
    # 底盤平板(方盒,低)+ 轉向架
    base = Iso(rows, ox, oy, 3.7, 1.1, 0.34)
    base.wheels([0.23, 0.77]); base.faces('steel')
    base.roof_panel(0.0, 1.0, 0.0, 1.0, RAMPS['steel'][2]); base.outline()
    # 圓罐(躺在平板上,沿 c 軸)——非方盒曲面
    rc = 1.1 / 2; zc = 0.34 + 0.62
    cyl_h(rows, ox, oy, 0.35, 3.35, rc, zc, 0.62, 'steel')
    # 頂高光縱脊(沿 c 軸畫一條亮線)
    for i in range(60):
        c = 0.4 + i * 0.05; x, y = screen(c, rc)
        xx, yy = int(x + ox), int(y + oy - (zc + 0.62) * HZ)
        if 0 <= yy < HH and 0 <= xx < W: rows[yy][xx] = RAMPS['steel'][5]
    # 頂部注入口(金,小圓柱)
    cyl_h(rows, ox, oy, 1.75, 2.05, rc, zc + 0.55, 0.16, 'gold', endcap=False)
    # 兩道金箍
    for cc in (1.1, 2.6):
        for a in range(-38, 210, 3):
            th = math.radians(a); Rv = screen(0, 1)
            dr, dz = math.cos(th), math.sin(th)
            x, y = screen(cc, rc)
            px = x + ox + 0.62 * dr * Rv[0]; py = y + oy - zc * HZ + 0.62 * (dr * Rv[1] + dz * (-HZ))
            xx, yy = int(round(px)), int(round(py))
            if 0 <= yy < HH and 0 <= xx < W: rows[yy][xx] = RAMPS['gold'][3]
    return add_outline(grid(rows), ink='0', diagonal=False)

def round_roof_passenger():
    """弧形車頂客車:車頂不是平的方盒頂,而是半圓弧(用圓柱頂罩)。"""
    W, HH = 150, 124; ox, oy = 58, 74
    rows = new_canvas(W, HH)
    color = 'azure'
    body = Iso(rows, ox, oy, 4.2, 1.0, 0.95)      # 車身(方盒,但頂矮)
    body.wheels([0.22, 0.80]); body.faces(color)
    R = RAMPS[color]
    body.long_panel(0.03, 0.97, 0.10, 0.145, R[1])
    for i in range(6):
        fa = 0.07 + i * (0.88 / 6); fb = fa + 0.62 / 6
        body.win(fa, fb, 0.5, 0.85)
    body.long_panel(0.03, 0.97, 0.42, 0.455, RAMPS['gold'][3])
    body.outline()
    # 弧形車頂 = 沿 c 軸的半圓柱罩(蓋在車身頂)
    rc = 1.0 / 2; zc = 0.95
    cyl_h(rows, ox, oy, 0.0, 4.2, rc, zc, 0.5, color, endcap=True)
    return add_outline(grid(rows), ink='0', diagonal=False)

if __name__ == '__main__':
    out = '/opt/sml/repo/tools/train-tycoon/pixel/out'
    os.makedirs(out, exist_ok=True)
    render(tank_car(), 6, out + '/iso_tank.png')
    render(round_roof_passenger(), 6, out + '/iso_roundroof.png')
    print('ok shape demo')
