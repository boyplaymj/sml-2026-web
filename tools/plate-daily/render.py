#!/usr/bin/env python3
"""渲染層:給號碼 → 產出單張車牌圖,並落地快取(同號=同圖)。

- 本地快取 cache/plates/<code>.png 為權威來源(存在就重用,永不重生)
- 同步上傳圖床 image.boyplaymj.link/plates/<code>.png,回填 DB imageUrl
- 字庫齊 → 用 montage 真字拼;缺字 → 字型 fallback(playwright)
"""
import os
import re
import subprocess

import db
import montage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache", "plates")
GLYPH_DIR = os.environ.get("GLYPH_DIR", os.path.join(BASE_DIR, "glyphs"))
COMPOSE_HTML = os.path.join(BASE_DIR, "compose_font.html")
S3_BUCKET = "boyplaymj-image"
IMG_BASE = "https://image.boyplaymj.link"
REGION = "ap-southeast-1"

os.makedirs(CACHE_DIR, exist_ok=True)


def _chars(code):
    pre, *rest = re.split(r"[-\s_]+", code)
    return set(pre) | set("".join(rest))


def _have_all_glyphs(code):
    return all(os.path.exists(f"{GLYPH_DIR}/{c}.png") for c in _chars(code))


# 字元只會是正規化後的 [A-Z0-9-],但仍以 env 傳參、避免任何字串注入面
_FALLBACK_JS = r"""
import os
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright
code = os.environ["PLATE_CODE"]
out = os.environ["PLATE_OUT"]
html = os.environ["PLATE_HTML"]
url = "file://" + html + "?" + urlencode({"code": code})
with sync_playwright() as pw:
    b = pw.chromium.launch(); p = b.new_page(viewport={"width":1216,"height":832})
    p.goto(url); p.wait_for_timeout(400)
    p.query_selector(".stage").screenshot(path=out)
    b.close()
"""


def _font_fallback(code, out):
    """字庫不齊時的暫代:playwright 套字型渲染。code 經 env 傳入,無字串拼接注入。"""
    env = dict(
        os.environ,
        FONTCONFIG_FILE=os.path.expanduser("~/.fonts/fonts.conf"),
        PLATE_CODE=code,
        PLATE_OUT=os.path.abspath(out),
        PLATE_HTML=COMPOSE_HTML,
    )
    subprocess.run(["python3", "-c", _FALLBACK_JS], check=True, env=env)


def _upload(code, path):
    """上傳圖床(best-effort),回傳 URL 或 None。"""
    key = f"plates/{code}.png"
    try:
        subprocess.run(
            ["aws", "s3", "cp", path, f"s3://{S3_BUCKET}/{key}",
             "--region", REGION, "--content-type", "image/png", "--only-show-errors"],
            check=True,
        )
        return f"{IMG_BASE}/{key}"
    except Exception as e:
        print(f"  ⚠️ 上傳圖床失敗 {code}: {str(e)[:80]}")
        return None


def _maybe_upload(code, path, upload):
    """需要時上傳圖床並回填 imageUrl;已有 imageUrl 則不覆蓋。"""
    if not upload:
        return
    item = db.get(code)
    if item and item.get("imageUrl"):
        return                       # 已回填,維持同號同圖、不覆蓋
    url = _upload(code, path)
    if url:
        db.set_image_url(code, url)


def ensure_plate(code, upload=True):
    """確保 code 有快取圖;回傳本地路徑。存在則直接重用(同號=同圖)。"""
    code = db.normalize_code(code)   # entrypoint 強制正規化,不合法直接擋
    if not code:
        raise ValueError(f"非法號碼格式:{code!r}")
    path = f"{CACHE_DIR}/{code}.png"

    if os.path.exists(path):
        _maybe_upload(code, path, upload)   # cache hit 也補回填(修 Codex Medium)
        return path

    if _have_all_glyphs(code):
        montage.GLYPH_DIR = GLYPH_DIR
        montage.compose(code, path)
        how = "montage真字"
    else:
        _font_fallback(code, path)
        how = "字型fallback"
    print(f"  渲染 {code}（{how}）")

    _maybe_upload(code, path, upload)
    return path


if __name__ == "__main__":
    import sys
    for c in sys.argv[1:]:
        print(ensure_plate(c, upload=False))
