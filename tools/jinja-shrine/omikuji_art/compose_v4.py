# 甜甜神社 御神籤籤紙 v4(1:1 仿淺草寺籤:標題方框+詩文直格欄線+下半逐項解說直排)
# 字型(不進git): NotoSerifTC.otf 明朝, github.com/notofonts/noto-cjk Serif/OTF/TraditionalChinese
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
# 六分項:(類名2字, 解4字) 右→左順序 商賣/爭事/學問/健康/戀愛/旅行
INTERP={
"大吉":[("商賣","財源連莊"),("爭事","逢戰必勝"),("學問","數盡向聽"),("健康","氣血調和"),("戀愛","良緣天成"),("旅行","途中拾福")],
"吉":[("商賣","財路漸寬"),("爭事","對局占先"),("學問","讀牌有神"),("健康","精神飽滿"),("戀愛","緣分升溫"),("旅行","出行平安")],
"中吉":[("商賣","財運平穩"),("爭事","勝負相當"),("學問","靈感忽至"),("健康","作息宜正"),("戀愛","宜緩不急"),("旅行","途順留意")],
"小吉":[("商賣","微利可圖"),("爭事","小勝勿貪"),("學問","用功見效"),("健康","身心俱佳"),("戀愛","慢火為上"),("旅行","近遊得福")],
"末吉":[("商賣","目下平淡"),("爭事","初戰後揚"),("學問","厚積薄發"),("健康","漸入佳境"),("戀愛","靜待花開"),("旅行","遠行宜延")],
"末小吉":[("商賣","財氣微弱"),("爭事","宜避其鋒"),("學問","貴在有恆"),("健康","尚可勿勞"),("戀愛","順其自然"),("旅行","平安勿貪")],
"凶":[("商賣","財路受阻"),("爭事","對局宜守"),("學問","唯讀尚可"),("健康","易倦調息"),("戀愛","緣滯勿求"),("旅行","遠行不宜")],
"小凶":[("商賣","破財緊守"),("爭事","連敗暫收"),("學問","心浮宜靜"),("健康","小恙早歇"),("戀愛","忍讓為上"),("旅行","途阻改期")],
"半凶":[("商賣","財損止血"),("爭事","敗象速退"),("學問","事倍功半"),("健康","體虛忌勞"),("戀愛","緣薄冷靜"),("旅行","不宜遠行")],
"末凶":[("商賣","大破財戒"),("爭事","逢戰必敗"),("學問","神思宜休"),("健康","病氣速養"),("戀愛","緣盡勿執"),("旅行","千萬勿行")],
"大凶":[("商賣","傾家緊守"),("爭事","一戰即潰"),("學問","心神宜停"),("健康","速歇速養"),("戀愛","緣斷勿纏"),("旅行","勿出遠門")],
}
JI=set(["大吉","吉","中吉","小吉","末吉","末小吉"])
ORDER=["大吉","吉","中吉","小吉","末吉","末小吉","凶","小凶","半凶","末凶","大凶"]
W=680
def cchar(d,cx,cy,ch,font,fill,stroke=0):
    b=d.textbbox((0,0),ch,font=font,stroke_width=stroke)
    d.text((cx-(b[2]-b[0])/2-b[0], cy-(b[3]-b[1])/2-b[1]),ch,font=font,fill=fill,stroke_width=stroke,stroke_fill=fill)
def vcol(d,cx,y0,chars,font,fill,cell,stroke=0):
    for i,ch in enumerate(chars): cchar(d,cx,y0+cell*i+cell/2,ch,font,fill,stroke)
def compose(rank,idx):
    ji=rank in JI
    bg=Image.open(f"omikuji_art/bg/{'plain_warm' if ji else 'plain_cool'}.png").convert("RGB")
    r=W/bg.width; H=int(bg.height*r); bg=bg.resize((W,H)); d=ImageDraw.Draw(bg)
    ink=(28,26,24); red=(170,30,30); rcol=red if ji else (22,22,22); line=(110,95,80)
    # ── 標題方框 ──
    hx0,hx1,hy0,hy1=int(W*.22),int(W*.78),int(H*.095),int(H*.19)
    d.rectangle([hx0,hy0,hx1,hy1],outline=ink,width=3)
    n=len(rank); rsz={1:78,2:68,3:54}.get(n,52); rf=F(rsz)
    ws=[d.textbbox((0,0),c,font=rf,stroke_width=2)[2]-d.textbbox((0,0),c,font=rf,stroke_width=2)[0] for c in rank]
    gap=int(rsz*.08); tw=sum(ws)+gap*(n-1); x=(W-tw)//2; ycen=(hy0+hy1)//2
    for c,wd in zip(rank,ws): cchar(d,x+wd/2,ycen,c,rf,rcol,2); x+=wd+gap
    # 甜甜神社(標題框右上外側直題小)
    vcol(d,int(W*.885),int(H*.10),"甜甜神社",F(18),(120,105,92),int(H*.034))
    # ── 詩文直格 4 欄(右起左行),含欄線 ──
    gx0,gx1=int(W*.205),int(W*.795); gy0,gy1=int(H*.25),int(H*.55)
    d.rectangle([gx0,gy0,gx1,gy1],outline=line,width=2)
    for k in range(1,4):
        lx=gx0+(gx1-gx0)*k//4; d.line([(lx,gy0),(lx,gy1)],fill=line,width=1)
    poem=POEMS[rank]; cw=(gx1-gx0)/4; cell=(gy1-gy0)/5; csz=42
    for i,ln in enumerate(poem):
        cx=int(gx1-cw*(i+0.5))   # 右→左
        vcol(d,cx,gy0+int(cell*0.1),ln,F(csz),ink,cell)
    # ── 下半:六分項解說直排(右起左行) ──
    ix0,ix1=int(W*.205),int(W*.795); iy0,iy1=int(H*.615),int(H*.85)
    d.line([(ix0,iy0),(ix1,iy0)],fill=line,width=1)
    items=INTERP[rank]; icw=(ix1-ix0)/6; icell=int(H*.030); isz=18; lsz=19
    for i,(cat,txt) in enumerate(items):
        cx=int(ix1-icw*(i+0.5))  # 右→左
        # 類名(紅,2字) + 解(墨,4字)
        vcol(d,cx,iy0+int(H*.012),cat,F(lsz),red if ji else (60,50,45),icell)
        vcol(d,cx,iy0+int(H*.012)+icell*2+6,txt,F(isz),ink,icell)
    # 朱印(底右角小)
    ss=58; sx=int(W*.76); sy=int(H*.91); sq=Image.new("RGB",(ss,ss),red); bg.paste(sq,(sx,sy))
    cchar(d,sx+ss/2,sy+ss/2,"福" if ji else "祓",F(40),(250,245,235))
    out=f"omikuji_art/out/v4_{idx:02d}_{rank}.png"; bg.save(out); print("ok",out)
for i,rk in enumerate(ORDER,1): compose(rk,i)
