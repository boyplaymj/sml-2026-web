"""
SML 賽程自動同步 Lambda
  Google Sheet(男生組/女生組分頁) -> 解析 -> 寫成 s3://boyplaymj-smlweb/sml-site/data/schedule.json
  由 EventBridge 每小時觸發。網站 app.js 載入時 fetch 這個 json(抓不到就用內建後備)。
  只用 Python 內建函式庫 + boto3(Lambda 執行環境內建),無外部相依、無密鑰。
"""
import csv
import io
import json
import re
import urllib.parse
import urllib.request

import boto3

SHEET_ID = "1_64EeJbdSuxbQzuIzWquNbkAs7Om3_Ti9w-VuQteE1A"
BUCKET = "boyplaymj-smlweb"
KEY = "sml-site/data/schedule.json"
TABS = {"men": "男生組", "women": "女生組"}  # 輸出 key -> 試算表分頁名


def fetch_csv(tab_name):
    """抓指定分頁的 CSV(gviz 匯出)。"""
    q = urllib.parse.urlencode({"tqx": "out:csv", "sheet": tab_name})
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8")


def parse(csv_text):
    """CSV -> [{g, date, cast, players[]}]。第一列是表頭;組別欄取數字當 g。"""
    games = []
    for row in list(csv.reader(io.StringIO(csv_text)))[1:]:
        if len(row) < 7:
            continue
        m = re.search(r"(\d+)", (row[0] or "").strip())  # "Game 1" -> 1
        if not m:
            continue
        date = (row[1] or "").strip()
        cast = (row[2] or "").strip()
        players = [p for p in ((row[i] or "").strip() for i in range(3, 7)) if p]
        if not date or not players:
            continue
        games.append({"g": int(m.group(1)), "date": date, "cast": cast, "players": players})
    return games


def handler(event, context):
    out = {key: parse(fetch_csv(tab)) for key, tab in TABS.items()}
    # 安全閥:任一組解析不到資料就不覆蓋,保留上一份正確的 schedule.json
    if not out["men"] or not out["women"]:
        raise RuntimeError(f"解析結果異常,放棄寫入: men={len(out['men'])} women={len(out['women'])}")
    body = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    boto3.client("s3").put_object(
        Bucket=BUCKET,
        Key=KEY,
        Body=body,
        ContentType="application/json; charset=utf-8",
        CacheControl="public, max-age=300",
    )
    return {"ok": True, "men": len(out["men"]), "women": len(out["women"]), "bytes": len(body)}
