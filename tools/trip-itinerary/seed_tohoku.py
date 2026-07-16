#!/usr/bin/env python3
"""P1 seed: 灌入東北行程為第一筆，並讀回驗證。
用法: python3 seed_tohoku.py            # 若已存在會沿用原 privateKey（不覆蓋 hash）
      python3 seed_tohoku.py --newkey   # 強制產新 key
"""
import boto3, hashlib, secrets, json, sys, datetime
from boto3.dynamodb.conditions import Key

REGION = "ap-southeast-1"
TABLE  = "sml-trip-itineraries"
TRIP_ID = "tohoku-2026-0826"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
tbl = dynamodb.Table(TABLE)

def sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode()).hexdigest()

# 行程結構（與前端 tohoku-0826.html 的 TRIP 一致；note=內部提醒，private=公開版隱藏）
DAYS = [
  {"no":1,"date":"8/26","wd":"三","theme":"宮城上陸！拉普拉斯之夜 & 裝備採買","items":[
    {"time":"14:35","ttl":"抵達仙台機場・接駁取車","desc":"搭接駁車至 TIMES 門市取車出發","tag":"✈️"},
    {"time":"17:00","ttl":"飯店 Check-in・拉普拉斯主題房","desc":"開箱夢幻主題房、領取專屬周邊","tag":"🛏️",
     "note":"Day1 飯店名稱未定 — 建議先確認訂房與『拉普拉斯主題房』是否真有此房型"},
    {"time":"晚餐","ttl":"仙台名物・烤牛舌","desc":"","tag":"🐮"},
    {"time":"採買","ttl":"東北寶可夢中心","desc":"仙台車站旁 PARCO 8F 買裝備","tag":"⚡"},
    {"time":"晚上","ttl":"吉伊卡哇・宮城限定鐵牌","desc":"車站內 KIOSK 掃貨","tag":"🩷"},
    {"time":"~21:00","ttl":"寶可夢機台","desc":"步行至 Yodobashi 仙台店 5F Molly Fantasy 打到 9 點","tag":"🎮"},
  ]},
  {"no":2,"date":"8/27","wd":"四","theme":"拉普拉斯公園 → 神社祈福 → 咖哩大作戰","items":[
    {"time":"上午","ttl":"拉普拉斯公園 in せんだい","desc":"2026 全新開幕、挑戰巨大溜滑梯","tag":"🛝",
     "note":"這天排程偏滿：公園與神社都掛『上午』，實際只能擇一先跑，另一個往後挪"},
    {"time":"上午","ttl":"鹽竈神社祈福","desc":"求全家交通安全御守","tag":"⛩️"},
    {"time":"午餐","ttl":"CoCo 壱番屋・島嶼咖哩","desc":"點 4 份抽吉伊卡哇周邊（往松島途中）","tag":"🍛"},
    {"time":"下午","ttl":"松島海岸","desc":"吃烤牡蠣、捕捉『拉普拉斯人孔蓋』","tag":"🦪"},
    {"time":"國道","ttl":"長者原 SA（下行）集章","desc":"上高速往北、收集寶可夢印章","tag":"🚗"},
    {"time":"晚上","ttl":"入住 Comfort Inn 一之關 IC","desc":"","tag":"🛏️"},
    {"time":"~21:00","ttl":"GiGO 一之關店機台","desc":"晚餐後開車 4 分鐘、打到 9 點","tag":"🎮"},
  ]},
  {"no":3,"date":"8/28","wd":"五","theme":"岩手鐵牌 → 小拳石公園 → 極致和牛溫泉","items":[
    {"time":"上午","ttl":"平泉・小拳石人孔蓋","desc":"平泉車站捕捉","tag":"🪨"},
    {"time":"上午","ttl":"中尊寺・岩手限定吉伊卡哇鐵牌","desc":"中尊寺旁掃貨","tag":"🩷"},
    {"time":"國道","ttl":"前澤 SA（下行）集章","desc":"高速往北、收集印章","tag":"🚗"},
    {"time":"下午","ttl":"小拳石公園 in きたかみ","desc":"北上市展勝地全新公園朝聖","tag":"🛝"},
    {"time":"16:00","ttl":"入住花卷溫泉・愛隣館","desc":"結びの宿・小拳石主題房、前澤牛大餐+溫泉，今晚提早休息","tag":"♨️"},
  ]},
  {"no":4,"date":"8/29","wd":"六","theme":"盛岡八幡宮 → 幻之寶可夢隱藏關 → 光之美少女之夜","items":[
    {"time":"上午","ttl":"盛岡八幡宮參拜","desc":"退房後前往岩手最強總鎮守","tag":"⛩️"},
    {"time":"上午","ttl":"小岩井農場","desc":"吃霜淇淋、看羊群","tag":"🍦"},
    {"time":"國道","ttl":"前澤 SA（上行）集章","desc":"一路南下開回仙台","tag":"🚗"},
    {"time":"國道","ttl":"長者原 SA（上行）集章","desc":"","tag":"🚗"},
    {"time":"彩蛋","ttl":"菅生 PA（上行）・瑪納霏金印章","desc":"頑皮熊貓+30 週年集章破關","tag":"✨",
     "note":"菅生 PA 在仙台『以南』：南下回仙台市區會先過交流道下高速，收這個彩蛋要開過頭再折返。建議改天/改順序"},
    {"time":"傍晚","ttl":"入住 Comfort Hotel 仙台東口","desc":"雙床、小學生免費","tag":"🛏️"},
    {"time":"~21:00","ttl":"ROUND1 機台最終戰","desc":"視體力選『苦竹店(輕鬆)』或『泉店 Spo-cha(放電)』，抽名偵探光之美少女杯墊","tag":"🎮"},
  ]},
  {"no":5,"date":"8/30","wd":"日","theme":"吉伊卡哇見面會 → 滿載而歸","items":[
    {"time":"上午","ttl":"AEON MALL 新利府","desc":"吃完飯店早餐直奔、吉伊卡哇電影版快閃店+三隻人偶見面會","tag":"🩷",
     "note":"見面會多半需現場抽選/預約，出發前先查當天場次與整理券規則"},
    {"time":"16:00","ttl":"出發前往仙台機場","desc":"走高速直奔","tag":"🚗"},
    {"time":"16:30","ttl":"TIMES 仙台機場門市還車","desc":"16:30–16:50 完成","tag":"🔑"},
    {"time":"19:00","ttl":"虎航 IT255 返台","desc":"帶著戰利品與回憶平安返台","tag":"✈️"},
  ]},
]

now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

# 沿用既有 privateKey（若已 seed 過），除非 --newkey
existing = tbl.get_item(Key={"id": TRIP_ID}).get("Item")
force_new = "--newkey" in sys.argv
if existing and not force_new and existing.get("privateKeyHash"):
    private_key = None  # 不重生，沿用舊 hash
    private_hash = existing["privateKeyHash"]
    created_at = existing.get("createdAt", now)
    print("↺ 已存在，沿用原 privateKeyHash（不變動私密連結）")
else:
    private_key = secrets.token_hex(16)   # 32 hex 明文 key（給站主）
    private_hash = sha256(private_key)
    created_at = existing.get("createdAt", now) if existing else now

item = {
    "id": TRIP_ID,
    "type": "trip",
    "slug": TRIP_ID,
    "title": "東北自駕・寶可夢×吉伊卡哇×ROUND1 大滿貫",
    "subtitle": "8/26–8/30・一家四口・自駕五日",
    "region": "日本・東北",
    "tags": ["自駕", "親子", "寶可夢", "吉伊卡哇", "ROUND1"],
    "cover": "https://image.boyplaymj.link/trip/covers/tohoku-2026-0826.jpg",
    "visibility": "public",
    "privateKeyHash": private_hash,
    "days": DAYS,
    "createdAt": created_at,
    "updatedAt": now,
}

tbl.put_item(Item=item)
print("✓ PutItem 完成")

# ---- 讀回驗證 ----
got = tbl.get_item(Key={"id": TRIP_ID}).get("Item")
checks = []
checks.append(("讀得回", got is not None))
checks.append(("id 一致", got.get("id") == TRIP_ID))
checks.append(("type=trip", got.get("type") == "trip"))
checks.append(("visibility=public", got.get("visibility") == "public"))
checks.append(("天數=5", len(got.get("days", [])) == 5))
total_items = sum(len(d["items"]) for d in DAYS)
got_items = sum(len(d["items"]) for d in got.get("days", []))
checks.append((f"項目數={total_items}", got_items == total_items))
checks.append(("privateKeyHash 存在且為 sha256", str(got.get("privateKeyHash","")).startswith("sha256:")))
checks.append(("明文 key 未落 DB", "privateKey" not in got))
# GSI 查詢驗證（列表用）
q = tbl.query(IndexName="type-updatedAt-index",
              KeyConditionExpression=Key("type").eq("trip"),
              ScanIndexForward=False)
checks.append(("GSI 查得到", any(i["id"] == TRIP_ID for i in q.get("Items", []))))

print("\n=== 讀回驗證 ===")
ok = True
for name, res in checks:
    print(f"  {'✅' if res else '❌'} {name}")
    ok = ok and res

print("\n" + ("🎉 P1 全部通過" if ok else "⚠️ 有驗證未過"))
if private_key:
    print(f"\n🔑 本次產生的私密 key（明文，只顯示這一次，DB 只存 hash）：\n   {private_key}")
    print(f"   私密連結格式：https://image.boyplaymj.link/trip/t/{TRIP_ID}#k={private_key}  （P3 前端上線後生效）")
print(f"\n項目總數：{total_items}｜更新時間：{now}")
sys.exit(0 if ok else 1)
