# 御朱印帳「封面」圖(布面書套 + 題簽「御朱印帳」+ 社名)。多色,$0 程式合成。
# 用法:python3 goshuin_art/compose_cover.py            → 產全色到 goshuin_art/out/cover_<id>.png
#       python3 goshuin_art/compose_cover.py <id> <out> → 單張(bot 免用,素材固定可預生成上圖床)
import sys, math
from PIL import Image, ImageDraw, ImageFont
import numpy as np

SR = "fonts/JinXiHaoLong.otf"   # 金梅浩龍(題簽大書「御朱印帳」)
SIDE = "fonts/SideFont.ttf"     # ZHLYSS_T(社名小字)
def F(s): return ImageFont.truetype(SR, s)
def FS(s): return ImageFont.truetype(SIDE, s)
W, H = 680, 964

# 色票:id -> (布底色, 深色紋, 題簽紙色, 墨色, 金框色)
COLORS = {
    "navy":      ((31, 47, 77),  (22, 35, 60),  (238, 232, 214), (26, 22, 20), (198, 168, 92)),
    "vermilion": ((166, 46, 40), (140, 34, 30), (240, 234, 216), (26, 22, 20), (206, 176, 98)),
}

def cchar(d, cx, cy, ch, font, fill):
    b = d.textbbox((0, 0), ch, font=font)
    d.text((cx - (b[2]-b[0])/2 - b[0], cy - (b[3]-b[1])/2 - b[1]), ch, font=font, fill=fill)
def vcol(d, cx, y0, s, font, fill, cell):
    for i, ch in enumerate(s): cchar(d, cx, y0 + cell*i + cell/2, ch, font, fill)

def cloth(base, dark, seed=7):
    # 布面質感:底色 + 麻葉風細格暗紋 + 顆粒
    rng = np.random.default_rng(seed)
    a = np.tile(np.array(base, np.float32), (H, W, 1))
    # 斜向織紋(細)
    yy, xx = np.mgrid[0:H, 0:W]
    weave = (np.sin((xx+yy)/3.0) + np.sin((xx-yy)/3.0)) * 3.0
    a += weave[..., None]
    a += rng.normal(0, 1, (H, W, 1)).astype(np.float32) * 3.5
    # 邊角壓深(書套厚重感)
    d2 = ((xx-W/2)/(W/2))**2 + ((yy-H/2)/(H/2))**2
    a *= (1 - 0.10*d2)[..., None]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGB")

def compose(cid, out=None):
    base, dark, paper, ink, gold = COLORS[cid]
    img = cloth(base, dark); d = ImageDraw.Draw(img)
    # 金色外框(雙線)
    d.rectangle([18, 18, W-18, H-18], outline=gold, width=3)
    d.rectangle([28, 28, W-28, H-28], outline=gold, width=1)
    # 題簽(左偏上、直長方、米紙色 + 細墨框)
    lx0, ly0, lw, lh = int(W*0.12), int(H*0.10), int(W*0.26), int(H*0.62)
    d.rectangle([lx0, ly0, lx0+lw, ly0+lh], fill=paper, outline=(60, 50, 44), width=2)
    # 題簽字「御朱印帳」直書大書
    tsz = int(lw*0.72); cell = int(tsz*1.14)
    vcol(d, lx0+lw//2, ly0+int(lh*0.055), "御朱印帳", F(tsz), ink, cell)
    # 社名(右下小字直書)
    ssz = int(W*0.046)
    vcol(d, int(W*0.80), int(H*0.60), "甜甜神社", FS(ssz), paper, int(ssz*1.15))
    # 中央社紋(圓,燙金線)
    cx, cy, rr = int(W*0.62), int(H*0.30), int(W*0.11)
    d.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], outline=gold, width=4)
    d.ellipse([cx-rr+8, cy-rr+8, cx+rr-8, cy+rr-8], outline=gold, width=1)
    for k in range(3):
        a2 = math.radians(90+k*120); px = cx+int(rr*.55*math.cos(a2)); py = cy-int(rr*.55*math.sin(a2))
        d.ellipse([px-6, py-6, px+6, py+6], fill=gold)
    cchar(d, cx, cy, "牌", F(int(rr*0.9)), gold)
    outp = out or f"goshuin_art/out/cover_{cid}.png"
    img.save(outp); print("ok", cid, outp)

if len(sys.argv) == 3:
    compose(sys.argv[1], sys.argv[2])
else:
    for c in COLORS: compose(c)
