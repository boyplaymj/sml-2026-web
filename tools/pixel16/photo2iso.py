#!/usr/bin/env python3
# photo2iso — 照片/圖片物件 → 統一角度 16bit iso sprite(原型)。
# 概念:使用者在照片上標物件的立方外框(iso 側影=六邊形6外角+近邊=7可見角)。
# 對每個可見面做透視校正(homography)扭正,貼到「數學固定的 iso 標準面」→
#   產出角度必然與所有遊戲資產一致(目的地是常數 screen(c,r))。
#   再套 PALETTE16 量化 + 像素化 + 描邊 = 16bit。deterministic、零成本、非擴散生圖。
import os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from engine16 import PALETTE16

TW, TH = 28, 14

def screen(c, r): return ((c - r) * TW / 2, (c + r) * TH / 2)

# ── 透視校正核心 ────────────────────────────────────────────
def find_coeffs(dst, src):
    """回傳 PIL PERSPECTIVE 係數:輸出座標 dst → 取樣輸入座標 src。"""
    A, B = [], []
    for (xo, yo), (xi, yi) in zip(dst, src):
        A.append([xo, yo, 1, 0, 0, 0, -xi*xo, -xi*yo]); B.append(xi)
        A.append([0, 0, 0, xo, yo, 1, -yi*xo, -yi*yo]); B.append(yi)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()

def warp_face(src_img, size, dst_quad, src_quad):
    coeffs = find_coeffs(dst_quad, src_quad)
    warped = src_img.transform(size, Image.PERSPECTIVE, coeffs, Image.BILINEAR)
    mask = Image.new('L', size, 0)
    ImageDraw.Draw(mask).polygon([tuple(p) for p in dst_quad], fill=255)
    return warped, mask

# ── 16 色量化 ───────────────────────────────────────────────
_PAL = np.array([v for v in PALETTE16.values() if v], dtype=float)
def quantize16(rgb):
    h, w, _ = rgb.shape
    flat = rgb.reshape(-1, 3).astype(float)
    d = ((flat[:, None, :] - _PAL[None, :, :]) ** 2).sum(2)
    return _PAL[d.argmin(1)].reshape(h, w, 3).astype(np.uint8)

# ── 主管線:照片 + 三面錨點 → iso 16bit ─────────────────────
def photo_to_iso(src_img, faces, L=3.2, D=3.2, H=3.2, scale=6):
    """faces = {'top':4src, 'left':4src, 'right':4src}(照片座標,角順序見下)。"""
    ox, oy = 52, 52; W, HH = 108, 104
    def g(c, r, z):
        x, y = screen(c, r); return (x + ox, y + oy - z * TH)
    t00, t10, t11, t01 = g(0,0,H), g(L,0,H), g(L,D,H), g(0,D,H)
    b10, b11, b01 = g(L,0,0), g(L,D,0), g(0,D,0)
    dst = {'top':  [t00, t10, t11, t01],
           'right':[t10, t11, b11, b10],
           'left': [t01, t11, b11, b01]}
    result = Image.new('RGBA', (W, HH), (0, 0, 0, 0))
    for key in ('top', 'left', 'right'):
        warped, mask = warp_face(src_img, (W, HH), dst[key], faces[key])
        result.paste(warped, (0, 0), mask)
    # 量化 16 色(只動不透明像素)
    rgba = np.array(result); rgb = rgba[:, :, :3]; a = rgba[:, :, 3]
    q = quantize16(rgb); q = np.dstack([q, a])
    out = Image.fromarray(q, 'RGBA')
    # 描邊:三面外緣 + 近邊,深色
    d = ImageDraw.Draw(out); ink = PALETTE16['0']
    edges = [(t00,t10),(t10,t11),(t11,t01),(t01,t00),         # 頂
             (t10,b10),(b10,b11),(t01,b01),(b01,b11),(t11,b11)] # 側+近邊
    for p, q2 in edges:
        d.line([tuple(p), tuple(q2)], fill=ink, width=1)
    return out.resize((W*scale, HH*scale), Image.NEAREST)


# ── 合成一張「木箱照片」(模擬真實透視,驗證管線)────────────
def synth_crate_photo():
    W, H = 900, 700
    img = Image.new('RGB', (W, H), (238, 240, 244))
    d = ImageDraw.Draw(img)
    # 7 可見角(帶透視,不是 iso)
    P = dict(t00=(300,150), t10=(660,180), t01=(250,255),
             t11=(505,300), b11=(505,560), b10=(660,440), b01=(250,515))
    faces = {'top':[P['t00'],P['t10'],P['t11'],P['t01']],
             'right':[P['t10'],P['t11'],P['b11'],P['b10']],
             'left':[P['t01'],P['t11'],P['b11'],P['b01']]}
    base = {'top':(178,132,74), 'right':(120,84,46), 'left':(150,108,60)}  # 木色三明暗
    for key, quad in faces.items():
        d.polygon(quad, fill=base[key])
    # 木板紋(每面畫幾條深線)+ 邊角釘
    def planks(quad, n, dark):
        (x0,y0),(x1,y1),(x2,y2),(x3,y3)=quad
        for i in range(1,n):
            f=i/n
            a=(x0+(x3-x0)*f, y0+(y3-y0)*f); b=(x1+(x2-x1)*f, y1+(y2-y1)*f)
            d.line([a,b], fill=dark, width=3)
    planks(faces['top'],5,(150,110,60)); planks(faces['left'],4,(120,86,48)); planks(faces['right'],4,(96,66,36))
    img = img.convert('RGB')
    arr = np.array(img).astype(np.int16)
    noise = np.random.default_rng(7).integers(-16, 16, arr.shape)  # 模擬照片雜訊
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr), faces

if __name__ == '__main__':
    out = '/opt/sml/repo/tools/pixel16/out'
    os.makedirs(out, exist_ok=True)
    photo, faces = synth_crate_photo()
    photo.save(out + '/p2i_source.png')
    iso = photo_to_iso(photo, faces)
    iso.save(out + '/p2i_result.png')
    print('ok photo2iso', iso.size)
