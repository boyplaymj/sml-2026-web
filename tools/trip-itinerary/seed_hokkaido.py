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
   "interlude":{"img":PH+"d1-yukata-family.jpg","cap":"Day 1 · 換上浴衣，洞爺湖畔的溫泉之夜"},
   "items":[
    {"time":"07:35","ttl":"抵達新千歲機場（班機提早到）","desc":"飛機比預定早抵達，但租車公司還沒開，索性走去國內線機場逛尋寶；小朋友在扭蛋機轉到一隻泥巴魚。附註：北海道的扭蛋機不知道為什麼很會吃錢，被吃了不少零錢","tag":"✈️",
     "photos":[PH+"d1-gacha-vulpix.jpg"],"caption":"國內線尋寶・扭蛋轉到泥巴魚（北海道扭蛋機超吃錢）"},
    {"time":"一到","ttl":"新千歲機場・寶可夢商店","desc":"入手新千歲機場限定的『機長皮卡丘＆空姐皮卡丘』娃娃（門口還有一尊機長皮卡丘大公仔，貨架上整排都是）；反而是札幌寶可夢中心沒有自家的中心限定娃，機場先買先贏","tag":"⚡",
     "gallery":[PH+"d1-pilot-pikachu.jpg",PH+"d1-pikachu-shelf.jpg"]},
    {"time":"一到","ttl":"機場・吉伊卡哇北海道限定鐵牌","desc":"吉伊卡哇貨架整排，鎖定北海道限定款鐵牌，一個個慢慢挑","tag":"🩷",
     "video":{"src":PH+"d1-chiikawa-tag.mp4","poster":PH+"d1-chiikawa-tag-poster.jpg"}},
    {"time":"一到","ttl":"機場・薰衣草款夢奇奇","desc":"還有一整籃 HOKKAIDO 薰衣草限定夢奇奇（モンチッチ），紫色薰衣草款超療癒","tag":"💜",
     "video":{"src":PH+"d1-monchhichi.mp4","poster":PH+"d1-monchhichi-poster.jpg"}},
    {"time":"墊肚","ttl":"かま栄＋飯糰","desc":"機場買炸魚板かま栄配飯糰先墊肚","tag":"🍢","photos":[PH+"d1-kamaei.png"]},
    {"time":"出發","ttl":"Times 租車・前往洞爺湖","desc":"逛完取車，開上道央自動車道；Times 門市有北海道動物探頭拍照板，小朋友把臉探進去玩得開心","tag":"🚗",
     "gallery":[PH+"d1-times-bear-board.jpg",PH+"d1-times-deer.jpg"]},
    {"time":"途中","ttl":"三島先生芝櫻庭園（大雨槓龜）","desc":"本想看芝櫻，結果下大雨沒下車，芝櫻無緣；連原訂的六尾人孔蓋也一起跳過","tag":"🌧️"},
    {"time":"~16:00","ttl":"洞爺湖萬世閣・Check-in","desc":"大雨作罷，約下午四點直接進飯店","tag":"🏨"},
    {"time":"傍晚","ttl":"泡湯（兩個池都泡到）","desc":"西館8樓＆中央館地下一樓，早上男女湯位置會互換；推薦8樓看得到洞爺湖景，兩館內部設施也略不同。帶了泳衣但泡完湯就差不多要吃晚餐，泳池沒玩到","tag":"♨️"},
    {"time":"晚餐","ttl":"和食會席膳・哥哥 9 歲生日","desc":"特別訂和食會席膳幫壽星慶生，穿著浴衣邊看洞爺湖暮色，邊用桌上小七輪烤鮭魚、涮個小鍋，一道道細緻上菜","tag":"🎂",
     "video":{"src":PH+"d1-kaiseki.mp4","poster":PH+"d1-kaiseki-poster.jpg"}},
    {"time":"上菜","ttl":"會席料理＆草莓甜點","desc":"從烤物到最後的草莓甜點杯，每一道都很講究","tag":"🍽️",
     "gallery":[PH+"d1-kaiseki-fish.jpg",PH+"d1-kaiseki-strawberry.jpg"]},
    {"time":"20:45","ttl":"洞爺湖浪漫煙火","desc":"訂房時可特別指定看得到煙火的房型，晚上在房間就欣賞到湖上綻放的浪漫煙火，倒映在洞爺湖面上","tag":"🎆",
     "video":{"src":PH+"d1-hanabi.mp4","poster":PH+"d1-hanabi-poster.jpg"}},
    {"time":"宵夜局","ttl":"飯店租麻將開一桌","desc":"萬世閣前台可租借麻將（牌＋台一組 2000 円，貸出價目表上還有圍棋、將棋、花札、色浴衣），回房開一桌打幾圈，小朋友也上桌","tag":"🀄",
     "gallery":[PH+"d1-mahjong.jpg",PH+"d1-rental-list.jpg"]},
    {"time":"住宿","ttl":"洞爺湖萬世閣 湖畔露台飯店","desc":"面湖和洋室","tag":"🛏️","stay":True,"addr":"北海道虻田郡洞爺湖町洞爺湖温泉21","parking":True},
  ]},
  {"no":2,"date":"5/25","wd":"一","theme":"人孔蓋巡禮、新選組變裝與百萬夜景",
   "kicker":"Day 2 · 5/25 週一",
   "intro":"雨終於停了。沿著洞爺湖畔散步找到伊布人孔蓋後，一路南下函館——八雲休息站公休撲空，卻在森町與函館公園補回好幾個寶可夢蓋子。午餐攻下吉伊卡哇聯名的麥當勞，下午在五稜郭領御城印、扮成新選組拍照，夜裡登上函館山看那價值百萬美元的夜景。",
   "interlude":{"img":PH+"d2-goryokaku-aerial.jpg","cap":"Day 2 · 五稜郭塔俯瞰星形五稜郭"},
   "items":[
    {"time":"早晨","ttl":"萬世閣 buffet 早餐","desc":"面湖飯店的自助早餐，吃飽再上路——北海道的蛋就是特別好吃，半熟溫泉蛋淋上醬油超銷魂","tag":"🍽️",
     "photos":[PH+"d2-breakfast-egg.jpg"],"caption":"北海道溫泉蛋・萬世閣自助早餐"},
    {"time":"退房","ttl":"雨停了・退房出發","desc":"昨天的大雨總算停了，退房迎接放晴的一天","tag":"🌤️"},
    {"time":"上午","ttl":"洞爺湖畔散步・伊布人孔蓋","desc":"沿著湖畔散步，找到洞爺湖限定的『伊布』寶可夢人孔蓋（Poké Lid），這天的人孔蓋巡禮從這裡開場","tag":"🚶",
     "photos":[PH+"d2-toya-eevee.jpg"],
     "gallery":[PH+"d2-toya-eevee.jpg",PH+"d2-toya-lake.jpg"]},
    {"time":"途中","ttl":"八雲休息站（當天設施公休）","desc":"原本要讓小朋友在這裡玩，偏偏當天設施公休，只能在外面看看海景、拍拍照就走","tag":"📷",
     "photos":[PH+"d2-yakumo-sea.jpg"],"caption":"設施公休，只能在停車場眺望海景"},
    {"time":"繞路","ttl":"森町・寶可夢人孔蓋","desc":"往函館的路上特地繞去森町，補進第二個寶可夢人孔蓋","tag":"🚗",
     "photos":[PH+"d2-mori-manhole.jpg"],"caption":"森町站前的寶可夢人孔蓋"},
    {"time":"午餐","ttl":"函館麥當勞・吉伊卡哇聯名","desc":"本來要吃幸運小丑漢堡，但這次剛好遇到吉伊卡哇 × 麥當勞聯名，一到函館就先攻麥當勞；可惜沒抽到小八（ハチワレ），還好回台灣跟好心人換到了","tag":"🍟",
     "photos":[PH+"d2-mcd-chiikawa.jpg"],"portrait":True,"caption":"吉伊卡哇 × 麥當勞聯名公仔"},
    {"time":"下午","ttl":"五稜郭塔","desc":"登上五稜郭塔，星形城郭盡收眼底（俯瞰照就是本日的收尾大圖）","tag":"🗼"},
    {"time":"下午","ttl":"五稜郭・箱館奉行所","desc":"走進復原的奉行所參觀，御城印就在奉行所內領取","tag":"🏯",
     "photos":[PH+"d2-magistrate.jpg"],"caption":"ようこそ函館へ・箱館奉行所前"},
    {"time":"體驗","ttl":"奉行所前・新選組變裝拍照","desc":"奉行所前有付費變裝拍照，我們選了新選組；跟其他觀光地不一樣，這裡是用自己的手機或相機拍，想拍幾張都行","tag":"🎭",
     "photos":[PH+"d2-shinsengumi.jpg"],"caption":"扮成新選組，用自己的相機拍個夠"},
    {"time":"園內","ttl":"五稜郭・紫藤花棚","desc":"五稜郭園內的紫藤花棚，規模不算大，但走進棚下，一串串淡紫色花穗垂掛下來還是很好看，錄了段影片留念","tag":"🌸",
     "video":{"src":PH+"d2-fuji-wisteria.mp4","poster":PH+"d2-fuji-wisteria-poster.jpg"}},
    {"time":"傍晚","ttl":"函館公園・第三個寶可夢人孔蓋","desc":"離開五稜郭開到函館公園，收集函館的寶可夢人孔蓋，這天集滿三個","tag":"🕳️",
     "photos":[PH+"d2-hakodate-park-manhole.jpg"],"caption":"這天第三個寶可夢人孔蓋"},
    {"time":"晚餐","ttl":"味彩拉麵・函館鹽味拉麵","desc":"紅磚倉庫旁的『味彩』，來一碗正宗函館鹽味拉麵——清澈鹽味湯頭配叉燒、鳴門卷與麩，太美味了！","tag":"🍜",
     "photos":[PH+"d2-ajisai-ramen.jpg"],"caption":"函館名物・味彩鹽味拉麵"},
    {"time":"夜晚","ttl":"函館山・百萬美元夜景","desc":"開車上函館山看百萬美元夜景，停車位繞好久才等到；夜景真的很美，還有雲霧飄過城市燈海。山上一樣有觀光照可拍——實體照片只能寄日本地址，或選電子檔，我們選了兩種都有的方案，結果電子檔忘了下載、單子也丟了，還好留著實體照","tag":"🌃",
     "video":{"src":PH+"d2-hakodate-night.mp4","poster":PH+"d2-hakodate-night-poster.jpg"}},
    {"time":"順帶","ttl":"函館夜景款・吉伊卡哇鐵牌","desc":"函館山上也買得到函館夜景款吉伊卡哇鐵牌，可惜沒買到兔兔（うさぎ）；還好隔天在函館車站前的松崗商店補齊了兔兔","tag":"🩷"},
    {"time":"住宿","ttl":"Comfort Hotel 函館","desc":"下山已經很晚，就沒再去打機台，直接回飯店休息。位置超好——走路就到隔天要去的函館朝市；館內雖有停車位但非常少，好在周邊平面停車場又多又好停，我們最後就停在周圍的停車場。","tag":"🛏️","stay":True,"addr":"北海道函館市大手町5-25"},
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
