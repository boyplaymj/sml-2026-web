# 御朱印圖(7款,對齊真品版式):中央書法大字壓大朱印 + 左邊日期 + 右邊社名 + 上/下小印。$0。
# 字型(不進git):NotoSerifTC.otf 明朝(全繁覆蓋)
from PIL import Image, ImageDraw, ImageFont
SR="fonts/NotoSerifTC.otf"
def F(s): return ImageFont.truetype(SR,s)
# id, 中央大字, 上小印字, accent色, 底
V=[
 ("honsha","牌神","社",(176,30,30),"warm"),
 ("shogatsu","初詣","正",(198,150,30),"warm"),
 ("sakura","春櫻","櫻",(206,92,132),"warm"),
 ("nagoshi","大祓","夏",(46,96,160),"cool"),
 ("momiji","紅葉","楓",(200,92,40),"warm"),
 ("okumiya","奧社","奧",(122,64,150),"cool"),
 ("okumiya-season","奧社","限",(198,150,30),"cool"),
]
W=680
def cchar(d,cx,cy,ch,font,fill,stroke=0,scol=None):
    b=d.textbbox((0,0),ch,font=font,stroke_width=stroke)
    d.text((cx-(b[2]-b[0])/2-b[0],cy-(b[3]-b[1])/2-b[1]),ch,font=font,fill=fill,stroke_width=stroke,stroke_fill=scol or fill)
def vcol(d,cx,y0,s,font,fill,cell,stroke=0,scol=None):
    for i,ch in enumerate(s): cchar(d,cx,y0+cell*i+cell/2,ch,font,fill,stroke,scol)
def compose(vid,big,acc1,acc,bg_):
    bg=Image.open(f"omikuji_art/bg/plain_{bg_}.png").convert("RGB")
    r=W/bg.width; H=int(bg.height*r); bg=bg.resize((W,H)); d=ImageDraw.Draw(bg)
    ink=(28,24,22); red=(172,32,32)
    # 右邊:奉拝 + 社名(甜甜神社)
    vcol(d,int(W*.855),int(H*.085),"奉拝",F(30),ink,int(H*.045))
    vcol(d,int(W*.855),int(H*.26),"甜甜神社",F(40),ink,int(H*.062))
    # 左邊:日期(占位 slot)
    vcol(d,int(W*.145),int(H*.18),"〇年〇月〇日",F(36),ink,int(H*.058))
    # 上方小印(季節accent色,圓,白字)
    tx,ty,tr=int(W*.50),int(H*.135),44
    d.ellipse([tx-tr,ty-tr,tx+tr,ty+tr],fill=acc); cchar(d,tx,ty,acc1,F(46),(250,247,240))
    # 中央:大朱印(方框)+ 書法大字壓印上
    cx,cy,hf=int(W*.50),int(H*.47),128
    d.rectangle([cx-hf,cy-hf,cx+hf,cy+hf],outline=red,width=9)
    d.rectangle([cx-hf+16,cy-hf+16,cx+hf-16,cy+hf-16],outline=red,width=3)
    # 大字(2字直排,墨,粗描邊;壓在紅框上)
    vcol(d,cx,cy-int(hf*.60),big,F(150),ink,int(hf*1.20),stroke=3,scol=ink)
    # 下方圓朱印(白字)
    bx,by,br=int(W*.50),int(H*.80),66
    d.ellipse([bx-br,by-br,bx+br,by+br],fill=red); cchar(d,bx,by,"甜",F(72),(250,245,235))
    out=f"goshuin_art/out/{vid}.png"; bg.save(out); print("ok",vid)
for v in V: compose(*v)
