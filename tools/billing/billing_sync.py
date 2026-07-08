#!/usr/bin/env python3
"""每週費用同步：AWS(當月+近6月歷史) + OpenAI + Claude(訂閱定額) → Firestore + Cognito 保護的 S3

安全改動(2026-07-03)：除了寫 Firestore(公開規則)外，另把整包 billing.json
寫進 broadcast 後台的 S3(sml-frontend-prod)。cost_tracker.html 優先讀 S3
(經 CloudFront + Cognito 保護)，讀不到才退回 Firestore。這樣費用數字不再只
躺在全開 Firestore。
"""
import json, os, subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request, urllib.error

FB_KEY     = "AIzaSyAZaa_yHu7gsRaj71YL8x3REHfL_V5Tq4w"
FB_PROJECT = "sml2026newscore"
FB_BASE    = f"https://firestore.googleapis.com/v1/projects/{FB_PROJECT}/databases/(default)/documents"

S3_BUCKET  = "sml-frontend-prod"          # broadcast.boyplaymj.com 的來源桶
S3_BILLING = "billing.json"               # 同源、Cognito 保護的費用快照
S3_DOMAINS = "domains.json"               # 網域控制塔快照(domains_sync.py 產),cost_tracker 分類③用

# 網域年費(NT$/年,手動維護:GoDaddy .com 無 API 抓不到價;.link=Amazon Registrar 年費待確認→留 0=前端顯示「年費待填」)
DOMAIN_YEAR_FEE_TWD = {
    "supermahjongleague.com": 699,   # 3 年 NT$2,097
    "boyplaymj.com":          699,   # 3 年 NT$2,097
}

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
# Claude = prepaid 用量額度(餘額模式，比照 OpenAI 卡)。
# 餘額 = 錨點 + 儲值(CLAUDE_TOPUP，一次性) − 用量花費(有 admin key 才能自動扣)。
# admin cost API: GET /v1/organizations/cost_report，需 sk-ant-admin01- 金鑰。

# ── Firestore helpers ─────────────────────────────────────────────────────────

def _wrap(val):
    if isinstance(val, bool):   return {"booleanValue": val}
    if isinstance(val, int):    return {"integerValue": str(val)}
    if isinstance(val, float):  return {"doubleValue": val}
    if isinstance(val, str):    return {"stringValue": val}
    if isinstance(val, dict):   return {"mapValue": {"fields": {k: _wrap(v) for k, v in val.items()}}}
    if isinstance(val, list):   return {"arrayValue": {"values": [_wrap(v) for v in val]}}
    return {"nullValue": None}

def fs_patch(path, data):
    url = f"{FB_BASE}/{path}?key={FB_KEY}"
    fields = {k: _wrap(v) for k, v in data.items()}
    body = json.dumps({"fields": fields}).encode()
    req = urllib.request.Request(url, data=body, method="PATCH",
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"Firestore PATCH error {e.code}: {e.read().decode()}")
        return None

def fs_get(path):
    url = f"{FB_BASE}/{path}?key={FB_KEY}"
    try:
        with urllib.request.urlopen(url) as r:
            doc = json.load(r)
        return {k: list(v.values())[0] for k, v in doc.get("fields", {}).items()}
    except:
        return {}

# ── AWS Cost Explorer ─────────────────────────────────────────────────────────

def get_aws_costs():
    today = datetime.now(timezone.utc)
    start = today.strftime("%Y-%m-01")
    end   = today.strftime("%Y-%m-%d")
    if start == end:  # 月初第一天
        end = today.strftime("%Y-%m-02") if today.day > 1 else start

    cmd = [
        "aws", "ce", "get-cost-and-usage",
        "--time-period", f"Start={start},End={end}",
        "--granularity", "MONTHLY",
        "--metrics", "UnblendedCost",
        "--group-by", "Type=DIMENSION,Key=SERVICE",
        "--output", "json"
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        groups = json.loads(out)["ResultsByTime"][0]["Groups"]
        services = {}
        total = 0.0
        for g in groups:
            svc = g["Keys"][0]
            amt = float(g["Metrics"]["UnblendedCost"]["Amount"])
            if amt > 0.0001:
                services[svc] = round(amt, 4)
                total += amt
        return round(total, 4), services
    except Exception as e:
        print(f"AWS cost error: {e}")
        return 0.0, {}

def ssm_get(name):
    """從 AWS SSM Parameter Store 讀 SecureString(解密)。讀不到回空字串。"""
    region = os.getenv("AWS_REGION", "ap-southeast-1")
    try:
        out = subprocess.check_output(
            ["aws", "ssm", "get-parameter", "--name", name,
             "--with-decryption", "--region", region,
             "--query", "Parameter.Value", "--output", "text"],
            stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return ""

def get_claude_cost(admin_key, start_iso, end_iso):
    """用 Anthropic Admin Cost API 取一段時間的 Claude 用量花費(USD)。
    回傳金額為 cents 字串，需 /100。無 key 或失敗回 None。"""
    if not admin_key:
        return None
    url = ("https://api.anthropic.com/v1/organizations/cost_report"
           f"?starting_at={start_iso}&ending_at={end_iso}")
    total_cents = 0.0
    page = None
    try:
        for _ in range(20):  # 分頁上限保護
            u = url + (f"&page={page}" if page else "")
            req = urllib.request.Request(u, headers={
                "x-api-key": admin_key,
                "anthropic-version": "2023-06-01",
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                doc = json.load(r)
            for bucket in doc.get("data", []):
                for item in bucket.get("results", []):
                    amt = item.get("amount")
                    if amt is not None:
                        total_cents += float(amt)
            if doc.get("has_more") and doc.get("next_page"):
                page = doc["next_page"]
            else:
                break
        return round(total_cents / 100.0, 2)
    except Exception as e:
        print(f"  ⚠️ Claude cost API 失敗: {e}")
        return None

def get_aws_history(months=6):
    """近 N 個月每月 AWS 總花費(含當月至今)，給趨勢圖用。"""
    today = datetime.now(timezone.utc)
    # 回推到 months 個月前的月初
    y, m = today.year, today.month - (months - 1)
    while m <= 0:
        m += 12; y -= 1
    start = f"{y:04d}-{m:02d}-01"
    end   = today.strftime("%Y-%m-%d")
    cmd = [
        "aws", "ce", "get-cost-and-usage",
        "--time-period", f"Start={start},End={end}",
        "--granularity", "MONTHLY",
        "--metrics", "UnblendedCost",
        "--output", "json"
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        res = json.loads(out)["ResultsByTime"]
        hist = {}
        for r in res:
            mon = r["TimePeriod"]["Start"][:7]   # YYYY-MM
            amt = float(r["Total"]["UnblendedCost"]["Amount"])
            hist[mon] = round(amt, 2)
        return hist
    except Exception as e:
        print(f"AWS history error: {e}")
        return {}

# ── 寫入 Cognito 保護的 S3 ─────────────────────────────────────────────────────

def read_s3_json():
    """讀回既有 billing.json(明細帳來源,JSON 原生)。讀不到回 {}。"""
    try:
        out = subprocess.check_output(
            ["aws", "s3", "cp", f"s3://{S3_BUCKET}/{S3_BILLING}", "-"],
            stderr=subprocess.DEVNULL)
        return json.loads(out.decode())
    except Exception:
        return {}

def write_s3(payload):
    try:
        blob = json.dumps(payload, ensure_ascii=False).encode()
        p = subprocess.run(
            ["aws", "s3", "cp", "-", f"s3://{S3_BUCKET}/{S3_BILLING}",
             "--content-type", "application/json", "--cache-control", "no-store"],
            input=blob, stderr=subprocess.PIPE)
        if p.returncode == 0:
            print(f"  ✅ 已寫 s3://{S3_BUCKET}/{S3_BILLING}")
        else:
            print(f"  ⚠️ S3 寫入失敗: {p.stderr.decode()[:200]}")
    except Exception as e:
        print(f"  ⚠️ S3 寫入例外: {e}")

# ── 偵測 OpenAI 自動儲值 ──────────────────────────────────────────────────────

def check_openai_recharge(prev_balance, new_balance):
    if new_balance - prev_balance > 1.0:
        return round(new_balance - prev_balance, 2)
    return None

# ── DynamoDB 實際用量(cost_tracker 分類②:甜甜遊戲館) ────────────────────────

def get_ddb_usage(days=30):
    """近 days 天各 DynamoDB 表實際用量(CloudWatch)→ billing.json 的 dynamodb_usage。
    收集器 = /opt/sml/repo/tools/ddb-usage/gen_usage.py(可用 DDB_USAGE_DIR 覆寫)。
    失敗回 None、不影響其餘費用同步(cost_tracker 該分類會顯示「尚未同步」)。"""
    import sys
    d = os.getenv("DDB_USAGE_DIR", "/opt/sml/repo/tools/ddb-usage")
    try:
        if d not in sys.path:
            sys.path.insert(0, d)
        import gen_usage
        return gen_usage.collect(days=days)
    except Exception as e:
        print(f"  ⚠️ DynamoDB 用量收集失敗(略過 dynamodb_usage): {e}")
        return None

# ── 網域(cost_tracker 分類③:網域) ─────────────────────────────────────────────

def get_domains():
    """讀網域控制塔 domains.json(S3)+ 附手動維護年費 → billing.json 的 domains。
    失敗回 None、不影響其餘同步(cost_tracker 分類③會顯示無資料)。"""
    try:
        out = subprocess.check_output(
            ["aws", "s3", "cp", f"s3://{S3_BUCKET}/{S3_DOMAINS}", "-"],
            stderr=subprocess.DEVNULL)
        data = json.loads(out.decode())
        doms = data.get("domains", []) if isinstance(data, dict) else (data or [])
        res = []
        for x in doms:
            name = x.get("domain", "")
            res.append({
                "domain":     name,
                "registrar":  x.get("registrar", ""),
                "autoRenew":  bool(x.get("autoRenew")),
                "expiry":     x.get("expiry") or x.get("expiration") or "",
                "yearFeeTwd": DOMAIN_YEAR_FEE_TWD.get(name, 0),   # 0 = 前端顯示「年費待填」
            })
        return res
    except Exception as e:
        print(f"  ⚠️ 網域資料讀取失敗(略過 domains): {e}")
        return None

# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    print(f"[{now_str}] 開始同步費用...")

    # ── AI 供應商手動餘額(Claude / Gemini)+ 共用明細帳 ──
    # 餘額 = 錨點 + 儲值(TOPUP) − 花費(SPEND)；SET 直接對齊 Console。
    # 每筆動作記進明細帳(sml_billing/ledger 的 entries，留最近 40 筆，來源存 S3)。
    prev_s3 = read_s3_json()
    ledger = (prev_s3.get("ledger") or [])[:]

    def manual_provider(name, prefix):
        prev = fs_get(f"sml_billing/{name}")
        bal  = float(prev.get("balance", os.getenv(f"{prefix}_BALANCE", "0") or 0))
        month = 0.0
        note = os.getenv(f"{prefix}_NOTE", "")
        topup = float(os.getenv(f"{prefix}_TOPUP", "0") or 0)
        spend = float(os.getenv(f"{prefix}_SPEND", "0") or 0)
        setb  = os.getenv(f"{prefix}_SET", "")
        if topup:
            bal = round(bal + topup, 2)
            ledger.append({"ts": now_str, "provider": name, "type": "topup",
                           "amount": topup, "balance_after": bal, "note": note or "額度儲值"})
            print(f"  💳 {name} 儲值 +${topup:.2f} → ${bal:.2f}")
        if spend:
            bal = round(bal - spend, 2); month = round(month + spend, 2)
            ledger.append({"ts": now_str, "provider": name, "type": "spend",
                           "amount": spend, "balance_after": bal, "note": note or "用量花費"})
            print(f"  🧾 {name} 花費 -${spend:.2f} → ${bal:.2f}")
        if setb:
            bal = round(float(setb), 2)
            ledger.append({"ts": now_str, "provider": name, "type": "set",
                           "amount": bal, "balance_after": bal, "note": note or "對齊 Console"})
            print(f"  🔧 {name} 餘額對齊 → ${bal:.2f}")
        fs_patch(f"sml_billing/{name}", {"balance": bal, "updated_at": now_str})
        return bal, month

    claude_balance, claude_month_spent = manual_provider("claude", "CLAUDE")

    # Gemini = 固定月訂閱(Google AI Ultra，台幣計價，換算美金計入總支出)
    gem_prev = fs_get("sml_billing/gemini")
    gem_twd  = float(os.getenv("GEMINI_MONTHLY_TWD", gem_prev.get("monthly_twd", "0")) or 0)
    gem_rate = float(os.getenv("TWD_USD_RATE",       gem_prev.get("rate", "32.5")) or 32.5)
    gemini_month_spent = round(gem_twd / gem_rate, 2) if gem_twd else 0.0
    gem_start = os.getenv("GEMINI_START", gem_prev.get("start", "2026-06"))
    fs_patch("sml_billing/gemini", {"monthly_twd": gem_twd, "rate": gem_rate,
                                     "monthly_usd": gemini_month_spent, "start": gem_start,
                                     "updated_at": now_str})

    ledger = ledger[-40:]
    fs_patch("sml_billing/ledger", {"entries": ledger, "updated_at": now_str})

    # ── 自訂分類(金流手續費…可自由擴充,台幣月費) ──
    # env CATEGORY="名稱:台幣[:icon[:色碼]]" 新增/更新;台幣=0 移除。
    cats = (prev_s3.get("categories") or [])[:]
    cadd = os.getenv("CATEGORY", "")
    if cadd:
        p = cadd.split(":")
        cname = p[0]
        ctwd  = float(p[1]) if len(p) > 1 and p[1] else 0
        cicon = p[2] if len(p) > 2 and p[2] else "💳"
        ccol  = p[3] if len(p) > 3 and p[3] else "#fb923c"
        cats = [c for c in cats if c.get("name") != cname]
        if ctwd > 0:
            cats.append({"name": cname, "twd": ctwd, "icon": cicon, "color": ccol})
            print(f"  🏷️ 分類 {cname} NT${ctwd:.0f}/月")
        else:
            print(f"  🗑️ 移除分類 {cname}")
    for c in cats:
        c["usd"] = round(c["twd"] / gem_rate, 2)
    cats_usd = round(sum(c["usd"] for c in cats), 2)
    fs_patch("sml_billing/categories", {"items": cats, "updated_at": now_str})

    existing = fs_get("sml_billing/summary")
    prev_balance = float(existing.get("openai_balance", 20.0))
    total_openai_spent = float(existing.get("openai_total_spent", 0.0))
    openai_balance = prev_balance

    aws_total, aws_services = get_aws_costs()
    aws_history = get_aws_history(14)   # CE 上限 ~14 個月，供季/年/去年同期分析
    # 確保當月一定在歷史裡(CE 當月值即時)
    aws_history[now.strftime("%Y-%m")] = aws_total

    ddb_usage = get_ddb_usage(30)   # 分類②:DynamoDB 每表實際用量(失敗回 None)
    if ddb_usage:
        print(f"  DynamoDB 用量: US${ddb_usage['totals']['grandTotal']} / {ddb_usage['totals']['tableCount']} 表(近30天)")

    domains = get_domains()         # 分類③:網域(domains.json + 年費;失敗回 None)
    if domains:
        print(f"  網域: {len(domains)} 個(年費合計 NT${sum(x['yearFeeTwd'] for x in domains):.0f})")

    print(f"  AWS 本月: ${aws_total:.2f}  | 歷史月數: {len(aws_history)}")
    print(f"  OpenAI ${openai_balance:.2f} | Claude ${claude_balance:.2f}"
          f"(本月${claude_month_spent:.2f}) | Gemini 月訂閱 ${gemini_month_spent:.2f}"
          f"(NT${gem_twd:.0f}@{gem_rate})")

    recharge_amt = check_openai_recharge(prev_balance, openai_balance)
    if recharge_amt:
        fs_patch("sml_billing_recharge/" + now.strftime("%Y%m%d%H%M%S"), {
            "timestamp": now_str, "type": "auto_recharge",
            "amount": recharge_amt, "balance_after": openai_balance,
            "note": "自動偵測儲值",
        })

    grand_total = round(aws_total + total_openai_spent
                        + claude_month_spent + gemini_month_spent + cats_usd, 2)

    summary = {
        "openai_balance":     openai_balance,
        "openai_total_spent": total_openai_spent,
        "aws_month_spent":    aws_total,
        "claude_balance":     claude_balance,
        "claude_month_spent": claude_month_spent,
        "claude_auto":        False,
        "gemini_month_spent": gemini_month_spent,
        "gemini_monthly_twd": gem_twd,
        "gemini_rate":        gem_rate,
        "gemini_start":       gem_start,
        "custom_cats_usd":    cats_usd,
        "twd_rate":           gem_rate,   # 全站美金→台幣換算用(平均匯率估值)
        "grand_total":        grand_total,
        "last_updated":       now_str,
        "sync_month":         now.strftime("%Y-%m"),
    }
    aws_doc = {"updated_at": now_str, "month": now.strftime("%Y-%m"),
               "services": aws_services, "total": aws_total}

    # Firestore(相容既有讀取)
    fs_patch("sml_billing/summary", summary)
    fs_patch("sml_billing/aws_services", aws_doc)
    fs_patch("sml_billing/history", {"updated_at": now_str, "months": aws_history})

    # Cognito 保護的 S3(cost_tracker 優先讀這份)
    write_s3({
        "summary":       summary,
        "aws_services":  aws_doc,
        "history":       {"months": aws_history},
        "ledger":        ledger,
        "categories":    cats,
        "dynamodb_usage": ddb_usage,   # 分類②:DynamoDB 每表實際用量(None=收集失敗,前端顯示未同步)
        "domains":        domains,     # 分類③:網域清單+年費(None=讀取失敗)
        "generated_at":  now_str,
    })

    print("  ✅ 同步完成")

if __name__ == "__main__":
    env_path = Path(__file__).parent / "sweetbot.env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    main()
