#!/usr/bin/env python3
"""每日推播管線:選4號 → 確保快取圖 → 拼「今日四連號」 → 發頻道 → 記錄已推。

用法:
    python3 daily.py                 # 正式:選4發到預設頻道
    python3 daily.py --dry           # 只產圖不發、不記錄(測試看圖)
    python3 daily.py --channel <id>  # 指定頻道
"""
import os
import sys
import json
import fcntl
import argparse
import datetime as dt
import subprocess
import urllib.request

import boto3
from PIL import Image, ImageDraw, ImageFont

import db
import render

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_CHANNEL = "903327108451950692"          # 私人測試頻道(只有使用者看得見)
POST_SH = os.path.join(BASE_DIR, "..", "..", "aws", "discord-bridge", "post-image.sh")
LOCKFILE = "/tmp/plate_daily.lock"

# 分級鐵律:只准發到「年齡限制封閉頻道」白名單;其餘一律拒發(fail-closed)
GATED_ALLOW = {"1525321679922921522"}        # 🔞每日四連號(NSFW+封閉,已驗)
TEST_ALLOW = {TEST_CHANNEL}                  # 私人測試頻道,測試用
VIEW_CHANNEL = 1 << 10
_REGION = "ap-southeast-1"


def _bot_token():
    return boto3.client("ssm", region_name=_REGION).get_parameter(
        Name="/sml/discord-bot/token", WithDecryption=True
    )["Parameter"]["Value"]


def _fetch_channel(cid):
    req = urllib.request.Request(
        f"https://discord.com/api/v10/channels/{cid}",
        headers={
            "Authorization": f"Bot {_bot_token()}",
            "User-Agent": "DiscordBot (https://boyplaymj.com, 1.0)",  # Discord 要求 UA
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def assert_postable(cid):
    """fail-closed 分級守門:非白名單 → 拒;正式頻道 → 執行期再驗 NSFW+@everyone封閉。"""
    if cid in TEST_ALLOW:
        return                                # 私人測試頻道,放行
    if cid not in GATED_ALLOW:
        raise SystemExit(f"❌ 拒發:{cid} 不在年齡限制頻道白名單(fail-closed)")
    info = _fetch_channel(cid)
    if not info.get("nsfw"):
        raise SystemExit(f"❌ 拒發:{cid} 非 NSFW,不符分級鐵律")
    guild = info.get("guild_id")
    closed = any(
        o.get("id") == guild and (int(o.get("deny", 0)) & VIEW_CHANNEL)
        for o in info.get("permission_overwrites", [])
    )
    if not closed:
        raise SystemExit(f"❌ 拒發:{cid} @everyone 可見(非封閉頻道)")

FONT_DIR = os.path.expanduser("~/.fonts")


FONT_CANDIDATES = (
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Black.ttc",
    os.path.expanduser("~/.fonts/NotoSansCJKtc-Regular.otf"),
)


def _font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    # fail-loud:找不到 CJK 字型就 raise,別默默 load_default 出一版豆腐圖看板
    raise RuntimeError(
        "找不到 CJK 字型(NotoSansCJK),看板標題會變豆腐。"
        f"請確認以下任一存在:{', '.join(FONT_CANDIDATES)}"
    )


def make_collage(plate_paths, out="/tmp/plate_daily.png"):
    """4 張車牌圖拼成一張「今日四連號」看板(2x2 + 標題/日期/頁尾)。"""
    cell_w = 600
    plates = []
    for p in plate_paths:
        im = Image.open(p).convert("RGB")
        h = round(im.height * cell_w / im.width)
        plates.append(im.resize((cell_w, h), Image.LANCZOS))
    cell_h = max(p.height for p in plates)

    gap = 24
    pad = 40
    head_h = 96
    foot_h = 46
    W = pad * 2 + cell_w * 2 + gap
    H = pad + head_h + cell_h * 2 + gap + foot_h + pad

    bg = (18, 22, 32)
    canvas = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(canvas)

    # 標題 + 日期
    today = dt.date.today().strftime("%Y / %m / %d")
    d.text((pad, pad + 8), "今日四連號", font=_font(52), fill=(232, 237, 247))
    df = _font(30)
    dw = d.textbbox((0, 0), today, font=df)[2]
    d.text((W - pad - dw, pad + 28), today, font=df, fill=(142, 160, 192))

    # 2x2 車牌
    y0 = pad + head_h
    for i, im in enumerate(plates):
        r, c = divmod(i, 2)
        x = pad + c * (cell_w + gap)
        y = y0 + r * (cell_h + gap) + (cell_h - im.height) // 2
        canvas.paste(im, (x, y))

    # 頁尾
    foot = "— 每日更新 · 隨機推薦 —"
    ff = _font(24)
    fw = d.textbbox((0, 0), foot, font=ff)[2]
    d.text(((W - fw) // 2, H - pad - foot_h + 8), foot, font=ff, fill=(120, 134, 160))

    canvas.save(out, quality=95)
    return out


def post(channel, path, msg):
    subprocess.run(["bash", POST_SH, channel, msg, path], check=True)


def main(argv):
    ap = argparse.ArgumentParser(description="每日車牌推播")
    ap.add_argument("--dry", action="store_true", help="只產圖,不發、不記錄")
    ap.add_argument("--channel", default=TEST_CHANNEL, help="目標頻道 ID(須在白名單)")
    args = ap.parse_args(argv)

    if not args.dry:
        assert_postable(args.channel)         # 分級守門(fail-closed),發前先擋

    # 單跑鎖:避免併發 daily 選到同一批
    lock = open(LOCKFILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("⚠️ 已有另一個 daily 在跑,略過本次")
        return 0

    picks = db.pick_for_today(4)
    codes = [it["code"] for it in picks]
    if len(codes) < 4:
        print(f"⚠️ 可用號碼不足 4 個(目前 {len(codes)}),請先灌號碼")
        return 1
    print("今日選號:", codes)

    paths = [render.ensure_plate(c, upload=not args.dry) for c in codes]
    collage = make_collage(paths)
    print("拼圖完成:", collage)

    if args.dry:
        print("（--dry:不發、不記錄)")
        return 0

    today = dt.date.today().strftime("%Y/%m/%d")
    post(args.channel, collage, f"🚗 今日四連號 · {today}")
    failed = db.mark_posted(codes)
    if failed:
        print(f"⚠️ 已發送,但下列號碼標記失敗(可能重推,請人工補):{failed}")
    print(f"✅ 已發到頻道 {args.channel} 並記錄推播")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
