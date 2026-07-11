"""每日車牌 · 資料層核心

- 統一入口:add_codes() 去重寫入 DynamoDB(來源無關,手動/匯入/爬蟲都走這)
- 號碼正規化:normalize_code()
- 供之後每日推播用:pick_for_today() / mark_posted()

表:sml-plate-codes (ap-southeast-1, PAY_PER_REQUEST)
"""
import re
import time
import random
import datetime as dt

import boto3
from botocore.exceptions import ClientError

REGION = "ap-southeast-1"
TABLE = "sml-plate-codes"

_ddb = boto3.resource("dynamodb", region_name=REGION)
_table = _ddb.Table(TABLE)

# 番號樣式:2~6 個英文字母前綴 + 2~5 位數字,例 SSIS-698 / ABP-123 / MIDV-789
_VALID = re.compile(r"^[A-Z]{2,6}-\d{2,5}$")
_SPLIT = re.compile(r"^([A-Z]{2,6})[-\s_]*?(\d{2,5})$")


def normalize_code(raw: str):
    """把各種寫法正規化成 'PREFIX-NUMBER'。無法辨識回傳 None。

    'ssis698' / 'SSIS 698' / 'ssis-698' -> 'SSIS-698'（保留前導零)
    """
    if not raw:
        return None
    s = raw.strip().upper().replace("　", "")           # 去全形空白
    s = re.sub(r"\s+", "", s)                            # 去所有空白
    m = _SPLIT.match(s)
    if not m:
        return None
    code = f"{m.group(1)}-{m.group(2)}"
    return code if _VALID.match(code) else None


def add_codes(raw_codes, source="manual"):
    """去重寫入。回傳 {'added':[], 'skipped':[], 'invalid':[]}。

    - invalid:正規化失敗
    - skipped:已存在(主鍵條件擋掉,不覆蓋既有 imageUrl 等)
    - added  :本次新增
    """
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    added, skipped, invalid = [], [], []
    seen = set()                                          # 同批次內去重
    for raw in raw_codes:
        code = normalize_code(raw)
        if not code:
            invalid.append(raw)
            continue
        if code in seen:
            skipped.append(code)
            continue
        seen.add(code)
        try:
            _table.put_item(
                Item={
                    "code": code,
                    "status": "active",
                    "createdAt": now,
                    "postedCount": 0,
                    "source": source,
                },
                ConditionExpression="attribute_not_exists(code)",
            )
            added.append(code)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                skipped.append(code)
            else:
                raise
    return {"added": added, "skipped": skipped, "invalid": invalid}


def count():
    """概略總數(scan Count,小表足夠)。"""
    total = 0
    kwargs = {"Select": "COUNT"}
    while True:
        r = _table.scan(**kwargs)
        total += r["Count"]
        if "LastEvaluatedKey" not in r:
            return total
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def pick_for_today(n=4):
    """選 n 個號碼:優先沒推過的、其次最久沒推的;同級隨機。

    小表一天一次 scan,成本可忽略。回傳 item list。
    """
    items = []
    kwargs = {
        "FilterExpression": "#s = :active",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":active": "active"},
        "ProjectionExpression": "code, imageUrl, postedCount, lastPostedAt",
    }
    while True:
        r = _table.scan(**kwargs)
        items.extend(r["Items"])
        if "LastEvaluatedKey" not in r:
            break
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]

    random.shuffle(items)  # 同級隨機的基礎
    items.sort(key=lambda it: (
        int(it.get("postedCount", 0)),
        it.get("lastPostedAt", ""),   # 空字串排最前 = 沒推過的優先
    ))
    return items[:n]


def get(code):
    """取單筆 item(強一致讀),不存在回 None。"""
    r = _table.get_item(Key={"code": code}, ConsistentRead=True)
    return r.get("Item")


def mark_posted(codes):
    """把選中的號碼 postedCount+1、更新 lastPostedAt(逐筆重試,降低半套風險)。

    回傳未能標記成功的 code 清單(全成功則空)。
    """
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    failed = []
    for code in codes:
        for attempt in range(3):
            try:
                _table.update_item(
                    Key={"code": code},
                    UpdateExpression="SET postedCount = if_not_exists(postedCount, :z) + :one, lastPostedAt = :t",
                    ExpressionAttributeValues={":one": 1, ":z": 0, ":t": now},
                )
                break
            except ClientError:
                if attempt == 2:
                    failed.append(code)
                else:
                    time.sleep(0.5 * (attempt + 1))
    return failed


def set_image_url(code, url):
    """第一次生成後回填快取圖網址(同號=同圖的關鍵)。"""
    _table.update_item(
        Key={"code": code},
        UpdateExpression="SET imageUrl = :u",
        ExpressionAttributeValues={":u": url},
    )
