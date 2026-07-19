# 御朱印圖(7款,對齊解析圖5部位):①社紋(頂圓神紋) ②奉拝(右上) ③社名(中央大書壓印)
# ④神社印(中央紅方印刻社名) ⑤日期(左直排)。季節靠社紋色+副印區分。$0程式合成。
# 印鑑來源:使用者提供之篆刻印鑑(Discord附件)→ goshuin_art/assets/seal.png(白底去背);素材不進git
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont as _TT
import math, datetime, sys

# ── 日期→國字直式(參拜日期,預設今天;可傳 YYYY-MM-DD 覆蓋) ──
_D="〇一二三四五六七八九"
def _cn_ymd(n):  # 月/日 1..31 → 國字
    if n<10: return _D[n]
    t,o=divmod(n,10); s=("" if t==1 else _D[t])+"十"+(_D[o] if o else "")
    return s
def date_cn(dstr=None):
    d=datetime.date.today() if not dstr else datetime.date.fromisoformat(dstr)
    y="".join(_D[int(c)] for c in str(d.year))
    return f"{y}年{_cn_ymd(d.month)}月{_cn_ymd(d.day)}日"
DATE_STR = sys.argv[1] if len(sys.argv)>1 else None   # 可命令列傳日期,否則今天
SR="fonts/JinXiHaoLong.otf"   # 金梅浩龍書法體(中央社名大書;御朱印用字全覆蓋)
SIDE="fonts/SideFont.ttf"     # ZHLYSS_T(使用者提供;側邊小字:奉拝/日期/副印)
def F(s): return ImageFont.truetype(SR,s)
def FS(s): return ImageFont.truetype(SIDE,s)
_side_cmap=set(_TT(SIDE).getBestCmap().keys())
def sfont(ch,sz): return FS(sz) if ord(ch) in _side_cmap else F(sz)  # 側字缺(〇奧宮)→回退書法體
def vcol_s(d,cx,y0,s,sz,fill,cell):  # 側邊小字:逐字挑字型
    for i,ch in enumerate(s): cchar(d,cx,y0+cell*i+cell/2,ch,sfont(ch,sz),fill)
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
# 季節印用「印鑑圖片」並重新上色的版本(可逐版本擴充):vid -> (印圖, 顏色RGB)
SUBSEAL_IMG={
  "shogatsu": ("goshuin_art/assets/seal_hatsu.png",  (201,162,58)),   # 初春=金色
  "sakura":   ("goshuin_art/assets/seal_sakura.png", (211,96,140)),   # 春櫻=櫻花桃紅
  "nagoshi":  ("goshuin_art/assets/seal_nagoshi.png",(46,104,168)),   # 夏越=水藍
  "momiji":   ("goshuin_art/assets/seal_momiji.png", (198,88,36)),    # 紅葉=楓橙
  "okumiya":  ("goshuin_art/assets/seal_okumiya.png",(126,66,156)),   # 奧社牌神=紫
  "okumiya-season": ("goshuin_art/assets/seal_okuseason.png",(190,150,52)), # 奧社限定=專屬印金色
}
def tint(img,color):  # 把不透明像素全塗成指定色(保留alpha)
    r,g,b=color; px=img.load(); w,h=img.size
    for y in range(h):
        for x in range(w):
            a=px[x,y][3]
            if a>0: px[x,y]=(r,g,b,a)
    return img
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
    vcol_s(d,int(W*.865),int(H*.135),"奉拝",64,ink,int(H*.086)) # ② 奉拝(右上,放大)
    # ⑤ 日期(左,今天日期,國字直式;字距縮小=cell 逼近字級)
    ds=date_cn(DATE_STR); dsz=min(int(H*.060),int(H*0.66/len(ds))); dcell=int(dsz*1.02)
    vcol_s(d,int(W*.125),int(H*.115),ds,dsz,ink,dcell)
    # 印鑑(兩顆,大小不同、位置錯開)
    seal1=Image.open("goshuin_art/assets/seal.png").convert("RGBA")   # 大顆=中央神社印
    seal2=Image.open("goshuin_art/assets/seal2.png").convert("RGBA")  # 小顆=上方鈐印
    s2=118; seal2=seal2.resize((s2,s2)); bg.paste(seal2,(int(W*.50)-s2//2,int(H*.075)),seal2) # 上方小印
    s1=250; seal1=seal1.resize((s1,s1)); scx,scy=int(W*.50),int(H*.49)
    bg.paste(seal1,(scx-s1//2,scy-s1//2),seal1)                       # 中央大印
    # ③ 社名(中央大書,墨,細筆不描邊,壓大印上;放大)
    n=len(big); csz={2:210,3:168,4:132}.get(n,128)
    vcol(d,int(W*.50),scy-int(csz*(n-1)/2)-int(csz*.05),big,F(csz),ink,int(csz*1.02),stroke=0)
    # 季節副印(左下方,accent白字方印)
    if vid in SUBSEAL_IMG:   # 季節印=印鑑圖片(重新上色)
        p,col=SUBSEAL_IMG[vid]; si=tint(Image.open(p).convert("RGBA"),col)
        ss=98; si=si.resize((ss,ss)); bg.paste(si,(int(W*.17),int(H*.785)),si)
    elif sub:                # 季節印=程式方印+字
        ss=84; sx,sy=int(W*.20),int(H*.80); d.rectangle([sx,sy,sx+ss,sy+ss],fill=acc)
        vcol_s(d,sx+ss//2,sy+8,sub,36,(250,247,240),int((ss-16)/2))
    out=f"goshuin_art/out/{vid}.png"; bg.save(out); print("ok",vid)
for v in V: compose(*v)
