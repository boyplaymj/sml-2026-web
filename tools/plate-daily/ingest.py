#!/usr/bin/env python3
"""號碼灌入 CLI(統一入口的手動/檔案來源)

用法:
    python3 ingest.py CODE [CODE ...]        # 直接帶號碼
    python3 ingest.py -f codes.txt           # 從檔案(每行一個,或逗號分隔)
    cat codes.txt | python3 ingest.py -       # 從 stdin

正規化 + 去重都在 db.add_codes 裡,重複灌不會覆蓋既有資料。
"""
import sys
import re

import db


def _split(text):
    return [t for t in re.split(r"[,\n\r\t]+", text) if t.strip()]


def main(argv):
    src = "manual"
    codes = []
    if not argv:
        print(__doc__)
        return 1
    if argv[0] == "-f":
        if len(argv) < 2:
            print("❌ -f 需要檔名:python3 ingest.py -f codes.txt")
            return 1
        with open(argv[1], encoding="utf-8") as fh:
            codes = _split(fh.read())
        src = "import"
    elif argv[0] == "-":
        codes = _split(sys.stdin.read())
        src = "import"
    else:
        codes = argv

    res = db.add_codes(codes, source=src)
    print(f"✅ 新增 {len(res['added'])}｜略過(重複) {len(res['skipped'])}｜無效 {len(res['invalid'])}")
    if res["added"]:
        print("  新增:", ", ".join(res["added"][:20]) + (" …" if len(res["added"]) > 20 else ""))
    if res["invalid"]:
        print("  ⚠️ 無效(格式不符):", ", ".join(map(str, res["invalid"][:20])))
    print(f"  目前表內總數:{db.count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
