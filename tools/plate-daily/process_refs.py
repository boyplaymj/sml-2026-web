#!/usr/bin/env python3
"""參考資料庫 EC2 端:抓 pending 參考圖 → 裁字併字庫 → 標 processed → 更新覆蓋度。

流程:scan sml-plate-refs status=pending → 下載 imageUrl → extract_ref.extract(圖, code)
      → 更新 status(processed/error)→ 全部跑完 republish atlas。

用法:python3 process_refs.py [--overwrite]
(可手動跑,或之後掛 systemd timer 定期跑。)
"""
import os
import re
import shutil
import sys
import tempfile
import urllib.request

import boto3

import extract_ref
import publish_atlas

REGION = "ap-southeast-1"
TABLE = "sml-plate-refs"
BUCKET = "boyplaymj-image"
IMG_BASE = "https://image.boyplaymj.link"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GLYPH_DIR = os.path.join(BASE_DIR, "glyphs")
UA = "sml-plate-daily/1.0"          # 圖床 CDN 有時擋空 UA

_s3 = boto3.client("s3", region_name=REGION)


def _download(url):
    """抓 imageUrl 到暫存檔,回傳路徑;帶 UA + timeout,避免卡死/被 CDN 擋。"""
    if not url:
        raise SystemExit("這筆沒有 imageUrl")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    fd, path = tempfile.mkstemp(suffix=".img")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path

_ddb = boto3.resource("dynamodb", region_name=REGION)
_table = _ddb.Table(TABLE)


def _pending():
    items, kw = [], {
        "FilterExpression": "#s = :p",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":p": "pending"},
    }
    while True:
        r = _table.scan(**kw)
        items.extend(r["Items"])
        if "LastEvaluatedKey" not in r:
            return items
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def _mark(ref_id, status, note=""):
    _table.update_item(
        Key={"refId": ref_id},
        UpdateExpression="SET #s = :s, note = :n",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status, ":n": note},
    )


def _process_one(ref_id, code, url, overwrite):
    """裁字 → 每字縮圖傳 S3 供前端當場驗證 → 缺字才併進 glyphs/。回傳 (added, matched, total)。"""
    chars = re.sub(r"[^A-Z0-9]", "", (code or "").upper())
    path = _download(url)
    stage = tempfile.mkdtemp(prefix=f"ref-{ref_id}-")
    single = len(chars) == 1
    try:
        if single:
            # 單字元:使用者 PS 去背好的透明 PNG → 擺正+統一尺寸(大小/角度由我判定)
            extract_ref.normalize_glyph(path, chars, out_dir=stage)
        else:
            # 多字元:整張牌自動切字(重裁進暫存夾拿實際裁切)
            extract_ref.extract(path, code, overwrite=True, out_dir=stage)
        os.makedirs(GLYPH_DIR, exist_ok=True)
        added, matched = [], []
        for ch in chars:
            gp = os.path.join(stage, f"{ch}.png")
            if not os.path.exists(gp):
                continue                       # 這個字沒裁出來(黏連/雜訊)
            matched.append(ch)
            # 縮圖傳 S3:前端依 refId+字元 直接載入驗證(路徑可預測,免改 Lambda)
            _s3.upload_file(gp, BUCKET, f"plate-refs/{ref_id}/crop-{ch}.png",
                            ExtraArgs={"ContentType": "image/png"})
            # 多字元:缺字才補(不盲蓋既有好字);單字元:刻意提供故覆蓋
            dst = os.path.join(GLYPH_DIR, f"{ch}.png")
            if overwrite or single or not os.path.exists(dst):
                shutil.copy2(gp, dst)
                added.append(ch)
        return added, matched, list(chars)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        if os.path.exists(path):
            os.unlink(path)


def main(overwrite=False):
    pend = _pending()
    if not pend:
        print("沒有 pending 參考圖。")
        return 0
    print(f"待處理 {len(pend)} 張")
    any_ok = False
    for it in pend:
        ref_id, code, url = it["refId"], it.get("code", ""), it.get("imageUrl", "")
        try:
            added, matched, total = _process_one(ref_id, code, url, overwrite)
            note = f"切{len(matched)}/{len(total)} 併入字庫{len(added)}({''.join(added)})"
            _mark(ref_id, "processed", note)
            any_ok = True
            print(f"  ✅ {code}: {note}")
        except SystemExit as e:
            _mark(ref_id, "error", str(e))
            print(f"  ❌ {code}: {e}")
        except Exception as e:
            _mark(ref_id, "error", str(e)[:120])
            print(f"  ❌ {code}: {str(e)[:120]}")
    if any_ok:
        where = publish_atlas.publish(publish_atlas.build())
        print(f"已更新覆蓋度 → {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main("--overwrite" in sys.argv))
