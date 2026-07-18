#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
偽文件解謎 — ARG 兔子洞產生器 v1
=================================================
讀一份「世界圖」JSON，編譯成一整包互相連結的靜態 HTML（每節點一個獨立檔）。
設計目標（對應使用者需求）：
  1. 規模：幾十份文件／連結交織成網，要一層層點進去挖。
  2. 間接：關鍵不在單一頁，要跨文件對照才拼得出。
  3. 刪檔還原：deleted 節點顯示「已刪除」，真實網址藏在頁面「原始碼」的 HTML 註解裡；
     玩家用每頁自帶的「⟨/⟩ 檢視原始檔」按鈕（手機也能用）看源碼 → 撈出網址 → 貼回網址列，
     才進得了那個「不被任何連結指到」的隱藏頁。

為什麼每頁一個獨立檔：看 A 頁源碼不會洩漏 B 頁——每頁源碼只含該頁該有的東西＋作者
故意留的麵包屑。隱藏頁檔名用 hash 混淆，S3+CloudFront 無目錄列表 → 無法枚舉。

用法：
  python3 build.py mingyan-world.json            # 輸出到 dist/<case>/
  python3 build.py mingyan-world.json --out /tmp/x
"""
import json, sys, html, hashlib, os, argparse, re

DEV = False  # --dev 時 True → 頁面注入 ?stage 覆寫(僅授權/測試);正式產出為 False
GATE_FROM = 4  # stage>=此值的節點內文「不烘進靜態檔」,改由伺服器閘門按全服階段發放(Codex:純靜態view-source會提前洩S4)
SECRET = {}    # build 過程收集:檔名 → 機密內文HTML;寫成 _secret_bundle.json 給閘門Lambda,不部署到S3

# ---------- 檔名 ----------
def filename(node):
    """隱藏節點用 hash 檔名（不可猜、不被連結）；一般節點用可讀 id。
    node['file'] 明指檔名 → 逐字採用（給「靠遞增數字網址才找得到」的節點用）。"""
    if node.get("file"):
        return node["file"]
    if node.get("hidden"):
        salt = node.get("salt", node["id"])
        h = hashlib.sha1(("arg-" + salt).encode()).hexdigest()[:8]
        return f"_{h}.html"
    return node["id"] + ".html"

# ---------- HTML 逃逸小工具 ----------
def esc(s):
    return html.escape(str(s), quote=True)

def linkref(nodes_by_id, ref, label=None):
    """把節點 id 轉成 <a href>。ref 可為 'id' 或 'id#anchor'。"""
    base = ref.split("#")[0]
    anchor = ("#" + ref.split("#")[1]) if "#" in ref else ""
    if base not in nodes_by_id:
        raise SystemExit(f"[錯誤] 連結指向不存在的節點：{ref}")
    href = filename(nodes_by_id[base]) + anchor
    text = label or nodes_by_id[base].get("title", base)
    return f'<a href="{esc(href)}">{esc(text)}</a>'

# ---------- 版面 CSS（延用 mingyan.html 深色調） ----------
CSS = """
:root{--bg:#12151a;--card:#1b1f27;--ink:#dbe1e8;--sub:#8790a0;--line:#2a3140;--accent:#5aa6b8;--warn:#c98f9f;--paper:#f3efe6;--paperink:#2a2620}
*{box-sizing:border-box}
body{margin:0;font-family:"PingFang TC","Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif;background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased;line-height:1.7}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header{background:linear-gradient(120deg,#171b22,#1f2530);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:50}
.bar{max-width:780px;margin:0 auto;padding:12px 18px;display:flex;align-items:center;gap:12px}
.logo{width:32px;height:32px;border-radius:9px;background:var(--accent);color:#0e1216;font-weight:900;display:grid;place-items:center;font-size:16px}
.brand{font-weight:800;letter-spacing:.5px}.brand small{display:block;font-weight:400;color:var(--sub);font-size:11px;letter-spacing:2px}
.bar nav{margin-left:auto;display:flex;gap:14px;font-size:13px;color:var(--sub)}
.wrap{max-width:780px;margin:16px auto 90px;padding:0 18px}
.crumbs{font-size:12px;color:var(--sub);margin:6px 0 12px}
h1{font-size:21px;margin:0 0 12px;line-height:1.45}h2{font-size:16px;margin:22px 0 8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.card+.card{margin-top:14px}
.op{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:10px;padding:13px 15px;color:#c2cad4;font-size:14px}
.who{display:flex;align-items:center;gap:9px;margin-bottom:8px}
.who .a{width:30px;height:30px;border-radius:50%;background:#3a4453;display:grid;place-items:center;font-size:13px;color:#cfd6df;font-weight:700}
.who b{font-size:14px}.who span{color:var(--sub);font-size:12px}
.bhead{display:flex;align-items:center;gap:8px;padding:12px 16px;border-bottom:1px solid var(--line);font-weight:700}
.bhead .cnt{margin-left:auto;font-weight:400;color:var(--sub);font-size:13px}
.acc{display:inline-block;width:4px;height:15px;background:var(--accent);border-radius:2px;margin-right:6px;vertical-align:-2px}
.cmt{display:flex;gap:12px;padding:14px 16px;border-bottom:1px solid var(--line)}.cmt:last-child{border-bottom:0}
.ava{flex:0 0 auto;width:36px;height:36px;border-radius:50%;display:grid;place-items:center;color:#0e1216;font-weight:700;font-size:13px}
.cbody{flex:1;min-width:0}.crow{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.cname{font-weight:700;font-size:14px}.ctime{color:var(--sub);font-size:12px}
.ctext{margin:5px 0 6px;font-size:14.5px;word-break:break-word;color:#d3dae2}
.cfoot{font-size:12px;color:var(--sub);display:flex;gap:16px}
.removed .ava{background:#39414d!important;color:#7a8494}
.removed .ctext{color:#79828f;font-style:italic;background:#191d24;border:1px dashed #313a48;border-radius:8px;padding:9px 12px;display:inline-block}
.tlist a{display:flex;gap:10px;align-items:baseline;padding:12px 16px;border-bottom:1px solid var(--line);color:var(--ink)}
.tlist a:hover{background:#20252f;text-decoration:none}.tlist a:last-child{border-bottom:0}
.tlist .tt{flex:1;font-size:14.5px}.tlist .rc{color:var(--sub);font-size:12px}.hot{color:#c98f6a;font-size:12px;margin-left:6px}
.board-h{padding:10px 16px;background:#161a21;border-bottom:1px solid var(--line);color:var(--sub);font-size:12px;letter-spacing:2px}
.kv{width:100%;border-collapse:collapse;font-size:14px}
.kv td{padding:9px 14px;border-bottom:1px solid var(--line);vertical-align:top}
.kv td:first-child{color:var(--sub);width:34%;white-space:nowrap}
.doc{background:var(--paper);color:var(--paperink);border-radius:10px;padding:22px 24px;font-family:"Noto Serif TC","PingFang TC",serif}
.doc h1{font-size:19px;border-bottom:2px solid #c9bfa8;padding-bottom:8px}
.doc .org{color:#6b6355;font-size:12px;letter-spacing:2px;margin-bottom:4px}
.doc .kv td{border-bottom:1px solid #ddd3bd}.doc .kv td:first-child{color:#7a715c}
.doc .sec{margin:14px 0}.doc .sec h3{font-size:14px;margin:0 0 4px;color:#4a4436}
.doc .stamp{display:inline-block;margin-top:14px;color:#a2432f;border:2px solid #a2432f;border-radius:6px;padding:4px 12px;font-weight:800;transform:rotate(-6deg);letter-spacing:2px;opacity:.82}
.thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px;padding:14px}
.thumbs a{display:block;text-decoration:none}
.thumbs .th{aspect-ratio:1;border-radius:8px;background:#252b35 center/cover no-repeat;border:1px solid var(--line);display:grid;place-items:center;color:#4c5563;font-size:11px}
.thumbs .lb{font-size:12px;color:var(--sub);margin-top:4px;text-align:center}
.imgview img{width:100%;border-radius:10px;display:block}
.cap{color:var(--sub);font-size:13px;margin-top:8px}
.deleted-box{text-align:center;padding:40px 20px;color:#79828f}
.deleted-box .big{font-size:40px;margin-bottom:10px;opacity:.5}
.deleted-box .r{font-style:italic;background:#191d24;border:1px dashed #313a48;border-radius:8px;padding:12px 16px;display:inline-block;margin-top:8px;font-size:13.5px}
.para{font-size:14.5px;margin:10px 0;color:#d3dae2}
.foot{max-width:780px;margin:0 auto;padding:18px;color:#4c5563;font-size:11.5px;line-height:1.9;border-top:1px solid var(--line)}
.lock{text-align:center;padding:60px 20px;color:#8790a0}
.lock .ic{font-size:44px}.lock .t{margin-top:12px;font-size:15px}
/* 檢視原始檔 */
#vs-btn{position:fixed;right:14px;bottom:14px;z-index:200;background:#232935;color:#9fb4c4;border:1px solid #38424f;border-radius:20px;padding:8px 14px;font-size:12.5px;cursor:pointer;font-family:ui-monospace,Menlo,monospace;box-shadow:0 4px 14px rgba(0,0,0,.4)}
#vs-btn:hover{background:#2b3340;color:#cfe0ec}
#vs-modal{position:fixed;inset:0;z-index:300;background:rgba(6,8,11,.86);display:none;padding:24px}
#vs-modal.on{display:flex;flex-direction:column;max-width:920px;margin:0 auto}
#vs-modal .h{color:#9fb4c4;font:600 13px ui-monospace,monospace;padding:6px 2px;display:flex;align-items:center;gap:12px}
#vs-modal .h b{color:#e0e8ef}#vs-modal .h .x{margin-left:auto;cursor:pointer;color:#8790a0;font-size:20px}
#vs-modal pre{flex:1;overflow:auto;background:#0d1015;border:1px solid #2a3140;border-radius:8px;margin:8px 0 0;padding:14px;color:#8fb7a8;font:12px/1.6 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-all}
#vs-modal pre .cm{color:#c98f6a}
.note-warn{color:var(--warn);font-size:12.5px}
"""

# ---------- 每頁尾端腳本：階段閘門 + 檢視原始檔 ----------
def page_script(cfg, node):
    stage = node.get("stage", 1)
    # ?stage=N 覆寫只在 --dev 版注入;正式產出不含——否則玩家在任何頁加 ?stage=4 即繞過階段閘門(Codex High)
    dev_read = "var ov = parseInt(new URLSearchParams(location.search).get('stage'),10);" if DEV else "/* stage 覆寫僅 --dev 版提供;正式版一律以 Firestore 階段為準 */"
    dev_branch = "if(ov>=1 && ov<=9){ applyStage(ov); return; }" if DEV else "/* 正式版:不吃網址 ?stage 覆寫 */"
    return f"""
<button id="vs-btn" onclick="showSrc()">⟨/⟩ 檢視原始檔</button>
<div id="vs-modal">
  <div class="h"><b>檢視原始檔</b>｜ {esc(filename(node))} <span style="color:#5c6675">— 本頁 HTML 原始碼</span><span class="x" onclick="hideSrc()">✕</span></div>
  <pre id="vs-pre"></pre>
</div>
<script>
/* ===== 檢視原始檔（手機也能用；等同瀏覽器 view-source，含 HTML 註解） ===== */
function showSrc(){{
  var raw = '<!DOCTYPE html>\\n' + document.documentElement.outerHTML;
  var e = document.getElementById('vs-pre');
  e.textContent = raw;
  /* 把 HTML 註解上色，暗示玩家「這裡有東西」 */
  e.innerHTML = e.innerHTML.replace(/(&lt;!--[\\s\\S]*?--&gt;)/g,'<span class="cm">$1</span>');
  document.getElementById('vs-modal').classList.add('on');
}}
function hideSrc(){{ document.getElementById('vs-modal').classList.remove('on'); }}
document.addEventListener('keydown',function(e){{ if(e.key==='Escape') hideSrc(); }});

/* ===== 階段閘門：本頁屬第 {stage} 階段，案情未到不給看（?stage 覆寫僅 --dev 版） ===== */
(function(){{
  var NODE_STAGE = {stage};
  var PID = {json.dumps(cfg['puzzleId'])};
  var FB = {json.dumps(cfg['firebaseKey'])};
  var CFG = 'https://firestore.googleapis.com/v1/projects/'+{json.dumps(cfg['firebaseProject'])}+'/databases/(default)/documents/sml_config/puzzle_stage?key='+FB;
  {dev_read}
  var body = document.getElementById('pagebody');
  function lock(){{ if(body) body.innerHTML = '<div class="lock"><div class="ic">🔒</div><div class="t">案情還沒進展到這裡。<br>先回去把手上的線索挖透，之後再來。</div></div>'; }}
  function applyStage(cur){{
    // 整頁閘門：本頁階段未到 → 鎖
    if(cur<NODE_STAGE){{ lock(); return; }}
    // 逐則閘門：討論串留言／連結，階段未到者隱藏、不計入樓層
    var shown=0;
    document.querySelectorAll('[data-cstage]').forEach(function(el){{
      var s=parseInt(el.getAttribute('data-cstage'),10)||1;
      var hide=s>cur;
      el.style.display=hide?'none':'';
      if(el.classList.contains('cmt')&&!hide) shown++;
    }});
    var cnt=document.getElementById('cmt-cnt');
    if(cnt) cnt.textContent='共 '+shown+' 則';
  }}
  {dev_branch}
  applyStage(1); // 先以 S1 呈現，避免抓資料前閃出後段內容
  fetch(CFG).then(function(r){{return r.json();}}).then(function(d){{
    var f=(d&&d.fields)||{{}};
    var pid=(f.puzzleId&&f.puzzleId.stringValue)||'';
    var st=parseInt((f.stage&&f.stage.integerValue)||'1',10);
    var cur=(pid===PID)?st:1;
    applyStage(cur);
  }}).catch(function(){{}});
}})();
</script>
"""

# ---------- 加固節點(stage>=GATE_FROM)的殼腳本：內文向伺服器閘門索取,view-source 看不到 ----------
def gated_script(cfg, node):
    stage = node.get("stage", 1)
    fn = filename(node)
    gate_url = cfg.get("gateUrl", "")  # 閘門 HTTP API(2a-2 Lambda);未設則保持鎖住
    return f"""
<button id="vs-btn" onclick="showSrc()">⟨/⟩ 檢視原始檔</button>
<div id="vs-modal">
  <div class="h"><b>檢視原始檔</b>｜ {esc(fn)} <span style="color:#5c6675">— 本頁 HTML 原始碼</span><span class="x" onclick="hideSrc()">✕</span></div>
  <pre id="vs-pre"></pre>
</div>
<script>
function showSrc(){{
  var raw='<!DOCTYPE html>\\n'+document.documentElement.outerHTML;
  var e=document.getElementById('vs-pre'); e.textContent=raw;
  e.innerHTML=e.innerHTML.replace(/(&lt;!--[\\s\\S]*?--&gt;)/g,'<span class="cm">$1</span>');
  document.getElementById('vs-modal').classList.add('on');
}}
function hideSrc(){{ document.getElementById('vs-modal').classList.remove('on'); }}
document.addEventListener('keydown',function(e){{ if(e.key==='Escape') hideSrc(); }});

/* ===== 加固殼：本頁(第 {stage} 階)內文不在靜態檔;到階段才向伺服器閘門索取 =====
   view-source 這一頁只會看到這個殼、看不到內文——內文由閘門按全服階段發放。 */
(function(){{
  var NODE_STAGE={stage}, FN={json.dumps(fn)}, CASE={json.dumps(cfg['case'])};
  var GATE={json.dumps(gate_url)};
  var PID={json.dumps(cfg['puzzleId'])}, FB={json.dumps(cfg['firebaseKey'])};
  var CFG='https://firestore.googleapis.com/v1/projects/'+{json.dumps(cfg['firebaseProject'])}+'/databases/(default)/documents/sml_config/puzzle_stage?key='+FB;
  var body=document.getElementById('pagebody');
  function lock(msg){{ if(body) body.innerHTML='<div class="lock"><div class="ic">🔒</div><div class="t">'+(msg||'案情還沒進展到這裡。<br>先回去把手上的線索挖透，之後再來。')+'</div></div>'; }}
  function unlock(){{
    if(!GATE){{ lock('（此頁尚未接上伺服器，稍後再試）'); return; }}
    fetch(GATE+'?case='+encodeURIComponent(CASE)+'&node='+encodeURIComponent(FN))
      .then(function(r){{ if(!r.ok) throw 0; return r.text(); }})
      .then(function(html){{ if(body) body.innerHTML=html; }})
      .catch(function(){{ lock('（連線逾時，重整再試）'); }});
  }}
  fetch(CFG).then(function(r){{return r.json();}}).then(function(d){{
    var f=(d&&d.fields)||{{}};
    var pid=(f.puzzleId&&f.puzzleId.stringValue)||'';
    var st=parseInt((f.stage&&f.stage.integerValue)||'1',10);
    var cur=(pid===PID)?st:1;
    if(cur<NODE_STAGE) lock(); else unlock();
  }}).catch(function(){{ lock(); }});
}})();
</script>
"""

# ---------- 各節點類型渲染 ----------
def r_forum(n, ix):
    out = []
    for sec in n.get("sections", []):
        out.append(f'<div class="card"><div class="board-h">{esc(sec.get("board",""))}</div><div class="tlist">')
        for t in sec["threads"]:
            hot = '<span class="hot">🔥熱</span>' if t.get("hot") else ''
            rc = f'<span class="rc">{esc(t.get("replies",""))} 則</span>' if t.get("replies") else ''
            out.append(f'{linkref_row(ix,t["id"],t["title"],hot,rc)}')
        out.append('</div></div>')
    return "\n".join(out)

def linkref_row(ix, ref, title, hot, rc):
    base=ref.split("#")[0]; href=filename(ix[base])
    return f'<a href="{esc(href)}"><span class="tt">{esc(title)}{hot}</span>{rc}</a>'

def r_thread(n, ix):
    """留言逐則分階段顯示：留言(或連結)的 stage 高於當前案情階段 → 前端隱藏、不計入樓層數。
    keystone 一律不寫進留言（會被『檢視原始檔』讀到）——後段留言只給異常感＋指向被刪文件。"""
    node_stage=n.get("stage",1)
    out=[]
    op=n.get("op")
    if op:
        ini=re.sub(r"\s","",op["name"])[-2:]
        out.append(f'<div class="op"><div class="who"><div class="a">{esc(ini)}</div><div><b>{esc(op["name"])}</b> <span>· {esc(op.get("time",""))}</span></div></div>{esc(op["text"])}</div>')
    cs=n.get("comments",[])
    out.append('<div class="card"><div class="bhead"><i class="acc"></i>留言 <span class="cnt" id="cmt-cnt">—</span></div>')
    for c in cs:
        cstage=c.get("stage",node_stage)
        if c.get("deleted"):
            out.append(f'<div class="cmt removed" data-cstage="{cstage}"><div class="ava">－</div><div class="cbody"><div class="crow"><span class="cname" style="color:#7a8494">{esc(c.get("name","匿名"))}</span><span class="ctime">{esc(c.get("time",""))}</span></div><div class="ctext">［此留言已被{esc(c.get("reason","原作者刪除"))}］</div></div></div>')
            continue
        ini=re.sub(r"\s","",c.get("name","匿名"))[-2:]
        color=c.get("color","#8fb0c9")
        extra=""
        if c.get("link"):
            # 連結自己的 stage 可比留言更晚（留言先出現、連到的證物晚點才通）
            lstage=c["link"].get("stage",cstage)
            extra=f' <span class="linkwrap" data-cstage="{lstage}" style="font-size:12px">🔗 {linkref(ix,c["link"]["node"],c["link"].get("label","（附連結）"))}</span>'
        out.append(f'<div class="cmt" data-cstage="{cstage}"><div class="ava" style="background:{esc(color)}">{esc(ini)}</div><div class="cbody"><div class="crow"><span class="cname">{esc(c["name"])}</span><span class="ctime">{esc(c.get("time",""))}</span></div><div class="ctext">{esc(c["text"])}{extra}</div><div class="cfoot"><span>讚 {c.get("likes",0)}</span><span>回覆</span><span>檢舉</span></div></div></div>')
    out.append('</div>')
    return "\n".join(out)

def r_profile(n, ix):
    out=[f'<div class="card" style="padding:16px"><div style="display:flex;gap:14px;align-items:center"><div class="ava" style="width:56px;height:56px;font-size:20px;background:{esc(n.get("color","#3a4453"))}">{esc(n.get("name","？")[-1])}</div><div><div style="font-weight:800;font-size:16px">{esc(n.get("name",""))}</div><div style="color:#8790a0;font-size:12px">{esc(n.get("handle",""))}</div></div></div>']
    if n.get("bio"): out.append(f'<div class="para" style="margin-top:12px">{esc(n["bio"])}</div>')
    if n.get("meta"):
        out.append('<table class="kv" style="margin-top:8px">'+''.join(f'<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>' for k,v in n["meta"])+'</table>')
    out.append('</div>')
    if n.get("posts"):
        out.append('<div class="card"><div class="board-h">近期貼文</div><div class="tlist">')
        for p in n["posts"]:
            if p.get("link"): out.append(linkref_row(ix,p["link"],p["title"],"",f'<span class="rc">{esc(p.get("time",""))}</span>'))
            else: out.append(f'<a style="cursor:default"><span class="tt">{esc(p["title"])}</span><span class="rc">{esc(p.get("time",""))}</span></a>')
        out.append('</div></div>')
    if n.get("album"):
        out.append(f'<div class="card" style="padding:14px">📁 {linkref(ix,n["album"],"個人相簿")}</div>')
    return "\n".join(out)

def r_album(n, ix):
    out=['<div class="card"><div class="thumbs">']
    for it in n["items"]:
        base=it["node"].split("#")[0]; href=filename(ix[base])
        bg=f'background-image:url({esc(it["thumb"])})' if it.get("thumb") else ''
        inner='' if it.get("thumb") else '🖼'
        out.append(f'<a href="{esc(href)}"><div class="th" style="{bg}">{inner}</div><div class="lb">{esc(it.get("label",""))}</div></a>')
    out.append('</div></div>')
    return "\n".join(out)

def r_image(n, ix):
    out=['<div class="card imgview" style="padding:14px">']
    if n.get("src"): out.append(f'<img src="{esc(n["src"])}" alt="">')
    else: out.append('<div class="th" style="aspect-ratio:4/3;display:grid;place-items:center;color:#4c5563">（影像）</div>')
    if n.get("caption"): out.append(f'<div class="cap">{esc(n["caption"])}</div>')
    out.append('</div>')
    if n.get("exif"):
        out.append('<div class="card"><div class="board-h">檔案資訊 / EXIF</div><table class="kv">'+''.join(f'<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>' for k,v in n["exif"])+'</table></div>')
    return "\n".join(out)

def r_doc(n, ix):
    out=['<div class="doc">']
    if n.get("org"): out.append(f'<div class="org">{esc(n["org"])}</div>')
    out.append(f'<h1>{esc(n.get("docTitle",n.get("title","")))}</h1>')
    if n.get("meta"):
        out.append('<table class="kv">'+''.join(f'<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>' for k,v in n["meta"])+'</table>')
    for s in n.get("secs",[]):
        out.append('<div class="sec">')
        if s.get("h"): out.append(f'<h3>{esc(s["h"])}</h3>')
        out.append(f'<div>{esc(s.get("body",""))}</div></div>')
    if n.get("stamp"): out.append(f'<div class="stamp">{esc(n["stamp"])}</div>')
    out.append('</div>')
    return "\n".join(out)

def r_deleted(n, ix):
    rec=n.get("recover")
    hint = ''
    if rec:
        base=rec["node"].split("#")[0]
        hidden_url = "./" + filename(ix[base])
        # 麵包屑：把隱藏頁真實網址藏進 HTML 註解，玩家要開「檢視原始檔」才看得到
        hint = f'\n<!-- ================= 站務系統備份紀錄（勿刪） ================= -->\n<!-- {esc(rec.get("note","此文件已由作者移除，備份仍在伺服器"))} -->\n<!-- 備份位置： {esc(hidden_url)} -->\n<!-- 需具權限並直接輸入上列位置存取，前台已不提供連結。 -->\n<!-- ============================================================ -->\n'
    out=[f'<div class="card"><div class="deleted-box"><div class="big">🗑</div><div style="font-weight:700">此文件已被刪除</div><div class="r">{esc(n.get("reason","本文件因檢舉／作者要求已自前台移除。"))}</div></div></div>']
    if n.get("hintText"):
        out.append(f'<div class="card" style="padding:14px"><div class="note-warn">{esc(n["hintText"])}</div></div>')
    out.append(hint)
    return "\n".join(out)

def r_note(n, ix):
    out=[]
    for para in n.get("paras",[]):
        out.append(f'<div class="para">{esc(para)}</div>')
    if n.get("links"):
        out.append('<div class="card"><div class="tlist">')
        for ref,label in n["links"]:
            out.append(linkref_row(ix,ref,label,"",""))
        out.append('</div></div>')
    if n.get("rawHtml"): out.append(n["rawHtml"])
    return "\n".join(out)

RENDER={"forum":r_forum,"thread":r_thread,"profile":r_profile,"album":r_album,"image":r_image,"doc":r_doc,"deleted":r_deleted,"note":r_note}

# ---------- 組頁 ----------
def build_page(cfg, node, ix):
    body = RENDER[node["type"]](node, ix)
    # 通用「相關連結」欄（任何節點可用 see:[[ref,label],...] 掛出動線；含跨階段連結會自動被階段閘門隱藏）
    see = node.get("see")
    if see:
        rows = "".join(
            f'<span class="linkwrap" data-cstage="{(ix[r.split("#")[0]].get("stage",1))}" style="display:block">{linkref(ix,r,lb)}</span>'
            for r, lb in see)
        body += f'<div class="card" style="margin-top:14px"><div class="board-h">相 關 連 結</div><div class="tlist" style="padding:6px 16px">{rows}</div></div>'
    crumb = f'<div class="crumbs">{esc(node.get("crumb",""))}</div>' if node.get("crumb") else ''
    title = f'<h1>{esc(node["title"])}</h1>' if node.get("showTitle",True) and node.get("title") else ''
    inner = f"{crumb}{title}\n{body}"

    # === 加固：stage>=GATE_FROM 的節點,內文不進靜態檔,收進 SECRET 交伺服器閘門按全服階段發放 ===
    # --dev 版不 gate(全靜態供作者預覽/截圖);正式版才 gate
    gated = (not DEV) and node.get("stage",1) >= GATE_FROM
    if gated:
        SECRET[filename(node)] = {"minStage": node.get("stage",1), "html": inner}  # 閘門按 minStage 發放
        page_title = esc(cfg['siteName'])                       # 標題不洩節點名
        pagebody   = ('<div class="lock" id="gate-lock"><div class="ic">🔒</div>'
                      '<div class="t">載入中…（此頁內容需案情進展到本階段、由伺服器發放）</div></div>')
        tail       = gated_script(cfg, node)
    else:
        page_title = f"{esc(node.get('title',''))}｜{esc(cfg['siteName'])}"
        pagebody   = inner
        tail       = page_script(cfg, node)

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_title}</title>
<style>{CSS}</style>
</head>
<body>
<header><div class="bar"><div class="logo">{esc(cfg['siteLogo'])}</div><div class="brand">{esc(cfg['siteName'])}<small>{esc(cfg.get('siteSub',''))}</small></div><nav>{''.join(f'<span>{esc(x)}</span>' for x in cfg.get('nav',[]))}</nav></div></header>
<div class="wrap"><div id="pagebody">{pagebody}
</div></div>
<div class="foot">{esc(cfg.get('footer',''))}<br><span style="color:#3f4650">（本頁為解謎遊戲虛構道具，地點／人物／情節／機構皆屬原創虛構，不影射任何真實個案。）</span></div>
{tail}
</body>
</html>"""

def main():
    global DEV,GATE_FROM,SECRET
    _default_gate=GATE_FROM
    ap=argparse.ArgumentParser()
    ap.add_argument("world")
    ap.add_argument("--out",default=None)
    ap.add_argument("--dev",action="store_true",help="注入 ?stage=N 覆寫且不 gate(僅授權/測試預覽,勿部署)")
    ap.add_argument("--gate-from",type=int,default=_default_gate,help=f"stage>=此值的節點內文改伺服器閘門發放(預設{_default_gate};0=關閉加固全靜態)")
    a=ap.parse_args()
    DEV=a.dev; GATE_FROM=(a.gate_from if a.gate_from>0 else 999); SECRET={}
    W=json.load(open(a.world,encoding="utf-8"))
    cfg=W["config"]; nodes=W["nodes"]
    ix={n["id"]:n for n in nodes}
    if len(ix)!=len(nodes): raise SystemExit("[錯誤] 有重複 node id")
    out=a.out or os.path.join(os.path.dirname(os.path.abspath(a.world)),"dist",cfg["case"])
    os.makedirs(out,exist_ok=True)
    # 先清掉上一版產物（避免改檔名後留 stale 頁被玩家撞見）
    for old in os.listdir(out):
        if old.endswith(".html") or old=="_manifest.json":
            os.remove(os.path.join(out,old))
    manifest=[]
    for n in nodes:
        if n["type"] not in RENDER: raise SystemExit(f"[錯誤] 未知節點類型 {n['type']} @ {n['id']}")
        fn=filename(n)
        open(os.path.join(out,fn),"w",encoding="utf-8").write(build_page(cfg,n,ix))
        manifest.append({"id":n["id"],"file":fn,"type":n["type"],"stage":n.get("stage",1),"hidden":bool(n.get("hidden")),"clue":bool(n.get("clue"))})
    json.dump(manifest,open(os.path.join(out,"_manifest.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    # 機密內文 bundle(stage>=GATE_FROM 的節點內文)→ 給閘門 Lambda,⚠️不部署到 S3
    json.dump(SECRET,open(os.path.join(out,"_secret_bundle.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    # 統計
    total=len(nodes); hidden=sum(1 for n in nodes if n.get("hidden")); clue=sum(1 for n in nodes if n.get("clue"))
    mode="[--dev:全靜態,勿部署]" if DEV else (f"[正式版:stage>={GATE_FROM}內文伺服器閘門發放,共{len(SECRET)}頁]" if GATE_FROM<999 else "[全靜態:未加固]")
    print(f"✅ 產出 {total} 頁 → {out}　{mode}")
    print(f"   隱藏頁：{hidden}　關鍵路徑節點：{clue}　機密bundle：{len(SECRET)}頁(_secret_bundle.json,勿部署)")
    print(f"   入口：{filename(ix[cfg['entry']])}")
if __name__=="__main__":
    main()
