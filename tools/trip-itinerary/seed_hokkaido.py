#!/usr/bin/env python3
"""灌入北海道 8 天 7 夜親子自駕行程（公開版）。
用法: python3 seed_hokkaido.py            # 沿用既有 privateKey（若已 seed 過）
      python3 seed_hokkaido.py --newkey   # 強制產新 key
結構/欄位與 seed_tohoku.py 一致。此為『出發前計畫版』，公開檢視。
"""
import boto3, hashlib, secrets, sys, datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key

REGION = "ap-southeast-1"
TABLE  = "sml-trip-itineraries"
TRIP_ID = "hokkaido-2026-0524"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
tbl = dynamodb.Table(TABLE)

def sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode()).hexdigest()

# 照片圖床基底（每天一個 hero 大圖 + 各項目 photos）
PH = "https://image.boyplaymj.link/trip/photos/hokkaido-2026-0524/"

# ── diary 編輯風：總覽地圖（數值全抄 preview.html 的 STOPS/ROUTE/stats）──
STOPS = [
    {"no": 1, "name": "新千歲機場",     "ll": [Decimal("42.775"), Decimal("141.692")]},
    {"no": 2, "name": "洞爺湖",         "ll": [Decimal("42.593"), Decimal("140.855")]},
    {"no": 3, "name": "函館",           "ll": [Decimal("41.768"), Decimal("140.729")]},
    {"no": 4, "name": "登別",           "ll": [Decimal("42.413"), Decimal("141.107")]},
    {"no": 5, "name": "札幌",           "ll": [Decimal("43.062"), Decimal("141.354")]},
    {"no": 6, "name": "小樽",           "ll": [Decimal("43.190"), Decimal("140.994")]},
    {"no": 7, "name": "新千歲・PORTOM", "ll": [Decimal("42.790"), Decimal("141.665")]},
]
# OSRM 編碼 polyline（precision 5，實際行車路線；抄 preview.html ROUTE）
POLYLINE = "cjadGslx_ZfjJ_xB`yFdhFljC|wKoaShe_@jqCjdR`uD~bFooBfkHzoClg\\~{Ll}NvuGpCnxBjgb@wj@huGttAfqHktGhdQxPfne@jkZbsWz}\\reKbeKoaCzxE_mT~aX}_e@jiTeoIjhLjqAtnR}uOtsEa`@msE|_@wnRrvOqhL}qAkiTdoI_bX|_e@_uE`fTsbCv~ByhLgYyzR{`G_k_@}sZ}d@yzRzrAc~DkkAqqCxvAqhPvoNioPvcGmlOxgRohIxrDq`RgcMcfNanXwzm@{nCdpBi_BcbNgqI_oP{hHsz\\eoIwSwxOv_Fy}EdzI_wJh~Ac{Zjjd@ssFvw@jcAvsMk`EftEkmLjfn@hmLwgn@|~DaqEyxAewRxaBsjGdoUw}JjbLwgNnoBqhI~gDdc@ruI{}M`~DoMouA`]"
OVERVIEW = {
    "lead": "八天環道路線 · 點圖釘看每一天",
    "stops": STOPS,
    "polyline": POLYLINE,
    "stats": [
        {"v": "8",    "label": "天 7 夜"},
        {"v": "4",    "label": "一家人"},
        {"v": "~700", "label": "公里自駕"},
        {"v": "6",    "label": "座城市"},
    ],
}

DAYS = [
  {"no":1,"date":"5/24","wd":"日","theme":"壽星降臨！機場尋寶、洞爺湖溫泉與煙火","hero":PH+"d1-pilot-pikachu.jpg",
   "kicker":"Day 1 · 5/24 週日",
   "intro":"班機提早落地，一家人索性先攻國內線的寶可夢商店尋寶；一路往洞爺湖，大雨打亂了芝櫻計畫，卻換來一整晚泡湯、和食會席與房間裡的煙火。",
   "interlude":{"img":PH+"d1-pilot-pikachu.jpg","cap":"Day 1 · 從機場一路玩到洞爺湖畔"},
   "items":[
    {"time":"07:35","ttl":"抵達新千歲機場（班機提早到）","desc":"飛機比預定早抵達，先不急著取車，走去國內線機場逛尋寶","tag":"✈️"},
    {"time":"一到","ttl":"新千歲機場・寶可夢商店","desc":"入手新千歲機場限定的『機長皮卡丘＆空姐皮卡丘』娃娃（門口還有一尊機長皮卡丘大公仔）；反而是札幌寶可夢中心沒有自家的中心限定娃，機場先買先贏","tag":"⚡","photos":[PH+"d1-pilot-pikachu.jpg"],
     "gallery":[PH+"d1-pilot-pikachu.jpg",PH+"d1-kamaei.png",PH+"d1-times-bear-board.jpg",PH+"d1-mahjong.jpg"]},
    {"time":"一到","ttl":"機場・吉伊卡哇掃貨","desc":"北海道限定吉伊卡哇鐵牌、薰衣草款夢奇奇","tag":"🩷","photos":[PH+"d1-lavender-monchhichi.jpg"],
     "portrait":True,"caption":"HOKKAIDO 限定・薰衣草夢奇奇"},
    {"time":"墊肚","ttl":"かま栄＋飯糰","desc":"機場買炸魚板かま栄配飯糰先墊肚","tag":"🍢","photos":[PH+"d1-kamaei.png"]},
    {"time":"出發","ttl":"Times 租車・前往洞爺湖","desc":"逛完取車，開上道央自動車道（Times 門市有北海道小熊探頭拍照板）","tag":"🚗","photos":[PH+"d1-times-bear-board.jpg"]},
    {"time":"途中","ttl":"三島先生芝櫻庭園（大雨槓龜）","desc":"本想看芝櫻，結果下大雨沒下車，芝櫻無緣；連原訂的六尾人孔蓋也一起跳過","tag":"🌧️"},
    {"time":"~16:00","ttl":"洞爺湖萬世閣・Check-in","desc":"大雨作罷，約下午四點直接進飯店","tag":"🏨"},
    {"time":"傍晚","ttl":"泡湯（兩個池都泡到）","desc":"西館8樓＆中央館地下一樓，早上男女湯位置會互換；推薦8樓看得到洞爺湖景，兩館內部設施也略不同。帶了泳衣但泡完湯就差不多要吃晚餐，泳池沒玩到","tag":"♨️"},
    {"time":"晚餐","ttl":"和食會席膳・哥哥 9 歲生日","desc":"特別訂和食會席膳幫壽星慶生","tag":"🎂"},
    {"time":"20:45","ttl":"洞爺湖浪漫煙火","desc":"訂房時可特別指定看得到煙火的房型，晚上在房間就欣賞到了","tag":"🎆",
     "reel":"https://www.instagram.com/reel/"},  # reel 佔位：換成真 reel 連結即內嵌 9:16
    {"time":"宵夜局","ttl":"飯店租麻將開一桌","desc":"萬世閣可租借麻將桌／麻將，回房打幾圈","tag":"🀄","photos":[PH+"d1-mahjong.jpg"],
     "video":{"src":"","poster":PH+"d1-mahjong.jpg"}},  # video 佔位：src 補上傳影片網址即可播
    {"time":"住宿","ttl":"洞爺湖萬世閣 湖畔露台飯店","desc":"面湖和洋室","tag":"🛏️","stay":True,"addr":"北海道虻田郡洞爺湖町洞爺湖温泉21","parking":True},
  ]},
  {"no":2,"date":"5/25","wd":"一","theme":"紫藤花、柯南朝聖與百萬夜景",
   "kicker":"Day 2 · 5/25 週一",
   "intro":"一路南下函館：路上收集人孔蓋、午餐幸運小丑漢堡，下午五稜郭賞紫藤花瀑布，晚上纜車上函館山看百萬夜景。","items":[
    {"time":"上午","ttl":"八雲休息站・第二個六尾人孔蓋","desc":"往函館途中，讓小朋友看海放電、收集人孔蓋","tag":"🚗"},
    {"time":"午餐","ttl":"幸運小丑漢堡","desc":"函館限定必吃！柯南與平次也吃過","tag":"🍔"},
    {"time":"下午","ttl":"五稜郭塔＆五稜郭公園","desc":"尋找怪盜基德足跡、欣賞初夏限定『紫藤花瀑布』","tag":"🌸"},
    {"time":"晚上","ttl":"函館山・百萬夜景","desc":"搭纜車上山賞夜景，下山找遊樂場打 Frienda 機台","tag":"🌃"},
    {"time":"22:00","ttl":"Comfort Hotel 函館","desc":"從容抵達新飯店 Check-in","tag":"🛏️","stay":True},
  ]},
  {"no":3,"date":"5/26","wd":"二","theme":"釣烏賊與企鵝大遊行",
   "kicker":"Day 3 · 5/26 週二",
   "intro":"函館朝市現釣現切活烏賊當早餐，中午北返，下午在登別尼克斯海洋公園看企鵝大遊行，晚上進札幌連泊基地。","items":[
    {"time":"上午","ttl":"函館朝市・活釣烏賊","desc":"現釣現切超新鮮，中午出發北返","tag":"🦑"},
    {"time":"下午","ttl":"登別尼克斯海洋公園","desc":"夢幻城堡、企鵝遊行、海豚表演","tag":"🐧"},
    {"time":"晚餐","ttl":"Gusto 家庭餐廳","desc":"往札幌途中，兒童餐順利拿到寶可夢 Frienda 卡匣","tag":"🍽️"},
    {"time":"住宿","ttl":"Comfort Hotel ERA 札幌北口","desc":"連泊第一晚","tag":"🛏️","stay":True},
  ]},
  {"no":4,"date":"5/27","wd":"三","theme":"寶可夢雙重奏與吉伊卡哇突擊！",
   "kicker":"Day 4 · 5/27 週三",
   "intro":"札幌市區尋寶日：寶可夢工藝展、大丸寶可夢中心、PARCO 吉伊卡哇樂園一路掃，晚餐用成吉思汗烤肉收尾。","items":[
    {"time":"上午","ttl":"札幌車站麥當勞・快樂兒童餐","desc":"放棄飯店早餐直衝，確保妹妹的吉伊卡哇入手","tag":"🍟"},
    {"time":"上午","ttl":"北海道近代美術館・寶可夢工藝展","desc":"","tag":"⚡"},
    {"time":"午餐","ttl":"根室花丸迴轉壽司","desc":"先抽號碼牌，空檔直衝大丸百貨寶可夢中心買生日禮物與限定六尾娃娃","tag":"🍣"},
    {"time":"下午","ttl":"大通公園・札幌紫丁香祭","desc":"感受花香與節慶氛圍，開啟『皮克敏任務』","tag":"🌷"},
    {"time":"下午","ttl":"PARCO・Chiikawa Land","desc":"幫妹妹買吉伊卡哇限定周邊","tag":"🩷"},
    {"time":"晚餐","ttl":"成吉思汗烤肉","desc":"札幌必吃","tag":"🐑"},
    {"time":"住宿","ttl":"Comfort Hotel ERA 札幌北口","desc":"連泊第二晚","tag":"🛏️","stay":True},
  ]},
  {"no":5,"date":"5/28","wd":"四","theme":"鬱金香花海與大人採購之夜",
   "kicker":"Day 5 · 5/28 週四",
   "intro":"白天在瀧野鈴蘭丘陵公園的鬱金香花海和巨蛋彈跳床玩瘋，傍晚北海道神宮參拜，宵夜場狸小路唐吉訶德大採購。","items":[
    {"time":"白天","ttl":"國營瀧野鈴蘭丘陵公園","desc":"彩色鬱金香花海拍照、巨蛋彈跳床＋熔岩溜滑梯玩瘋","tag":"🌷"},
    {"time":"下午","ttl":"北海道神宮＆圓山公園","desc":"參拜祈福，皮克敏種花集滿 7 個特殊地點破札幌限定任務","tag":"⛩️"},
    {"time":"晚餐","ttl":"暖呼呼湯咖哩","desc":"","tag":"🍛"},
    {"time":"宵夜","ttl":"狸小路・唐吉訶德大採購","desc":"吉伊卡哇鐵牌、六尾零食、大人的 SAVAS 免稅高蛋白粉一次買齊","tag":"🛒"},
    {"time":"住宿","ttl":"Comfort Hotel ERA 札幌北口","desc":"連泊第三晚","tag":"🛏️","stay":True},
  ]},
  {"no":6,"date":"5/29","wd":"五","theme":"小樽童話之旅（免搬行李）",
   "kicker":"Day 6 · 5/29 週五",
   "intro":"連泊札幌不用搬行李，輕裝殺去小樽：運河邊拍全家福、入手小樽限定吉伊卡哇鐵牌，堺町通挑音樂盒、配 LeTAO 起司蛋糕，回札幌用十勝豚丼收尾。","items":[
    {"time":"上午","ttl":"小樽運河","desc":"輕裝出門拍全家福，買下心心念念的『小樽運河限定吉伊卡哇鐵牌』","tag":"🚣"},
    {"time":"午餐","ttl":"若雞時代・炸半雞","desc":"小樽名產、皮脆多汁","tag":"🍗"},
    {"time":"下午","ttl":"小樽堺町通・音樂盒堂","desc":"妹妹主場，挑選夢幻音樂盒","tag":"🎵"},
    {"time":"下午","ttl":"LeTAO 雙層起司蛋糕","desc":"全家一起吃","tag":"🍰"},
    {"time":"晚餐","ttl":"十勝豚丼","desc":"開車回札幌後，甜鹹超下飯","tag":"🐷"},
    {"time":"住宿","ttl":"Comfort Hotel ERA 札幌北口","desc":"連泊第四晚","tag":"🛏️","stay":True},
  ]},
  {"no":7,"date":"5/30","wd":"六","theme":"寶可夢一番賞與稱霸新千歲",
   "kicker":"Day 7 · 5/30 週六",
   "intro":"最後的尋寶衝刺：市區 Lawson／TSUTAYA 決戰寶可夢 30 週年一番賞，千歲 AEON 掃零食，還車後入住 PORTOM，把新千歲機場的寶可夢商店與遊樂場一次玩透。","items":[
    {"time":"上午","ttl":"寶可夢 30 週年一番賞","desc":"退房前後鎖定札幌市區 Lawson 或 TSUTAYA 書店決戰","tag":"🎯"},
    {"time":"中午","ttl":"千歲 AEON・超市掃貨","desc":"開車前往千歲，最後的零食大採買","tag":"🛒"},
    {"time":"14:30","ttl":"Times 新千歲機場店還車","desc":"提早還車、搭接駁車回機場","tag":"🔑"},
    {"time":"15:00","ttl":"PORTOM INTERNATIONAL HOKKAIDO","desc":"超豪華小型套房！放完行李下樓國內線 2F 寶可夢商店補貨","tag":"🛏️","stay":True},
    {"time":"晚餐","ttl":"北海道拉麵道場","desc":"國內線 3F、吃飽在遊樂場打最後一次 Frienda","tag":"🍜"},
  ]},
  {"no":8,"date":"5/31","wd":"日","theme":"滿載而歸",
   "kicker":"Day 8 · 5/31 週日",
   "intro":"睡飽從 PORTOM 優雅下樓、國際線報到，帶著滿滿戰利品與一家四口的回憶，VZ571 平安返台。","items":[
    {"time":"07:00","ttl":"退房・國際線報到","desc":"睡飽後從飯店優雅下樓，抵達國際線櫃檯","tag":"🧳"},
    {"time":"09:00","ttl":"VZ571 班機返台","desc":"帶著超豐富戰利品與無可取代的家庭回憶平安返台","tag":"✈️"},
  ]},
]

now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

existing = tbl.get_item(Key={"id": TRIP_ID}).get("Item")
force_new = "--newkey" in sys.argv
if existing and not force_new and existing.get("privateKeyHash"):
    private_key = None
    private_hash = existing["privateKeyHash"]
    created_at = existing.get("createdAt", now)
    print("↺ 已存在，沿用原 privateKeyHash（不變動私密連結）")
else:
    private_key = secrets.token_hex(16)
    private_hash = sha256(private_key)
    created_at = existing.get("createdAt", now) if existing else now

item = {
    "id": TRIP_ID,
    "type": "trip",
    "slug": TRIP_ID,
    "title": "北海道自駕・親子尋寶 8 日",
    "subtitle": "一家四口 · 初夏環道自駕 · 追寶可夢與吉伊卡哇",
    "region": "日本・北海道",
    "mode": "diary",
    "kicker": "Hokkaido Road Trip",
    "dates": "2026.05.24 – 05.31",
    "tags": ["自駕", "親子", "寶可夢", "吉伊卡哇", "溫泉"],
    "cover": "https://image.boyplaymj.link/trip/covers/hokkaido-2026-0524-v2.jpg",
    "overview": OVERVIEW,
    "visibility": "draft",
    "privateKeyHash": private_hash,
    "days": DAYS,
    "createdAt": created_at,
    "updatedAt": now,
}

tbl.put_item(Item=item)
print("✓ PutItem 完成")

got = tbl.get_item(Key={"id": TRIP_ID}).get("Item")
checks = []
checks.append(("讀得回", got is not None))
checks.append(("id 一致", got.get("id") == TRIP_ID))
checks.append(("type=trip", got.get("type") == "trip"))
checks.append(("visibility=draft", got.get("visibility") == "draft"))
checks.append(("天數=8", len(got.get("days", [])) == 8))
total_items = sum(len(d["items"]) for d in DAYS)
got_items = sum(len(d["items"]) for d in got.get("days", []))
checks.append((f"項目數={total_items}", got_items == total_items))
checks.append(("privateKeyHash 存在且為 sha256", str(got.get("privateKeyHash","")).startswith("sha256:")))
checks.append(("明文 key 未落 DB", "privateKey" not in got))
q = tbl.query(IndexName="type-updatedAt-index",
              KeyConditionExpression=Key("type").eq("trip"),
              ScanIndexForward=False)
checks.append(("GSI 查得到", any(i["id"] == TRIP_ID for i in q.get("Items", []))))

print("\n=== 讀回驗證 ===")
ok = True
for name, res in checks:
    print(f"  {'✅' if res else '❌'} {name}")
    ok = ok and res
print("\n" + ("🎉 全部通過" if ok else "⚠️ 有驗證未過"))
if private_key:
    print(f"\n🔑 私密 key（明文，只顯示這次）：{private_key}")
print(f"\n項目總數：{total_items}｜更新時間：{now}")
sys.exit(0 if ok else 1)
