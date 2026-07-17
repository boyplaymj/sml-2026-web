#!/usr/bin/env python3
# 讓「煙圖層」稍微動:車體底圖完全靜止,只把使用者畫的煙(獨立透明圖層)做
# 輕輕上升 + 往左後拖 + 淡出的循環(交錯 K 團成連續小煙,無縫循環)。
# 用法: SRC=底圖.png SMOKELAYER=煙層.png OUT=xxx.gif python3 animate_smokelayer.py
import os, glob, subprocess
import numpy as np
from PIL import Image

SRC = os.environ["SRC"]
SMK = os.environ["SMOKELAYER"]
OUT = os.environ.get("OUT", "/tmp/train-emoji/smoke.gif")
N = int(os.environ.get("FRAMES", 20))
K = int(os.environ.get("PUFFS", 3))              # 交錯煙團數(連續感)
RISE = float(os.environ.get("RISE", 14))         # 上升幅度(小,別飄出框)
DRIFT = float(os.environ.get("DRIFT", 10))       # 往左後拖
FADEPOW = float(os.environ.get("FADEPOW", 1.0))  # 淡出曲線
SCALE = float(os.environ.get("SCALE", 1.0))
DUR = int(os.environ.get("DUR", 110))
DARK = (54, 57, 63)

base = Image.open(SRC).convert("RGBA")
W, H = base.size
smoke = Image.open(SMK).convert("RGBA")
if smoke.size != (W, H):
    smoke = smoke.resize((W, H), Image.NEAREST)
smk_arr = np.array(smoke).astype(np.float32)

frames = []
for f in range(N):
    canvas = Image.new("RGBA", (W, H), DARK + (255,))
    canvas.alpha_composite(base)
    for k in range(K):
        phase = ((f / N) + k / K) % 1.0
        dy = -int(round(phase * RISE))
        dx = -int(round(phase * DRIFT))
        fade = (1.0 - phase) ** FADEPOW           # 上升越高越淡
        a = smk_arr.copy()
        a[:, :, 3] *= fade
        layer = Image.fromarray(a.astype(np.uint8), "RGBA")
        canvas.alpha_composite(layer, (dx, dy))
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
