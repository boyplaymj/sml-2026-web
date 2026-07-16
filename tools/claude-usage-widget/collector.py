#!/usr/bin/env python3
"""Claude 用量採集器 —— 桌面液體槽小工具的資料源。

每次執行:幫 main + backup1 各查一次 /api/oauth/usage,產出一份精簡 usage.json
(只含百分比與重置時間,不含任何 token/密鑰),供桌面 HTML 小工具讀取。

設計要點:
- 查用量是純 GET,不燒 LLM token、不影響計費(與 bridge !用量 同源)。
- token 過期會自動用 refreshToken 刷新(端點/參數沿用 aws/discord-bridge)。
  * main   憑證在 ~/.claude/.credentials.json,刷新後原子寫回檔案。
  * backup1 憑證在 SSM,刷新後寫回 SSM(自癒:下次切回不會拿到過期值)。
- 任一帳號查失敗只讓該帳號 ok=false,不影響另一個。

用法:
  collector.py                 # 印出 usage.json 到 stdout
  collector.py --out FILE      # 寫到檔案(原子)
  collector.py --out FILE --s3 s3://bucket/path/usage.json  # 並上傳 S3

成本:$0(無 LLM、無新表;S3 PUT 每分鐘一次可忽略)。詳見 tools/COST_CONTROL.md。
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

OAUTH_BASE = os.environ.get("CLAUDE_OAUTH_BASE_URL", "https://console.anthropic.com").rstrip("/")
OAUTH_CLIENT_ID = os.environ.get("CLAUDE_OAUTH_CLIENT_ID", "9d1c250a-e61b-44d9-88ed-5944d1962f5e")
OAUTH_BETA = "oauth-2025-04-20"
# 必帶非預設 UA,否則 Cloudflare 會擋(error 1010)。沿用 bridge 的值。
UA = "anthropic-sdk-typescript/0.60.0 userOAuthProvider"
EXPIRY_SKEW_SEC = 120  # 距到期不足此秒數就當「該刷新」
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
MAIN_CRED_PATH = os.path.expanduser("~/.claude/.credentials.json")
BACKUP1_SSM = "/sml/claude/accounts/backup1/credentials-json"


def _http(url, method="GET", headers=None, data=None, timeout=15):
    req = urllib.request.Request(url, method=method, data=data)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def oauth_refresh(refresh_token):
    """用 refreshToken 換新。回傳 (access, new_refresh, expires_in) 或拋例外。"""
    body = json.dumps({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": OAUTH_CLIENT_ID,
    }).encode()
    try:
        status, raw = _http(
            OAUTH_BASE + "/v1/oauth/token", method="POST", data=body,
            headers={
                "Content-Type": "application/json",
                "anthropic-beta": OAUTH_BETA,
                "User-Agent": UA,
                "Accept": "application/json",
            },
        )
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        if "invalid_grant" in detail or "invalid_client" in detail:
            raise RuntimeError("需重新登入")  # 憑證確定失效
        raise RuntimeError("刷新失敗 HTTP %d" % e.code)
    tok = json.loads(raw)
    access = tok.get("access_token", "").strip()
    if not access:
        raise RuntimeError("刷新回應缺少 access_token")
    return access, tok.get("refresh_token", "").strip(), int(tok.get("expires_in", 0))


def ensure_fresh(cred_json):
    """確保 accessToken 新鮮。回傳 (access_token, merged_json_or_None)。
    merged_json 非 None 代表有刷新過、呼叫端應寫回持久層。"""
    oauth = cred_json.get("claudeAiOauth", {})
    access = oauth.get("accessToken", "")
    exp_ms = oauth.get("expiresAt", 0)
    now_ms = time.time() * 1000
    if exp_ms and exp_ms > now_ms + EXPIRY_SKEW_SEC * 1000:
        return access, None  # 仍有效,免刷新
    rt = oauth.get("refreshToken", "").strip()
    if not rt:
        return access, None  # 沒得刷,拿舊的試(可能 401)
    new_access, new_rt, expires_in = oauth_refresh(rt)
    oauth["accessToken"] = new_access
    if new_rt:
        oauth["refreshToken"] = new_rt
    if expires_in > 0:
        oauth["expiresAt"] = int(now_ms + expires_in * 1000)
    cred_json["claudeAiOauth"] = oauth
    return new_access, cred_json


def parse_usage(raw):
    """把 /api/oauth/usage 回應攤平成 {session, weekly, fable}。
    每項 = {pct, resets_at}。查得到 200 但該窗無資料 → pct=0(閒置帳號=空槽)。"""
    d = json.loads(raw)
    out = {
        "session": {"pct": 0.0, "resets_at": 0},
        "weekly": {"pct": 0.0, "resets_at": 0},
        "fable": {"pct": 0.0, "resets_at": 0},
    }

    def iso_to_unix(s):
        if not s:
            return 0
        try:
            import datetime
            return int(datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
        except Exception:
            return 0

    # 新格式:limits 陣列(最準,含 severity/scope)
    for lim in d.get("limits") or []:
        kind = lim.get("kind")
        pct = float(lim.get("percent", 0) or 0)
        reset = iso_to_unix(lim.get("resets_at"))
        if kind == "session":
            out["session"] = {"pct": pct, "resets_at": reset, "severity": lim.get("severity")}
        elif kind == "weekly_all":
            out["weekly"] = {"pct": pct, "resets_at": reset, "severity": lim.get("severity")}
        elif kind == "weekly_scoped":
            scope = (lim.get("scope") or {}).get("model") or {}
            if (scope.get("display_name") or "").lower() == "fable":
                out["fable"] = {"pct": pct, "resets_at": reset, "severity": lim.get("severity")}

    # 舊格式回退:頂層 five_hour / seven_day / seven_day_opus(fable)
    def legacy(key):
        obj = d.get(key)
        if not obj:
            return None
        u = obj.get("utilization")
        if u is None:
            u = obj.get("used_percentage")
        if u is None:
            return None
        return {"pct": float(u), "resets_at": iso_to_unix(obj.get("resets_at"))}

    if out["session"]["pct"] == 0 and out["session"]["resets_at"] == 0:
        lg = legacy("five_hour")
        if lg:
            out["session"] = lg
    if out["weekly"]["pct"] == 0 and out["weekly"]["resets_at"] == 0:
        lg = legacy("seven_day")
        if lg:
            out["weekly"] = lg
    if out["fable"]["pct"] == 0 and out["fable"]["resets_at"] == 0:
        lg = legacy("seven_day_fable") or legacy("seven_day_opus")
        if lg:
            out["fable"] = lg
    return out


def fetch_usage(access_token):
    status, raw = _http(USAGE_URL, headers={
        "Authorization": "Bearer " + access_token,
        "anthropic-beta": OAUTH_BETA,
    })
    return parse_usage(raw)


def account_main():
    # main 是「目前實際在跑」的活躍帳號,其憑證檔由 bridge/claude session 自己維護、
    # 幾乎永遠新鮮。採集器對此檔採「唯讀」:絕不刷新、絕不寫回,徹底杜絕污染活躍帳號的風險
    # (曾發生過憑證檔被別帳號 token 蓋掉的事故)。萬一剛好過期,就這輪回報 transient、
    # widget 保留上一筆,下次 bridge 用到時自然刷新即恢復。
    with open(MAIN_CRED_PATH) as f:
        cred = json.load(f)
    access = cred.get("claudeAiOauth", {}).get("accessToken", "")
    return fetch_usage(access)


def _ssm_get(name):
    out = subprocess.run(
        ["aws", "ssm", "get-parameter", "--name", name, "--with-decryption",
         "--query", "Parameter.Value", "--output", "text"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def _ssm_put(name, value):
    subprocess.run(
        ["aws", "ssm", "put-parameter", "--name", name, "--type", "SecureString",
         "--overwrite", "--value", value],
        capture_output=True, text=True, check=True,
    )


def account_backup1():
    cred = json.loads(_ssm_get(BACKUP1_SSM))
    access, merged = ensure_fresh(cred)
    if merged is not None:
        _ssm_put(BACKUP1_SSM, json.dumps(merged))
    return fetch_usage(access)


ACCOUNTS = [
    ("main", "Main", account_main),
    ("backup1", "Backup1", account_backup1),
]


def build_payload():
    accounts = []
    for slot, label, fn in ACCOUNTS:
        entry = {"slot": slot, "label": label}
        try:
            u = fn()
            entry.update(u)
            entry["ok"] = True
        except Exception as e:
            msg = str(e)[:200]
            entry["ok"] = False
            entry["error"] = msg
            # dead = 憑證確定失效(需重新登入);其餘(429/網路/5xx)為暫時性
            entry["dead"] = ("需重新登入" in msg)
        accounts.append(entry)
    return {"updated": int(time.time()), "accounts": accounts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="寫到檔案(原子)")
    ap.add_argument("--s3", help="上傳到 s3://bucket/key")
    args = ap.parse_args()

    payload = build_payload()
    text = json.dumps(payload, ensure_ascii=False, indent=1)

    if args.out:
        d = os.path.dirname(os.path.abspath(args.out))
        fd, tmp = tempfile.mkstemp(dir=d)
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, args.out)
    if args.s3:
        subprocess.run(
            ["aws", "s3", "cp", "-", args.s3, "--content-type", "application/json",
             "--cache-control", "no-cache, max-age=0"],
            input=text.encode(), check=True,
        )
    if not args.out and not args.s3:
        print(text)


if __name__ == "__main__":
    main()
