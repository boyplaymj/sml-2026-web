#!/usr/bin/env python3
"""灌一筆示範影片專案，驗證 sml-video-projects 讀寫一致。之後由真實資料取代。"""
import boto3, json, datetime

REGION = "ap-southeast-1"
TABLE = "sml-video-projects"
ddb = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)

now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

item = {
    "id": "demo-crossroad-promo",
    "type": "vproj",
    "slug": "demo-crossroad-promo",
    "title": "捍衛路權宣傳片（示範）",
    "subtitle": "路口安全・30 秒短片",
    "cover": "",
    "status": "active",
    "tasks": [
        {"tid": "t1", "title": "腳本定稿",       "date": "2026-07-17", "importance": 3, "status": "done", "tag": "企劃", "note": "30 秒三幕結構", "doneAt": now},
        {"tid": "t2", "title": "拍攝路口空景",    "date": "2026-07-20", "importance": 3, "status": "todo", "tag": "拍攝", "note": "早上光線佳，備空拍機", "doneAt": None},
        {"tid": "t3", "title": "訪談路人 3 位",    "date": "2026-07-20", "importance": 2, "status": "todo", "tag": "拍攝", "note": "", "doneAt": None},
        {"tid": "t4", "title": "剪輯初版",        "date": "2026-07-23", "importance": 3, "status": "todo", "tag": "剪輯", "note": "先粗剪對節奏", "doneAt": None},
        {"tid": "t5", "title": "上字幕",          "date": "2026-07-25", "importance": 2, "status": "todo", "tag": "上字", "note": "", "doneAt": None},
        {"tid": "t6", "title": "配樂選曲",        "date": "",           "importance": 1, "status": "todo", "tag": "配樂", "note": "未定日，找無版權", "doneAt": None},
        {"tid": "t7", "title": "發布 YT + IG",    "date": "2026-07-28", "importance": 3, "status": "todo", "tag": "發布", "note": "", "doneAt": None},
    ],
    "createdAt": now,
    "updatedAt": now,
}

ddb.put_item(Item=item)
print("PUT ok:", item["id"])

got = ddb.get_item(Key={"id": item["id"]}).get("Item")
assert got, "read back failed"
assert got["title"] == item["title"]
assert len(got["tasks"]) == len(item["tasks"])
print("read-back ok:", got["title"], "| tasks:", len(got["tasks"]),
      "| done:", sum(1 for t in got["tasks"] if t["status"] == "done"))
