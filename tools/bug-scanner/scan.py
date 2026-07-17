#!/usr/bin/env python3
"""
SML bug-scanner — 掃描「bug回報區」頻道，把 tenten(甜甜)回報的問題交給 headless claude
判定並整理，把報告貼回頻道。每天 04:00(台灣)由 systemd timer 觸發，或手動執行。

安全鐵律:
  - claude 一律在「隔離的 git worktree」(從乾淨 HEAD 拉出)裡跑,碰不到主工作樹的未提交 WIP。
  - 永不 push、永不部署。AUTO_FIX 開啟時只在 bug-scan/<date> 分支上 commit,等人複核。
  - kill switch: BUG_SCANNER_ENABLED=0 直接空轉退出。
  - DRY_RUN: 抓訊息+叫 claude 但不貼 Discord、不保留分支(印到 stdout)。

環境變數(皆有預設):
  BUG_SCANNER_ENABLED   1 啟用 / 0 停用(kill switch)          預設 1
  BUG_SCANNER_DRY_RUN   非空且非0 → 不貼 Discord、不保留分支    預設 關
  BUG_AUTO_FIX          非空且非0 → 明確 bug 就在分支上 commit  預設 關(只診斷+附 patch)
  BUG_CHANNEL_ID        來源頻道                                預設 1527659065281609828
  BUG_GUILD_ID          頻道所在伺服器(查身分組用)             預設 698760345660948530
  BUG_REQUIRED_ROLE     作者須持有此身分組才算數                預設 872861844388335617 (天王里里民)
  BUG_POST_CHANNEL      報告貼哪                                預設 = 來源頻道
  BUG_REPO_DIR          repo 路徑                               預設 /opt/sml/repo
  BUG_STATE_PATH        游標狀態檔                              預設 ~/.claude/bug-scanner/state.json
  BUG_MAX_REPORTS       單次最多處理幾則(煞車)                預設 20
  CLAUDE_BIN            claude 執行檔                            預設 claude
"""
import os
import sys
import json
import time
import shutil
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

CHANNEL_ID   = os.environ.get("BUG_CHANNEL_ID", "1527659065281609828")
GUILD_ID     = os.environ.get("BUG_GUILD_ID", "698760345660948530")
# 判定資格:作者(非 bot)必須持有這個身分組才算有效回報。天王里里民 = 872861844388335617。
REQUIRED_ROLE = os.environ.get("BUG_REQUIRED_ROLE", "872861844388335617")
POST_CHANNEL = os.environ.get("BUG_POST_CHANNEL", CHANNEL_ID)
REPO_DIR     = os.environ.get("BUG_REPO_DIR", "/opt/sml/repo")
STATE_PATH   = os.environ.get("BUG_STATE_PATH", os.path.expanduser("~/.claude/bug-scanner/state.json"))
CLAUDE_BIN   = os.environ.get("CLAUDE_BIN", "claude")
MAX_REPORTS  = int(os.environ.get("BUG_MAX_REPORTS", "20"))
SSM_TOKEN_PARAM = os.environ.get("BUG_TOKEN_PARAM", "/sml/discord-bot/token")

def truthy(v: str) -> bool:
    return str(v).strip().lower() not in ("", "0", "false", "no", "off")

ENABLED  = truthy(os.environ.get("BUG_SCANNER_ENABLED", "1"))
DRY_RUN  = truthy(os.environ.get("BUG_SCANNER_DRY_RUN", ""))
AUTO_FIX = truthy(os.environ.get("BUG_AUTO_FIX", ""))

API = "https://discord.com/api/v10"
_token_cache = None

def log(*a):
    print(f"[{datetime.now(timezone.utc).isoformat()}]", *a, flush=True)

def bot_token() -> str:
    global _token_cache
    if _token_cache:
        return _token_cache
    out = subprocess.run(
        ["aws", "ssm", "get-parameter", "--name", SSM_TOKEN_PARAM,
         "--with-decryption", "--query", "Parameter.Value", "--output", "text"],
        capture_output=True, text=True, check=True).stdout.strip()
    if not out:
        raise RuntimeError("empty bot token from SSM")
    _token_cache = out
    return out

def discord(method: str, path: str, body=None, retries=3, soft_404=False):
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(API + path, data=data, method=method)
        req.add_header("Authorization", "Bot " + bot_token())
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "sml-bug-scanner/1.0")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code == 404 and soft_404:
                return None
            if e.code == 429:
                retry_after = 1.0
                try:
                    retry_after = float(json.loads(e.read()).get("retry_after", 1.0))
                except Exception:
                    pass
                log(f"429 rate limited, sleep {retry_after}s")
                time.sleep(retry_after + 0.5)
                continue
            body_txt = e.read().decode(errors="replace")
            raise RuntimeError(f"discord {method} {path} -> {e.code}: {body_txt}")
        except urllib.error.URLError as e:
            if attempt == retries:
                raise
            log(f"net error {e}, retry {attempt}")
            time.sleep(2 * attempt)
    raise RuntimeError("discord: retries exhausted")

def load_state() -> dict:
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        log(f"state read error {e}, treating as empty")
        return {}

def save_state(st: dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATE_PATH)

def fetch_messages_after(after_id: str) -> list:
    """回傳 after_id 之後的所有訊息,依時間由舊到新排序。"""
    collected = []
    cursor = after_id
    while True:
        path = f"/channels/{CHANNEL_ID}/messages?limit=100&after={cursor}"
        batch = discord("GET", path)
        if not batch:
            break
        # Discord 以「新→舊」回傳,轉成「舊→新」
        batch = list(reversed(batch))
        collected.extend(batch)
        cursor = batch[-1]["id"]  # 最新的 id
        if len(batch) < 100:
            break
    return collected

def latest_message_id() -> str:
    batch = discord("GET", f"/channels/{CHANNEL_ID}/messages?limit=1")
    return batch[0]["id"] if batch else "0"

def is_reportish(content: str) -> bool:
    return len(content.strip()) >= 4  # 太短的招呼語略過;圖片另計

_member_roles_cache = {}

def member_has_role(user_id: str) -> bool:
    """查該使用者在伺服器是否持有 REQUIRED_ROLE(有快取;不在群/查無 → False)。"""
    if user_id in _member_roles_cache:
        roles = _member_roles_cache[user_id]
    else:
        m = discord("GET", f"/guilds/{GUILD_ID}/members/{user_id}", soft_404=True)
        roles = set(m.get("roles", [])) if m else set()
        _member_roles_cache[user_id] = roles
    return REQUIRED_ROLE in roles

def collect_reports(messages: list):
    reports = []
    for m in messages:
        author = m["author"]
        if author.get("bot"):
            continue
        content = (m.get("content") or "").strip()
        atts = [a.get("url") for a in m.get("attachments", []) if a.get("url")]
        if not is_reportish(content) and not atts:
            continue
        if not member_has_role(author["id"]):
            continue
        reports.append({
            "id": m["id"], "ts": m.get("timestamp", ""),
            "author": author.get("global_name") or author.get("username") or author["id"],
            "content": content, "attachments": atts,
        })
    return reports

# ---------- 隔離 worktree ----------

def git(args, cwd=REPO_DIR, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)

def make_worktree(branch: str):
    """從乾淨 HEAD 拉一個隔離 worktree,碰不到主工作樹 WIP。回傳 (path, branch)。"""
    wt = f"/tmp/bug-scan-{int(time.time())}"
    if AUTO_FIX and not DRY_RUN:
        git(["worktree", "add", "-b", branch, wt, "HEAD"])
    else:
        # 診斷/乾跑:detached,不建分支
        git(["worktree", "add", "--detach", wt, "HEAD"])
    return wt

def remove_worktree(wt: str, keep_branch: bool):
    try:
        git(["worktree", "remove", "--force", wt], check=False)
    except Exception as e:
        log(f"worktree remove error {e}")
    if not keep_branch:
        shutil.rmtree(wt, ignore_errors=True)

def branch_has_commits(branch: str) -> bool:
    r = git(["rev-list", "--count", f"HEAD..{branch}"], check=False)
    try:
        return int(r.stdout.strip()) > 0
    except ValueError:
        return False

# ---------- claude ----------

def build_prompt(reports: list, branch: str) -> str:
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    lines = []
    for i, r in enumerate(reports, 1):
        lines.append(f"── 回報 #{i} (回報人 {r.get('author','?')}, 訊息id {r['id']}, {r['ts']}) ──")
        lines.append(r["content"] or "(無文字)")
        for u in r["attachments"]:
            lines.append(f"[附件] {u}")
        lines.append("")
    reports_block = "\n".join(lines)

    if AUTO_FIX:
        fix_rule = (
            f"1. 【明確 bug / 不該出現的錯誤】找出根因,並「直接在這個 worktree 修好、git add 你改的檔案、git commit」"
            f"(現在的分支就是 {branch})。絕對不要 push、不要跑任何 deploy 腳本。commit 訊息用中文說明修了什麼。"
        )
    else:
        fix_rule = (
            "1. 【明確 bug / 不該出現的錯誤】找出根因,說明修法(哪個 repo/檔案/行),"
            "並在報告裡附上精簡的修補 patch 或 diff 片段。**不要實際改動檔案**(這是診斷模式)。"
        )

    return f"""你是 SML 專案的資深除錯工程師。工作目錄是這個「隔離的乾淨 worktree」(= 主 repo 的 HEAD,沒有任何未提交 WIP)。你可以自由讀程式碼、grep、查 git log。

以下是「bug回報區」頻道收到、由「天王里里民」身分組成員回報的問題。請逐則判定並分類:

{fix_rule}
2. 【不是 bug、需要決策/設計取捨】不要改 code。整理成清單:問題是什麼、有哪些選項、你的建議。
3. 【資訊不足無法判定】列出你需要向對方追問的具體問題。

判定原則:寧可保守。只有你有把握是真 bug 才歸類 (1);模稜兩可一律歸 (2) 或 (3)。附件是圖片時你看不到內容,請在報告裡標「需人工看圖」。

最後只輸出一份【給 Discord 看的繁體中文 markdown 報告】,精簡可掃讀,固定用這三段(沒有內容的段落就寫「(無)」):

**🐛 Bug 掃描報告 · {today}**

**✅ 已處理 / 修法**
（逐項:回報摘要 → 根因 → {"已 commit 的檔案+commit 摘要" if AUTO_FIX else "建議修法+patch"}）

**🤔 需要決策**
（逐項:問題 → 選項 → 建議）

**❓ 需補充資訊**
（逐項:要追問什麼）

不要輸出報告以外的任何前言或結語。

===== 回報清單({len(reports)} 則) =====
{reports_block}"""

def run_claude(prompt: str, cwd: str) -> str:
    args = [CLAUDE_BIN, "--output-format", "json", "--permission-mode", "bypassPermissions", "-p", "--", prompt]
    log(f"invoking claude in {cwd} (auto_fix={AUTO_FIX})")
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=1500)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exit {proc.returncode}: {proc.stderr[:2000]}")
    try:
        obj = json.loads(proc.stdout)
        return (obj.get("result") or "").strip()
    except json.JSONDecodeError:
        return proc.stdout.strip()

# ---------- Discord post ----------

def chunk(text: str, limit=1900):
    out, buf = [], ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > limit:
            if buf:
                out.append(buf)
            # 單行超長硬切
            while len(line) > limit:
                out.append(line[:limit]); line = line[limit:]
            buf = line
        else:
            buf = line if not buf else buf + "\n" + line
    if buf:
        out.append(buf)
    return out or ["(空報告)"]

def post_report(text: str):
    for part in chunk(text):
        discord("POST", f"/channels/{POST_CHANNEL}/messages", {"content": part})
        time.sleep(0.4)

# ---------- main ----------

def main():
    if not ENABLED:
        log("BUG_SCANNER_ENABLED=0 → 空轉退出(kill switch)")
        return 0
    log(f"start dry_run={DRY_RUN} auto_fix={AUTO_FIX} channel={CHANNEL_ID} required_role={REQUIRED_ROLE}")

    st = load_state()
    last_id = st.get("last_message_id")

    if not last_id:
        # 首次執行:設基準為最新訊息,不回溯歷史
        base = latest_message_id()
        st["last_message_id"] = base
        st["initialized_at"] = datetime.now(timezone.utc).isoformat()
        if not DRY_RUN:
            save_state(st)
        log(f"首次執行,設基準游標={base},本次不處理歷史。")
        return 0

    messages = fetch_messages_after(last_id)
    new_cursor = messages[-1]["id"] if messages else last_id
    reports = collect_reports(messages)
    log(f"新訊息 {len(messages)} 則,其中回報 {len(reports)} 則。")

    if not reports:
        st["last_message_id"] = new_cursor
        st["last_scan_at"] = datetime.now(timezone.utc).isoformat()
        if not DRY_RUN:
            save_state(st)
        log("無新 bug 回報,更新游標後結束。")
        return 0

    if len(reports) > MAX_REPORTS:
        log(f"回報數 {len(reports)} 超過上限 {MAX_REPORTS},本次只處理最舊的 {MAX_REPORTS} 則。")
        reports = reports[:MAX_REPORTS]
        # 游標只推進到最後處理的那則,剩下的下次再掃
        new_cursor = reports[-1]["id"]

    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")
    branch = f"bug-scan/{today}"
    wt = make_worktree(branch)
    keep_branch = False
    try:
        prompt = build_prompt(reports, branch)
        report = run_claude(prompt, wt)
        if AUTO_FIX and not DRY_RUN:
            keep_branch = branch_has_commits(branch)
            if keep_branch:
                report += f"\n\n———\n🌿 已 commit 到分支 `{branch}`(未 push、未部署),請複核後走正常部署流程。"
        if DRY_RUN:
            print("\n========= DRY RUN 報告(不貼 Discord)=========\n")
            print(report)
            print("\n============================================\n")
        else:
            post_report(report)
            st["last_message_id"] = new_cursor
            st["last_scan_at"] = datetime.now(timezone.utc).isoformat()
            save_state(st)
            log(f"報告已貼回頻道 {POST_CHANNEL},游標推進到 {new_cursor}。")
    finally:
        remove_worktree(wt, keep_branch)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"FATAL: {e}")
        sys.exit(1)
