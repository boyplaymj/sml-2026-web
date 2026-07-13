#!/usr/bin/env python3
# 通用截圖器:把 HTML 的某元素(預設 .stage)截成 PNG。
# 用法: FONTCONFIG_FILE=~/.fonts/fonts.conf python3 shot.py <in.html> <out.png> [selector]
import sys, os
from playwright.sync_api import sync_playwright

html, out = sys.argv[1], sys.argv[2]
sel = sys.argv[3] if len(sys.argv) > 3 else ".stage"
url = "file://" + os.path.abspath(html)
with sync_playwright() as pw:
    b = pw.chromium.launch()
    p = b.new_page(device_scale_factor=2)
    p.goto(url)
    p.wait_for_timeout(400)
    el = p.query_selector(sel)
    if not el:
        raise SystemExit(f"selector not found: {sel}")
    el.screenshot(path=out)
    b.close()
print("ok", out)
