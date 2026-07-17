#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_case.py — 偽文件解謎 case JSON 一鍵機械驗收（把 DESIGN_DIRECTION §5 的機械檢查自動化）。

用法:
    python3 verify_case.py CASE-13-mingyan.json
    python3 verify_case.py CASE-13-mingyan.json --site mingyan.html
    python3 verify_case.py CASE-13-mingyan.json --assets /opt/sml/sweetbot-next/data/puzzle-assets

檢查項（✗=阻斷/exit 1、⚠=人工確認、✓=通過）:
  1. JSON parse + 必要欄位齊全
  2. 洩漏掃描「對真 core.any」(非手寫詞表——這是本工具存在的理由):
       - hints / partial nudge / genericNudge / npc.fallbackNudges → 任何 core 詞都不准 (含兇手名)  [✗]
       - intro / npc.system → method/motive **keystone** 不准；culprit 稱謂可留(公平伏筆)          [✗ / 允許]
       - 早階段(S1–S3) clue 的 .html → keystone 不准 (culprit 稱謂允許)                             [⚠]
       - 假網站 .html 出現 keystone 詞 → 列行號待人工確認只在 appear:4 留言                          [⚠]
  3. 素材↔JSON 對映：poster/message/docs 是否存在(posters/ 或 assets/)；*-notebook-* 缺→已知 TODO  [✗ / INFO]
  4. core.any 偏泛短詞(≤2字)警示：includes 判定易被無關/負向輸入撞到                                [⚠]
  5. win-gate 推演：S1+S2 能不能湊齊 core（method/motive keystone 是否真的鎖在 S4）                 [提示]

keystone vs 兇手名分野見 DESIGN_DIRECTION §5：要 grep 零命中的是 method/motive keystone；
culprit 稱謂是正解必需詞、可早期公平伏筆、不構成 win（win=三 core 全中）。
core id 含 'culprit'/'suspect' 者視為 culprit 核心，其餘視為 keystone。
"""
import sys, os, json, re, argparse

RED, YEL, GRN, DIM, RST = '\033[31m', '\033[33m', '\033[32m', '\033[2m', '\033[0m'
def emoji(ok): return f'{GRN}✓{RST}' if ok else f'{RED}✗{RST}'

errors = []   # 阻斷
warns = []    # 人工確認
def err(msg): errors.append(msg); print(f'  {RED}✗{RST} {msg}')
def warn(msg): warns.append(msg); print(f'  {YEL}⚠{RST} {msg}')
def ok(msg): print(f'  {GRN}✓{RST} {msg}')
def info(msg): print(f'  {DIM}·{RST} {msg}')
def head(msg): print(f'\n{msg}')

REQUIRED = ['id', 'title', 'intro', 'stageCount', 'stages', 'npc', 'hints', 'solution', 'reveal']  # caseNo 有 runtime fallback → 另做 warn
CULPRIT_IDS = ('culprit', 'suspect', 'who')
NOTEBOOK_RE = re.compile(r'-notebook-|notebook')

def load(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        err(f'JSON parse 失敗: {e}'); sys.exit(1)

def split_cores(sol):
    """回傳 (keystone_tokens:set, culprit_tokens:set, all_tokens:set)。"""
    ks, cp = set(), set()
    for c in sol.get('core', []):
        toks = set(c.get('any', []))
        if any(k in str(c.get('id', '')).lower() for k in CULPRIT_IDS):
            cp |= toks
        else:
            ks |= toks
    return ks, cp, ks | cp

def hits(text, tokens):
    if not text: return []
    return sorted({t for t in tokens if t in text}, key=len)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('case_json')
    ap.add_argument('--posters', default=None, help='posters/ HTML 目錄 (預設: json 同層 posters/)')
    ap.add_argument('--assets', action='append', default=None,
                    help='圖檔搜尋目錄，可多次；預設 posters/ + 甜甜 data/puzzle-assets')
    ap.add_argument('--site', default=None, help='假網站 HTML (預設: 自動找同 id 的 *.html)')
    args = ap.parse_args()

    base = os.path.dirname(os.path.abspath(args.case_json))
    posters = args.posters or os.path.join(base, 'posters')
    assets = args.assets or [posters, '/opt/sml/sweetbot-next/data/puzzle-assets']

    d = load(args.case_json)
    print(f'{DIM}=== verify_case: {os.path.basename(args.case_json)} (id={d.get("id")}, caseNo={d.get("caseNo")}) ==={RST}')

    # ── 1. schema ──
    head('1. Schema / 必要欄位')
    miss = [k for k in REQUIRED if k not in d]
    if miss: err(f'缺欄位: {miss}')
    else: ok('必要欄位齊全 + JSON parse OK')
    if 'caseNo' not in d: warn('無 caseNo（有 runtime fallback 不阻斷，但新案建議補上）')
    stages = d.get('stages', [])
    if len(stages) != d.get('stageCount'):
        warn(f'stageCount={d.get("stageCount")} 但 stages 有 {len(stages)} 筆')

    ks, cp, allc = split_cores(d.get('solution', {}))
    info(f'keystone 詞 {len(ks)} 個、culprit 詞 {len(cp)} 個')

    # ── 2. 洩漏掃描 (對真 core.any) ──
    head('2. 洩漏掃描（對真 core.any）')
    sol = d.get('solution', {})
    # 2a. answer-adjacent：任何 core 詞都不准（含兇手名）
    for i, h in enumerate(d.get('hints', [])):
        hh = hits(h.get('text', ''), allc)
        if hh: err(f'hint[{h.get("cost","?")}] 含 core 詞 {hh}（買提示=送破案詞）')
    for p in sol.get('partial', []):
        hh = hits(p.get('nudge', ''), allc)
        if hh: err(f'partial:{p.get("id")} nudge 含 core 詞 {hh}')
    hh = hits(sol.get('genericNudge', ''), allc)
    if hh: err(f'genericNudge 含 core 詞 {hh}')
    for i, fn in enumerate(d.get('npc', {}).get('fallbackNudges', [])):
        hh = hits(fn, allc)
        if hh: err(f'npc.fallbackNudges[{i}] 含 core 詞 {hh}')
    # 2b. intro / npc.system：keystone 不准；culprit 允許
    hh = hits(d.get('intro', ''), ks)
    if hh: err(f'intro 含 keystone {hh}')
    cph = hits(d.get('intro', ''), cp)
    if cph: warn(f'intro 出現 culprit 稱謂 {cph}（可,但 S0 通常不需點名，確認是否刻意）')
    # npc.system：只有「知情段」(禁令標記之前) 出現 keystone 才算洩漏；「絕不透露 keystone」屬 gate 指令，允許。
    sysfull = d.get('npc', {}).get('system', '')
    PROHIB = re.compile(r'絕不透露|絕不確認|【絕不|不得透露|不可透露|安全規則|不得談|不得推理')
    m = PROHIB.search(sysfull)
    know_part = sysfull[:m.start()] if m else sysfull
    prohib_part = sysfull[m.start():] if m else ''
    sysh = hits(know_part, ks)
    if sysh: err(f'npc.system 知情段含 keystone {sysh}（NPC「知道」不得涵蓋 keystone，會跳過 S4）')
    gateh = hits(prohib_part, ks)
    if gateh: info(f'npc.system 禁令段提到 keystone {gateh}（在「絕不透露…」內，允許）')
    syscp = hits(d.get('npc', {}).get('system', ''), cp)
    if syscp: info(f'npc.system 提到 culprit 稱謂 {syscp}（允許＝高層反常伏筆，win 仍鎖 method+motive）')
    # 2c. hotTopics（若有）
    for t in d.get('npc', {}).get('hotTopics', []) or []:
        blob = json.dumps(t, ensure_ascii=False)
        hh = hits(blob, ks)
        if hh: err(f'npc.hotTopics 某項含 keystone {hh}')
    if not errors:
        ok('answer-adjacent(hints/nudge/fallback) 對 core.any 零命中；intro/npc.system 無 keystone')

    # ── 2d. 早階段 clue .html + 假網站 → keystone 掃描 (⚠) ──
    head('2d. 早階段 clue HTML + 假網站 keystone 掃描')
    def scan_html(path, label, only_keystone=True):
        if not os.path.isfile(path): return
        try: txt = open(path, encoding='utf-8').read()
        except Exception: return
        txt = re.sub(r'<!--.*?-->', lambda mm: '\n' * mm.group(0).count('\n'), txt, flags=re.S)  # 去 HTML 註解(設計備註常含keystone)、保留行號
        toks = ks if only_keystone else allc
        found = {}
        for ln, line in enumerate(txt.splitlines(), 1):
            for t in toks:
                if t in line: found.setdefault(t, []).append(ln)
        if found:
            for t, lns in sorted(found.items(), key=lambda x: len(x[0])):
                warn(f'{label}: keystone「{t}」在行 {lns[:6]}{"…" if len(lns)>6 else ""}（確認只在 S4/appear:4）')
    # 早階段 (stage 1..3) 的 poster/message/docs 對應 .html
    early_htmls = set()
    for s in stages:
        if int(s.get('stage', 99)) >= 4: continue
        for fn in [s.get('poster'), s.get('message')] + (s.get('docs') or []):
            if fn:
                hp = os.path.join(posters, re.sub(r'\.png$', '.html', fn))
                if os.path.isfile(hp): early_htmls.add(hp)
    for hp in sorted(early_htmls):
        scan_html(hp, f'S1–3 clue {os.path.basename(hp)}')
    # 假網站
    site = args.site
    if not site:
        cand = os.path.join(base, re.sub(r'-.*', '', d.get('id', '')) + '.html')
        # fallback: 任一 stages[].site basename
        for s in stages:
            u = s.get('site') or ''
            m = re.search(r'/([^/?]+\.html)', u)
            if m:
                p = os.path.join(base, m.group(1))
                if os.path.isfile(p): site = p; break
    if site and os.path.isfile(site):
        scan_html(site, f'假網站 {os.path.basename(site)}')
    else:
        info('未找到假網站 HTML（--site 指定，或尚未建）')
    if not any('keystone' in w for w in warns):
        ok('早階段 clue HTML + 假網站 無 keystone（或已人工確認）')

    # ── 3. 素材↔JSON 對映 ──
    head('3. 素材↔JSON 對映')
    def find_asset(fn):
        return any(os.path.isfile(os.path.join(a, fn)) for a in assets)
    refs, missing, todo = [], [], []
    for s in stages:
        for fn in [s.get('poster'), s.get('message')] + (s.get('docs') or []):
            if not fn: continue
            refs.append(fn)
            if not find_asset(fn):
                (todo if NOTEBOOK_RE.search(fn) else missing).append((s.get('stage'), fn))
    for st, fn in missing: err(f'stage {st} 缺圖: {fn}（不在 {"/".join(assets)}）')
    for st, fn in todo: info(f'stage {st} 缺 {fn} — 已知 notebook TODO，panel 會優雅略過')
    # audio
    for s in stages:
        for au in (s.get('audio') or []):
            if not find_asset(au): info(f'stage {s.get("stage")} 缺語音 {au} — 待錄，優雅略過')
    if not missing: ok(f'{len(set(refs))} 個圖 ref，非-notebook 全部到位')

    # ── 4. core.any 短詞警示 ──
    head('4. core.any 偏泛短詞（includes 誤判風險）')
    shorts = []
    for c in sol.get('core', []):
        for t in c.get('any', []):
            if len(t) <= 2 and not re.search(r'[A-Za-z0-9]', t):
                shorts.append((c.get('id'), t))
    if shorts:
        warn(f'≤2字短詞 {len(shorts)} 個易被無關/負向輸入撞到: ' +
             ', '.join(f'{i}:{t}' for i, t in shorts))
    else:
        ok('無 ≤2字 純中文短詞')

    # ── 5. win-gate 提示 ──
    head('5. win-gate 推演（人工確認）')
    ids = [c.get('id') for c in sol.get('core', [])]
    info(f'core = {ids}；win=三者全中(evaluateAnswer)。請確認 method/motive keystone 素材只在 S4，')
    info('即「只用 S1+S2 湊不齊 core」。（此項半自動，最終靠 §5 人工推演＋交 Codex）')

    # ── 總結 ──
    print(f'\n{"="*48}')
    if errors:
        print(f'{RED}✗ 阻斷 {len(errors)} 項{RST}、{YEL}⚠ 待確認 {len(warns)} 項{RST} — 修掉 ✗ 才可交 Codex/開案')
        sys.exit(1)
    elif warns:
        print(f'{GRN}✓ 無阻斷{RST}、{YEL}⚠ {len(warns)} 項待人工確認{RST}（多為 keystone 需確認在 S4/appear:4）')
    else:
        print(f'{GRN}✓ 全數通過，無阻斷、無待確認{RST}')

if __name__ == '__main__':
    main()
