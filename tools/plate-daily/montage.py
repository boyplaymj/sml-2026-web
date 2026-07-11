#!/usr/bin/env python3
"""拼湊合成器:用真牌裁下的字元圖,拼成任意號碼並疊到車牌底。

字庫:glyphs/<字元>.png(RGBA,保留真牌浮凸色)
底  :car_base3.png,牌面 bbox 見 PLATE
用法:python3 montage.py CODE [out.png]
"""
import sys
import re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import os as _os
BASE_DIR = _os.path.dirname(_os.path.abspath(__file__))
BASE = _os.path.join(BASE_DIR, "car_base3.png")
PLATE = (129, 194, 1087, 652)      # 牌面 bbox on car_base3
GLYPH_DIR = _os.environ.get("GLYPH_DIR", _os.path.join(BASE_DIR, "glyphs"))
NAVY = (26, 28, 36)                # 分隔點顏色(近似字色)


def load_glyph(ch):
    return Image.open(f"{GLYPH_DIR}/{ch}.png").convert("RGBA")


def scaled(img, h):
    w = max(1, round(img.width * h / img.height))
    return img.resize((w, h), Image.LANCZOS)


def dot(h):
    d = int(h * 0.2)
    im = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([0, 0, d - 1, d - 1], fill=NAVY + (255,))
    return im


def compose(code, out="/tmp/montage.png"):
    px0, py0, px1, py1 = PLATE
    pw, ph = px1 - px0, py1 - py0
    gh = int(ph * 0.55)                       # 字高
    gap = int(gh * 0.06)                      # 字距

    pre, *rest = re.split(r"[-\s_]+", code)
    num = "".join(rest)

    tiles, kinds = [], []
    for ch in pre:
        tiles.append(scaled(load_glyph(ch), gh)); kinds.append("g")
    tiles.append(dot(gh)); kinds.append("d")   # 分隔點
    for ch in num:
        tiles.append(scaled(load_glyph(ch), gh)); kinds.append("g")

    total = sum(t.width for t in tiles) + gap * (len(tiles) - 1)
    scale = min(1.0, pw * 0.92 / total)        # 太寬則整體縮
    if scale < 1.0:
        gh2 = int(gh * scale); gap = int(gap * scale)
        tiles = [scaled(t, gh2) if k == "g" else dot(gh2) for t, k in zip(tiles, kinds)]
        total = sum(t.width for t in tiles) + gap * (len(tiles) - 1)

    # 文字層(先畫在透明層,好加陰影)
    maxh = max(t.height for t in tiles)
    layer = Image.new("RGBA", (total, maxh), (0, 0, 0, 0))
    x = 0
    for t, k in zip(tiles, kinds):
        y = (maxh - t.height) // 2 if k == "g" else int(maxh * 0.42)  # 點置中偏上
        layer.alpha_composite(t, (x, y))
        x += t.width + gap

    base = Image.open(BASE).convert("RGBA")
    ox = px0 + (pw - total) // 2
    oy = py0 + (ph - maxh) // 2

    # 柔和投影,讓字座落在牌面
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 90), (0, 0), layer)
    sh.alpha_composite(shadow, (ox + 4, oy + 6))
    sh = sh.filter(ImageFilter.GaussianBlur(4))
    base = Image.alpha_composite(base, sh)
    base.alpha_composite(layer, (ox, oy))

    base.convert("RGB").save(out, quality=95)
    return out


if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv) > 1 else "BZP-8753"
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/montage.png"
    print(compose(code, out))
