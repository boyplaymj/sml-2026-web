#!/usr/bin/env python3
# 火車大亨 · 最完整 iso 蒸汽機車頭(pixel16)。
# 集合所有難外型:圓鍋爐(水平圓柱)+ 煙囪/汽包(垂直圓柱)+ 大動輪連桿(圓)+ 排障器(斜楔)+ 煙。
# 鐵律:全用同一條 screen(c,r) 投影 → 與所有車廂角度「數學上完全一致」,改不掉。
import sys, os, math
sys.path.insert(0, '/opt/sml/repo/tools/pixel16')
sys.path.insert(0, '/opt/sml/repo/tools/train-tycoon/pixel')
from engine16 import RAMPS, add_outline, render
from iso_cars16 import Iso, new_canvas, grid, screen, HZ, disc, line, fill_poly, lerp2
from shape_demo16 import cyl_h

def cyl_v(rows, ox, oy, cc, rc, z0, z1, rad, ramp, cap=True):
    """iso 垂直圓柱(沿 z 軸站):煙囪/汽包/注水口。前弧壁上下拉 + 頂橢圓蓋。
    左亮右暗做圓柱體積。底圓在 (c,r) 平面 → 投影成 2:1 橢圓。"""
    R = RAMPS[ramp] if isinstance(ramp, str) else ramp
    def sp(c, r, z):
        x, y = screen(c, r); return (x + ox, y + oy - z * HZ)
    # 壁面:遠→近畫(近蓋遠),依 (dc+dr) 排序
    rim = []
    for a in range(0, 360, 2):
        th = math.radians(a); dc = rad * math.cos(th); dr = rad * math.sin(th)
        rim.append((dc + dr, dc, dr, th))
    rim.sort()
    for _, dc, dr, th in rim:
        wx, wtop = sp(cc + dc, rc + dr, z1)
        _, wbot = sp(cc + dc, rc + dr, z0)
        # 左亮右暗:用 cos(th) 對映(左=負x=亮)
        f = (math.cos(th - math.radians(35)) + 1) / 2
        idx = min(len(R) - 1, int((1 - f) * (len(R) - 1)))
        for yy in range(int(min(wtop, wbot)), int(max(wtop, wbot)) + 1):
            if 0 <= yy < len(rows) and 0 <= int(wx) < len(rows[0]): rows[yy][int(wx)] = R[idx]
    if cap:
        cx, cy = sp(cc, rc, z1)
        for a in range(0, 360, 2):
            for rr in [k * 0.05 for k in range(int(rad / 0.05) + 1)]:
                th = math.radians(a); px, py = sp(cc + rr*math.cos(th), rc + rr*math.sin(th), z1)
                if 0 <= int(py) < len(rows) and 0 <= int(px) < len(rows[0]):
                    rows[int(py)][int(px)] = R[-1] if rr < rad*0.6 else R[max(0, len(R)-2)]

def drive_wheel(rows, ox, oy, cc, rr, rad, zc):
    """大動輪(側視圓,金輻):裝在近側 r=rr。"""
    S = RAMPS['steel']; G = RAMPS['gold']
    x, y = screen(cc, rr); cx = x + ox; cy = y + oy - zc * HZ
    disc(rows, cx, cy, rad, S[0])
    disc(rows, cx, cy, rad - 1.3, S[3])
    disc(rows, cx - 0.8, cy - 0.8, rad - 2.4, S[4])
    for a in range(0, 360, 45):                       # 金輻
        t = math.radians(a)
        for k in [j * 0.5 for j in range(1, int((rad - 1) / 0.5))]:
            xx, yy = int(round(cx + k * math.cos(t))), int(round(cy + k * math.sin(t)))
            if 0 <= yy < len(rows) and 0 <= xx < len(rows[0]): rows[yy][xx] = G[2]
    disc(rows, cx, cy, 1.6, G[3]); disc(rows, cx, cy, 0.8, G[4])
    return cx, cy

def draw_loco(rows, ox, oy, c0=0.0, D=1.15, outline=True):
    """把蒸汽機車頭畫進 rows,車頭起點在 c=c0(可掛進共用軌道)。"""
    W, HH = len(rows[0]), len(rows)
    rc = D / 2
    C = lambda v: v + c0                       # 所有 c 座標平移 c0(保持同一投影)
    coral, gold, steel = 'coral', 'gold', RAMPS['steel']
    bz = 0.34 + 0.55
    # === 依 iso 深度嚴格由遠(後方/低c)到近(前方/高c)繪製,杜絕圖層穿幫 ===
    # 1) 底架(整體最底層)
    frame = Iso(rows, ox, oy, 4.4, D, 0.34, dc=c0)
    frame.faces('steel'); frame.roof_panel(0, 1, 0, 1, steel[1]); frame.outline()
    # 2) 駕駛室(最後方 c=0~1.15,先畫)+ 弧頂
    cab = Iso(rows, ox, oy, 1.15, D, 1.05, z0=0.34, dc=c0)
    cab.faces(coral)
    cab.long_panel(0.15, 0.85, 0.35, 0.72, '0')
    cab.long_grad(0.2, 0.8, 0.4, 0.68, [RAMPS['azure'][3], RAMPS['azure'][2], RAMPS['azure'][1]])
    cab.roof_panel(0, 1, 0, 1, RAMPS['coral'][0])
    cab.outline()
    cyl_h(rows, ox, oy, C(0.0), C(1.15), rc, 0.34 + 1.05, 0.5, coral, endcap=True)
    # 3) 鍋爐(水平圓柱,蓋住駕駛室前緣)+ 金箍
    cyl_h(rows, ox, oy, C(1.0), C(3.95), rc, bz, 0.56, coral)
    for cc in (1.7, 2.9):
        for a in range(-40, 210, 3):
            th = math.radians(a); dr = math.cos(th); dz = math.sin(th)
            x, y = screen(C(cc), rc)
            px = x + ox + 0.56 * dr * screen(0,1)[0]
            py = y + oy - bz*HZ + 0.56*(dr*screen(0,1)[1] + dz*(-HZ))
            if 0 <= int(py) < HH and 0 <= int(px) < W: rows[int(py)][int(px)] = RAMPS['gold'][3]
    # 4) 鍋爐上方配件:汽包 → 煙囪(在鍋爐之上)
    cyl_v(rows, ox, oy, C(2.4), rc, bz + 0.35, bz + 0.72, 0.24, 'gold')
    cyl_v(rows, ox, oy, C(3.4), rc, bz + 0.3, bz + 1.05, 0.26, 'steel')
    cyl_v(rows, ox, oy, C(3.4), rc, bz + 1.02, bz + 1.12, 0.34, 'steel')
    # 5) 煙箱前臉(鍋爐最前端 c=3.95,近)
    xf, yf = screen(C(3.95), rc); fx = xf + ox; fy = yf + oy - bz * HZ
    disc(rows, fx, fy, 7.4, RAMPS['coral'][0])
    disc(rows, fx, fy, 3.0, steel[3]); disc(rows, fx - 0.6, fy - 0.6, 1.6, steel[4])
    disc(rows, fx, fy, 0.9, steel[5])
    # 6) 動輪+連桿(近側 r>rc,畫在鍋爐之前露出下半)+ 前導小輪
    zc = 0.5; cs = []
    for cc in (1.35, 2.35, 3.35):
        cs.append(drive_wheel(rows, ox, oy, C(cc), D + 0.02, 5.2, zc))
    for i in range(len(cs) - 1):
        (x0, y0), (x1, y1) = cs[i], cs[i+1]
        line(rows, (x0, y0 + 3), (x1, y1 + 3), steel[4]); line(rows, (x0, y0 + 4), (x1, y1 + 4), steel[2])
        disc(rows, x0, y0 + 3.5, 1.2, steel[5])
    drive_wheel(rows, ox, oy, C(4.15), D + 0.02, 3.0, zc - 0.05)
    # 7) 排障器(最前端底部,最後畫)
    xb, yb = screen(C(4.1), rc); bxp = xb + ox; byp = yb + oy - 0.34*HZ
    fill_poly(rows, [(bxp - 2, byp - 4), (bxp + 12, byp + 4), (bxp - 2, byp + 8)], RAMPS['gold'][2])
    for i in range(4):
        line(rows, (bxp - 2, byp - 4 + i*3), (bxp + 10 - i*2, byp + 4), RAMPS['gold'][0])
    # 8) 煙(最上層)
    for (cc, zz, r) in [(3.4, bz + 1.35, 2.6), (3.15, bz + 1.7, 3.0), (2.95, bz + 1.5, 2.0)]:
        x, y = screen(C(cc), rc); sx = x + ox; sy = y + oy - zz * HZ
        disc(rows, sx, sy, r, RAMPS['enamel'][2]); disc(rows, sx, sy, r - 1, RAMPS['enamel'][3])

def steam_loco():
    W, HH = 172, 138; ox, oy = 48, 90
    rows = new_canvas(W, HH)
    draw_loco(rows, ox, oy, 0.0)
    return add_outline(grid(rows), ink='0', diagonal=False)

if __name__ == '__main__':
    out = '/opt/sml/repo/tools/train-tycoon/pixel/out'
    os.makedirs(out, exist_ok=True)
    render(steam_loco(), 6, out + '/iso_loco.png')
    print('ok iso_loco.png')
