# 甜甜神社 御神籤籤紙 v3(傳統版式,全 Noto Serif 明朝體)
# 字型(不進git): NotoSerifTC.otf <- github.com/notofonts/noto-cjk Serif/OTF/TraditionalChinese
from PIL import Image, ImageDraw, ImageFont
SR="fonts/NotoSerifTC.otf"
def F(s): return ImageFont.truetype(SR,s)
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
JI=set(["大吉","吉","中吉","小吉","末吉","末小吉"])
ORDER=["大吉","吉","中吉","小吉","末吉","末小吉","凶","小凶","半凶","末凶","大凶"]
W=680
def cchar(d,cx,cy,ch,font,fill,stroke=0,scol=None):
    b=d.textbbox((0,0),ch,font=font,stroke_width=stroke); w=b[2]-b[0]; h=b[3]-b[1]
    d.text((cx-w/2-b[0], cy-h/2-b[1]),ch,font=font,fill=fill,stroke_width=stroke,stroke_fill=scol or fill)
def vcol(d,cx,y0,chars,font,fill,cell):
    for i,ch in enumerate(chars): cchar(d,cx,y0+cell*i+cell/2,ch,font,fill)
def compose(rank,idx):
    ji=rank in JI
    bg=Image.open(f"omikuji_art/bg/{'plain_warm' if ji else 'plain_cool'}.png").convert("RGB")
    r=W/bg.width; H=int(bg.height*r); bg=bg.resize((W,H)); d=ImageDraw.Draw(bg)
    ink=(30,28,26); red=(176,32,32); rcol=red if ji else (24,24,24)
    # 階名(明朝粗描邊,置中上)
    n=len(rank); rsz={1:140,2:124,3:100}.get(n,96); rf=F(rsz)
    ws=[d.textbbox((0,0),c,font=rf,stroke_width=3)[2]-d.textbbox((0,0),c,font=rf,stroke_width=3)[0] for c in rank]
    gap=int(rsz*0.08); tw=sum(ws)+gap*(n-1); x=(W-tw)//2; yc=int(H*0.145)
    for c,wd in zip(rank,ws): cchar(d,x+wd/2,yc,c,rf,rcol,3,rcol); x+=wd+gap
    # 分隔線
    ly=int(H*0.255)
    d.line([(int(W*0.18),ly),(int(W*0.82),ly)],fill=(160,140,120),width=2)
    # 詩:4欄直排右起左行,置中
    poem=POEMS[rank]; csz=70; cell=int(csz*1.32)
    y0=int(H*0.315); centers=[int(W*(0.685-0.145*i)) for i in range(4)]  # 右→左
    for i,line in enumerate(poem): vcol(d,centers[i],y0,line,F(csz),ink,cell)
    # 甜甜神社(右上直題,清楚分開)
    vcol(d,int(W*0.845),int(H*0.30),"甜甜神社",F(28),(120,105,92),int(H*0.046))
    # 朱印(底右)
    ss=98; sx=int(W*0.70); sy=int(H*0.83); sq=Image.new("RGB",(ss,ss),red); bg.paste(sq,(sx,sy))
    seal="福" if ji else "祓"; sf=F(70); cchar(d,sx+ss/2,sy+ss/2,seal,sf,(250,245,235))
    # 麻雀大明神(底左小caption)
    vcol(d,int(W*0.20),int(H*0.80),"麻雀大明神",F(24),(140,122,105),int(H*0.036))
    out=f"omikuji_art/out/v3_{idx:02d}_{rank}.png"; bg.save(out); print("ok",out)
for i,rk in enumerate(ORDER,1): compose(rk,i)
