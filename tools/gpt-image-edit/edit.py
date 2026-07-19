#!/usr/bin/env python3
"""
gpt-image-edit — 用 OpenAI GPT Image 2 對既有圖做「精準微調」的個人 CLI。

核心用途：Gemini/nano-banana 聽不懂指令時，改用 GPT Image 2 的 images/edits，
搭配 mask 只重繪指定區域，其餘不動。

用法：
  # 整張依指令重繪（會連沒指定的地方一起變，適合大改）
  ./edit.py in.png "把背景換成夜晚的城市，霓虹燈" -o out.png

  # 局部微調（推薦）：只改 mask 透明區，其餘鎖住
  ./edit.py in.png "把角色的帽子改成紅色" --mask mask.png -o out.png

  # 多張參考圖（把幾張圖的元素合成一張）
  ./edit.py a.png b.png "讓 a 的角色站在 b 的場景裡" -o out.png

環境變數：
  OPENAI_API_KEY   必填。跟 Claude 帳號無關，要另開 OpenAI 付費帳號。

mask 規則（很重要）：
  mask 必須是「跟原圖同尺寸的 PNG」，且帶 alpha 通道。
  **透明(alpha=0)的區域 = 允許被重繪**；不透明的區域 = 鎖住不動。
  可用 --make-mask-from 產生一張全透明的空白 mask 當起點，再拿修圖軟體塗黑要保留的地方。
"""
import argparse
import base64
import os
import sys
import tempfile
from datetime import datetime

# 官方估算單價（1024x1024，USD/張）。edit 情境參考圖以高保真讀入，實際約 2-3x。
_QUALITY_COST = {"low": 0.006, "medium": 0.053, "high": 0.211}


def _die(msg: str, code: int = 1):
    print(f"錯誤：{msg}", file=sys.stderr)
    sys.exit(code)


def make_blank_mask(ref_image: str, out_path: str):
    """依參考圖尺寸產一張全透明 PNG 當 mask 起點。"""
    try:
        from PIL import Image
    except ImportError:
        _die("--make-mask-from 需要 Pillow：pip install Pillow")
    src = Image.open(ref_image)
    mask = Image.new("RGBA", src.size, (0, 0, 0, 0))  # 全透明=全部可編輯
    mask.save(out_path)
    print(f"已產生空白 mask：{out_path}（{src.size[0]}x{src.size[1]}，全透明）")
    print("下一步：用修圖軟體把『要保留、不准動』的區域塗成不透明(黑)，再存回。")


def _parse_len(token: str, full: int) -> int:
    """把 '30' 當像素、'30%' 當該維度百分比。"""
    token = token.strip()
    if token.endswith("%"):
        return round(float(token[:-1]) / 100.0 * full)
    return round(float(token))


def build_region_mask(ref_image: str, regions, feather: int, save_to: str = None) -> str:
    """
    依座標圈選自動產 mask，回傳暫存檔路徑（呼叫端負責清理）。

    region 語法（可重複）：
      rect:x,y,w,h        矩形，左上角(x,y) 寬高(w,h)
      ellipse:x,y,w,h     橢圓，內接於該矩形
    座標可用像素或百分比（如 10%,10%,30%,25%），左上為原點。
    圈到的區域 = 可編輯（透明）；其餘鎖住（不透明）。
    """
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        _die("--region 需要 Pillow：pip install Pillow")

    src = Image.open(ref_image)
    w, h = src.size
    alpha = Image.new("L", (w, h), 255)  # 255=不透明=全鎖住
    draw = ImageDraw.Draw(alpha)

    for spec in regions:
        try:
            shape, coords = spec.split(":", 1)
            parts = coords.split(",")
            if len(parts) != 4:
                raise ValueError
            x = _parse_len(parts[0], w)
            y = _parse_len(parts[1], h)
            rw = _parse_len(parts[2], w)
            rh = _parse_len(parts[3], h)
        except ValueError:
            _die(f"region 格式錯誤：{spec}（應為 rect:x,y,w,h 或 ellipse:x,y,w,h）")
        box = [x, y, x + rw, y + rh]
        if shape == "rect":
            draw.rectangle(box, fill=0)     # 0=透明=可編輯
        elif shape == "ellipse":
            draw.ellipse(box, fill=0)
        else:
            _die(f"不支援的形狀：{shape}（只支援 rect / ellipse）")

    if feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather))  # 邊緣羽化，融合更自然

    mask = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask.putalpha(alpha)

    out_path = save_to or tempfile.NamedTemporaryFile(
        suffix=".png", delete=False).name
    mask.save(out_path)
    return out_path


def run_edit(args):
    try:
        from openai import OpenAI
    except ImportError:
        _die("需要 openai SDK：pip install openai")

    if not os.environ.get("OPENAI_API_KEY"):
        _die("未設定 OPENAI_API_KEY 環境變數")

    for p in args.images:
        if not os.path.isfile(p):
            _die(f"找不到輸入圖：{p}")
    if args.mask and not os.path.isfile(args.mask):
        _die(f"找不到 mask：{args.mask}")
    if args.mask and args.region:
        _die("--mask 與 --region 擇一（--region 會自動產 mask）")

    # 座標圈選 → 自動產 mask（依第一張圖尺寸）
    auto_mask_path = None
    mask_path = args.mask
    if args.region:
        auto_mask_path = build_region_mask(
            args.images[0], args.region, args.feather, save_to=args.save_mask)
        mask_path = auto_mask_path
        print(f"→ 已依 {len(args.region)} 個圈選區自動產 mask"
              f"{'（羽化 %dpx）' % args.feather if args.feather else ''}"
              f"{'，另存 ' + args.save_mask if args.save_mask else ''}")

    client = OpenAI()

    # openai SDK：多張圖傳 list of file handles
    image_files = [open(p, "rb") for p in args.images]
    mask_file = open(mask_path, "rb") if mask_path else None

    kwargs = dict(
        model=args.model,
        image=image_files if len(image_files) > 1 else image_files[0],
        prompt=args.prompt,
        size=args.size,
        quality=args.quality,
        n=args.n,
    )
    if mask_file:
        kwargs["mask"] = mask_file

    print(f"→ 呼叫 {args.model}｜quality={args.quality}｜size={args.size}｜n={args.n}"
          f"{'｜含 mask 局部重繪' if mask_file else ''}")
    try:
        resp = client.images.edit(**kwargs)
    except Exception as e:  # noqa: BLE001
        _die(f"API 呼叫失敗：{e}")
    finally:
        for f in image_files:
            f.close()
        if mask_file:
            mask_file.close()
        # 清掉暫存的自動 mask（除非使用者用 --save-mask 要求保留）
        if auto_mask_path and not args.save_mask and os.path.isfile(auto_mask_path):
            os.unlink(auto_mask_path)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base, ext = os.path.splitext(args.output)
    ext = ext or ".png"

    for i, data in enumerate(resp.data):
        img_b64 = data.b64_json
        if not img_b64:
            _die("回傳沒有影像資料")
        out = args.output if args.n == 1 else f"{base}-{i+1}{ext}"
        if args.n > 1:
            out = f"{base}-{stamp}-{i+1}{ext}"
        with open(out, "wb") as fh:
            fh.write(base64.b64decode(img_b64))
        print(f"✓ 已存 {out}")

    # 成本提示（估算，非帳單）
    per = _QUALITY_COST.get(args.quality, 0.05)
    lo, hi = per * args.n, per * args.n * 3
    print(f"約略成本估算：${lo:.3f} ~ ${hi:.3f}（edit 含參考圖高保真，取區間上緣較準）")


def main():
    ap = argparse.ArgumentParser(
        description="用 GPT Image 2 精準微調既有圖片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("images", nargs="*", help="輸入圖片路徑（可多張當參考）")
    ap.add_argument("prompt", nargs="?", help="修改指令（自然語言）")
    ap.add_argument("-o", "--output", default="out.png", help="輸出檔名（預設 out.png）")
    ap.add_argument("-m", "--mask", help="mask PNG：透明區=可編輯、不透明區=鎖住")
    ap.add_argument("--region", action="append", metavar="SPEC",
                    help="座標圈選自動產 mask（可重複）："
                         "rect:x,y,w,h 或 ellipse:x,y,w,h，座標可用像素或 %%")
    ap.add_argument("--feather", type=int, default=0,
                    help="mask 邊緣羽化像素（讓改動融合更自然，預設 0）")
    ap.add_argument("--save-mask", metavar="PATH",
                    help="把自動產生的 mask 另存下來供檢視/微調")
    ap.add_argument("--model", default="gpt-image-2", help="模型（預設 gpt-image-2）")
    ap.add_argument("--size", default="1024x1024",
                    help="1024x1024 / 1536x1024 / 1024x1536 / auto（預設 1024x1024）")
    ap.add_argument("--quality", default="medium",
                    choices=["low", "medium", "high"], help="品質/成本（預設 medium）")
    ap.add_argument("-n", type=int, default=1, help="一次生幾張候選（預設 1）")
    ap.add_argument("--make-mask-from", metavar="IMG",
                    help="依此圖尺寸產一張全透明空白 mask 到 -o 指定路徑後結束")
    args = ap.parse_args()

    if args.make_mask_from:
        make_blank_mask(args.make_mask_from, args.output)
        return

    if not args.images or not args.prompt:
        ap.error("需要至少一張輸入圖 + 一段修改指令。範例：./edit.py in.png \"把帽子改紅色\" -o out.png")

    run_edit(args)


if __name__ == "__main__":
    main()
