#!/usr/bin/env python3
"""發佈字庫覆蓋度到 S3,供老司機後台「字庫覆蓋」分頁讀取。

掃 glyphs/ 有哪些字元 → 產 {char:bool}(A-Z + 0-9)→ 寫 S3。
字庫變動後(裁了新字)重跑一次即可。
"""
import os
import json
import datetime as dt
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GLYPH_DIR = os.path.join(BASE_DIR, "glyphs")
CHARS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
S3_BUCKET = "boyplaymj-image"
S3_KEY = "plate-meta/atlas.json"
REGION = "ap-southeast-1"


def build():
    have = {c: os.path.exists(os.path.join(GLYPH_DIR, f"{c}.png")) for c in CHARS}
    missing = [c for c in CHARS if not have[c]]
    return {
        "glyphs": have,
        "haveCount": sum(have.values()),
        "total": len(CHARS),
        "missing": missing,
        "updatedAt": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def publish(data):
    tmp = "/tmp/atlas.json"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    subprocess.run(
        ["aws", "s3", "cp", tmp, f"s3://{S3_BUCKET}/{S3_KEY}",
         "--region", REGION, "--content-type", "application/json", "--only-show-errors"],
        check=True,
    )
    return f"s3://{S3_BUCKET}/{S3_KEY}"


if __name__ == "__main__":
    data = build()
    where = publish(data)
    print(f"✅ 已發佈 {where}")
    print(f"   有 {data['haveCount']}/{data['total']} 字;缺:{' '.join(data['missing'])}")
