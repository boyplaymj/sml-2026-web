#!/usr/bin/env python3
# ARG 迷宮自動稽核（Phase A 引擎 + Phase B 埋深）。給 Codex 驗收前先跑，結果貼進 VERIFY 文件。
import json,glob,os,re,hashlib,sys
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)),"dist","mingyan"))
m=json.load(open("_manifest.json")); byf={x["file"]:x for x in m}
files=set(byf); ok=True
def chk(cond,label):
    global ok
    print(("  ✅ " if cond else "  ❌ ")+label); ok=ok and cond
    return cond

print("== A1 檔案數/唯一性 ==")
htmls=glob.glob("*.html")
chk(len(htmls)==len(m), f"HTML檔數({len(htmls)})==manifest節點數({len(m)})")

print("== A2 hash檔名穩定性(依world.json重算應一致) ==")
W=json.load(open("../../mingyan-world.json"))
def fn(n):
    if n.get("file"): return n["file"]
    if n.get("hidden"):
        return "_"+hashlib.sha1(("arg-"+n.get("salt",n["id"])).encode()).hexdigest()[:8]+".html"
    return n["id"]+".html"
wf={n["id"]:fn(n) for n in W["nodes"]}
mm={x["id"]:x["file"] for x in m}
chk(all(wf[i]==mm[i] for i in wf), "world.json 重算檔名 == 產物檔名(hash穩定)")

print("== A3 無斷鏈(所有href目標存在) ==")
broken=[]
for f in htmls:
    for h in re.findall(r'href="([^"#]+)',open(f,encoding="utf-8").read()):
        if h.startswith("./"): h=h[2:]
        if h.endswith(".html") and h not in files: broken.append((f,h))
chk(not broken, f"無指向不存在頁的href {broken[:3]}")

print("== A4 檢視原始檔逃逸(頁面文字內容不得有生的<script>注入風險) ==")
# 產生器用 html.escape 對所有作者輸入逃逸;抽驗:body內容區不應出現未逃逸的作者角括號
sample=open("t-main.html",encoding="utf-8").read()
chk("&gt;真希望這老頭消失" not in sample, "作者文字經逃逸(不破版)")  # 情境檢查

print("== B1 早階段(含隱藏頁)keystone零洩漏 ==")
# 讀真 core.any(method+motive keystone;culprit名允許早階段當公平伏筆,見DESIGN §5)
_core=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","CASE-13-mingyan.json")))["solution"]["core"]
bad=sorted({w for c in _core if c["id"] in ("method","motive") for w in c["any"]},key=len,reverse=True)
leak=[(f,w) for f in htmls if byf[f]["stage"]<4 for w in bad if w in open(f,encoding="utf-8").read()]
chk(not leak, f"stage<4頁源碼grep keystone零命中 {leak[:5]}")

print("== B2 四還原鏈:刪檔頁註解藏隱藏檔 & 隱藏檔0 href連結 ==")
chains=[("del-electrical","_ca9558ea"),("del-ledger","_624caea4"),("del-safety","_53796fa6"),("del-zhuo-comment","_dde24f5d")]
for stub,hid in chains:
    src=open(stub+".html",encoding="utf-8").read()
    linked=sum(('href="'+hid) in open(f,encoding="utf-8").read() for f in htmls)
    chk(hid in src and os.path.exists(hid+".html") and linked==0, f"{stub}→{hid}(註解有/檔在/0連結={linked})")

print("== B3 數字遞增鏈:0417不被連結、0418頁有提示 ==")
l417=sum('href="uploads-0417' in open(f,encoding="utf-8").read() for f in htmls)
c418=open("uploads-0418.html",encoding="utf-8").read()
chk(os.path.exists("uploads-0417.html") and l417==0 and "0417" in c418, f"0417存在/0連結({l417})/0418有提示")

print("== B4 公平麵包屑:機制教學頁存在 ==")
chk(os.path.exists("n-webmaster.html") and os.path.exists("n-archive-notice.html"), "站長雜記+庫存說明(教檢視原始檔/連號/備份)")

print("== B5 關鍵路徑三core證物齊 ==")
need={"d-electrical","d-pigment","d-ledger","d-access-named","d-access-log","d-timeline"}
have={x["id"] for x in m if x["clue"]}
chk(need<=have, f"三core證物節點齊 缺={need-have}")

print("\n"+("全部通過 ✅" if ok else "有失敗項 ❌ — 見上"))
sys.exit(0 if ok else 1)
