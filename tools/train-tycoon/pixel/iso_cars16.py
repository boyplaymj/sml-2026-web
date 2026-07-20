#!/usr/bin/env python3
# 火車大亨 · 16bit iso 3/4 車廂目錄(pixel16)— 加強細節版。
# iso 投影是數學公式 → 每台角度像素級一致(解掉擴散生圖「角度飄」)。
# 細節全用「斜面貼片器」貼在 iso 平行四邊形面上,角度自動吻合:
#   窗框+玻璃反光 / 滑門+把手+鉸鏈 / 克拉風通氣脊 / 波浪楞貨櫃+角鎖 / 轉向架+車輪。
import sys, os, math
sys.path.insert(0, '/opt/sml/repo/tools/pixel16')
from engine16 import PALETTE16, RAMPS, add_outline, render

TW, TH = 28, 14
HZ = TH

def screen(c, r):
    return (c - r) * (TW / 2), (c + r) * (TH / 2)

def _spans(pts, y):
    yc = y + 0.5; xs = []; n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        if (y1 <= yc < y2) or (y2 <= yc < y1):
            xs.append(x1 + (yc - y1) / (y2 - y1) * (x2 - x1))
    xs.sort(); return xs

def fill_poly(rows, pts, ch):
    H, W = len(rows), len(rows[0]); ys = [p[1] for p in pts]
    for y in range(max(0, int(math.floor(min(ys)))), min(H, int(math.ceil(max(ys))) + 1)):
        xs = _spans(pts, y)
        for k in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(round(xs[k]))), min(W, int(round(xs[k + 1])))):
                rows[y][x] = ch

def fill_grad(rows, pts, ramp_chars):
    H, W = len(rows), len(rows[0]); ys = [p[1] for p in pts]
    y0, y1 = int(math.floor(min(ys))), int(math.ceil(max(ys))); span = max(1, y1 - y0)
    for y in range(max(0, y0), min(H, y1 + 1)):
        f = (y - y0) / span
        ch = ramp_chars[min(len(ramp_chars) - 1, int(f * len(ramp_chars)))]
        xs = _spans(pts, y)
        for k in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(round(xs[k]))), min(W, int(round(xs[k + 1])))):
                rows[y][x] = ch

def line(rows, p0, p1, ch):
    H, W = len(rows), len(rows[0])
    x0, y0 = int(round(p0[0])), int(round(p0[1])); x1, y1 = int(round(p1[0])), int(round(p1[1]))
    dx, dy = abs(x1 - x0), abs(y1 - y0); sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        if 0 <= y0 < H and 0 <= x0 < W: rows[y0][x0] = ch
        if x0 == x1 and y0 == y1: break
        e2 = 2 * err
        if e2 > -dy: err -= dy; x0 += sx
        if e2 < dx:  err += dx; y0 += sy

def disc(rows, cx, cy, r, ch):
    for y in range(int(cy - r), int(cy + r) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + r * 0.4:
                if 0 <= y < len(rows) and 0 <= x < len(rows[0]): rows[y][x] = ch

def vsub(a, b): return (a[0] - b[0], a[1] - b[1])
def lerp2(O, U, V, fu, fv): return (O[0] + U[0]*fu + V[0]*fv, O[1] + U[1]*fu + V[1]*fv)

class Iso:
    def __init__(self, rows, ox, oy, L, D, H, z0=0.0, dc=0.0, dr=0.0):
        self.rows = rows; self.ox = ox; self.oy = oy
        self.L, self.D, self.H, self.z0 = L, D, H, z0
        def g(c, r, z):
            x, y = screen(c + dc, r + dr); return (x + ox, y + oy - z * HZ)
        self.g = g
        z1 = z0 + H
        self.b00=g(0,0,z0); self.b10=g(L,0,z0); self.b11=g(L,D,z0); self.b01=g(0,D,z0)
        self.t00=g(0,0,z1); self.t10=g(L,0,z1); self.t11=g(L,D,z1); self.t01=g(0,D,z1)

    def faces(self, ramp):
        R = RAMPS[ramp] if isinstance(ramp, str) else ramp
        mid = R[len(R)//2]; hi = R[-1]
        end = [self.b10, self.b11, self.t11, self.t10]
        lng = [self.b01, self.b11, self.t11, self.t01]
        roof = [self.t00, self.t10, self.t11, self.t01]
        fill_grad(self.rows, end,  [R[max(0,len(R)-3)], R[len(R)//2-1], R[0]])
        fill_grad(self.rows, lng,  [hi, R[max(0,len(R)-2)], mid])
        fill_grad(self.rows, roof, [hi, hi, R[max(0,len(R)-2)]])

    def _L(self): return (self.b01, vsub(self.b11, self.b01), vsub(self.t01, self.b01))
    def _R(self): return (self.b10, vsub(self.b11, self.b10), vsub(self.t10, self.b10))
    def _T(self): return (self.t00, vsub(self.t10, self.t00), vsub(self.t01, self.t00))

    def long_panel(self, fa, fb, za, zb, ch):
        O, U, V = self._L()
        fill_poly(self.rows, [lerp2(O,U,V,fa,za), lerp2(O,U,V,fb,za),
                              lerp2(O,U,V,fb,zb), lerp2(O,U,V,fa,zb)], ch)
    def long_grad(self, fa, fb, za, zb, ramp_chars):
        O, U, V = self._L()
        fill_grad(self.rows, [lerp2(O,U,V,fa,za), lerp2(O,U,V,fb,za),
                              lerp2(O,U,V,fb,zb), lerp2(O,U,V,fa,zb)], ramp_chars)
    def long_edge(self, fa, za, fb, zb, ch):
        O, U, V = self._L()
        line(self.rows, lerp2(O,U,V,fa,za), lerp2(O,U,V,fb,zb), ch)
    def roof_panel(self, fa, fb, da, db, ch):
        O, U, V = self._T()
        fill_poly(self.rows, [lerp2(O,U,V,fa,da), lerp2(O,U,V,fb,da),
                              lerp2(O,U,V,fb,db), lerp2(O,U,V,fa,db)], ch)
    def roof_edge(self, fa, da, fb, db, ch):
        O, U, V = self._T()
        line(self.rows, lerp2(O,U,V,fa,da), lerp2(O,U,V,fb,db), ch)
    def end_panel(self, fa, fb, za, zb, ch):
        O, U, V = self._R()
        fill_poly(self.rows, [lerp2(O,U,V,fa,za), lerp2(O,U,V,fb,za),
                              lerp2(O,U,V,fb,zb), lerp2(O,U,V,fa,zb)], ch)

    def win(self, fa, fb, za=0.44, zb=0.74, glass='azure'):
        """車窗:深窗框 + 玻璃(下深上亮)+ 左上角反光。"""
        self.long_panel(fa-0.006, fb+0.006, za-0.03, zb+0.03, '0')          # 窗框
        G = RAMPS[glass]
        self.long_grad(fa, fb, za, zb, [G[2], G[1], G[0]])                   # 玻璃(上亮下深)
        self.long_panel(fa, fa+(fb-fa)*0.45, zb-0.09, zb, G[3])             # 左上反光
        self.long_panel(fa, fb, zb-0.02, zb, G[3])                          # 上緣亮邊

    def door_slide(self, fc=0.5, w=0.11, za=0.05, zb=0.9):
        s = RAMPS['steel']
        self.long_grad(fc-w, fc+w, za, zb, [s[4], s[3], s[2]])
        self.long_panel(fc-w, fc-w+0.008, za, zb, s[1])                     # 左框
        self.long_panel(fc+w-0.008, fc+w, za, zb, s[1])                     # 右框
        self.long_panel(fc-0.006, fc+0.006, za, zb, s[1])                   # 對開門縫
        self.long_panel(fc+0.02, fc+0.05, 0.42, 0.5, s[5])                  # 把手
        for zz in (za+0.02, zb-0.04):                                       # 上下軌
            self.long_panel(fc-w, fc+w, zz, zz+0.02, s[1])

    def clerestory(self):
        """克拉風通氣頂:中央微凸淺色脊 + 細肋(非死白)。"""
        self.roof_panel(0.05, 0.95, 0.34, 0.66, RAMPS['enamel'][1])
        for i in range(9):
            f = 0.1 + i*0.095
            self.roof_edge(f, 0.34, f, 0.66, RAMPS['enamel'][0])           # 通氣肋
        self.roof_edge(0.05, 0.34, 0.95, 0.34, PALETTE16 and RAMPS['steel'][2])

    def wheels(self, centers, r=3.4):
        """iso 雙軸轉向架:每組 = 台車框 + 兩輪,往車底收(頂緣藏在車身後)。"""
        O, U, _ = self._L()
        s = RAMPS['steel']
        # 底架橫樑(整條)
        line(self.rows, lerp2(O,U,(0,0),0.06,0), lerp2(O,U,(0,0),0.94,0), s[1])
        for fc in centers:
            # 台車框(深色短塊,貼在底緣下方)
            pa = lerp2(O,U,(0,0), fc-0.11, 0); pb = lerp2(O,U,(0,0), fc+0.11, 0)
            frame = [(pa[0], pa[1]-1), (pb[0], pb[1]-1),
                     (pb[0], pb[1]+r*0.9), (pa[0], pa[1]+r*0.9)]
            fill_poly(self.rows, frame, s[1])
            line(self.rows, frame[0], frame[1], s[0]); line(self.rows, frame[3], frame[2], s[0])
            for f in (fc-0.07, fc+0.07):
                p = lerp2(O, U, (0,0), f, 0)
                cx, cy = p[0], p[1] + r*0.25          # 收進車底,只露下半
                disc(self.rows, cx, cy, r, s[0])       # 輪胎(深)
                disc(self.rows, cx, cy, r-1.2, s[3])   # 輪面
                disc(self.rows, cx-0.7, cy-0.7, r-2.3, s[4])  # 受光
                disc(self.rows, cx, cy, 1.0, s[5])     # 輪轂

    def outline(self):
        ink = '0'
        for a, b in [(self.t00,self.t10),(self.t10,self.t11),(self.t11,self.t01),(self.t01,self.t00)]:
            line(self.rows, a, b, ink)
        line(self.rows, self.t10, self.b10, ink); line(self.rows, self.t11, self.b11, ink)
        line(self.rows, self.t01, self.b01, ink)
        line(self.rows, self.b10, self.b11, ink); line(self.rows, self.b11, self.b01, ink)

def new_canvas(w, h): return [['.'] * w for _ in range(h)]
def grid(c): return [''.join(r) for r in c]

def _mk(draw):
    W, HH = 150, 124; ox, oy = 58, 74
    rows = new_canvas(W, HH)
    draw(rows, ox, oy)
    return add_outline(grid(rows), ink='0', diagonal=False)

# ── 各車種 ──────────────────────────────────────────────────
def passenger(color='coral', windows=6):
    def d(rows, ox, oy):
        iso = Iso(rows, ox, oy, 4.2, 1.0, 1.25)
        iso.wheels([0.22, 0.80])
        iso.faces(color); R = RAMPS[color]
        iso.long_panel(0.03, 0.97, 0.10, 0.145, R[1])       # 裙板暗邊
        for i in range(windows):
            fa = 0.07 + i*(0.88/windows); fb = fa + 0.62/windows
            iso.win(fa, fb)
        iso.long_panel(0.03, 0.97, 0.36, 0.395, RAMPS['gold'][3])  # 金腰線
        iso.long_edge(0.03, 0.36, 0.97, 0.36, RAMPS['gold'][4])
        iso.clerestory()
        iso.end_panel(0.30, 0.70, 0.1, 0.72, R[1])          # 端門
        iso.outline()
    return _mk(d)

def box_car(color='wood'):
    def d(rows, ox, oy):
        iso = Iso(rows, ox, oy, 3.4, 1.05, 1.15)
        iso.wheels([0.23, 0.77])
        iso.faces(color); R = RAMPS[color]
        for i in range(12):                                  # 木板直紋
            f = 0.05 + i*0.078
            iso.long_edge(f, 0.05, f, 0.92, R[0])
        iso.door_slide(0.5, 0.12)
        for f in (0.06, 0.94):                                # 端角鐵
            iso.long_panel(f-0.008, f+0.008, 0.03, 0.95, R[0])
        iso.roof_panel(0.0, 1.0, 0.0, 1.0, RAMPS['coral'][2])
        iso.roof_panel(0.05, 0.95, 0.08, 0.92, RAMPS['coral'][1])
        for i in range(6):                                    # 屋頂橫肋
            f = 0.12 + i*0.15; iso.roof_edge(f, 0.06, f, 0.94, RAMPS['coral'][0])
        iso.outline()
    return _mk(d)

def reefer():
    def d(rows, ox, oy):
        iso = Iso(rows, ox, oy, 3.4, 1.05, 1.15)
        iso.wheels([0.23, 0.77])
        iso.faces('enamel')
        iso.door_slide(0.5, 0.12)
        iso.long_panel(0.03, 0.97, 0.5, 0.56, RAMPS['azure'][2])   # 藍冷藏腰條
        iso.long_edge(0.03, 0.5, 0.97, 0.5, RAMPS['azure'][3])
        for f in (0.06, 0.94):
            iso.long_panel(f-0.008, f+0.008, 0.03, 0.95, RAMPS['steel'][2])
        iso.roof_panel(0.0, 1.0, 0.0, 1.0, RAMPS['enamel'][2])
        for fx in (0.26, 0.74):                                     # 兩冷卻艙口
            iso.roof_panel(fx-0.06, fx+0.06, 0.36, 0.64, RAMPS['steel'][3])
            iso.roof_panel(fx-0.04, fx+0.04, 0.4, 0.6, RAMPS['steel'][4])
        iso.outline()
    return _mk(d)

def flat_car():
    def d(rows, ox, oy):
        iso = Iso(rows, ox, oy, 3.7, 1.15, 0.4)
        iso.wheels([0.23, 0.77])
        iso.faces('steel')
        for i in range(11):                                        # 台面木板
            f = 0.04 + i*0.088
            iso.roof_edge(f, 0.05, f, 0.95, RAMPS['wood'][1])
        iso.roof_panel(0.0, 1.0, 0.0, 0.05, RAMPS['wood'][0])
        iso.roof_panel(0.0, 1.0, 0.95, 1.0, RAMPS['wood'][0])
        for f in (0.06, 0.30, 0.54, 0.78, 0.96):                   # 側柱插槽
            iso.long_panel(f-0.01, f+0.01, 0.55, 0.95, RAMPS['steel'][5])
        iso.outline()
    return _mk(d)

def _container(rows, ox, oy, color, dc):
    box = Iso(rows, ox, oy, 1.6, 1.0, 0.92, z0=0.4, dc=dc)
    box.faces(color); C = RAMPS[color]
    for i in range(8):                                             # 波浪楞紋
        f = 0.06 + i*0.115
        box.long_edge(f, 0.08, f, 0.9, C[0])
    box.long_panel(0.02, 0.98, 0.86, 0.9, C[max(0,len(C)-2)])      # 上緣鋼樑
    box.long_panel(0.02, 0.98, 0.08, 0.12, C[0])                   # 下緣鋼樑
    box.long_panel(0.4, 0.52, 0.4, 0.58, RAMPS['enamel'][3])       # 標誌牌
    box.end_panel(0.12, 0.88, 0.1, 0.88, C[len(C)//2-1])           # 端門
    box.end_panel(0.48, 0.52, 0.1, 0.88, C[0])                     # 門縫
    box.outline()
    # 角鎖(四下角深塊)
    for f in (0.03, 0.97):
        box.long_panel(f-0.03, f+0.03, 0.0, 0.12, RAMPS['steel'][1])

def container_car():
    def d(rows, ox, oy):
        iso = Iso(rows, ox, oy, 3.7, 1.0, 0.4)
        iso.wheels([0.23, 0.77])
        iso.faces('steel')
        iso.roof_panel(0.0, 1.0, 0.0, 1.0, RAMPS['steel'][2])
        for i in range(8):
            f = 0.06 + i*0.12; iso.roof_edge(f, 0.05, f, 0.95, RAMPS['steel'][1])
        iso.outline()
        _container(rows, ox, oy, 'coral', 0.05)
        _container(rows, ox, oy, 'azure', 1.95)
    return _mk(d)

def render_all():
    out = '/opt/sml/repo/tools/train-tycoon/pixel/out'
    os.makedirs(out, exist_ok=True)
    render(passenger('coral', 6), 6, out + '/iso_passenger.png')
    render(passenger('mint', 6), 6, out + '/iso_green.png')
    render(box_car(), 6, out + '/iso_box.png')
    render(reefer(), 6, out + '/iso_reefer.png')
    render(flat_car(), 6, out + '/iso_flat.png')
    render(container_car(), 6, out + '/iso_container.png')
    print('ok iso cars (detailed)')

if __name__ == '__main__':
    render_all()
