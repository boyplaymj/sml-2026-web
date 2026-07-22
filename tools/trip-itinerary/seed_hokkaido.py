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
    {"time":"下午","ttl":"五稜郭塔","desc":"登上五稜郭塔，星形城郭盡收眼底（俯瞰照就是本日的收尾大圖）；展望台上還有新選組副長土方歲三的銅像，跟哥哥合照一張","tag":"🗼",
     "photos":[PH+"d2-hijikata.jpg"],"caption":"五稜郭塔展望台・與土方歲三銅像合照"},
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
  {"no":3,"date":"5/26","wd":"二","theme":"朝市帝王蟹、八幡宮御朱印與北上札幌",
   "kicker":"Day 3 · 5/26 週二",
   "intro":"晚出門的一天：先在函館車站旁松崗商店掃伴手禮、車站集章，原訂的朝市早餐順勢變成午餐——帝王蟹、現釣烏賊、螃蟹可樂餅，還喝到全程最好喝的駒ケ岳牛乳。午後到寧靜的函館八幡宮求限定新幹線御朱印，接著一路北上札幌，沿途逛玩具店、收集恵庭人孔蓋，很晚才進連泊基地。","items":[
    {"time":"較晚","ttl":"松崗商店・伴手禮採買","desc":"這天比較晚出門，先到函館車站旁的松崗商店採買一波伴手禮（Day 2 沒買到的函館夜景款吉伊卡哇兔兔鐵牌，就是在這裡補齊的）","tag":"🛍️",
     "video":{"src":PH+"d3-matsuoka.mp4","poster":PH+"d3-matsuoka-poster.jpg"}},
    {"time":"接著","ttl":"函館車站・集章","desc":"順道在函館車站集章","tag":"🖊️"},
    {"time":"午餐","ttl":"函館朝市・現場挑帝王蟹","desc":"因為晚出門，原本要當早餐的朝市變成了午餐。先在攤前挑一隻活跳跳的帝王蟹","tag":"🦀",
     "video":{"src":PH+"d3-crab-hold.mp4","poster":PH+"d3-crab-hold-poster.jpg"}},
    {"time":"朝市","ttl":"帝王蟹（選了烤的）","desc":"帝王蟹我們選了烤的，吃完覺得下次應該點蒸的","tag":"🦀",
     "photos":[PH+"d3-king-crab.jpg"],"caption":"朝市現點的烤帝王蟹"},
    {"time":"朝市","ttl":"排隊釣活烏賊","desc":"市場裡的『活いか釣』，排了好久才輪到，親手釣一隻活烏賊","tag":"🦑",
     "video":{"src":PH+"d3-squid-fishing.mp4","poster":PH+"d3-squid-fishing-poster.jpg"}},
    {"time":"朝市","ttl":"現切烏賊生魚片","desc":"釣上來現切，透明的活烏賊生魚片超新鮮","tag":"🍣",
     "photos":[PH+"d3-squid.jpg"],"caption":"現釣現切・透明的活烏賊"},
    {"time":"朝市","ttl":"駒ケ岳牛乳・全程最好喝","desc":"市場內一攤小販賣的駒ケ岳牛乳，是這趟旅程喝到最好喝的北海道牛奶（還有咖啡牛乳）","tag":"🥛",
     "photos":[PH+"d3-komagatake-milk.jpg"],"caption":"駒ヶ岳牛乳・全程最好喝的北海道牛奶"},
    {"time":"朝市","ttl":"螃蟹奶油可樂餅＆丼飯","desc":"再配上螃蟹奶油可樂餅和海鮮丼飯，朝市一次吃滿","tag":"🍤",
     "photos":[PH+"d3-croquette.jpg"],"caption":"熱呼呼的螃蟹奶油可樂餅"},
    {"time":"下午","ttl":"函館八幡宮・寧靜社殿","desc":"午後到函館八幡宮，沿著長長石階拾級而上，社殿背著青翠的山，是個很寧靜、很美的地方","tag":"⛩️",
     "video":{"src":PH+"d3-hachimangu.mp4","poster":PH+"d3-hachimangu-poster.jpg"}},
    {"time":"八幡宮","ttl":"限定・新幹線10周年御朱印","desc":"這裡有限定的北海道新幹線開業10周年御朱印，特地求了一張","tag":"📜",
     "gallery":[PH+"d3-hachimangu-torii.jpg",PH+"d3-goshuin.jpg"]},
    {"time":"途中","ttl":"玩具店・戰鬥陀螺","desc":"往札幌的路上經過好幾間大型玩具店，進去找戰鬥陀螺（BEYBLADE X）","tag":"🧸",
     "photos":[PH+"d3-beyblade.jpg"],"caption":"玩具店掃到戰鬥陀螺 BEYBLADE X"},
    {"time":"玩具店","ttl":"名偵探光之美少女・新商品","desc":"同一間玩具店還有『名偵探光之美少女』的新商品，妹妹在櫃前挑了好久","tag":"💗",
     "video":{"src":PH+"d3-precure.mp4","poster":PH+"d3-precure-poster.jpg"}},
    {"time":"順路","ttl":"恵庭・寶可夢人孔蓋","desc":"北上途中順路收集恵庭的寶可夢人孔蓋——是隻被花朵環繞的六尾（ロコン），全家開著寶可夢 GO 一起找到","tag":"🕳️",
     "photos":[PH+"d3-eniwa-manhole.jpg"],"caption":"恵庭・六尾（ロコン）寶可夢人孔蓋"},
    {"time":"很晚","ttl":"抵達札幌・進飯店休息","desc":"到札幌已經很晚，趕快進飯店休息；把這幾天的戰利品在床頭排一排，超有成就感","tag":"🌙",
     "photos":[PH+"d3-hotel-loot.jpg"],"caption":"床頭的戰利品大集合"},
    {"time":"住宿","ttl":"Comfort Hotel ERA 札幌北口","desc":"連泊基地第一晚。飯店附停車位但很少，我們回到飯店時位置通常都沒了，好在旁邊停車場非常多；離札幌車站很近，而且這裡的服務人員是我們住過這麼多家 Comfort 之中遇過最好的！","tag":"🛏️","stay":True,"addr":"北海道札幌市北区北七条西5丁目17-1"},
  ]},
  {"no":4,"date":"5/27","wd":"三","theme":"北海道神宮、小樽運河與寶可夢日K",
   "kicker":"Day 4 · 5/27 週三",
   "intro":"一早的獵人一番賞從第一天找到最後一天還是槓龜，索性玩娃娃機、扭皮克敏；到北海道神宮參拜、吃六花亭現烤判官さま，再把握好天氣殺去小樽——收人孔蓋、若鶏時代炸半雞、運河搭船、LeTAO 冰吃好吃滿。晚上回札幌登電視塔掃テレビ父さん周邊，最後在飯店旁卡拉OK體驗寶可夢30週年聯名的日K。","items":[
    {"time":"一早","ttl":"東急・一番賞專賣店（獵人槓龜）","desc":"一早先衝東急的一番賞專賣店，想抽獵人×獵人的一番賞——結果又賣光了。從到北海道第一天就開始找，整趟旅程硬是沒讓我們遇上","tag":"🎯",
     "photos":[PH+"d4-ichiban-case.jpg"],"caption":"櫃裡滿滿動漫景品，就是抽不到獵人一番賞"},
    {"time":"順手","ttl":"娃娃機・夾寶可夢","desc":"沒抽到一番賞，就在旁邊娃娃機玩了一下，機台裡滿滿快龍、瑪力露","tag":"🎰",
     "video":{"src":PH+"d4-clawmachine.mp4","poster":PH+"d4-clawmachine-poster.jpg"}},
    {"time":"順手","ttl":"皮克敏扭蛋","desc":"還扭了皮克敏扭蛋，藍、紫、黑一整手吊飾","tag":"🎡",
     "video":{"src":PH+"d4-pikmin-gacha.mp4","poster":PH+"d4-pikmin-gacha-poster.jpg"}},
    {"time":"同棟","ttl":"東急 hands 逛逛","desc":"在同一棟的 hands 逛了一圈，還看到寶可夢 30 周年的娃娃（阿羅拉六尾）","tag":"🛒",
     "video":{"src":PH+"d4-pokemon-plush.mp4","poster":PH+"d4-pokemon-plush-poster.jpg"}},
    {"time":"上午","ttl":"北海道神宮・參拜","desc":"接著到北海道神宮參拜，社殿莊嚴、還求到限定御朱印，在參拜記念木牌前拍了全家福","tag":"⛩️",
     "gallery":[PH+"d4-jingu-shrine.jpg",PH+"d4-jingu-family.jpg",PH+"d4-jingu-goshuin.jpg"]},
    {"time":"神宮","ttl":"六花亭・判官さま現烤中","desc":"北海道神宮內的六花亭非常好吃好買，判官さま（判官樣）在鐵板上一顆顆現烤，看著就香","tag":"🍡",
     "video":{"src":PH+"d4-hangan-grill.mp4","poster":PH+"d4-hangan-grill-poster.jpg"}},
    {"time":"神宮","ttl":"六花亭・買一份判官さま","desc":"買了現烤的判官さま，熱熱吃","tag":"🍡",
     "photos":[PH+"d4-hangan.jpg"],"caption":"六花亭・現烤判官さま"},
    {"time":"把握好天氣","ttl":"前往小樽運河","desc":"把握最後的好天氣，開往小樽運河","tag":"🚗"},
    {"time":"小樽","ttl":"小樽・寶可夢人孔蓋","desc":"先收集小樽的寶可夢人孔蓋——是彩繪玻璃風的阿羅拉六尾（アローラロコン），全家蹲下合照","tag":"🕳️",
     "photos":[PH+"d4-otaru-manhole.jpg"],"caption":"小樽・阿羅拉六尾寶可夢人孔蓋"},
    {"time":"午餐","ttl":"若鶏時代・炸半雞","desc":"小樽名產若鶏時代（なると）的若鶏半身揚げ，皮脆多汁，小朋友還玩了臉出拍照板","tag":"🍗",
     "gallery":[PH+"d4-wakadori-eat.jpg",PH+"d4-wakadori-board.jpg"]},
    {"time":"下午","ttl":"小樽運河・搭遊船","desc":"吃飽到運河搭遊船，全家坐上船從水上看小樽","tag":"🚣",
     "video":{"src":PH+"d4-canal-boat.mp4","poster":PH+"d4-canal-boat-poster.jpg"}},
    {"time":"運河","ttl":"從船上看紅磚倉庫","desc":"順著運河滑過一排紅磚倉庫，角度跟岸上完全不同","tag":"🚣",
     "photos":[PH+"d4-canal.jpg"],"caption":"小樽運河・從船上看紅磚倉庫"},
    {"time":"下午","ttl":"LeTAO・冰淇淋","desc":"搭完船來一份 LeTAO 冰淇淋，還配上一塊招牌起司蛋糕，透心涼","tag":"🍦",
     "photos":[PH+"d4-letao.jpg"],"caption":"LeTAO 冰淇淋＋起司蛋糕"},
    {"time":"傍晚","ttl":"開回札幌・札幌電視塔","desc":"晚上開回札幌，來到亮著燈的札幌電視塔","tag":"🗼",
     "photos":[PH+"d4-tower-night.jpg"],"caption":"札幌電視塔・夜間點燈"},
    {"time":"電視塔","ttl":"テレビ父さん周邊","desc":"買了好多電視塔吉祥物『テレビ父さん』的周邊，小朋友還玩了臉出拍照板","tag":"📺",
     "photos":[PH+"d4-terebi-board.jpg"],"caption":"テレビ塔のテレビ父さん・臉出拍照板"},
    {"time":"電視塔","ttl":"補到吉伊卡哇鐵牌","desc":"也在這裡補到小樽運河限定、之前沒買到的吉伊卡哇鐵牌","tag":"🩷",
     "video":{"src":PH+"d4-chiikawa-tag.mp4","poster":PH+"d4-chiikawa-tag-poster.jpg"}},
    {"time":"晚上","ttl":"飯店旁卡拉OK・寶可夢30週年聯名","desc":"回飯店前，到飯店旁的卡拉OK唱歌——剛好有寶可夢 30 週年 × まねきねこ聯名活動，點聯名曲有限定特典、還有聯名喵喵薯條；爸爸一首唱到 90,843 分，第一次體驗日本卡拉OK（日K），很有趣","tag":"🎤",
     "gallery":[PH+"d4-karaoke-sing.jpg",PH+"d4-karaoke-food.jpg",PH+"d4-karaoke-poster.jpg",PH+"d4-karaoke-loot.jpg"]},
    {"time":"住宿","ttl":"Comfort Hotel ERA 札幌北口","desc":"連泊基地第二晚","tag":"🛏️","stay":True,"addr":"北海道札幌市北区北七条西5丁目17-1"},
  ]},
  {"no":5,"date":"5/28","wd":"四","theme":"寶可夢工藝展、諏訪神社與狸小路大採購",
   "kicker":"Day 5 · 5/28 週四",
   "intro":"札幌市區慢遊日：根室花丸平日不用久等、便宜又好吃；期待已久的寶可夢工藝展終於在近代美術館遇上，限定皮卡丘讓人失心瘋；北菓樓收齊北海道三大洋菓子。午後諏訪神社的花手水與御朱印美到選不完，一場雨把我們帶去三笠收人孔蓋、薄野駿河屋挖到絕版空姐皮卡丘，晚上松尾成吉思汗配大雨，最後在狸小路 donki 搬滿蛋白粉收工。","items":[
    {"time":"上午","ttl":"根室花丸・抽號碼牌","desc":"這天先到札幌車站的根室花丸迴轉壽司抽號碼牌，平日排隊沒想像中久","tag":"🍣",
     "photos":[PH+"d5-hanamaru-sign.jpg"],"caption":"寿司 根室花まる・現在叫號 76"},
    {"time":"候位","ttl":"寶可夢中心＆寶可夢機台","desc":"等候的空檔，順道逛旁邊的寶可夢中心和寶可夢機台","tag":"⚡",
     "photos":[PH+"d5-pokemon-arcade.jpg"],"caption":"寶可夢機台入手一張卡匣"},
    {"time":"入座","ttl":"根室花丸・便宜又好吃","desc":"很快就入座了——不愧是北海道，隨便點都好吃（海膽、松葉蟹軍艦超鮮），結帳金額還便宜到令人嚇一跳","tag":"🍣",
     "gallery":[PH+"d5-uni.jpg",PH+"d5-crab.jpg"]},
    {"time":"下午","ttl":"寶可夢工藝展・北海道立近代美術館","desc":"吃完直奔北海道立近代美術館——這趟剛好遇到寶可夢工藝展在這裡展出，想逛很久了，這次時間對、地點也對；裡面很多日本工藝大師的寶可夢作品（超夢、伊布、火精靈、鳳王…），非常厲害，還有金色垂簾的沉浸空間","tag":"🎨",
     "gallery":[PH+"d5-kogei-ticket.jpg",PH+"d5-kogei-mewtwo.jpg",PH+"d5-kogei-eevee.jpg",PH+"d5-kogei-flareon.jpg",PH+"d5-kogei-hooh.jpg",PH+"d5-kogei-groudon.jpg",PH+"d5-kogei-mimikyu.jpg",PH+"d5-kogei-immersive.jpg"]},
    {"time":"工藝展","ttl":"限定皮卡丘・失心瘋商品部","desc":"最重要的商品販賣部有工藝展限定的皮卡丘，整排和服皮卡丘超可愛，各種商品都令人失心瘋","tag":"⚡",
     "photos":[PH+"d5-kogei-pikachu.jpg"],"caption":"工藝展限定・和服皮卡丘"},
    {"time":"對面","ttl":"北菓樓・冰淇淋＆泡芙","desc":"逛完直接去美術館對面的北菓樓吃冰、吃泡芙——北海道三大洋菓子名店（六花亭、LeTAO、北菓樓）就這樣收集齊了，兩兄妹一支霜淇淋吃得超開心","tag":"🍦",
     "video":{"src":PH+"d5-kitakaro.mp4","poster":PH+"d5-kitakaro-poster.jpg"}},
    {"time":"下午","ttl":"札幌諏訪神社・花手水","desc":"接著到札幌諏訪神社，這裡的花手水非常漂亮——粉色和傘配上滿滿鮮花圍著手水缽","tag":"⛩️",
     "video":{"src":PH+"d5-hanachozu.mp4","poster":PH+"d5-hanachozu-poster.jpg"}},
    {"time":"神社","ttl":"御朱印＆御神籤・多到選不完","desc":"御朱印種類繁多、每一款都很漂亮，超難選不知道挑哪些才好；連御神籤都有超多可以選，還有骰子造型的『發轉みくじ』","tag":"📜",
     "gallery":[PH+"d5-suwa-goshuin.jpg",PH+"d5-suwa-mikuji.jpg"]},
    {"time":"下雨","ttl":"三笠・寶可夢人孔蓋","desc":"開始下雨，撐著傘也要開去三笠蒐集三笠的寶可夢人孔蓋","tag":"🕳️",
     "photos":[PH+"d5-mikasa-manhole.jpg"],"caption":"三笠・寶可夢人孔蓋（雨中撐傘合照）"},
    {"time":"傍晚","ttl":"薄野・駿河屋挖寶","desc":"蒐集完人孔蓋往薄野的駿河屋，挖到前一代新千歲機場限定的空姐皮卡丘（CTS 空姐皮卡丘）","tag":"🛍️",
     "photos":[PH+"d5-surugaya-pikachu.jpg"],"caption":"駿河屋挖到絕版・CTS 空姐皮卡丘"},
    {"time":"晚餐","ttl":"松尾ジンギスカン・すすきの店","desc":"超級大雨的晚上，就近吃成吉思汗烤肉——松尾ジンギスカン薄野店","tag":"🐑"},
    {"time":"晚餐","ttl":"北海道羊肉上鍋","desc":"羊肉配上洋蔥、南瓜、豆芽在中央凸起的鐵鍋上滋滋作響——北海道的羊肉、蔬果還有馬鈴薯，真的太好吃了","tag":"🐑",
     "video":{"src":PH+"d5-jingisukan.mp4","poster":PH+"d5-jingisukan-poster.jpg"}},
    {"time":"途中","ttl":"NIKKA 招牌・到此一遊","desc":"往狸小路的路上經過必拍的 NIKKA 威士忌大招牌，雨夜的薄野十字路口，免不了撐著傘拍一張到此一遊","tag":"📸",
     "photos":[PH+"d5-nikka.jpg"],"caption":"雨夜薄野・NIKKA 招牌到此一遊"},
    {"time":"最後一站","ttl":"狸小路・唐吉訶德採買","desc":"最後一站到狸小路的唐吉訶德（donki）採買，重點是搬蛋白粉回來，試了很多口味都好好喝","tag":"🛒",
     "photos":[PH+"d5-protein.jpg"],"caption":"donki 一整排蛋白粉，搬好搬滿"},
    {"time":"住宿","ttl":"Comfort Hotel ERA 札幌北口","desc":"連泊基地第三晚","tag":"🛏️","stay":True,"addr":"北海道札幌市北区北七条西5丁目17-1"},
  ]},
  {"no":6,"date":"5/29","wd":"五","theme":"寶可夢人孔蓋巡禮、Royce 工廠與富良野くまげら",
   "kicker":"Day 6 · 5/29 週五",
   "intro":"一早用 app 搶預約麥當勞吉伊卡哇二彈、yodobashi 取餐、7-11 抽 sunsun 一番賞，回飯店把麥當勞當早餐。好天氣的行程前幾天都跑完了，這天就應壽星許願一路蒐集寶可夢人孔蓋——當別『北歐の風』、富良野日之出公園、砂川六尾＆胖甜妮，中途被 hobby off 的戰鬥陀螺吸進去、順逛 Royce 工廠掃限定伴手禮，晚餐意外吃到緯來日本台拍過的富良野くまげら。","items":[
    {"time":"一早","ttl":"手機預約麥當勞・吉伊卡哇第二彈","desc":"一早起床先用手機 app 預約麥當勞快樂兒童餐的吉伊卡哇第二彈（第2弾 5/29–6/11）——這次為了防黃牛，開賣首日要用公式 app 預約才能購買","tag":"🍟",
     "video":{"src":PH+"d6-mcd-chiikawa.mp4","poster":PH+"d6-mcd-chiikawa-poster.jpg"}},
    {"time":"取餐","ttl":"yodobashi 內麥當勞取餐＋玩具樓層","desc":"走去飯店附近 yodobashi（ヨドバシカメラ）裡的麥當勞取餐，順便逛了玩具樓層，逆転バリバリバース 一整排","tag":"🛗",
     "photos":[PH+"d6-beyblade-shelf.jpg"],"caption":"yodobashi 玩具樓層・逆転バリバリバース"},
    {"time":"順路","ttl":"7-11・sunsun 一番賞新發售","desc":"這天剛好是 sunsun 一番賞的新發售日，在旁邊的 7-11 也抽了一波","tag":"🎯",
     "photos":[PH+"d6-sunsun.jpg"],"caption":"7-11・SUNSUN 一番賞新發售"},
    {"time":"早餐","ttl":"回飯店吃麥當勞","desc":"帶回飯店把麥當勞當早餐吃","tag":"🍔",
     "reel":"https://www.instagram.com/reel/DZEb_m0zFHx/"},
    {"time":"改行程","ttl":"壽星許願・寶可夢人孔蓋大蒐集","desc":"原本安排的行程趁前幾天好天氣都跑完了，這天就應壽星的要求，四處去蒐集寶可夢人孔蓋","tag":"🕳️"},
    {"time":"途中","ttl":"hobby off・被戰鬥陀螺吸進去","desc":"預計第一站是當別的人孔蓋，結果途中經過 hobby off 就被吸進去，一口氣抱走六個戰鬥陀螺","tag":"🌀",
     "video":{"src":PH+"d6-hobbyoff-beyblade.mp4","poster":PH+"d6-hobbyoff-beyblade-poster.jpg"}},
    {"time":"路過","ttl":"Royce Town 車站","desc":"路上還經過 JR 北海道的 Royce Town 車站，還入手了車站造型的模型鑰匙圈","tag":"🚉",
     "gallery":[PH+"d6-royce-station.jpg",PH+"d6-royce-station-model.jpg"]},
    {"time":"當別","ttl":"當別・寶可夢人孔蓋（北歐の風 道之驛）","desc":"當別的寶可夢人孔蓋（アローラロコン＆ポットデス）在『北歐の風 道之驛』","tag":"🕳️",
     "photos":[PH+"d6-tobetsu-manhole.jpg"],"caption":"當別とうべつ・寶可夢人孔蓋"},
    {"time":"道之驛","ttl":"北歐の風・豬肉香腸","desc":"在道之驛買了冰淇淋，還有現烤的豬肉香腸，邊逛邊吃","tag":"🌭",
     "video":{"src":PH+"d6-sausage.mp4","poster":PH+"d6-sausage-poster.jpg"}},
    {"time":"道之驛","ttl":"北歐の風・跟風麵包","desc":"麵包區看到掛著 NO.1 人氣招牌，大家都在拿，就也跟著拿了幾個","tag":"🥐",
     "video":{"src":PH+"d6-bread.mp4","poster":PH+"d6-bread-poster.jpg"}},
    {"time":"道之驛","ttl":"北歐の風・採買袋（麵包＆北海道杯湯）","desc":"結帳戰利品：吐司麵包配上北海道限定的 Knorr 杯湯，道之驛採買滿滿一袋","tag":"🛍️",
     "video":{"src":PH+"d6-royce-haul.mp4","poster":PH+"d6-royce-haul-poster.jpg"}},
    {"time":"附近","ttl":"Royce 巧克力工廠・限定伴手禮","desc":"蒐集完這站，去附近的 Royce 巧克力工廠，買了很多限定伴手禮，還有 Royce 麵包；館內連座位區都佈置得像巧克力世界，深咖啡方格軟墊根本就是一整片巧克力磚","tag":"🍫",
     "photos":[PH+"d6-royce-chair.jpg"],"caption":"Royce 工廠・坐在像巧克力磚的座位上"},
    {"time":"富良野","ttl":"日之出公園・寶可夢人孔蓋","desc":"接著往富良野的日之出公園蒐集下一個寶可夢人孔蓋；這段時間不是花期，所以沒看到美麗的富良野花海","tag":"🌸",
     "photos":[PH+"d6-hinode-manhole.jpg"],"caption":"富良野・日之出公園寶可夢人孔蓋"},
    {"time":"晚餐","ttl":"富良野・くまげら（山賊鍋＆和牛丼）","desc":"晚餐吃富良野的くまげら，點了山賊鍋和牛丼。出發前才在家看緯來日本台拍到這間，當時還想說應該不會去富良野，沒想到最後真的來吃了（靠 AI 問附近有開、推薦的餐廳找到的）","tag":"🍲",
     "photos":[PH+"d6-kumagera.jpg"],"caption":"富良野くまげら・熱呼呼山賊鍋"},
    {"time":"回程","ttl":"砂川・六尾＆胖甜妮人孔蓋","desc":"吃完回飯店的路上，再去砂川蒐集六尾＆胖甜妮（マホイップ）的寶可夢人孔蓋","tag":"🕳️",
     "photos":[PH+"d6-sunagawa-manhole.jpg"],"caption":"砂川すながわ・六尾＆胖甜妮人孔蓋"},
    {"time":"住宿","ttl":"Comfort Hotel ERA 札幌北口","desc":"連泊基地第四晚","tag":"🛏️","stay":True,"addr":"北海道札幌市北区北七条西5丁目17-1"},
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
