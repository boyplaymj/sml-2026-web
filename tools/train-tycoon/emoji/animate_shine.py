#!/usr/bin/env python3
# 車輛「光澤掃過」動畫:車體完全靜止(不抖、軌道不動),一道斜向高光由左掃到右、
# 玻璃(暗色像素)最亮、車體金屬給微光。蒸汽車可另加煙囪煙(SMOKE)。
# 用法: SRC=xxx.png OUT=xxx.gif [SMOKE="x:y"] python3 animate_shine.py
import os, math, subprocess, glob
import numpy as np
from PIL import Image, ImageDraw

SRC = os.environ["SRC"]
OUT = os.environ.get("OUT", "/tmp/train-emoji/shine.gif")
N = int(os.environ.get("FRAMES", 16))
SCALE = float(os.environ.get("SCALE", 1.0))
DARK = (54, 57, 63)
GMAX = float(os.environ.get("GLOSS", 0.75))      # 高光最大強度
SIGMA_F = float(os.environ.get("SIGMA", 0.05))   # 光帶寬(占寬比例)
SLOPE = float(os.environ.get("SLOPE", 0.45))     # 斜度
GLASS_LUM = float(os.environ.get("GLASS_LUM", 115))  # 亮度低於此=玻璃/暗面,吃最多光
GLASS_YMAX = float(os.environ.get("GLASS_YMAX", 0.58))  # 玻璃只認上半部(排除底盤/輪子)
BODY_W = float(os.environ.get("BODY_W", 0.12))   # 非玻璃車體的微光權重(壓低,光主要落玻璃)

SMOKE = os.environ.get("SMOKE", "")

def parse(s):
    return [tuple(int(v) for v in p.split(":")) for p in s.split(",") if p.strip()]

base = Image.open(SRC).convert("RGBA")
W, H = base.size
arr = np.array(base).astype(np.float32)
rgb = arr[:, :, :3]
alpha = arr[:, :, 3]
lum = rgb @ np.array([0.3, 0.6, 0.1], dtype=np.float32)
opaque = alpha > 8
ys, xs = np.mgrid[0:H, 0:W]
region = ys < (H * GLASS_YMAX)                 # 窗戶在上半部
glass = opaque & (lum < GLASS_LUM) & region
weight = np.where(glass, 1.0, np.where(opaque, BODY_W, 0.0)).astype(np.float32)
diag = xs.astype(np.float32) - (H - ys).astype(np.float32) * SLOPE
sigma = max(2.0, W * SIGMA_F)
smoke_src = parse(SMOKE)

frames = []
for f in range(N):
    t = f / N
    sx = -0.4 * W + t * 1.8 * W            # 高光帶中心從框外左掃到框外右
    strg = np.exp(-((diag - sx) ** 2) / (2 * sigma ** 2)) * weight * GMAX
    out = rgb + (255.0 - rgb) * strg[:, :, None]
    a = np.dstack([np.clip(out, 0, 255), alpha]).astype(np.uint8)
    fr = Image.fromarray(a, "RGBA")
    canvas = Image.new("RGBA", (W, H), DARK + (255,))
    canvas.alpha_composite(fr)
    # 蒸汽煙(可選):小煙珠上升往左後拖淡出
    if smoke_src:
        d2 = ImageDraw.Draw(canvas)
        for (sxk, syk) in smoke_src:
            for i in range(5):
                age = ((f / N) + i / 5) % 1.0
                rise = age * 22; drift = -age * 24; rad = 2 + age * 5
                al = int(190 * (1 - age))
                px = sxk + drift; py = syk - rise
                d2.ellipse([px - rad, py - rad, px + rad, py + rad], fill=(225, 225, 228, al))
    frames.append(canvas)

if SCALE != 1.0:
    frames = [f.resize((int(W * SCALE), int(H * SCALE)), Image.NEAREST) for f in frames]

fdir = os.path.join(os.path.dirname(OUT) or ".", "_shineframes")
os.makedirs(fdir, exist_ok=True)
for old in glob.glob(f"{fdir}/*.png"):
    os.remove(old)
for i, fr in enumerate(frames):
    fr.convert("RGB").save(f"{fdir}/f{i:03d}.png")
FF = os.environ.get("FF", "/opt/sml/repo/tools/bin/ffmpeg")
pal = f"{fdir}/pal.png"
fps = 1000 // int(os.environ.get("DUR", 80))
subprocess.run([FF, "-y", "-loglevel", "error", "-i", f"{fdir}/f%03d.png",
                "-vf", "palettegen=max_colors=128:stats_mode=full", pal], check=True)
subprocess.run([FF, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", f"{fdir}/f%03d.png",
                "-i", pal, "-lavfi", "paletteuse=dither=none", "-loop", "0", OUT], check=True)
print("GIF", OUT, len(frames), "frames", frames[0].size)
