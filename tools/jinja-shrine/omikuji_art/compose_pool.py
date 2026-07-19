# 逐籤出圖(33張):讀 omikuji_pool.json,套 v6 定稿版式。圖文相符。
import json
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont as _TT
SR="fonts/NotoSerifTC.otf"        # 明朝(缺字回退,全覆蓋)
SIDE="fonts/SideFont.ttf"         # ZHLYSS_T(全部文字主用字型;使用者指定)
def F(s): return ImageFont.truetype(SR,s)
def FS(s): return ImageFont.truetype(SIDE,s)
_sd=set(_TT(SIDE).getBestCmap().keys())
def gf(ch,sz): return FS(sz) if ord(ch) in _sd else F(sz)  # 主用ZHLYSS,缺字(詩~13/解~12)回退明朝
POOL=json.load(open("omikuji_pool.json"))["pool"]
JI=set(["大吉","吉","中吉","小吉","末吉","末小吉"])
AXES=["商賣","爭事","學問","健康","戀愛","旅行"]
W=680
def cchar(d,cx,cy,ch,font,fill,stroke=0):
    b=d.textbbox((0,0),ch,font=font,stroke_width=stroke)
    d.text((cx-(b[2]-b[0])/2-b[0],cy-(b[3]-b[1])/2-b[1]),ch,font=font,fill=fill,stroke_width=stroke,stroke_fill=fill)
def vcol(d,cx,y0,chars,font,fill,cell,stroke=0):
    for i,ch in enumerate(chars): cchar(d,cx,y0+cell*i+cell/2,ch,font,fill,stroke)
def gvcol(d,cx,y0,chars,sz,fill,cell,stroke=0):  # 逐字挑字型(ZHLYSS優先,缺回退明朝)
    for i,ch in enumerate(chars): cchar(d,cx,y0+cell*i+cell/2,ch,gf(ch,sz),fill,stroke)
def compose(s):
    rank=s["rank"]; ji=rank in JI
    bg=Image.open(f"omikuji_art/bg/{'plain_warm' if ji else 'plain_cool'}.png").convert("RGB")
    r=W/bg.width; H=int(bg.height*r); bg=bg.resize((W,H)); d=ImageDraw.Draw(bg)
    ink=(28,26,24); red=(170,30,30); rcol=red if ji else (22,22,22); line=(110,95,80)
    # 標題方框
    hx0,hx1,hy0,hy1=int(W*.22),int(W*.78),int(H*.095),int(H*.19)
    d.rectangle([hx0,hy0,hx1,hy1],outline=ink,width=3)
    n=len(rank); rsz={1:82,2:72,3:56}.get(n,54); rf=FS(rsz)  # 階名=ZHLYSS_T
    ws=[d.textbbox((0,0),c,font=rf,stroke_width=2)[2]-d.textbbox((0,0),c,font=rf,stroke_width=2)[0] for c in rank]
    gap=int(rsz*.08); tw=sum(ws)+gap*(n-1); x=(W-tw)//2; ycen=(hy0+hy1)//2
    for c,wd in zip(rank,ws): cchar(d,x+wd/2,ycen,c,rf,rcol,2); x+=wd+gap
    gvcol(d,int(W*.885),int(H*.10),"甜甜神社",18,(120,105,92),int(H*.034))
    # 詩文直格 4 欄(右起左行)
    gx0,gx1=int(W*.205),int(W*.795); gy0,gy1=int(H*.25),int(H*.55)
    d.rectangle([gx0,gy0,gx1,gy1],outline=line,width=2)
    for k in range(1,4):
        lx=gx0+(gx1-gx0)*k//4; d.line([(lx,gy0),(lx,gy1)],fill=line,width=1)
    poem=s["shi"]; cw=(gx1-gx0)/4; cell=(gy1-gy0)/5; csz=42
    for i,ln in enumerate(poem):
        cx=int(gx1-cw*(i+0.5)); gvcol(d,cx,gy0+int(cell*0.1),ln,csz,ink,cell)
    # 下半六分項解說(右起左行)
    ix0,ix1=int(W*.205),int(W*.795); iy0=int(H*.615)
    d.line([(ix0,iy0),(ix1,iy0)],fill=line,width=1)
    icw=(ix1-ix0)/6; icell=int(H*.030); isz=18; lsz=19
    for i,ax in enumerate(AXES):
        cx=int(ix1-icw*(i+0.5))
        gvcol(d,cx,iy0+int(H*.012),ax,lsz,red if ji else (60,50,45),icell)
        gvcol(d,cx,iy0+int(H*.012)+icell*2+6,s["items"][ax]["text"],isz,ink,icell)
    # 朱印
    ss=58; sx=int(W*.76); sy=int(H*.91); sq=Image.new("RGB",(ss,ss),red); bg.paste(sq,(sx,sy))
    sc="福" if ji else "祓"; cchar(d,sx+ss/2,sy+ss/2,sc,gf(sc,40),(250,245,235))
    out=f"omikuji_art/out/pool_{s['omikujiId']}.png"; bg.save(out); return out
for s in POOL: compose(s)
print("rendered",len(POOL),"slips")
