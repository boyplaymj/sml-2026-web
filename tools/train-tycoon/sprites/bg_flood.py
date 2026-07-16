import sys
from PIL import Image
from collections import deque
import numpy as np
inp, out = sys.argv[1], sys.argv[2]
tol = int(sys.argv[3]) if len(sys.argv)>3 else 34
im = Image.open(inp).convert("RGBA")
a = np.array(im); h,w = a.shape[:2]
rgb = a[:,:,:3].astype(int)
# 邊緣採樣背景色(取四邊中位)
border = np.concatenate([rgb[0,:],rgb[-1,:],rgb[:,0],rgb[:,-1]])
bg = np.median(border,axis=0)
dist = np.sqrt(((rgb-bg)**2).sum(axis=2))
near = dist < tol
# 從邊緣 flood fill,只刪「與邊緣相連」的近背景 → 保住內部白煙
vis = np.zeros((h,w),bool); q=deque()
for x in range(w):
    for y in (0,h-1):
        if near[y,x]: q.append((y,x)); vis[y,x]=True
for y in range(h):
    for x in (0,w-1):
        if near[y,x] and not vis[y,x]: q.append((y,x)); vis[y,x]=True
while q:
    y,x=q.popleft()
    for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
        ny,nx=y+dy,x+dx
        if 0<=ny<h and 0<=nx<w and not vis[ny,nx] and near[ny,nx]:
            vis[ny,nx]=True; q.append((ny,nx))
a[:,:,3] = np.where(vis,0,255).astype('uint8')
# 邊緣羽化一點
Image.fromarray(a).save(out)
kept = (a[:,:,3]>0).sum()
print("ok",out,"kept%%=%.0f"%(100*kept/(h*w)))
