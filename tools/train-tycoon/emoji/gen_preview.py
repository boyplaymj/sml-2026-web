#!/usr/bin/env python3
# 車型 emoji 拼車 — 側視 8-bit 預覽產生器。
# 流程:Bedrock SD3.5 生側視寬圖 → 去背 → 高度正規化 → 每節切 N 個方 tile(emoji)→ 拼預覽。
# 用法: python3 gen_preview.py            (生成+處理+拼預覽 → /tmp/train-emoji/preview.png)
#        SKIP_GEN=1 python3 gen_preview.py (跳過 Bedrock,用已存在的 raw 重跑處理)
import os, sys, json, base64
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from collections import deque

OUT = os.environ.get("OUT", "/tmp/train-emoji")
os.makedirs(OUT, exist_ok=True)
H = int(os.environ.get("TILE_H", 16))     # 每個 emoji tile 的低解析度邊長(越小越 8-bit 粗)
NCOL = int(os.environ.get("NCOL", 12))    # 共用調色盤色數(越少越 8-bit)
DISP = int(os.environ.get("DISP", 20))    # 預覽放大倍率(nearest)

STYLE = ("flat side view pixel art, 8-bit NES retro style, strict side elevation, camera exactly level facing "
         "the side, chunky blocky pixels, very limited flat palette, hard flat cel shading, no gradients, "
         "a single railway vehicle centered and facing right, wheels resting on one straight horizontal rail at "
         "the very bottom edge, isolated on a pure flat white background, no sky, no ground plane, no perspective, "
         "no cast shadow, no text, no logo, no border")

# (id, 中文, tile 數, subject)  —— 車頭給 3 tile(較長)、車廂 2 tile
VEHICLES = [
    ("d51",  "D51車頭",  2, "a black Japanese JR D51 steam locomotive with a tall smokestack, round boiler, driver cab and large black driving wheels, a small white puff of steam above the smokestack"),
    ("koki", "コキ貨櫃", 2, "a JR koki flat container wagon carrying one bright red shipping container box with panel lines"),
    ("taki", "タキ罐車", 2, "a JR taki tank wagon, one horizontal silver cylindrical tank mounted on a flat wagon frame with two bogies"),
]

def bedrock(prompt, out, aspect="16:9"):
    import boto3
    cli = boto3.client("bedrock-runtime", region_name="us-west-2")
    body = {"prompt": prompt, "mode": "text-to-image", "aspect_ratio": aspect, "output_format": "png"}
    resp = cli.invoke_model(modelId="stability.sd3-5-large-v1:0", body=json.dumps(body))
    data = json.loads(resp["body"].read())
    b64 = data.get("images", [None])[0] or data.get("image")
    if not b64:
        raise SystemExit("no image: " + json.dumps(data)[:200])
    open(out, "wb").write(base64.b64decode(b64))
    print("  gen ok", out)

def remove_bg(im, tol=32):
    a = np.array(im.convert("RGBA")); h, w = a.shape[:2]; rgb = a[:, :, :3].astype(int)
    border = np.concatenate([rgb[0, :], rgb[-1, :], rgb[:, 0], rgb[:, -1]])
    bg = np.median(border, axis=0); near = np.sqrt(((rgb - bg) ** 2).sum(2)) < tol
    vis = np.zeros((h, w), bool); q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if near[y, x] and not vis[y, x]: vis[y, x] = True; q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if near[y, x] and not vis[y, x]: vis[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not vis[ny, nx] and near[ny, nx]:
                vis[ny, nx] = True; q.append((ny, nx))
    a[:, :, 3] = np.where(vis, 0, 255).astype("uint8")
    return Image.fromarray(a)

def bbox_trim(im):
    a = np.array(im); ys, xs = np.where(a[:, :, 3] > 0)
    if len(xs) == 0: return im
    return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))

def to_tiles(im, tiles):
    """去背+裁切後 → 高度正規化到 H,置中 letterbox 進 tiles*H 寬的畫布(硬邊 alpha)。"""
    im = bbox_trim(remove_bg(im))
    W = tiles * H
    # 車體塞進「底座上方」:上 H-BASE 給車身、下 BASE 留給全隊共用底座 → 車輪坐在軌道上
    rail = int(os.environ.get("RAIL_PX", 2))     # 軌道厚(最底)
    frame = int(os.environ.get("FRAME_PX", 3))   # 車架橫樑厚(其上)
    base = rail + frame
    body = im.resize((W, H - base), Image.LANCZOS)
    a = np.zeros((H, W, 4), dtype="uint8")
    a[0:H - base] = np.array(body)
    a[:, :, 3] = np.where(a[:, :, 3] > 128, 255, 0)  # 車身硬邊
    # 共用底座(全寬同色同高)→ 相鄰車拼起來軌道/車架連續、耦合無縫
    a[H - base:H - rail, :, :] = (58, 60, 66, 255)   # 車架橫樑
    a[H - rail:H, :, :] = (28, 28, 32, 255)          # 軌道
    return Image.fromarray(a)

def main():
    raws = []
    for vid, _, tiles, subj in VEHICLES:
        raw = f"{OUT}/{vid}_raw.png"
        if not os.environ.get("SKIP_GEN"):
            print("──", vid); bedrock(f"{STYLE}, {subj}", raw, "16:9")
        raws.append((vid, tiles, raw))

    # 正規化成 tile 畫布
    norm = [(vid, tiles, to_tiles(Image.open(r), tiles)) for vid, tiles, r in raws]

    # 共用 16 色調色盤(蒐集全部不透明像素 median-cut)
    pool = np.concatenate([np.array(im)[np.array(im)[:, :, 3] > 0][:, :3] for _, _, im in norm])
    pal = Image.fromarray(pool.reshape(-1, 1, 3).astype("uint8"), "RGB").quantize(colors=NCOL, method=Image.MEDIANCUT)
    def quant(im):
        a = np.array(im); alpha = a[:, :, 3]
        rgb = Image.fromarray(a[:, :, :3], "RGB").quantize(palette=pal, dither=Image.NONE).convert("RGB")
        return Image.fromarray(np.dstack([np.array(rgb), alpha]), "RGBA")
    norm = [(vid, tiles, quant(im)) for vid, tiles, im in norm]

    # 切 tile
    tiles_of = {}
    for vid, tiles, im in norm:
        tiles_of[vid] = [im.crop((i * H, 0, (i + 1) * H, H)) for i in range(tiles)]

    # ── 預覽版面 ──
    def up(im, s=DISP): return im.resize((im.width * s, im.height * s), Image.NEAREST)
    pad = 10; gap_tile = 3
    checker = (245, 245, 245); dividerc = (255, 120, 120)
    # A 區:每車型 tile 拆解(顯示 2/3 顆 emoji 的切法,tile 間畫紅虛線)
    rowsA = []
    font = ImageFont.load_default()
    for fp in ("/usr/share/fonts/google-noto-cjk/NotoSansCJK-DemiLight.ttc",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(fp):
            try: font = ImageFont.truetype(fp, 22); break
            except Exception: pass
    for vid, cn, _t, _s in VEHICLES:
        ts = [up(t) for t in tiles_of[vid]]
        w = sum(t.width for t in ts) + gap_tile * (len(ts) - 1)
        strip = Image.new("RGBA", (w, ts[0].height), checker + (255,))
        x = 0
        for i, t in enumerate(ts):
            strip.alpha_composite(t, (x, 0)); x += t.width
            if i < len(ts) - 1:
                d = ImageDraw.Draw(strip)
                for yy in range(0, strip.height, 8): d.line([(x + gap_tile // 2, yy), (x + gap_tile // 2, yy + 4)], fill=dividerc, width=2)
                x += gap_tile
        rowsA.append((vid, cn, len(ts), strip))
    # B 區:模擬編組 D51 + コキ + コキ + タキ(tile 直接連續拼、Discord 暗底)
    consist = ["d51", "koki", "koki", "taki"]
    ctiles = [up(t) for v in consist for t in tiles_of[v]]
    cw = sum(t.width for t in ctiles); ch = ctiles[0].height
    darkbg = (54, 57, 63)  # Discord 暗色
    consist_im = Image.new("RGBA", (cw + 2 * pad, ch + 2 * pad), darkbg + (255,))
    x = pad
    for t in ctiles: consist_im.alpha_composite(t, (x, pad)); x += t.width

    # 合成整張預覽
    labelh = 30
    Aw = max(s.width for _, _, _, s in rowsA) + 260
    Ah = sum(s.height for _, _, _, s in rowsA) + labelh * len(rowsA) + pad * (len(rowsA) + 1)
    W = max(Aw, consist_im.width + 2 * pad) + 2 * pad
    Hh = Ah + consist_im.height + labelh * 2 + pad * 4
    canvas = Image.new("RGBA", (W, Hh), (255, 255, 255, 255))
    d = ImageDraw.Draw(canvas)
    y = pad
    d.text((pad, y), "每一節 = 2~3 顆 emoji(紅線=emoji邊界,同源切開天生連續)", fill=(40, 40, 40), font=font); y += labelh
    for vid, cn, ntile, strip in rowsA:
        canvas.alpha_composite(strip, (pad, y))
        d.text((strip.width + pad + 20, y + strip.height // 2 - 12), f"{cn}  ({ntile}顆emoji)", fill=(30, 30, 30), font=font)
        y += strip.height + pad
    y += pad
    d.text((pad, y), "在 Discord 訊息裡拼成編組:D51 + コキ + コキ + タキ", fill=(40, 40, 40), font=font); y += labelh
    canvas.alpha_composite(consist_im, (pad, y))
    out = f"{OUT}/preview.png"; canvas.convert("RGB").save(out)
    print("PREVIEW", out, canvas.size)

if __name__ == "__main__":
    main()
