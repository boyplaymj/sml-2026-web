#!/usr/bin/env python3
# 把靜態 D51 sprite 做成動圖:①煙囪冒煙 ②行駛抖動(車體上下微晃)③輪子轉動(疊旋轉輻條)。
# 座標可用環境變數微調(先估、看圖再調)。輸出 GIF(深底預覽)。
import os, math
from PIL import Image, ImageDraw

SRC = os.environ.get("SRC", "/tmp/discord-att-2525581616.png")
OUT = os.environ.get("OUT", "/tmp/train-emoji/d51_anim.gif")
N = int(os.environ.get("FRAMES", 12))
SCALE = float(os.environ.get("SCALE", 0.7))          # 預覽縮放
DARK = (54, 57, 63)

# 煙囪頂端(原圖座標,facing right → 前方偏右);多個煙囪逗號分隔 "x:y"
SMOKE = os.environ.get("SMOKE", "486:22")
# 車輪 "x:y:r" 逗號分隔(大動輪 + 煤水車/前導小輪)
WHEELS = os.environ.get("WHEELS", "236:236:34,306:236:34,376:236:34,70:256:18,132:256:18,452:258:15,487:258:15")

def parse(s, n):
    out = []
    for part in s.split(","):
        if not part.strip():
            continue
        out.append(tuple(int(v) for v in part.split(":")))
    return out

smoke_src = parse(SMOKE, 2)
wheels = parse(WHEELS, 3)

base = Image.open(SRC).convert("RGBA")
W, H = base.size
PAD_TOP = 0        # 不加上留白(煙自然飄出框、不改變原圖比例)
canvas_h = H

frames = []
for f in range(N):
    t = f / N
    fr = Image.new("RGBA", (W, canvas_h), DARK + (255,))
    # ② 行駛抖動:上下微晃 + 偶爾左右 1px
    bob = int(round((math.sin(2 * math.pi * (f / N) * 2) + 1) * 0.9))  # 只往下 0~2px、不裁上緣
    jit = 1 if f % 4 == 1 else (-1 if f % 4 == 3 else 0)          # 微幅左右
    layer = base.copy()
    # ③ 輪子轉動:在每個輪上疊旋轉輻條(灰,over 近黑輪)
    d = ImageDraw.Draw(layer)
    ang = 2 * math.pi * (f / N)   # 一圈轉滿 → 無縫循環
    for (cx, cy, r) in wheels:
        for k in range(6):  # 6 輻條、30° 步進看得出轉
            a = ang + k * math.pi / 3
            x2 = cx + math.cos(a) * (r - 2); y2 = cy + math.sin(a) * (r - 2)
            d.line([(cx, cy), (x2, y2)], fill=(110, 112, 120, 230), width=max(1, r // 12))
        # 輪緣一個亮點跟著轉(更明顯)
        gx = cx + math.cos(ang) * (r - 3); gy = cy + math.sin(ang) * (r - 3)
        d.ellipse([gx - 2, gy - 2, gx + 2, gy + 2], fill=(200, 200, 205, 255))
    fr.alpha_composite(layer, (jit, PAD_TOP + bob))
    # ① 冒煙:多團煙珠,沿時間上升+飄+變大+淡出,交錯循環
    d2 = ImageDraw.Draw(fr)
    for (sx, sy) in smoke_src:
        npuff = 5
        for i in range(npuff):
            age = ((f / N) + i / npuff) % 1.0
            rise = age * 22            # 小幅上升(留在框內、頂多飄出上緣一點)
            drift = -age * 24          # 往左後方拖(行進中煙尾)
            rad = 2 + age * 5          # 小煙珠
            alpha = int(190 * (1 - age))
            px = sx + jit + drift
            py = sy + bob - rise
            col = (225, 225, 228, alpha)
            d2.ellipse([px - rad, py - rad, px + rad, py + rad], fill=col)
    frames.append(fr)

# 縮放 + 存 GIF(用 ffmpeg palettegen/paletteuse 出乾淨循環,避免 PIL 每幀 ADAPTIVE 色崩)
import subprocess, glob
if SCALE != 1.0:
    nw, nh = int(W * SCALE), int(canvas_h * SCALE)
    frames = [f.resize((nw, nh), Image.NEAREST) for f in frames]
fdir = os.path.join(os.path.dirname(OUT) or ".", "_d51frames")
os.makedirs(fdir, exist_ok=True)
for old in glob.glob(f"{fdir}/*.png"):
    os.remove(old)
for i, fr in enumerate(frames):
    fr.convert("RGB").save(f"{fdir}/f{i:03d}.png")
FF = os.environ.get("FF", "/opt/sml/repo/tools/bin/ffmpeg")
fps = 1000 // int(os.environ.get("DUR", 90))
pal = f"{fdir}/pal.png"
subprocess.run([FF, "-y", "-loglevel", "error", "-i", f"{fdir}/f%03d.png",
                "-vf", "palettegen=max_colors=128:stats_mode=full", pal], check=True)
subprocess.run([FF, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", f"{fdir}/f%03d.png",
                "-i", pal, "-lavfi", "paletteuse=dither=none", "-loop", "0", OUT], check=True)
print("GIF", OUT, len(frames), "frames", frames[0].size)
