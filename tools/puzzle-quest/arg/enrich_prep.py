#!/usr/bin/env python3
# Phase C 準備:把「可加厚」的氛圍/紅鯡魚節點分批抽出;凍結結構簽章供合併時驗證。
import json,os
W=json.load(open("mingyan-world.json"))
ix={n["id"]:n for n in W["nodes"]}

# 絕不交給Fable5的節點(keystone/關鍵路徑/已校準的埋深素材)——名單即「凍結區」
FROZEN={"t-main","d-electrical","d-ledger","d-pigment","d-safety-check","d-access-log",
        "d-access-named","d-timeline","del-electrical","del-ledger","del-safety",
        "del-zhuo-comment","img-zhuo-notebook","uploads-0417",
        "n-webmaster","n-archive-notice","n-sitemap","n-404",
        "uploads-index","img-0416","img-0418","d-appraisal-draft"}

# 可加厚節點依主題分4批(各批節點互不重疊→可平行、無合併衝突)
BATCHES={
 "batch1_atmosphere": ["t-memorial","t-blackout","t-food","t-lostcat","p-shen","d-obituary","d-news"],
 "batch2_assistant":  ["t-artgossip","t-jobrant","p-zhuo","d-hr","al-zhuo","img-notebook-a","img-scene"],
 "batch3_collector":  ["t-collector","p-guo","d-buyer-alibi","t-auction","d-catalog","al-auction","img-painting","img-painting-detail"],
 "batch4_facade_staff":["p-gao","d-gaostatement","p-insider","p-guard","n-rules"],
}

os.makedirs("_enrich",exist_ok=True)
sig={}
def struct_sig(n):
    # 凍結欄位:結構性的一律不准動
    s={"id":n["id"],"type":n["type"],"stage":n.get("stage",1),"hidden":bool(n.get("hidden")),
       "file":n.get("file"),"see":n.get("see")}
    if n["type"]=="thread":
        s["op_present"]=bool(n.get("op"))
        s["comments"]=[{"stage":c.get("stage",n.get("stage",1)),"deleted":bool(c.get("deleted")),
                        "link":(c.get("link") or {}).get("node")} for c in n.get("comments",[])]
    if n["type"]=="forum":
        s["sections"]=[[t["id"] for t in sec["threads"]] for sec in n["sections"]]
    if n["type"]=="profile":
        s["album"]=n.get("album"); s["posts_links"]=[p.get("link") for p in n.get("posts",[])]
    if n["type"]=="album":
        s["items"]=[it["node"] for it in n["items"]]
    if n["type"]=="note":
        s["links"]=n.get("links")
    return s

allids=set()
for bname,ids in BATCHES.items():
    nodes=[]
    for i in ids:
        assert i in ix, f"批次節點不存在:{i}"
        assert i not in FROZEN, f"批次誤含凍結節點:{i}"
        assert i not in allids, f"節點重複跨批:{i}"
        allids.add(i)
        nodes.append(ix[i]); sig[i]=struct_sig(ix[i])
    json.dump(nodes,open(f"_enrich/{bname}.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print(f"{bname}: {len(nodes)} 節點 → _enrich/{bname}.json")
json.dump(sig,open("_enrich/_signatures.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(f"凍結區(不交Fable5): {len(FROZEN)} 節點 | 交Fable5加厚: {len(allids)} 節點 | 簽章存 _enrich/_signatures.json")
