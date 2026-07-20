#!/usr/bin/env python3
# 實測:把真實 JR ワム 側視照 → 現行 iso 格盤角度 16bit。
# 混合流:照片木牆側面 homography 扭正貼 iso 長面(保留 JR/木紋/滑門)
#          + 程式補生 頂面(圓頂灰)/端面(木紋)/轉向架 = 完整 iso 方盒。
import os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from photo2iso import warp_face, quantize16, screen, TH

# 素材路徑:argv[1] > 環境變數 JR_SRC > 同資料夾 sample_jr.png。缺檔友善結束(不 crash)。
SRC = (sys.argv[1] if len(sys.argv) > 1
       else os.environ.get('JR_SRC')
       or os.path.join(os.path.dirname(__file__), 'sample_jr.png'))
# WALL 木牆四角(TL,TR,BR,BL)是為 1024×506 的 JR ワム 範例圖調的;換圖需重標。
WALL = [(36, 110), (987, 110), (987, 358), (36, 358)]

def lerp(a, b, t): return (a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t)

def build():
    src = Image.open(SRC).convert('RGBA')
    L, D, H = 4.4, 1.15, 1.15
    ox, oy, W, HH = 24, 30, 104, 100
    def g(c, r, z):
        x, y = screen(c, r); return (x + ox, y + oy - z * TH)
    t00,t10,t11,t01 = g(0,0,H), g(L,0,H), g(L,D,H), g(0,D,H)
    b10,b11,b01     = g(L,0,0), g(L,D,0), g(0,D,0)

    out = Image.new('RGBA', (W, HH), (0,0,0,0))
    dr = ImageDraw.Draw(out)
    # 1) 頂面(圓頂灰:漸層 + 通氣口)——在最後方,先畫
    dr.polygon([t00,t10,t11,t01], fill=(120,128,136))
    dr.polygon([lerp(t00,t11,0.04)]+[lerp(t10,t01,0.04)]+[lerp(t11,t00,0.04)]+[lerp(t01,t10,0.04)], fill=(150,158,166))
    for f in (0.28,0.5,0.72):                       # 3 通氣口(仿原圖)
        cvt=lerp(t00,t10,f); cvb=lerp(t01,t11,f)
        m=lerp(cvt,cvb,0.5); dr.ellipse([m[0]-3,m[1]-2,m[0]+3,m[1]+2], fill=(60,64,70))
    # 2) 端面(右,c=L:木紋深一階 + 直板 + 角鐵)
    dr.polygon([t10,t11,b11,b10], fill=(110,80,48))
    for i in range(1,5):                             # 端面直板
        f=i/5
        dr.line([lerp(t10,t11,f), lerp(b10,b11,f)], fill=(78,54,30), width=1)
    dr.line([t10,b10], fill=(60,42,24), width=1); dr.line([t11,b11], fill=(60,42,24), width=1)
    # 3) 長面(左,c 向:貼真實照片木牆,扭正到 iso 面)
    warped, mask = warp_face(src, (W,HH), [t01,t11,b11,b01], WALL)
    out.paste(warped, (0,0), mask)
    # 4) 量化 16 色
    a = np.array(out); q = quantize16(a[:,:,:3]); out = Image.fromarray(np.dstack([q, a[:,:,3]]))
    dr = ImageDraw.Draw(out)
    # 5) 轉向架(兩台車,近側長面底緣下)
    def wheels(centers, rad=3.4):
        for fc in centers:
            cbase = lerp(b01, b11, fc)
            dr.rectangle([cbase[0]-9, cbase[1]-1, cbase[0]+9, cbase[1]+rad*0.9], fill=(34,32,52))
            for dxx in (-6,6):
                cx,cy=cbase[0]+dxx, cbase[1]+rad*0.3
                dr.ellipse([cx-rad,cy-rad,cx+rad,cy+rad], fill=(13,13,22))
                dr.ellipse([cx-rad+1.4,cy-rad+1.4,cx+rad-1.4,cy+rad-1.4], fill=(94,90,120))
                dr.ellipse([cx-1,cy-1,cx+1,cy+1], fill=(203,204,219))
    wheels([0.24, 0.78])
    # 6) 描邊(方盒可見棱)
    ink=(13,13,22)
    for p,q2 in [(t00,t10),(t10,t11),(t11,t01),(t01,t00),(t10,b10),(t11,b11),(t01,b01),(b10,b11),(b11,b01)]:
        dr.line([p,q2], fill=ink, width=1)
    return out.resize((W*6, HH*6), Image.NEAREST)

if __name__ == '__main__':
    if not os.path.exists(SRC):
        print(f'⚠️ 找不到素材圖:{SRC}\n'
              f'   用法:python3 build_jr_iso.py <JR側視圖路徑>(或設 JR_SRC 環境變數)。\n'
              f'   WALL 錨點是為 1024×506 的 JR ワム 範例調的,換圖需重標。跳過。')
        sys.exit(0)
    outdir=os.path.join(os.path.dirname(__file__),'out'); os.makedirs(outdir,exist_ok=True)
    img=build(); img=img.crop(img.getbbox()); img.save(os.path.join(outdir,'jr_iso.png'))
    print('ok jr_iso.png', img.size)
