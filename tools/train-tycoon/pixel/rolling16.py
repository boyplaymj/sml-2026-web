#!/usr/bin/env python3
# 火車大亨 · 16bit 認真版車輛 sprite(側視 roster,車庫/購車選單用)。
# pixel16:多階漸層 ramp 上金屬光影 + 圓輪連桿 + 車窗鉚釘。程式擺像素、零成本。
# 這才是「認真生成」:每台車手工雕細節,不是拿方塊擠。
import sys, os, math
sys.path.insert(0, '/opt/sml/repo/tools/pixel16')
from engine16 import RAMPS, add_outline, render, make_sheet

# ── 低階畫布工具 ────────────────────────────────────────────
def canvas(w, h): return [['.'] * w for _ in range(h)]
def grid(c): return [''.join(r) for r in c]
def put(c, x, y, ch):
    if 0 <= y < len(c) and 0 <= x < len(c[0]): c[y][x] = ch
def rect(c, x0, y0, x1, y1, ch):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1): put(c, x, y, ch)

def disc(c, cx, cy, r, ch):
    for y in range(int(cy - r), int(cy + r) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + r * 0.5: put(c, x, y, ch)

def ring(c, cx, cy, r, ch, t=1.4):
    for y in range(int(cy - r), int(cy + r) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            d = (x - cx) ** 2 + (y - cy) ** 2
            if (r - t) ** 2 <= d <= r * r + r * 0.5: put(c, x, y, ch)

def vgrad(c, x0, y0, x1, y1, ramp):
    """矩形內垂直漸層:上亮下暗(圓柱體積感)。ramp 由暗到亮,故上用亮階。"""
    R = RAMPS[ramp] if isinstance(ramp, str) else ramp
    n = y1 - y0
    for y in range(y0, y1 + 1):
        f = (y - y0) / max(1, n)          # 0 上 → 1 下
        idx = int((1 - f) * (len(R) - 1))  # 上亮
        for x in range(x0, x1 + 1): put(c, x, y, R[idx])

# ── 可重用零件 ──────────────────────────────────────────────
def wheel(c, cx, cy, r, spoke='gold'):
    """金屬車輪:鋼輪圈 + 亮輪面漸層 + 輪轂 + 輻條。"""
    S = RAMPS['steel']; G = RAMPS[spoke]
    disc(c, cx, cy, r, S[3])            # 輪面(中灰)
    # 受光:左上亮一點
    for y in range(int(cy - r), int(cy + 1)):
        for x in range(int(cx - r), int(cx + 1)):
            if (x - cx) ** 2 + (y - cy) ** 2 <= (r - 1) ** 2: put(c, x, y, S[4])
    ring(c, cx, cy, r, S[1], t=1.6)     # 深色輪圈(鋼胎)
    # 輻條(十字 + 斜)
    for ang in range(0, 360, 45):
        a = math.radians(ang)
        for rr in range(1, int(r - 1)):
            put(c, int(round(cx + rr * math.cos(a))), int(round(cy + rr * math.sin(a))), G[max(0, len(G) - 3)])
    disc(c, cx, cy, 1.6, G[-1])         # 亮輪轂
    put(c, int(cx), int(cy), G[-2])

def coupler(c, x, y):
    S = RAMPS['steel']
    rect(c, x, y - 1, x + 2, y + 1, S[2]); put(c, x + 2, y, S[4])

# ── 蒸汽機車頭(旗艦)────────────────────────────────────────
def steam_loco():
    W, H = 60, 40
    c = canvas(W, H)
    coral, gold, steel, enamel = 'coral', 'gold', RAMPS['steel'], 'enamel'
    R = RAMPS[coral]
    GROUND = 34
    # 台車底盤(黑鋼)
    rect(c, 6, GROUND - 4, 52, GROUND - 2, steel[1])
    # 大動輪 x2 + 前導小輪
    wheel(c, 18, GROUND - 1, 6, spoke=gold)
    wheel(c, 32, GROUND - 1, 6, spoke=gold)
    wheel(c, 46, GROUND - 1, 4, spoke=gold)
    # 連桿(連兩大輪)
    rect(c, 18, GROUND - 1, 32, GROUND, steel[4])
    put(c, 18, GROUND - 1, steel[5]); put(c, 32, GROUND - 1, steel[5])
    # 鍋爐(橫圓柱,coral 紅,上亮下暗)+ 前煙箱圓面
    vgrad(c, 20, 14, 50, 26, coral)
    disc(c, 50, 20, 6, R[1])                     # 煙箱前臉(深)
    disc(c, 49, 19, 5, R[2])
    ring(c, 50, 20, 6, steel[0], t=1.4)
    disc(c, 50, 20, 2.2, steel[4]); put(c, 50, 20, steel[5])  # 煙箱門把手
    # 鍋爐金箍 x2
    for bx in (28, 40):
        rect(c, bx, 14, bx, 26, gold and RAMPS['gold'][2])
        rect(c, bx + 1, 14, bx + 1, 26, RAMPS['gold'][3])
    # 蒸汽室頂(dome)+ 汽笛
    disc(c, 30, 13, 3, RAMPS['gold'][3]); disc(c, 30, 12, 2, RAMPS['gold'][4])
    # 煙囪
    rect(c, 44, 6, 48, 14, steel[2]); rect(c, 43, 5, 49, 6, steel[1])
    rect(c, 45, 7, 47, 13, steel[3])
    # 駕駛室(後方高箱)
    vgrad(c, 6, 8, 22, 26, coral)
    rect(c, 6, 8, 22, 9, R[1])                   # 車頂邊
    rect(c, 8, 12, 18, 18, RAMPS['azure'][1])    # 車窗(深藍玻璃)
    rect(c, 8, 12, 18, 13, RAMPS['azure'][3])    # 窗上高光
    put(c, 13, 12, RAMPS['azure'][3])
    # 車頂(平頂 + 高光)
    rect(c, 5, 7, 23, 8, R[0]); rect(c, 6, 6, 22, 6, R[1])
    # 排障器(cowcatcher)
    for i in range(5):
        put(c, 54 + i // 2, GROUND - 6 + i, RAMPS['gold'][2])
        put(c, 55, GROUND - 6 + i, RAMPS['gold'][3])
    # 緩衝器(後)
    coupler(c, 3, 24)
    # 煙(白,enamel)
    for (sx, sy, rr) in [(46, 3, 2), (48, 0, 2.4), (43, 1, 1.6)]:
        disc(c, sx, sy, rr, RAMPS['enamel'][2])
        disc(c, sx, sy, rr - 1, RAMPS['enamel'][3])
    g = add_outline(grid(c), ink='0', diagonal=True)
    return g

# ── 柴電機車頭 ──────────────────────────────────────────────
def diesel_loco():
    W, H = 60, 40
    c = canvas(W, H)
    steel = RAMPS['steel']; GROUND = 34
    body = 'azure'; R = RAMPS[body]
    # 底盤
    rect(c, 4, GROUND - 4, 54, GROUND - 2, steel[1])
    # 轉向架(兩組各兩小輪)
    for cx in (12, 22, 38, 48):
        wheel(c, cx, GROUND - 1, 4, spoke='steel')
    # 車身(長方 hood,前段低、駕駛室高)
    vgrad(c, 6, 14, 40, 26, body)          # 主機艙
    vgrad(c, 40, 10, 54, 26, body)          # 駕駛室(較高)
    rect(c, 6, 14, 54, 15, R[1])            # 頂邊暗
    # 黃色警示斜紋(前端)
    for i in range(6):
        put(c, 52 - i, 26 - i, RAMPS['gold'][3]); put(c, 51 - i, 26 - i, RAMPS['gold'][2])
    # 駕駛室大窗
    rect(c, 42, 13, 52, 19, RAMPS['enamel'][3]); rect(c, 42, 13, 52, 13, RAMPS['enamel'][2])
    rect(c, 47, 13, 47, 19, steel[2])        # 窗框中柱
    # 機艙通風百葉 + 車身腰線
    for gx in range(10, 38, 3):
        rect(c, gx, 18, gx, 23, R[1])
    rect(c, 6, 20, 40, 20, RAMPS['gold'][2])  # 腰線金條
    # 車頂(平 + 排氣口)
    rect(c, 6, 13, 54, 13, R[0]); rect(c, 20, 11, 24, 12, steel[2])
    coupler(c, 1, 24); coupler(c, 56, 24)
    g = add_outline(grid(c), ink='0', diagonal=True)
    return g

# ── 車廂共用底座(平台 + 轉向架四輪 + 前後緩衝器)──────────────
def _chassis(c, x0, x1, GROUND):
    steel = RAMPS['steel']
    rect(c, x0, GROUND - 4, x1, GROUND - 2, steel[1])
    for cx in (x0 + 7, x0 + 15, x1 - 15, x1 - 7):
        wheel(c, cx, GROUND - 1, 4, spoke='steel')
    coupler(c, x0 - 3, GROUND - 8); coupler(c, x1 + 1, GROUND - 8)

def passenger_car():
    W, H = 60, 34; c = canvas(W, H); GROUND = 30
    _chassis(c, 6, 54, GROUND)
    R = RAMPS['coral']
    vgrad(c, 6, 8, 54, GROUND - 4, 'coral')
    rect(c, 6, 8, 54, 9, R[1])
    # 車窗帶(一排大窗 + 窗間柱)
    for wx in range(10, 50, 8):
        rect(c, wx, 12, wx + 5, 18, RAMPS['azure'][3])
        rect(c, wx, 12, wx + 5, 12, RAMPS['azure'][2])
    rect(c, 6, 20, 54, 21, RAMPS['gold'][2])   # 腰線
    # 圓弧車頂
    rect(c, 5, 7, 55, 7, R[0]); rect(c, 7, 6, 53, 6, R[1])
    rect(c, 10, 5, 50, 5, RAMPS['enamel'][2])  # 頂高光
    return add_outline(grid(c), ink='0', diagonal=True)

def box_car():
    W, H = 60, 34; c = canvas(W, H); GROUND = 30
    _chassis(c, 6, 54, GROUND)
    vgrad(c, 6, 8, 54, GROUND - 4, 'wood')
    W_ = RAMPS['wood']
    # 木板直紋 + 鉚釘
    for px in range(9, 54, 4): rect(c, px, 10, px, GROUND - 5, W_[0])
    # 滑門(中央,金屬)
    rect(c, 26, 11, 38, GROUND - 5, RAMPS['steel'][3])
    rect(c, 26, 11, 26, GROUND - 5, RAMPS['steel'][1]); rect(c, 38, 11, 38, GROUND - 5, RAMPS['steel'][1])
    rect(c, 31, 11, 32, GROUND - 5, RAMPS['steel'][1])  # 門縫
    rect(c, 6, 9, 54, 9, W_[2])                 # 頂板
    rect(c, 6, 7, 54, 8, RAMPS['coral'][1])     # 紅頂
    return add_outline(grid(c), ink='0', diagonal=True)

def tank_car():
    W, H = 60, 34; c = canvas(W, H); GROUND = 30
    _chassis(c, 6, 54, GROUND)
    rect(c, 8, GROUND - 6, 52, GROUND - 5, RAMPS['steel'][2])  # 平板
    # 圓罐(橫圓柱,銀鋼,上亮下暗)+ 端蓋
    vgrad(c, 12, 11, 48, GROUND - 6, 'steel')
    disc(c, 12, (11 + GROUND - 6) // 2, (GROUND - 6 - 11) / 2, RAMPS['steel'][2])
    disc(c, 48, (11 + GROUND - 6) // 2, (GROUND - 6 - 11) / 2, RAMPS['steel'][2])
    rect(c, 12, 12, 48, 12, RAMPS['steel'][5])  # 頂高光縱脊
    rect(c, 12, 13, 48, 13, RAMPS['steel'][4])
    # 頂部注入口 + 護欄
    rect(c, 28, 8, 32, 11, RAMPS['gold'][2]); rect(c, 29, 7, 31, 7, RAMPS['gold'][3])
    return add_outline(grid(c), ink='0', diagonal=True)

def hopper_car():
    W, H = 60, 34; c = canvas(W, H); GROUND = 30
    _chassis(c, 6, 54, GROUND)
    R = RAMPS['steel']
    # 梯形斗身(上寬下窄)
    for y in range(9, GROUND - 4):
        f = (y - 9) / (GROUND - 4 - 9)
        inset = int(f * 8)
        for x in range(8 + inset, 52 - inset): put(c, x, y, R[3] if x < 30 else R[2])
    rect(c, 8, 9, 52, 10, R[1])
    # 煤炭(頂部堆疊,深塊 + 少量高光)
    for x in range(10, 50):
        h = 2 + int(2 * abs(math.sin(x * 0.7)))
        for y in range(8 - h, 9): put(c, x, y, R[0] if (x + y) % 2 else R[1])
    for x in range(12, 48, 5): put(c, x, 6, R[3])  # 煤塊反光
    return add_outline(grid(c), ink='0', diagonal=True)

def render_all():
    out = '/opt/sml/repo/tools/train-tycoon/pixel/out'
    os.makedirs(out, exist_ok=True)
    render(steam_loco(), 8, out + '/loco_steam.png')
    render(diesel_loco(), 8, out + '/loco_diesel.png')
    render(passenger_car(), 8, out + '/car_passenger.png')
    render(box_car(), 8, out + '/car_box.png')
    render(tank_car(), 8, out + '/car_tank.png')
    render(hopper_car(), 8, out + '/car_hopper.png')
    print('ok all sprites')

if __name__ == '__main__':
    render_all()
