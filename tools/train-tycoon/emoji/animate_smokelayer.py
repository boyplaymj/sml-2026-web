#!/usr/bin/env python3
# 讓「煙圖層」稍微動:車體底圖完全靜止,只把使用者畫的煙(獨立透明圖層)做
# 輕輕上升 + 往左後拖 + 淡出的循環(交錯 K 團成連續小煙,無縫循環)。
# 用法: SRC=底圖.png SMOKELAYER=煙層.png OUT=xxx.gif python3 animate_smokelayer.py
import os, glob, subprocess, math
import numpy as np
from PIL import Image

SRC = os.environ["SRC"]
SMK = os.environ["SMOKELAYER"]
OUT = os.environ.get("OUT", "/tmp/train-emoji/smoke.gif")
N = int(os.environ.get("FRAMES", 20))
AMP = float(os.environ.get("AMP", 0.28))         # 脹大縮小幅度(±%)
RISE = float(os.environ.get("RISE", 4))          # 附帶輕微上升(0=純脹縮)
OPA = float(os.environ.get("OPA", 0.15))         # 附帶透明度呼吸(0=不變)
SCALE = float(os.environ.get("SCALE", 1.0))
DUR = int(os.environ.get("DUR", 110))
DARK = (54, 57, 63)

base = Image.open(SRC).convert("RGBA")
W, H = base.size
smoke = Image.open(SMK).convert("RGBA")
if smoke.size != (W, H):
    smoke = smoke.resize((W, H), Image.NEAREST)

# 抓煙團 bbox,以「底部中心」為錨 → 脹縮時像從煙囪往上billow
sa = np.array(smoke)
ys, xs = np.where(sa[:, :, 3] > 8)
if len(xs) == 0:
    raise SystemExit("煙層沒有不透明像素")
x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
puff = smoke.crop((x0, y0, x1, y1))
pw, ph = puff.size
ax = (x0 + x1) // 2      # 錨 x = 煙團中心
aby = y1                 # 錨 y = 煙團底(往上長)

frames = []
for f in range(N):
    canvas = Image.new("RGBA", (W, H), DARK + (255,))
    canvas.alpha_composite(base)
    th = 2 * math.pi * f / N
    s = 1.0 + AMP * math.sin(th)                    # 脹縮
    rise = int(round(RISE * (0.5 - 0.5 * math.cos(th))))  # 輕微上下(0→上→0)
    nw, nh = max(1, int(round(pw * s))), max(1, int(round(ph * s)))
    p2 = puff.resize((nw, nh), Image.LANCZOS)
    if OPA:
        a = np.array(p2).astype(np.float32)
        a[:, :, 3] *= (1.0 - OPA * (0.5 - 0.5 * math.cos(th)))  # 大時略淡(散開感)
        p2 = Image.fromarray(a.astype(np.uint8), "RGBA")
    px = ax - nw // 2
    py = (aby - rise) - nh
    canvas.alpha_composite(p2, (px, py))
    frames.append(canvas)

if SCALE != 1.0:
    frames = [f.resize((int(W * SCALE), int(H * SCALE)), Image.NEAREST) for f in frames]

fdir = os.path.join(os.path.dirname(OUT) or ".", "_smkframes")
os.makedirs(fdir, exist_ok=True)
for old in glob.glob(f"{fdir}/*.png"):
    os.remove(old)
for i, fr in enumerate(frames):
    fr.convert("RGB").save(f"{fdir}/f{i:03d}.png")
FF = os.environ.get("FF", "/opt/sml/repo/tools/bin/ffmpeg")
pal = f"{fdir}/pal.png"
fps = 1000 // DUR
subprocess.run([FF, "-y", "-loglevel", "error", "-i", f"{fdir}/f%03d.png",
                "-vf", "palettegen=max_colors=128:stats_mode=full", pal], check=True)
subprocess.run([FF, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", f"{fdir}/f%03d.png",
                "-i", pal, "-lavfi", "paletteuse=dither=none", "-loop", "0", OUT], check=True)
print("GIF", OUT, len(frames), "frames", frames[0].size)
