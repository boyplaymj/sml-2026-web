#!/usr/bin/env python3
"""背景工作帳本寫入器 —— 桌面掛件任務面板的資料源。

Claude / Codex 在開始一件背景大工作時往帳本寫一筆 running,跑進度時更新,
完成時寫 done/failed。採集器(collector.py)每 60 秒唯讀轉發這份帳本到雲端,
掛件據以畫「工作中卡片 + 進度條」,完成時彈桌面通知。

帳本 = 一個 JSON 陣列,每筆:
  {id, title, channel?, state: running|done|failed, started, updated,
   progress?: {cur, total, note}}

所有寫入都經 flock 獨佔鎖 + 原子替換,支援 Claude/Codex 併發寫同一份檔。
完成超過 DONE_TTL 的項目在每次寫入時就地清掉,檔案不會無限長大。

用法:
  taskline.py start  <id> --title "生成 25 張 GIF" [--channel 頻道名] [--total 25]
  taskline.py progress <id> [--cur 12] [--total 25] [--note "第12張"]
  taskline.py done   <id> [--note "已上傳"]
  taskline.py fail   <id> [--note "逾時"]
  taskline.py drop   <id>          # 直接移除某筆
  taskline.py list                 # 印出目前帳本(除錯)

成本:$0(純本機檔案操作,無 LLM、無 API、無新表)。
"""
import argparse
import fcntl
import json
import os
import tempfile
import time

LEDGER_PATH = os.environ.get("CLAUDE_TASKS_LEDGER", "/mnt/sml-brain/_runtime/claude-tasks.json")
LOCK_PATH = LEDGER_PATH + ".lock"
DONE_TTL_SEC = int(os.environ.get("CLAUDE_TASKS_DONE_TTL", "600"))  # 完成保留 10 分鐘


def _load(path):
    try:
        with open(path) as f:
            arr = json.load(f)
        return arr if isinstance(arr, list) else []
    except Exception:
        return []


def _atomic_write(path, arr):
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(arr, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _prune(arr, now):
    """移除完成太久的項目,避免帳本無限長大。"""
    out = []
    for t in arr:
        if not isinstance(t, dict):
            continue
        if t.get("state") in ("done", "failed"):
            updated = int(t.get("updated") or t.get("started") or 0)
            if updated and now - updated > DONE_TTL_SEC:
                continue
        out.append(t)
    return out


def mutate(fn):
    """在 flock 獨佔鎖下對帳本做 read-modify-write(併發安全)。"""
    os.makedirs(os.path.dirname(os.path.abspath(LOCK_PATH)) or ".", exist_ok=True)
    with open(LOCK_PATH, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            now = int(time.time())
            arr = _prune(_load(LEDGER_PATH), now)
            fn(arr, now)
            _atomic_write(LEDGER_PATH, arr)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _find(arr, tid):
    for t in arr:
        if isinstance(t, dict) and t.get("id") == tid:
            return t
    return None


def cmd_start(args):
    def fn(arr, now):
        t = _find(arr, args.id)
        if t is None:
            t = {"id": args.id}
            arr.append(t)
        t.update({"title": args.title or t.get("title") or args.id,
                  "state": "running", "started": t.get("started") or now, "updated": now})
        if args.channel:
            t["channel"] = args.channel
        if args.total is not None:
            t["progress"] = {"cur": 0, "total": args.total, "note": ""}
    mutate(fn)


def cmd_progress(args):
    def fn(arr, now):
        t = _find(arr, args.id)
        if t is None:  # 沒 start 過就 progress → 當作補建 running
            t = {"id": args.id, "title": args.id, "state": "running", "started": now}
            arr.append(t)
        t["state"] = "running"
        t["updated"] = now
        p = t.get("progress") or {}
        if args.cur is not None:
            p["cur"] = args.cur
        if args.total is not None:
            p["total"] = args.total
        if args.note is not None:
            p["note"] = args.note
        if p:
            t["progress"] = p
    mutate(fn)


def _finish(args, state):
    def fn(arr, now):
        t = _find(arr, args.id)
        if t is None:
            t = {"id": args.id, "title": args.id, "started": now}
            arr.append(t)
        t["state"] = state
        t["updated"] = now
        if args.note is not None:
            p = t.get("progress") or {}
            p["note"] = args.note
            t["progress"] = p
    mutate(fn)


def cmd_drop(args):
    def fn(arr, now):
        arr[:] = [t for t in arr if not (isinstance(t, dict) and t.get("id") == args.id)]
    mutate(fn)


def cmd_list(_args):
    print(json.dumps(_load(LEDGER_PATH), ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description="背景工作帳本寫入器")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("start"); p.add_argument("id"); p.add_argument("--title")
    p.add_argument("--channel"); p.add_argument("--total", type=int); p.set_defaults(func=cmd_start)

    p = sub.add_parser("progress"); p.add_argument("id"); p.add_argument("--cur", type=int)
    p.add_argument("--total", type=int); p.add_argument("--note"); p.set_defaults(func=cmd_progress)

    p = sub.add_parser("done"); p.add_argument("id"); p.add_argument("--note")
    p.set_defaults(func=lambda a: _finish(a, "done"))

    p = sub.add_parser("fail"); p.add_argument("id"); p.add_argument("--note")
    p.set_defaults(func=lambda a: _finish(a, "failed"))

    p = sub.add_parser("drop"); p.add_argument("id"); p.set_defaults(func=cmd_drop)
    p = sub.add_parser("list"); p.set_defaults(func=cmd_list)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
