# 甜甜神社 御神籤籤紙(傳統版式:階名在上+五言四句直排右起左行)
# 字型(不進git,re-download):
#   MaShanZheng-Regular.ttf(毛筆,階名) <- github.com/google/fonts ofl/mashanzheng
#   NotoSerifTC.otf(明朝,詩文全繁) <- github.com/notofonts/noto-cjk Serif/OTF/TraditionalChinese
from PIL import Image, ImageDraw, ImageFont
import os
BR="fonts/MaShanZheng-Regular.ttf"      # 毛筆(階名/印)
SR="fonts/NotoSerifTC.otf"              # 明朝(詩文)
def FB(s): return ImageFont.truetype(BR,s)
def FS(s): return ImageFont.truetype(SR,s)
POEMS={
"大吉":["牌山凝瑞氣","高台自摸成","滿座皆仰望","莫作等閒輕"],
"吉":["春風入牌局","聽張逐手來","守正無躁進","福自摸中開"],
"中吉":["兩面聽已成","靜候一張來","心平牌路順","躁進反成災"],
"小吉":["小牌亦成台","積少福自來","莫嫌張數薄","穩紮運方開"],
"末吉":["此局牌未順","聽張猶在遲","耐得洗牌過","福在後半時"],
"末小吉":["牌風正平淡","未見大三元","安分守聽候","微福亦堪憐"],
"凶":["牌山藏暗湧","摸來盡孤張","收斂宜自守","險處莫輕嘗"],
"小凶":["連莊忽中斷","聽張總落空","退步且觀局","勿與天爭鋒"],
"半凶":["牌局半傾頹","放銃在目前","謹守休妄動","繫神方保全"],
"末凶":["終局見敗象","滿手是孤張","唯有繫神願","方免厄加身"],
"大凶":["牌山盡崩摧","八方皆放銃","非繫神不可","穢氣噬無窮"],
}
JI=set("大吉 吉 中吉 小吉 末吉 末小吉".split())
ORDER=["大吉","吉","中吉","小吉","末吉","末小吉","凶","小凶","半凶","末凶","大凶"]
W=680
def cchar(d,cx,cy,ch,font,fill):
    b=d.textbbox((0,0),ch,font=font); w=b[2]-b[0]; h=b[3]-b[1]
    d.text((cx-w/2-b[0], cy-h/2-b[1]), ch, font=font, fill=fill)
def vcol(d,cx,y0,chars,font,fill,cell):
    for i,ch in enumerate(chars): cchar(d,cx,y0+i*cell+cell/2,ch,font,fill)
def compose(rank,idx):
    ji = rank in JI
    bg=Image.open(f"omikuji_art/bg/{'plain_warm' if ji else 'plain_cool'}.png").convert("RGB")
    r=W/bg.width; H=int(bg.height*r); bg=bg.resize((W,H)); d=ImageDraw.Draw(bg)
    ink=(26,26,26); red=(178,30,30); rank_col= red if ji else (20,20,20)
    # 右緣直題:麻雀大明神御籤
    vcol(d,int(W*0.90),int(H*0.09),"麻雀大明神御籤",FS(26),(120,105,92),int(H*0.052))
    # 階名(毛筆,上方置中)
    n=len(rank); rsz={1:150,2:132,3:96}.get(n,90)
    rf=FB(rsz); tot=0; hs=[]
    for c in rank:
        b=rf.getbbox(c); hs.append(b[3]-b[1])
    # 階名橫排置中
    widths=[rf.getbbox(c)[2]-rf.getbbox(c)[0] for c in rank]
    gap=int(rsz*0.06); tw=sum(widths)+gap*(n-1); x=(W-tw)//2; ytop=int(H*0.075)
    for c,wd in zip(rank,widths):
        b=rf.getbbox(c); d.text((x-b[0], ytop-b[1]), c, font=rf, fill=rank_col); x+=wd+gap
    # 分隔線
    ly=int(H*0.235); d.line([(int(W*0.15),ly),(int(W*0.85),ly)],fill=(150,130,110),width=2)
    # 五言四句直排,右起左行
    poem=POEMS[rank]; csz=76; cell=int(csz*1.34)
    y0=int(H*0.30)
    xr=int(W*0.775); xstep=int(W*0.155)   # 右→左
    for i,line in enumerate(poem):
        vcol(d,xr-i*xstep,y0,line,FS(csz),ink,cell)
    # 底部朱印
    ss=104; sx=int(W*0.145); sy=int(H*0.845)
    sq=Image.new("RGB",(ss,ss),red); bg.paste(sq,(sx,sy))
    sf=FB(74); seal="福" if ji else "祓"; b=sf.getbbox(seal)
    d.text((sx+(ss-(b[2]-b[0]))/2-b[0], sy+(ss-(b[3]-b[1]))/2-b[1]),seal,font=sf,fill=(250,245,235))
    # 甜甜神社(底右直題小)
    vcol(d,int(W*0.86),int(H*0.80),"甜甜神社",FS(30),(120,105,92),int(H*0.045))
    out=f"omikuji_art/out/v2_{idx:02d}_{rank}.png"; bg.save(out); print("ok",out)
for i,rk in enumerate(ORDER,1): compose(rk,i)
