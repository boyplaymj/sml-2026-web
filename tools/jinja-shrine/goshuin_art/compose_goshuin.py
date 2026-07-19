# 御朱印圖(7款,對齊解析圖5部位):①社紋(頂圓神紋) ②奉拝(右上) ③社名(中央大書壓印)
# ④神社印(中央紅方印刻社名) ⑤日期(左直排)。季節靠社紋色+副印區分。$0程式合成。
# 印鑑來源:使用者提供之篆刻印鑑(Discord附件)→ goshuin_art/assets/seal.png(白底去背);素材不進git
from PIL import Image, ImageDraw, ImageFont
import math
SR="fonts/JinXiHaoLong.otf"   # 金梅浩龍書法體(使用者提供;御朱印用字全覆蓋)
def F(s): return ImageFont.truetype(SR,s)
# id, 中央大書, 社紋內字, 季節副印, accent色, 底
V=[
 ("honsha","甜甜神社","牌",None,(176,30,30),"warm"),
 ("shogatsu","初詣參","牌","初春",(198,150,30),"warm"),
 ("sakura","春櫻詣","牌","櫻花",(206,92,132),"warm"),
 ("nagoshi","夏越祓","牌","大祓",(46,96,160),"cool"),
 ("momiji","紅葉詣","牌","紅楓",(200,92,40),"warm"),
 ("okumiya","奧社參","牌","奧宮",(122,64,150),"cool"),
 ("okumiya-season","奧社限","牌","限定",(198,150,30),"cool"),
]
W=680
def cchar(d,cx,cy,ch,font,fill,stroke=0,scol=None):
    b=d.textbbox((0,0),ch,font=font,stroke_width=stroke)
    d.text((cx-(b[2]-b[0])/2-b[0],cy-(b[3]-b[1])/2-b[1]),ch,font=font,fill=fill,stroke_width=stroke,stroke_fill=scol or fill)
def vcol(d,cx,y0,s,font,fill,cell,stroke=0,scol=None):
    for i,ch in enumerate(s): cchar(d,cx,y0+cell*i+cell/2,ch,font,fill,stroke,scol)
def crest(d,cx,cy,rr,ch,col):  # ① 社紋:雙環+三點巴+中字
    d.ellipse([cx-rr,cy-rr,cx+rr,cy+rr],outline=col,width=5)
    d.ellipse([cx-rr+9,cy-rr+9,cx+rr-9,cy+rr-9],outline=col,width=2)
    for k in range(3):  # 三巴風小點
        a=math.radians(90+k*120); px=cx+int(rr*.60*math.cos(a)); py=cy-int(rr*.60*math.sin(a))
        d.ellipse([px-7,py-7,px+7,py+7],fill=col)
    cchar(d,cx,cy,ch,F(int(rr*.85)),col)
def nameseal(d,cx,cy,hf,col):  # ④ 神社印:紅方框+內刻「甜甜神社」2x2(淡紅,退居背景讓毛筆主導)
    faint=(206,130,130)
    d.rectangle([cx-hf,cy-hf,cx+hf,cy+hf],outline=col,width=7)
    d.rectangle([cx-hf+13,cy-hf+13,cx+hf-13,cy+hf-13],outline=col,width=2)
    q=int(hf*.5); f=F(int(hf*.46))
    for (ch,dx,dy) in [("甜",-q,-q),("甜",q,-q),("神",-q,q),("社",q,q)]:
        cchar(d,cx+dx,cy+dy,ch,f,faint)
def compose(vid,big,crestch,sub,acc,bg_):
    # 底:取 washi 內部(去掉框線),縮放成 A5 直式比例(148:210)
    src=Image.open(f"omikuji_art/bg/plain_{bg_}.png").convert("RGB")
    sw,sh=src.size; src=src.crop((int(sw*.13),int(sh*.11),int(sw*.87),int(sh*.89)))
    H=int(W*210/148); bg=src.resize((W,H)); d=ImageDraw.Draw(bg)
    ink=(26,22,20); red=(172,32,32)
    vcol(d,int(W*.85),int(H*.20),"奉拝",F(34),ink,int(H*.05)) # ② 奉拝(右上)
    vcol(d,int(W*.145),int(H*.22),"〇年〇月〇日",F(34),ink,int(H*.055)) # ⑤ 日期(左)
    # 印鑑(兩顆,大小不同、位置錯開)
    seal1=Image.open("goshuin_art/assets/seal.png").convert("RGBA")   # 大顆=中央神社印
    seal2=Image.open("goshuin_art/assets/seal2.png").convert("RGBA")  # 小顆=上方鈐印
    s2=118; seal2=seal2.resize((s2,s2)); bg.paste(seal2,(int(W*.50)-s2//2,int(H*.075)),seal2) # 上方小印
    s1=250; seal1=seal1.resize((s1,s1)); scx,scy=int(W*.50),int(H*.49)
    bg.paste(seal1,(scx-s1//2,scy-s1//2),seal1)                       # 中央大印
    # ③ 社名(中央大書,墨,細筆不描邊,壓大印上)
    n=len(big); csz={2:150,3:118,4:96}.get(n,92)
    vcol(d,int(W*.50),scy-int(csz*(n-1)/2)-int(csz*.1),big,F(csz),ink,int(csz*1.06),stroke=0)
    # 季節副印(左下方,accent白字方印)
    if sub:
        ss=84; sx,sy=int(W*.20),int(H*.80); d.rectangle([sx,sy,sx+ss,sy+ss],fill=acc)
        vcol(d,sx+ss//2,sy+8,sub,F(36),(250,247,240),int((ss-16)/2))
    out=f"goshuin_art/out/{vid}.png"; bg.save(out); print("ok",vid)
for v in V: compose(*v)
