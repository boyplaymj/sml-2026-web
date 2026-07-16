import sys, os, numpy as np
from PIL import Image
from collections import deque

# 可用環境變數覆蓋(8-bit 風:更低解析度+更少色+更粗像素)
# 16-bit 預設 TARGET_W=128 NCOL=24;8-bit 試 TARGET_W=64 NCOL=16 SCALE=9
TARGET_W = int(os.environ.get("PX_TARGET_W", 128))   # 降到的低解析度寬(高按比例)
SCALE    = int(os.environ.get("PX_SCALE", 5))        # 顯示放大(nearest)
NCOL     = int(os.environ.get("PX_NCOL", 24))        # 共用調色盤色數

def remove_bg(im, tol=30):
    a=np.array(im.convert("RGBA")); h,w=a.shape[:2]; rgb=a[:,:,:3].astype(int)
    border=np.concatenate([rgb[0,:],rgb[-1,:],rgb[:,0],rgb[:,-1]])
    bg=np.median(border,axis=0); near=np.sqrt(((rgb-bg)**2).sum(2))<tol
    vis=np.zeros((h,w),bool); q=deque()
    for x in range(w):
        for y in (0,h-1):
            if near[y,x] and not vis[y,x]: vis[y,x]=True;q.append((y,x))
    for y in range(h):
        for x in (0,w-1):
            if near[y,x] and not vis[y,x]: vis[y,x]=True;q.append((y,x))
    while q:
        y,x=q.popleft()
        for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
            ny,nx=y+dy,x+dx
            if 0<=ny<h and 0<=nx<w and not vis[ny,nx] and near[ny,nx]:
                vis[ny,nx]=True;q.append((ny,nx))
    a[:,:,3]=np.where(vis,0,255).astype('uint8'); return Image.fromarray(a)

def downscale(im):
    w,h=im.size; nw=TARGET_W; nh=round(h*nw/w)
    small=im.resize((nw,nh), Image.LANCZOS)
    arr=np.array(small); arr[:,:,3]=np.where(arr[:,:,3]>128,255,0)  # 硬邊
    return Image.fromarray(arr)

inputs=sys.argv[1:]
smalls=[downscale(remove_bg(Image.open(f))) for f in inputs]
# 共用調色盤:蒐集所有不透明像素 → median-cut NCOL 色
pool=[]
for s in smalls:
    a=np.array(s); op=a[a[:,:,3]>0][:,:3]; pool.append(op)
pool=np.concatenate(pool)
pimg=Image.fromarray(pool.reshape(-1,1,3).astype('uint8'),"RGB")
pal=pimg.quantize(colors=NCOL, method=Image.MEDIANCUT)
# 套用共用調色盤到每張,保留 alpha,nearest 放大
for f,s in zip(inputs,smalls):
    a=np.array(s); alpha=a[:,:,3]
    rgb=Image.fromarray(a[:,:,:3],"RGB").quantize(palette=pal, dither=Image.NONE).convert("RGB")
    out=np.dstack([np.array(rgb), alpha])
    im=Image.fromarray(out,"RGBA")
    big=im.resize((im.width*SCALE, im.height*SCALE), Image.NEAREST)
    o=f.replace(".png","_px.png"); big.save(o); print("ok",o,big.size)
