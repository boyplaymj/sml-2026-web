#!/usr/bin/env python3
"""
Codex(OpenAI)側 token 用量統計 —— 對應 report.py(Claude 側)。

為什麼要單獨一份:report.py 只讀 ~/.claude,看不到 Codex 的用量。
bot↔bot 轉傳給 Codex 那半邊燒的是 OpenAI 額度,得從 Codex 自己的 rollout 記錄看。

資料源:
  ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl   每次 codex exec 的逐事件記錄
    - 第一行 type=session_meta:session_id / parent_thread_id
    - event_msg type=token_count:info.total_token_usage(該 rollout 累計)
      + rate_limits(primary=5h 視窗、secondary=週視窗 的 used_percent)
頻道歸屬:~/.claude/codex-bridge-sessions.json(channelID -> thread_id)反查。

用法:
  python3 report_codex.py [起始日 YYYY-MM-DD]   # 省略=全部
"""
import json, os, glob, sys, collections

HOME = os.path.expanduser("~")
SESS_GLOB = os.path.join(HOME, ".codex", "sessions", "*", "*", "*", "*.jsonl")
CHAN_MAP_FILE = os.path.join(HOME, ".claude", "codex-bridge-sessions.json")
NAMES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "channel_names.json")

FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def fmt(c):
    return (f"in={c['input_tokens']:,}(cached {c['cached_input_tokens']:,}) "
            f"out={c['output_tokens']:,} total={c['total_tokens']:,}")


def main():
    since = sys.argv[1] if len(sys.argv) > 1 else None
    chan_map = load_json(CHAN_MAP_FILE, {})          # channelID -> thread_id
    thread_to_chan = {v: k for k, v in chan_map.items()}
    names = load_json(NAMES_FILE, {})                 # channelID -> name

    per_chan = collections.defaultdict(collections.Counter)
    per_day = collections.defaultdict(collections.Counter)
    totals = collections.Counter()
    latest_rl, latest_rl_ts = None, ""
    nfiles = 0

    for path in sorted(glob.glob(SESS_GLOB)):
        parts = path.split(os.sep)
        day = f"{parts[-4]}-{parts[-3]}-{parts[-2]}" if len(parts) >= 4 else ""
        if since and day and day < since:
            continue

        sid = parent = None
        last_total = None
        rl, rl_ts = None, ""
        try:
            with open(path) as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    t = d.get("type")
                    if t == "session_meta":
                        p = d.get("payload", {})
                        sid = p.get("session_id")
                        parent = p.get("parent_thread_id")
                    elif t == "event_msg":
                        p = d.get("payload", {})
                        if p.get("type") == "token_count":
                            info = p.get("info") or {}
                            if info.get("total_token_usage"):
                                last_total = info["total_token_usage"]
                            if p.get("rate_limits"):
                                rl, rl_ts = p["rate_limits"], d.get("timestamp", "")
        except Exception:
            continue
        nfiles += 1

        chan = thread_to_chan.get(sid) or thread_to_chan.get(parent) or "(未分類/subagent)"
        if last_total:
            for k in FIELDS:
                v = last_total.get(k, 0) or 0
                per_chan[chan][k] += v
                per_day[day][k] += v
                totals[k] += v
        if rl and rl_ts > latest_rl_ts:
            latest_rl, latest_rl_ts = rl, rl_ts

    scope = f"(自 {since})" if since else "(全部)"
    print(f"=== Codex(OpenAI)Token 用量 {scope} ===")
    print(f"掃描 {nfiles} 個 rollout;總計 {fmt(totals)}")
    print("\n— 各頻道 —")
    for chan, c in sorted(per_chan.items(), key=lambda x: -x[1]['total_tokens']):
        print(f"  {names.get(chan, chan)}: {fmt(c)}")
    print("\n— 各日 —")
    for day in sorted(per_day):
        print(f"  {day}: {fmt(per_day[day])}")
    if latest_rl:
        p = latest_rl.get("primary") or {}
        s = latest_rl.get("secondary") or {}
        print(f"\n— 最新 rate limit(Codex 帳號,{latest_rl_ts}）—")
        if p:
            print(f"  5h 視窗:{p.get('used_percent')}% 用掉")
        if s:
            print(f"  週視窗:{s.get('used_percent')}% 用掉")
    print("\n注:cached_input 較便宜;精確成本需依 Codex 模型單價加權。Claude 側請看 report.py。")


if __name__ == "__main__":
    main()
