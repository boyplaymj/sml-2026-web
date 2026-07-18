#!/usr/bin/env python3
# ARG 迷宮自動稽核（A 引擎 + B 埋深 + 加固）。給 Codex 驗收前先跑,全綠才交。
import json,glob,os,re,hashlib,sys
ARGDIR=os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.join(ARGDIR,"dist","mingyan"))
m=json.load(open("_manifest.json")); byf={x["file"]:x for x in m}
files=set(byf); ok=True
bundle=json.load(open("_secret_bundle.json")) if os.path.exists("_secret_bundle.json") else {}
core=json.load(open(os.path.join(ARGDIR,"..","CASE-13-mingyan.json")))["solution"]["core"]
KEY=sorted({w for c in core if c["id"] in("method","motive") for w in c["any"]},key=len,reverse=True)  # 真keystone
def chk(cond,label):
    global ok; print(("  ✅ " if cond else "  ❌ ")+label); ok=ok and cond; return cond

print("== A1 檔案數/唯一性 ==")
htmls=glob.glob("*.html")
chk(len(htmls)==len(m), f"HTML檔數({len(htmls)})==manifest節點數({len(m)})")

print("== A2 hash檔名穩定性 ==")
W=json.load(open(os.path.join(ARGDIR,"mingyan-world.json")))
def fn(n):
    if n.get("file"): return n["file"]
    if n.get("hidden"): return "_"+hashlib.sha1(("arg-"+n.get("salt",n["id"])).encode()).hexdigest()[:8]+".html"
    return n["id"]+".html"
chk(all(fn(n)==({x["id"]:x["file"] for x in m})[n["id"]] for n in W["nodes"]), "world重算檔名==產物檔名")

print("== A3 無斷鏈 ==")
broken=[]
for f in htmls:
    for h in re.findall(r'href="([^"#]+)',open(f,encoding="utf-8").read()):
        h=h[2:] if h.startswith("./") else h
        if h.endswith(".html") and h not in files: broken.append((f,h))
chk(not broken, f"無指向不存在頁的href {broken[:3]}")

print("== A4 檢視原始檔逃逸 ==")
chk("&gt;真希望這老頭消失" not in open("t-main.html",encoding="utf-8").read(), "作者文字經逃逸")

print("== B1 早階段(stage<4)靜態源碼 keystone 零命中 ==")
leak=[(f,w) for f in htmls if byf[f]["stage"]<4 for w in KEY if w in open(f,encoding="utf-8").read()]
chk(not leak, f"stage<4靜態grep真core.any零命中 {leak[:5]}")

print("== B6 [加固] 全部靜態html keystone 零命中(含S4殼;S4內文須全在bundle) ==")
leak6=[(f,w) for f in htmls for w in KEY if w in open(f,encoding="utf-8").read()]
chk(not leak6, f"任何靜態檔grep真core.any零命中 {leak6[:6]}")

print("== B7 [加固] stage>=4節點=殼且內文在bundle;bundle不外流到殼 ==")
gated=[x for x in m if x["stage"]>=4]
b7=True
for x in gated:
    st=open(x["file"],encoding="utf-8").read()
    inb=x["file"] in bundle
    shell="gate-lock" in st and not any(w in st for w in KEY)
    b7=b7 and inb and shell
chk(b7 and len(bundle)==len(gated), f"{len(gated)}個S4節點皆殼+入bundle(bundle={len(bundle)})")

print("== B2 還原鏈:gated走bundle / 非gated走靜態 ==")
chains=[("del-electrical","_ca9558ea"),("del-ledger","_624caea4"),("del-safety","_53796fa6"),("del-zhuo-comment","_dde24f5d")]
for stub,hid in chains:
    sf,hf=stub+".html",hid+".html"
    if sf in bundle:  # gated:還原線索在bundle、靜態殼不得洩
        static_clean = hid not in open(sf,encoding="utf-8").read()
        in_bundle    = hid in bundle.get(sf,{}).get("html","")
        chk(static_clean and in_bundle and os.path.exists(hf), f"{stub}→{hid}[gated:殼淨={static_clean}/bundle有={in_bundle}]")
    else:             # 非gated(S2/S3):維持靜態註解、且0 href連結
        src=open(sf,encoding="utf-8").read()
        linked=sum(('href="'+hid) in open(f,encoding="utf-8").read() for f in htmls)
        chk(hid in src and os.path.exists(hf) and linked==0, f"{stub}→{hid}[static:註解有/0連結={linked}]")

print("== B3 數字遞增鏈 ==")
c418=open("uploads-0418.html",encoding="utf-8").read()
l417=sum('href="uploads-0417' in open(f,encoding="utf-8").read() for f in htmls)
chk(os.path.exists("uploads-0417.html") and l417==0 and "0417" in c418, f"0417存在/0連結({l417})/0418有提示")

print("== B4 公平麵包屑教學頁 ==")
chk(os.path.exists("n-webmaster.html") and os.path.exists("n-archive-notice.html"), "站長雜記+庫存說明")

print("== B5 關鍵路徑三core證物齊 ==")
need={"d-electrical","d-pigment","d-ledger","d-access-named","d-access-log","d-timeline"}
chk(need<=set(x["id"] for x in m if x["clue"]), "三core證物節點齊")

print("\n"+("全部通過 ✅" if ok else "有失敗項 ❌"))
sys.exit(0 if ok else 1)
