# 石柱(奉納芳名)16bit 像素版:竹林背景 + 一排玉垣石柱刻暱稱+名次(前12名)。
# 純程式擺像素、鎖 PALETTE16、最近鄰放大 → 無擴散,符合 pixel16 產線鐵律。
# 中文暱稱用真字型「小尺寸點陣化」(二值化貼進像素網格)當像素字。
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "pixel16"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "pixel8"))
# PALETTE16 由 engine16 鎖定(不自創色)
sys.path.insert(0, "/opt/sml/repo/tools/pixel16")
from engine16 import PALETTE16  # noqa

P = {k: v for k, v in PALETTE16.items() if v}
FONT = "/opt/sml/repo/tools/jinja-shrine/fonts/NotoSerifTC.otf"
KOU = 20000
BW, BH, SCALE = 344, 220, 5     # 基準像素尺寸 → 放大 5 倍 = 1720x1100
GROUND = 178
PN = 12

def canvas(ch="f"):
    return np.tile(np.array(P[ch], np.uint8), (BH, BW, 1))

def pset(a, x, y, ch):
    if 0 <= x < BW and 0 <= y < BH and ch in P:
        a[y, x] = P[ch]

def vline(a, x, y0, y1, ch):
    for y in range(y0, y1): pset(a, x, y, ch)

def rect(a, x0, y0, x1, y1, ch):
    for y in range(y0, y1):
        for x in range(x0, x1): pset(a, x, y, ch)

# ── 中文字點陣化:回傳 set 像素的相對座標 list(size×size 內) ──
_fcache = {}
def glyph(ch, size):
    key = (ch, size)
    if key in _fcache: return _fcache[key]
    f = ImageFont.truetype(FONT, size)
    im = Image.new("L", (size, size), 0); d = ImageDraw.Draw(im)
    b = d.textbbox((0, 0), ch, font=f)
    ox = (size - (b[2] - b[0])) // 2 - b[0]
    oy = (size - (b[3] - b[1])) // 2 - b[1]
    d.text((ox, oy), ch, font=f, fill=255)
    arr = np.array(im) > 96
    pts = [(x, y) for y in range(size) for x in range(size) if arr[y, x]]
    _fcache[key] = pts; return pts

def stamp(a, cx, top, ch, size, col, hi=None):
    # 以像素字蓋章;hi=陰刻高光色(右下+1 先鋪,製造內凹刻痕)
    pts = glyph(ch, size); x0 = cx - size // 2
    if hi:
        for (x, y) in pts: pset(a, x0 + x + 1, top + y + 1, hi)
    for (x, y) in pts: pset(a, x0 + x, top + y, col)

# ── 竹林背景 ──
def bamboo(a, seed):
    rng = np.random.default_rng(seed)
    # 天光:上深下亮的綠,分帶(像素味)
    for y in range(GROUND):
        t = y / GROUND
        ch = "f" if t < 0.30 else ("g" if t < 0.62 else "h")
        for x in range(BW): a[y, x] = P[ch]
    # 遠景竹(細、暗、密)
    for _ in range(46):
        x = rng.integers(0, BW); w = 1
        body, edge, node = "f", "1", "2"
        top = rng.integers(-4, 30)
        vline(a, x, max(0, top), GROUND, body)
        vline(a, x + 1, max(0, top), GROUND, edge)
        for ny in range(max(0, top) + rng.integers(0, 16), GROUND, 22):
            pset(a, x, ny, node); pset(a, x + 1, ny, node)
    # 中景竹(粗、亮、綠節)
    for _ in range(16):
        x = rng.integers(6, BW - 6); w = rng.integers(3, 5)
        top = rng.integers(-6, 18)
        for i in range(w):
            c = "h" if i == 1 else ("g" if i < w - 1 else "f")
            vline(a, x + i, max(0, top), GROUND, c)
        vline(a, x, max(0, top), GROUND, "i")             # 左高光稜
        for ny in range(max(0, top) + rng.integers(4, 20), GROUND, 26):  # 竹節
            rect(a, x, ny, x + w, ny + 2, "f")
            rect(a, x, ny - 1, x + w, ny, "i")
            # 節上小枝
            if rng.random() < 0.5:
                pset(a, x - 1, ny + 1, "g"); pset(a, x - 2, ny, "g")
        # 竹葉叢(頂端)
        if top < 8:
            lx, ly = x + w // 2, max(2, top)
            for (dx, dy) in [(-3,-2),(-5,-4),(3,-3),(6,-5),(0,-6),(-2,-8),(4,-8)]:
                pset(a, lx + dx, ly + dy, "h"); pset(a, lx + dx, ly + dy - 1, "i")
    # 光斑(少量亮直帶,像林間漏光)
    for _ in range(4):
        x = rng.integers(0, BW)
        for y in range(0, GROUND, 2): pset(a, x, y, "i")

def ground(a):
    # 参道:泥土 + 石板 + 草
    rect(a, 0, GROUND, BW, BH, "x")
    rect(a, 0, GROUND, BW, GROUND + 2, "0")
    rect(a, 0, GROUND + 2, BW, GROUND + 5, "y")
    for x in range(0, BW, 14):                      # 石板縫
        vline(a, x, GROUND + 5, BH, "x")
    for _ in range(60):                             # 草
        import random
        pass
    rng = np.random.default_rng(7)
    for _ in range(70):
        x = rng.integers(0, BW); y = GROUND + rng.integers(0, 3)
        pset(a, x, y, "g"); pset(a, x, y - 1, "h")

# ── 單根石柱(玉垣)──
def pillar(a, px, pw, h, name, rank):
    top = GROUND - h; cap = max(6, pw // 2 + 2)
    # 帽(尖頂三角)
    for j in range(cap):
        half = int((pw / 2) * (j / cap))
        cx = px + pw // 2
        for x in range(cx - half, cx + half + 1):
            c = "4" if abs(x - cx) < half - 1 else "2"
            pset(a, x, top + j, c)
    # 柱身:左暗右暗中亮(圓柱體積)
    body_top = top + cap
    for i in range(pw):
        t = i / max(1, pw - 1)
        if i == 0 or i == pw - 1: c = "1"
        elif t < 0.28: c = "2"
        elif t < 0.72: c = "4"
        else: c = "3"
        vline(a, px + i, body_top, GROUND, c)
    vline(a, px + 1, body_top, GROUND, "5")           # 高光稜
    rect(a, px, GROUND - 2, px + pw, GROUND, "1")     # 柱基陰影
    # 名次(帽下方,前三鎏金)
    rc = "d" if rank <= 3 else "5"
    rhi = "b" if rank <= 3 else "2"
    stamp(a, px + pw // 2, body_top + 1, str(rank), 8, rc, rhi)
    # 暱稱(直書陰刻)
    nm = name[:3]; nsz = 15 if len(nm) <= 2 else 13
    ny = body_top + 11
    for c in nm:
        stamp(a, px + pw // 2, ny, c, nsz, "0", "5"); ny += nsz + 1

def render(donors, out, subtitle_note=""):
    a = canvas("f")
    bamboo(a, seed=42); ground(a)
    # 遠景鳥居剪影(暗紅,竹林中)
    tx = BW // 2
    rect(a, tx - 40, 40, tx + 40, 45, "j")
    rect(a, tx - 34, 52, tx + 34, 55, "j")
    rect(a, tx - 34, 40, tx - 30, GROUND - 30, "j")
    rect(a, tx + 30, 40, tx + 34, GROUND - 30, "j")
    # 石柱列(#1 最高最左)
    top = donors[:PN]; pw, gap = 18, 8
    total = len(top) * pw + (len(top) - 1) * gap
    x0 = (BW - total) // 2
    hi, lo = 128, 92
    for i, dn in enumerate(top):
        h = int(hi - (hi - lo) * i / max(1, PN - 1))
        pillar(a, x0 + i * (pw + gap), pw, h, dn["name"], i + 1)
    # 標題匾(頂部,像素中文)
    rect(a, tx - 78, 6, tx + 78, 30, "j")
    rect(a, tx - 78, 6, tx + 78, 8, "l")
    for i, c in enumerate("奉納芳名"):
        stamp(a, tx - 57 + i * 38, 10, c, 18, "e", "a")
    # 放大輸出(最近鄰保硬邊)
    img = Image.fromarray(a, "RGB").resize((BW * SCALE, BH * SCALE), Image.NEAREST)
    img.save(out); return out

if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "out"), exist_ok=True)
    demo = [
        {"name": "伯夷", "kou": 18}, {"name": "甜甜控", "kou": 12},
        {"name": "牙大戶", "kou": 9}, {"name": "阿彥", "kou": 7},
        {"name": "小美", "kou": 6}, {"name": "崇德", "kou": 5},
        {"name": "文瀚", "kou": 4}, {"name": "阿旺", "kou": 3},
        {"name": "里長伯", "kou": 3}, {"name": "花牙", "kou": 2},
        {"name": "阿福", "kou": 1}, {"name": "路人甲", "kou": 1},
    ]
    demo.sort(key=lambda x: -x["kou"])
    out = os.path.join(os.path.dirname(__file__), "out", "pillar16.png")
    render(demo, out)
    print("rendered", out)
