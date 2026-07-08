#!/usr/bin/env python3
"""DynamoDB「近 N 天實際用量」收集器(ap-southeast-1)。

抓每張表的 CloudWatch ConsumedR/WCU + describe-table 容量/item 數,×官方單價
(AWS Price List API 校準,與 cost_tracker/dashboard 的 PRICING 一致)→ 產 snapshot dict。

兩種用法:
  1) 匯入:`import gen_usage; snap = gen_usage.collect(days=30)` — 給 billing_sync.py 塞進 billing.json 的 dynamodb_usage。
  2) CLI:`python3 gen_usage.py [輸出路徑] [天數,預設30]` — 產獨立 usage.json。

輸出 schema(對齊 cost_tracker.html 期待):
  { generated_at, source, region, window_days, totals:{grandTotal,tableCount,totalGB,throughputCost,storageCost},
    tables:[ {name, cost, throughputCost, wru, rru, gb, items, class, ...} ] }   # cost=每表金額(cost_tracker 讀 cost||total||monthly)
"""
import json, sys, datetime
import boto3

REGION = "ap-southeast-1"

# 官方單價(US$/百萬 RU、US$/GB-月)。與 cost_tracker.html / dashboard PRICING[ap-southeast-1] 一致。
PRICE = {
    "STANDARD":                   {"WRU": 0.71, "RRU": 0.1425, "STOR": 0.285},
    "STANDARD_INFREQUENT_ACCESS": {"WRU": 0.89, "RRU": 0.178,  "STOR": 0.114},
}
FREE_GB = 25  # 帳號級 Standard 儲存免費額度(在總計扣一次,非每表)


def collect(region=REGION, days=30):
    """回傳 DynamoDB 用量 snapshot dict(不寫檔)。CloudWatch/describe-table 失敗會拋例外,由呼叫端處理。"""
    ddb = boto3.client("dynamodb", region_name=region)
    cw = boto3.client("cloudwatch", region_name=region)
    end = datetime.datetime.utcnow().replace(microsecond=0)
    start = end - datetime.timedelta(days=days)

    def consumed(table, metric):
        r = cw.get_metric_statistics(
            Namespace="AWS/DynamoDB", MetricName=metric,
            Dimensions=[{"Name": "TableName", "Value": table}],
            StartTime=start, EndTime=end, Period=days * 86400, Statistics=["Sum"],
        )
        return sum(p["Sum"] for p in r.get("Datapoints", []))

    tables = []
    names = [n for pg in ddb.get_paginator("list_tables").paginate() for n in pg["TableNames"]]
    for name in names:
        d = ddb.describe_table(TableName=name)["Table"]
        cls = (d.get("TableClassSummary") or {}).get("TableClass", "STANDARD")
        p = PRICE.get(cls, PRICE["STANDARD"])
        wru = consumed(name, "ConsumedWriteCapacityUnits")
        rru = consumed(name, "ConsumedReadCapacityUnits")
        gb = d.get("TableSizeBytes", 0) / 1e9
        write_cost = wru / 1e6 * p["WRU"]
        read_cost = rru / 1e6 * p["RRU"]
        tp = round(write_cost + read_cost, 4)
        tables.append({
            "name": name,
            "class": cls,
            "billingMode": (d.get("BillingModeSummary") or {}).get("BillingMode", "PROVISIONED"),
            "wru": round(wru), "rru": round(rru),
            "gb": round(gb, 4), "items": d.get("ItemCount", 0),
            "writeCost": round(write_cost, 4), "readCost": round(read_cost, 4),
            "throughputCost": tp,
            "cost": tp,   # cost_tracker.html 每列讀 t.cost||t.total||t.monthly
        })

    tables.sort(key=lambda t: t["cost"], reverse=True)

    std_gb = sum(t["gb"] for t in tables if t["class"] == "STANDARD")
    ia_gb = sum(t["gb"] for t in tables if t["class"] != "STANDARD")
    storage_cost = max(0, std_gb - FREE_GB) * PRICE["STANDARD"]["STOR"] + ia_gb * PRICE["STANDARD_INFREQUENT_ACCESS"]["STOR"]
    throughput_cost = sum(t["cost"] for t in tables)

    return {
        "generated_at": end.isoformat() + "Z",
        "region": region,
        "window_days": days,
        "window_start": start.isoformat() + "Z",
        "source": "CloudWatch ConsumedR/WCU + DynamoDB describe-table",
        "price": PRICE, "free_gb": FREE_GB,
        "totals": {
            "throughputCost": round(throughput_cost, 2),
            "storageCost": round(storage_cost, 2),
            "grandTotal": round(throughput_cost + storage_cost, 2),
            "totalGB": round(std_gb + ia_gb, 3),
            "tableCount": len(tables),
        },
        "tables": tables,
    }


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "usage.json"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    out = collect(days=days)
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    t = out["totals"]
    print(f"✅ 寫出 {out_path}")
    print(f"   近{days}天實際:吞吐 US${t['throughputCost']} + 儲存 US${t['storageCost']} = US${t['grandTotal']} · {t['tableCount']} 表")
    for x in out["tables"][:5]:
        print(f"     {x['name']:34} 寫{x['wru']:>9} 讀{x['rru']:>9} = US${x['cost']}")
