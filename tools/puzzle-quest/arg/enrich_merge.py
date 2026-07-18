#!/usr/bin/env python3
# Phase C 合併:讀 Fable5 各批輸出,對每個節點做①結構簽章比對(凍結欄位不准動)②keyword閘
# (禁詞出現即退回原文)。通過才替換進 mingyan-world.json;任一不過→保留原節點並記錄。
import json,glob,os,sys,copy
W=json.load(open("mingyan-world.json")); ix={n["id"]:n for n in W["nodes"]}
sig=json.load(open("_enrich/_signatures.json"))
FORBID=["人為破壞","接地被剪","剪斷接地","外殼帶電","火線接外殼","接外殼","帶電的鐵","鈦白","贗品",
        "偽作","仿作","仿冒","洗錢","洗白","髒錢","黑錢","滅口","他殺","謀殺","兇殺","謀害","動過手腳","動手腳"]
def struct_sig(n):
    s={"id":n["id"],"type":n["type"],"stage":n.get("stage",1),"hidden":bool(n.get("hidden")),
       "file":n.get("file"),"see":n.get("see")}
    if n["type"]=="thread":
        s["op_present"]=bool(n.get("op"))
        s["comments"]=[{"stage":c.get("stage",n.get("stage",1)),"deleted":bool(c.get("deleted")),
                        "link":(c.get("link") or {}).get("node")} for c in n.get("comments",[])]
    if n["type"]=="forum": s["sections"]=[[t["id"] for t in sec["threads"]] for sec in n["sections"]]
    if n["type"]=="profile": s["album"]=n.get("album"); s["posts_links"]=[p.get("link") for p in n.get("posts",[])]
    if n["type"]=="album": s["items"]=[it["node"] for it in n["items"]]
    if n["type"]=="note": s["links"]=n.get("links")
    return s
def alltext(n):
    return json.dumps(n,ensure_ascii=False)
acc=[]; rej=[]
for outf in sorted(glob.glob("_enrich/out_*.json")):
    try: nodes=json.load(open(outf,encoding="utf-8"))
    except Exception as e: print(f"❌ {outf} 非合法JSON: {e}"); sys.exit(1)
    if isinstance(nodes,dict) and "nodes" in nodes: nodes=nodes["nodes"]
    for n in nodes:
        i=n.get("id")
        if i not in ix: rej.append((i,"未知節點")); continue
        if i not in sig: rej.append((i,"不在可加厚清單(凍結區?)")); continue
        if struct_sig(n)!=sig[i]:
            # 找出差異欄位
            a,b=struct_sig(n),sig[i]; diff=[k for k in b if a.get(k)!=b.get(k)]
            rej.append((i,f"結構被改:{diff}")); continue
        hit=[w for w in FORBID if w in alltext(n)]
        if hit: rej.append((i,f"禁詞:{hit}")); continue
        acc.append(n)
# 套用
accids={n["id"] for n in acc}
newnodes=[]
for n in W["nodes"]:
    if n["id"] in accids: newnodes.append(next(x for x in acc if x["id"]==n["id"]))
    else: newnodes.append(n)
if "--apply" in sys.argv:
    os.rename("mingyan-world.json","mingyan-world.json.bak")
    json.dump({"config":W["config"],"nodes":newnodes},open("mingyan-world.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print("✅ 已套用,原檔備份 mingyan-world.json.bak")
print(f"\n通過並加厚: {len(acc)} | 退回原文: {len(rej)}")
for i,why in rej: print(f"  ↩︎ {i}: {why}")
covered=accids|set(x[0] for x in rej)
missing=[i for i in sig if i not in covered]
if missing: print(f"⚠️ 未收到輸出的節點({len(missing)}): {missing}")
