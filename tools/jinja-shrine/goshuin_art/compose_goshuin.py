# 御朱印圖(7款):washi底+明朝社名大書+副題+大朱印(圓)+季節配色小印(方)。$0程式合成。
# 字型(不進git):NotoSerifTC.otf 明朝
from PIL import Image, ImageDraw, ImageFont
SR="fonts/NotoSerifTC.otf"
def F(s): return ImageFont.truetype(SR,s)
# id, 副題, 大印2字, 季節小印1字, accent色, 底圖
V=[
 ("honsha","麻雀大明神","牌神","社",(176,30,30),"warm"),
 ("shogatsu","初詣・正月","初春","正",(198,150,30),"warm"),
 ("sakura","春櫻詣","櫻花","櫻",(206,92,132),"warm"),
 ("nagoshi","夏越大祓","祓除","夏",(46,96,160),"cool"),
 ("momiji","秋葉紅葉","紅楓","楓",(200,92,40),"warm"),
 ("okumiya","奧社牌神","奧社","奧",(122,64,150),"cool"),
 ("okumiya-season","奧社限定","限定","奧",(198,150,30),"cool"),
]
W=680
def cchar(d,cx,cy,ch,font,fill,stroke=0,scol=None):
    b=d.textbbox((0,0),ch,font=font,stroke_width=stroke)
    d.text((cx-(b[2]-b[0])/2-b[0],cy-(b[3]-b[1])/2-b[1]),ch,font=font,fill=fill,stroke_width=stroke,stroke_fill=scol or fill)
def vcol(d,cx,y0,s,font,fill,cell,stroke=0,scol=None):
    for i,ch in enumerate(s): cchar(d,cx,y0+cell*i+cell/2,ch,font,fill,stroke,scol)
def compose(vid,sub,seal2,acc1,acc,bg_):
    bg=Image.open(f"omikuji_art/bg/plain_{bg_}.png").convert("RGB")
    r=W/bg.width; H=int(bg.height*r); bg=bg.resize((W,H)); d=ImageDraw.Draw(bg)
    ink=(32,28,24); red=(170,30,30)
    # 奉拝(右上直書小)
    vcol(d,int(W*.85),int(H*.11),"奉拝",F(34),ink,int(H*.05))
    # 社名(中央大書,直排;縮小上移避免被朱印蓋)
    vcol(d,int(W*.42),int(H*.135),"甜甜神社",F(80),ink,int(H*.132),stroke=1,scol=ink)
    # 副題(社名右側,中字直排)
    vcol(d,int(W*.71),int(H*.185),sub,F(38),ink,int(H*.056))
    # 大朱印(圓,底部,不壓社名)
    cx,cy,rr=int(W*.42),int(H*.83),80
    d.ellipse([cx-rr,cy-rr,cx+rr,cy+rr],outline=red,width=6)
    d.ellipse([cx-rr+11,cy-rr+11,cx+rr-11,cy+rr-11],fill=red)
    vcol(d,cx,cy-int(rr*.52),seal2,F(50),(250,245,235),int(rr*.62))
    # 季節小印(方,右下,accent色白字)
    ss=84; sx,sy=int(W*.70),int(H*.80)
    d.rectangle([sx,sy,sx+ss,sy+ss],fill=acc)
    cchar(d,sx+ss/2,sy+ss/2,acc1,F(60),(250,247,240))
    out=f"goshuin_art/out/{vid}.png"; bg.save(out); print("ok",vid)
for v in V: compose(*v)
