# 石柱(奉納芳名)圖:参道玉垣風,一人一柱,前12名。純PIL+numpy程式石材質感,$0。
# 假資料先跑;正式接 sweetbot-shrine-pillar 掃出 top12(暱稱+奉納口數)再餵 render()。
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from fontTools.ttLib import TTFont as _TT

FZH = "fonts/ShiShiRuYi.ttf"     # 獅尸如意(暱稱/標題主用)
FLAT = "fonts/NotoSerifTC.otf"   # 明朝(數字/拉丁回退)
_zh = set(_TT(FZH).getBestCmap().keys())
def Fz(s): return ImageFont.truetype(FZH, s)
def Fl(s): return ImageFont.truetype(FLAT, s)
def gf(ch, s): return Fz(s) if ord(ch) in _zh else Fl(s)

KOU = 20000  # 一口奉納額(牙)
W, H = 1440, 880
GROUND = 792         # 参道地面線
PN = 12              # 上圖名額

def cchar(d, cx, cy, ch, font, fill):
    b = d.textbbox((0, 0), ch, font=font)
    d.text((cx-(b[2]-b[0])/2-b[0], cy-(b[3]-b[1])/2-b[1]), ch, font=font, fill=fill)

def granite(w, h, seed):
    # 花崗岩灰:低頻斑駁+細顆粒+左光右暗(側光立體)
    rng = np.random.default_rng(seed)
    base = np.full((h, w, 3), (150, 148, 145), np.float32)
    lo = rng.integers(0, 256, (max(2, h//14), max(2, w//8))).astype(np.uint8)
    mot = (np.asarray(Image.fromarray(lo).resize((w, h), Image.BICUBIC)).astype(np.float32)-128)/128
    base += mot[..., None]*16
    base += rng.normal(0, 1, (h, w, 1)).astype(np.float32)*5      # 顆粒
    xr = np.linspace(1.10, 0.80, w)[None, :, None]               # 左亮右暗(側光)
    base *= xr
    return base

def pillar(w, h, name, kou, rank, seed):
    # 回傳 RGBA 石柱(含金字塔頂帽 + 陰刻暱稱 + 奉納額 + 名次)
    cap = int(w*0.42)                       # 帽高
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g = granite(w, h, seed)
    body = Image.fromarray(g.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.polygon([(w//2, 2), (w-2, cap), (2, cap)], fill=255)       # 尖頂帽
    md.rectangle([2, cap, w-2, h-2], fill=255)                    # 柱身
    img.paste(body, (0, 0), mask)
    d = ImageDraw.Draw(img)
    ink, edge = (52, 50, 48), (250, 249, 246)
    # 帽底分隔線 + 柱身左右邊緣立體
    d.line([(6, cap), (w-6, cap)], fill=(90, 88, 85), width=2)
    d.line([(3, cap), (3, h-3)], fill=(240, 238, 234, 120), width=2)
    d.line([(w-3, cap), (w-3, h-3)], fill=(70, 68, 66, 140), width=2)
    # 名次(帽上,前三鎏金)
    gold = (198, 158, 60)
    rc = gold if rank <= 3 else (70, 68, 66)
    cchar(d, w//2, cap-int(w*0.16), str(rank), Fl(int(w*0.30)), rc)
    # 陰刻:先亮邊(右下+1)後暗字 → 內凹刻痕感
    def engrave(cx, cy, ch, font, col=ink):
        cchar(d, cx+1, cy+1, ch, font, edge)
        cchar(d, cx, cy, ch, font, col)
    # 暱稱(直書,由帽下往下)
    nm = name[:5]
    nsz = int(w*0.52) if len(nm) <= 3 else int(w*0.40)
    ny = cap + int(w*0.42)
    for ch in nm:
        engrave(w//2, ny, ch, gf(ch, nsz)); ny += int(nsz*1.06)
    # 奉納額(柱身下段,小字直書「N口」)
    amt = f"{kou*KOU//10000}萬" if kou*KOU >= 10000 else str(kou*KOU)
    tail = f"奉{kou}口"
    ty = h - int(w*0.30)*len(tail) - int(w*0.10)
    for ch in tail:
        engrave(w//2, ty, ch, gf(ch, int(w*0.26)), (72, 68, 64)); ty += int(w*0.30)
    return img

def scene():
    im = Image.new("RGB", (W, H), (222, 224, 226))
    a = np.asarray(im).astype(np.float32)
    # 天空:上淡青→下暖白 漸層
    yr = np.linspace(0, 1, H)[:, None, None]
    top, bot = np.array([206, 214, 220]), np.array([238, 232, 220])
    a[:] = top*(1-yr)+bot*yr
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(im)
    # 遠景鳥居剪影(中央,淡)
    tx, tw2, ty0 = W//2, 150, 250
    tor = (192, 150, 120)
    d.rectangle([tx-tw2, ty0, tx+tw2, ty0+16], fill=tor)          # 笠木
    d.rectangle([tx-tw2+22, ty0+40, tx+tw2-22, ty0+52], fill=tor)  # 貫
    d.rectangle([tx-tw2+14, ty0, tx-tw2+30, GROUND], fill=tor)
    d.rectangle([tx+tw2-30, ty0, tx+tw2-14, GROUND], fill=tor)
    # 参道地面
    d.rectangle([0, GROUND, W, H], fill=(196, 188, 176))
    d.rectangle([0, GROUND, W, GROUND+6], fill=(150, 142, 130))
    # 石板紋
    for gx in range(0, W, 90):
        d.line([(gx, GROUND+8), (gx, H)], fill=(178, 170, 158), width=2)
    return im

def render(donors, out="pillar_art/out/pillar.png", subtitle=""):
    # donors: [{"name":..., "kou":...}] 已依 kou 由大到小排序;取前12
    im = scene()
    d = ImageDraw.Draw(im)
    # 標題橫額
    ttl = "甜甜神社　奉納芳名"
    tf = Fz(58); x = W//2
    tb = d.textbbox((0, 0), ttl, font=tf)
    d.rectangle([x-(tb[2]-tb[0])//2-40, 40, x+(tb[2]-tb[0])//2+40, 118],
                fill=(139, 30, 30))
    cchar(d, x, 79, "　".join(list("")) or ttl, tf, (250, 244, 232)) if False else \
        d.text((x-(tb[2]-tb[0])/2-tb[0], 79-(tb[3]-tb[1])/2-tb[1]), ttl, font=tf, fill=(250, 244, 232))
    if subtitle:
        sf = Fl(24)
        sb = d.textbbox((0, 0), subtitle, font=sf)
        d.text((x-(sb[2]-sb[0])/2, 126), subtitle, font=sf, fill=(90, 80, 70))
    # 石柱列(#1最高最左,遞減)
    top = donors[:PN]
    pw, gap = 90, 18
    total = len(top)*pw + (len(top)-1)*gap
    x0 = (W-total)//2
    hi, lo = 470, 372
    for i, dn in enumerate(top):
        h = int(hi-(hi-lo)*i/max(1, PN-1))
        px = x0 + i*(pw+gap)
        pil = pillar(pw, h, dn["name"], dn["kou"], i+1, seed=1000+i*7)
        # 落地陰影
        sh = Image.new("RGBA", (pw+30, 26), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse([0, 0, pw+30, 26], fill=(40, 36, 30, 70))
        im.paste(Image.alpha_composite(
            Image.new("RGBA", sh.size, (0, 0, 0, 0)), sh).convert("RGB")
            if False else sh, (px-15, GROUND-8), sh)
        im.paste(pil, (px, GROUND-h+4), pil)
    im.save(out)
    return out

if __name__ == "__main__":
    import os
    os.makedirs("pillar_art/out", exist_ok=True)
    demo = [
        {"name": "伯夷", "kou": 18}, {"name": "甜甜控", "kou": 12},
        {"name": "牙齒大戶", "kou": 9}, {"name": "阿彥", "kou": 7},
        {"name": "小美", "kou": 6}, {"name": "崇德", "kou": 5},
        {"name": "文瀚", "kou": 4}, {"name": "gameboy", "kou": 3},
        {"name": "里長伯", "kou": 3}, {"name": "花牙", "kou": 2},
        {"name": "阿旺", "kou": 1}, {"name": "路人甲", "kou": 1},
    ]
    demo.sort(key=lambda x: -x["kou"])
    render(demo, subtitle="全時累計 · 一口 = 20,000 牙")
    print("rendered pillar.png")
