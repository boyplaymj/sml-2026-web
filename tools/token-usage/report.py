#!/usr/bin/env python3
"""
Token 用量分析：把本機 claude session 的逐則 usage 依「頻道/功能」聚合。

資料來源：
  ~/.claude/projects/**/*.jsonl        每則回覆的 token 明細(含 sessionId / entrypoint)
  ~/.claude/bridge-sessions.json       頻道ID -> 現役 sessionId

分桶邏輯：
  entrypoint=sdk-cli  -> bridge(Discord 各頻道)
  entrypoint=cli      -> 本機互動開發
  sessionId 在 bridge-sessions.json -> 對到現役頻道名(呼叫 Discord API 換名)
  其餘 -> 「開新對話」前的舊 session，頻道無法回貼，僅依所屬 repo 粗分

計費採 Opus 4.8 牌價「加權」，只用來看比例(實付為 Max 訂閱吃到飽)。

用法：  python3 report.py            # 印報表
       python3 report.py --no-names # 跳過 Discord 改名(離線)
"""
import json, os, glob, sys, collections, urllib.request, urllib.error, subprocess

HOME = os.path.expanduser("~")
PRICE = {"in": 15.0, "out": 75.0, "c_write": 18.75, "c_read": 1.5}  # USD / Mtok, Opus 4.8
NAMES_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "channel_names.json")

# 單一頻道專屬的 workdir(來自 CHANNEL_WORKDIRS)：該 repo 底下所有舊 session 都可
# 確定歸給這個頻道。project 目錄名是 workdir 路徑把 / 換成 - 。
REPO_EXCLUSIVE = {
    "-opt-sml-score-repo": "1519443528831336629",  # 🀄sml分數系統後台
}


def resolve_channel_names(channel_ids):
    """呼叫 Discord API 把頻道ID換成名稱；失敗則退回快取檔。"""
    names = {}
    try:
        names = json.load(open(NAMES_CACHE))
    except Exception:
        pass
    try:
        tok = subprocess.check_output(
            ["aws", "ssm", "get-parameter", "--name", "/sml/discord-bot/token",
             "--with-decryption", "--region", "ap-southeast-1",
             "--query", "Parameter.Value", "--output", "text"],
            text=True).strip()
        hdr = {"Authorization": f"Bot {tok}",
               "User-Agent": "DiscordBot (https://boyplaymj.com, 1.0)"}
        for cid in channel_ids:
            try:
                req = urllib.request.Request(
                    f"https://discord.com/api/v10/channels/{cid}", headers=hdr)
                d = json.loads(urllib.request.urlopen(req, timeout=10).read())
                names[cid] = d.get("name", cid)
            except Exception:
                names.setdefault(cid, cid)
        json.dump(names, open(NAMES_CACHE, "w"), ensure_ascii=False, indent=0)
    except Exception as e:
        print(f"[warn] 取頻道名失敗，改用快取/ID：{e}", file=sys.stderr)
    return names


def collect():
    """回傳 {sessionId: {counter, project, entrypoint}}。"""
    sess = collections.defaultdict(
        lambda: {"c": collections.Counter(), "proj": "?", "ep": "?"})
    for path in glob.glob(os.path.join(HOME, ".claude/projects/*/*.jsonl")):
        proj = os.path.basename(os.path.dirname(path))
        try:
            with open(path) as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    u = d.get("message", {}).get("usage")
                    if not u:
                        continue
                    sid = d.get("sessionId", "?")
                    s = sess[sid]
                    s["proj"] = proj
                    if d.get("entrypoint"):
                        s["ep"] = d["entrypoint"]
                    c = s["c"]
                    c["in"] += u.get("input_tokens", 0)
                    c["out"] += u.get("output_tokens", 0)
                    c["c_write"] += u.get("cache_creation_input_tokens", 0)
                    c["c_read"] += u.get("cache_read_input_tokens", 0)
        except Exception:
            pass
    return sess


def cost(c):
    return sum(c[k] / 1e6 * PRICE[k] for k in PRICE)


def main():
    use_names = "--no-names" not in sys.argv
    sess = collect()
    try:
        chmap = json.load(open(os.path.join(HOME, ".claude/bridge-sessions.json")))
    except Exception:
        chmap = {}
    sid2ch = {v: k for k, v in chmap.items()}
    names = resolve_channel_names(list(chmap.keys())) if use_names else {}

    grand = sum(cost(s["c"]) for s in sess.values())

    # A) 頻道(功能別) cost 聚合：現役 session 直接對應；舊 session 若落在單一頻道
    #    專屬 repo 也折進該頻道，其餘才進「未對應」桶。
    perch = collections.defaultdict(lambda: collections.Counter())  # channelID -> counter
    unattrib = collections.defaultdict(lambda: collections.Counter())  # proj -> counter
    bucket = collections.Counter()  # entrypoint -> cost
    for sid, s in sess.items():
        bucket[s["ep"]] += cost(s["c"])
        ch = sid2ch.get(sid) or REPO_EXCLUSIVE.get(s["proj"])
        target = perch[ch] if ch else unattrib[s["proj"]]
        for k in ("in", "out", "c_write", "c_read"):
            target[k] += s["c"][k]
    named = [(names.get(ch, ch), ch, cost(c), c) for ch, c in perch.items()]

    print(f"\n總估算(牌價加權)成本：約 ${grand:,.0f} USD ｜ {len(sess)} 個 session")
    print("（僅供比例參考，實付為 Max 訂閱吃到飽）\n")

    print("【桶總覽】")
    ep_name = {"sdk-cli": "Discord bridge", "cli": "本機互動開發", "?": "未知"}
    for ep, ct in bucket.most_common():
        print(f"  {ct/grand*100:5.1f}%  ${ct:>8,.0f}  {ep_name.get(ep, ep)}")

    print("\n【現役頻道(功能別) — 精確對應】")
    named.sort(key=lambda r: -r[2])
    sub = sum(r[2] for r in named)
    print(f"  小計 ${sub:,.0f}（占全部 {sub/grand*100:.0f}%；其餘為開新對話前的舊 session）")
    print(f"  {'佔比':>6} {'成本':>9}   頻道/功能")
    for nm, ch, ct, c in named:
        print(f"  {ct/grand*100:5.1f}% ${ct:>8,.0f}   {nm}")

    print("\n【未對應舊 session — 依 repo 粗分】")
    print("  (開新對話前的歷史脈絡，頻道ID未存進 transcript 無法回貼)")
    rows = sorted(unattrib.items(), key=lambda kv: -cost(kv[1]))
    for proj, c in rows:
        ct = cost(c)
        print(f"  {ct/grand*100:5.1f}% ${ct:>8,.0f}   {proj}")
    print()


if __name__ == "__main__":
    main()
