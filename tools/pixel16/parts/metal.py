"""
pixel16 金屬技法庫 —— 把「精緻版金磚」的手工技法沉澱成可重用零件。

一旦技法函式化,精緻不再是一次性苦工:任何金屬/寶石物件套 plate() 就有
浮凸邊框 + 對角鏡面掃光;再用 engine16.shift_ramp 換 ramp,金→銀→翡翠→紅寶
全保留光影。這就是「在高質感層級跑複利」。

所有函式吃/吐字元網格 list[str],用具名 ramp 上色(故 shift_ramp 可換材質)。
'9' = 純白鏡面高光(不屬任何 ramp,shift 時保留 → 各材質都有白反光)。
"""
from engine16 import RAMPS

HI = "9"  # 純白鏡面高光核


def _to(c):
    return [list(r) for r in c]


def _from(c):
    return ["".join(r) for r in c]


def _ramp_step(ramp):
    r = RAMPS[ramp]
    n = len(r)
    def S(f):                       # f: 0=最暗 .. 1=最亮
        return r[min(n - 1, max(0, round(f * (n - 1))))]
    return S


def rrect_inside(L, R, T, B, rad=2):
    """回傳 inside(x,y):是否在圓角矩形內。"""
    corners = [(L + rad, T + rad, -1, -1), (R - rad, T + rad, 1, -1),
               (L + rad, B - rad, -1, 1), (R - rad, B - rad, 1, 1)]
    def inside(x, y):
        if not (L <= x <= R and T <= y <= B):
            return False
        for cxr, cyr, sx, sy in corners:
            in_cx = (x < cxr) if sx < 0 else (x > cxr)
            in_cy = (y < cyr) if sy < 0 else (y > cyr)
            if in_cx and in_cy and (x - cxr) ** 2 + (y - cyr) ** 2 > rad * rad + rad:
                return False
        return True
    return inside


def plate(ramp, w, h, rad=2, sheen=0.30):
    """核心:發亮金屬板(圓角 + 柱面漸層 + 浮凸邊框 + 對角鏡面掃光)。
    金錠/銀錠/寶石板共用。sheen=掃光在板面的位置(0左~1右)。"""
    S = _ramp_step(ramp)
    L, R, T, B = 0, w - 1, 0, h - 1
    inside = rrect_inside(L, R, T, B, rad)
    cx = (L + R) / 2
    c = [["."] * w for _ in range(h)]

    # 柱面橫向漸層:中央亮脊、兩側漸暗
    for y in range(h):
        for x in range(w):
            if not inside(x, y):
                continue
            u = abs(x - (cx - 2)) / (w) * 2
            c[y][x] = S(1 - min(1, u))

    # 浮凸邊框:左上受光亮、右下陰影暗
    for y in range(h):
        for x in range(w):
            if not inside(x, y):
                continue
            tl = (not inside(x - 1, y)) or (not inside(x, y - 1))
            br = (not inside(x + 1, y)) or (not inside(x, y + 1))
            if tl:
                c[y][x] = S(1)
            elif br:
                c[y][x] = S(0)

    # 對角鏡面掃光(亮帶 + 白核)
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if not inside(x, y):
                continue
            band = (x - L) - (y - T) * 1.25 - (R - L) * sheen
            if -2 <= band <= 3:
                c[y][x] = S(1)
            if -0.5 <= band <= 1:
                c[y][x] = HI
    return _from(c)


def emboss_line(grid, x0, x1, y, ramp):
    """壓紋刻痕:一列暗線 + 下一列亮線 = 凹刻立體。"""
    S = _ramp_step(ramp)
    c = _to(grid)
    for x in range(x0, x1 + 1):
        if 0 <= y < len(c) and 0 <= x < len(c[0]) and c[y][x] != ".":
            c[y][x] = S(0)
        if 0 <= y + 1 < len(c) and 0 <= x < len(c[0]) and c[y + 1][x] != ".":
            c[y + 1][x] = S(1)
    return _from(c)


def inset_panel(grid, cx, cy, hw, hh, ramp):
    """中央凹刻盤面:邊框暗、內部中亮、左上內緣提亮 = 下沉立體。"""
    S = _ramp_step(ramp)
    c = _to(grid)
    for y in range(cy - hh, cy + hh + 1):
        for x in range(cx - hw, cx + hw + 1):
            if not (0 <= y < len(c) and 0 <= x < len(c[0])) or c[y][x] == ".":
                continue
            edge = x in (cx - hw, cx + hw) or y in (cy - hh, cy + hh)
            inner_hi = x == cx - hw + 1 or y == cy - hh + 1
            c[y][x] = S(0) if edge else (S(0.75) if inner_hi else S(0.5))
    return _from(c)


def gem(grid, cx, cy, rad, ramp):
    """菱形寶石:左上受光亮、右下暗 + 白色反光點。"""
    S = _ramp_step(ramp)
    c = _to(grid)
    for dy in range(-rad, rad + 1):
        for dx in range(-rad, rad + 1):
            if abs(dx) + abs(dy) > rad:
                continue
            x, y = cx + dx, cy + dy
            if not (0 <= y < len(c) and 0 <= x < len(c[0])):
                continue
            s = dx + dy
            c[y][x] = HI if s < -1 else (S(1) if s < 1 else S(0.4))
    return _from(c)
