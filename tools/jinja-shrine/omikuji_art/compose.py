# 甜甜神社 御神籤籤紙合成器。字型來源(不進git,re-download):
#   MaShanZheng-Regular.ttf <- github.com/google/fonts/raw/main/ofl/mashanzheng/
# 用法: python3 omikuji_art/compose.py  (輸出 omikuji_art/out/*.png)
from PIL import Image, ImageDraw, ImageFont
import os
FONT="fonts/MaShanZheng-Regular.ttf"
def F(sz): return ImageFont.truetype(FONT, sz)
# rank -> (tier, ink color, seal char)
RANKS = [
 ("大吉","ji",(178,30,30),"福"),
 ("吉","ji",(178,30,30),"福"),
 ("中吉","ji",(178,30,30),"福"),
 ("小吉","ji",(178,30,30),"福"),
 ("末吉","ji",(178,30,30),"福"),
 ("末小吉","ji",(178,30,30),"福"),
 ("凶","kyo",(28,28,28),"祓"),
 ("小凶","kyo",(28,28,28),"祓"),
 ("半凶","kyo",(28,28,28),"祓"),
 ("末凶","kyo",(28,28,28),"祓"),
 ("大凶","kyo",(20,20,20),"祓"),
]
W=600
def vtext(draw,cx,y0,chars,font,fill,gap):
    for ch in chars:
        b=draw.textbbox((0,0),ch,font=font)
        w=b[2]-b[0]; h=b[3]-b[1]
        draw.text((cx-w/2-b[0], y0-b[1]), ch, font=font, fill=fill)
        y0+=h+gap
    return y0
def compose(rank,tier,ink,seal,idx):
    bg = Image.open(f"omikuji_art/bg/{'paper_warm' if tier=='ji' else 'paper_cool'}.png").convert("RGB")
    r = W/bg.width; H=int(bg.height*r)
    bg = bg.resize((W,H))
    d = ImageDraw.Draw(bg)
    # side labels
    vtext(d, int(W*0.80), int(H*0.10), "甜甜神社", F(46), (60,50,45), 8)
    vtext(d, int(W*0.20), int(H*0.12), "麻雀大明神", F(34), (90,80,72), 6)
    # center rank (fit by count)
    n=len(rank)
    sz = {1:230,2:190,3:132}.get(n,120)
    # vertical block height
    tmp=F(sz); hh=[tmp.getbbox(c)[3]-tmp.getbbox(c)[1] for c in rank]
    gap=int(sz*0.12); total=sum(hh)+gap*(n-1)
    y0=(H-total)//2 - int(H*0.03)
    vtext(d, W//2, y0, rank, F(sz), ink, gap)
    # bottom seal (red square, white char)
    ss=118; sx=(W-ss)//2; sy=int(H*0.80)
    sq=Image.new("RGB",(ss,ss),(178,30,30)); Image.Image.paste(bg,sq,(sx,sy))
    sd=ImageDraw.Draw(bg); sf=F(84); b=sd.textbbox((0,0),seal,font=sf)
    sd.text((sx+(ss-(b[2]-b[0]))/2-b[0], sy+(ss-(b[3]-b[1]))/2-b[1]), seal, font=sf, fill=(250,245,235))
    out=f"omikuji_art/out/{idx:02d}_{rank}.png"
    bg.save(out); print("ok",out)
for i,(rk,ti,ink,se) in enumerate(RANKS,1):
    compose(rk,ti,ink,se,i)
