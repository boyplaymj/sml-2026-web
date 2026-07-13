#!/usr/bin/env python3
"""參考素材上傳+即時裁字驗證(獨立小服務,與正式服務零耦合)。

用途:staff 從瀏覽器上傳一張車牌圖 + 打字輸入正確號碼 → 當場裁字 →
      把裁出來的每個字元縮圖秀回去驗證 → 按「採用」才寫進正式字庫 glyphs/。
非破壞式:裁字先進 _staging/<sid>/,確認 OK 才 commit 到 glyphs/ 並重發 atlas。

啟動:REF_UPLOAD_TOKEN=<秘鑰> python3 -m uvicorn ref_uploader:app --host 0.0.0.0 --port 8770
      (沒設 token 會自動生一個寫進 .ref_token 並印出網址)
"""
import base64
import json
import os
import re
import secrets
import shutil
import time

from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

import extract_ref
import publish_atlas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GLYPH_DIR = os.path.join(BASE_DIR, "glyphs")
REFS_DIR = os.path.join(BASE_DIR, "refs")
STAGE_DIR = os.path.join(BASE_DIR, "_staging")
MAX_BYTES = 12 * 1024 * 1024
CODE_RE = re.compile(r"^[A-Z]{2,6}[0-9]{2,5}$")     # 正規化後的合法格式(同 db.py)

_TOKEN_FILE = os.path.join(BASE_DIR, ".ref_token")


def _token():
    t = os.environ.get("REF_UPLOAD_TOKEN")
    if t:
        return t
    if os.path.exists(_TOKEN_FILE):
        return open(_TOKEN_FILE).read().strip()
    t = secrets.token_urlsafe(12)
    with open(_TOKEN_FILE, "w") as f:
        f.write(t)
    os.chmod(_TOKEN_FILE, 0o600)
    return t


TOKEN = _token()
app = FastAPI()
os.makedirs(STAGE_DIR, exist_ok=True)
os.makedirs(REFS_DIR, exist_ok=True)


def _norm(code):
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _sweep(max_age=7200):
    """清掉逾 2 小時未 commit 的暫存夾,避免磁碟屯積。"""
    now = time.time()
    for d in os.listdir(STAGE_DIR):
        p = os.path.join(STAGE_DIR, d)
        try:
            if os.path.isdir(p) and now - os.path.getmtime(p) > max_age:
                shutil.rmtree(p, ignore_errors=True)
        except OSError:
            pass


PAGE = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>車牌參考字庫 · 上傳裁字</title>
<style>
body{{font-family:system-ui,"PingFang TC","Noto Sans TC",sans-serif;max-width:760px;
margin:24px auto;padding:0 16px;background:#0f1216;color:#e8eaed}}
h1{{font-size:20px}} .card{{background:#1a1f26;border:1px solid #2a313b;border-radius:12px;
padding:18px;margin:16px 0}}
label{{display:block;margin:10px 0 4px;font-size:13px;color:#9aa4b2}}
input[type=text]{{width:100%;padding:10px;border-radius:8px;border:1px solid #333c48;
background:#0f1216;color:#e8eaed;font-size:18px;letter-spacing:2px;text-transform:uppercase}}
input[type=file]{{width:100%;color:#9aa4b2}}
button{{background:#3b82f6;color:#fff;border:0;padding:11px 20px;border-radius:8px;
font-size:15px;cursor:pointer;margin-top:14px}}
button.ghost{{background:#333c48}}
.glyphs{{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}}
.g{{text-align:center;background:#fff;border-radius:8px;padding:8px}}
.g img{{height:80px;display:block}} .g span{{color:#111;font-weight:700;font-size:14px}}
.ok{{color:#34d399}} .warn{{color:#fbbf24}} .err{{color:#f87171}}
small{{color:#6b7480}}
</style></head><body>
<h1>🔠 車牌參考字庫 · 上傳裁字驗證</h1>
{body}
</body></html>"""

FORM = """<div class="card">
<form action="/submit" method="post" enctype="multipart/form-data">
<input type="hidden" name="t" value="{t}">
<label>① 車牌圖(高清、對焦清、牌拍得大;歪沒關係會自動拉正)</label>
<input type="file" name="file" accept="image/*" required>
<label>② 這張圖的正確號碼(英+數,分隔符自動忽略)</label>
<input type="text" name="code" placeholder="ABC-5678" required>
<button type="submit">上傳並裁字 →</button>
</form>
<small>裁完會把每個字元縮圖秀給你看,確認漂亮才按「採用進字庫」。</small>
</div>"""


@app.get("/", response_class=HTMLResponse)
def home(t: str = ""):
    if t != TOKEN:
        return HTMLResponse(PAGE.format(body='<div class="card err">網址缺少或錯誤的存取碼 ?t=</div>'), status_code=403)
    return PAGE.format(body=FORM.format(t=t))


@app.post("/submit", response_class=HTMLResponse)
async def submit(t: str = Form(""), code: str = Form(""), file: UploadFile = File(...)):
    if t != TOKEN:
        return HTMLResponse("forbidden", status_code=403)
    _sweep()
    chars = _norm(code)
    if not CODE_RE.match(chars):
        return _err(f"號碼格式不合法:{code!r}(需 2-6 英文字母 + 2-5 數字)", t)
    data = await file.read()
    if not data:
        return _err("沒收到檔案內容", t)
    if len(data) > MAX_BYTES:
        return _err(f"檔案過大({len(data)//1024//1024}MB > 12MB)", t)

    sid = f"{int(time.time())}-{secrets.token_hex(3)}"
    sdir = os.path.join(STAGE_DIR, sid)
    sglyphs = os.path.join(sdir, "glyphs")
    os.makedirs(sglyphs, exist_ok=True)
    ext = (os.path.splitext(file.filename or "")[1] or ".png").lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        ext = ".png"
    src = os.path.join(sdir, f"src{ext}")
    with open(src, "wb") as f:
        f.write(data)
    json.dump({"code": chars, "src": os.path.basename(src)},
              open(os.path.join(sdir, "meta.json"), "w"))

    try:
        # 預覽一律重裁進暫存夾,讓使用者看到「這張圖」的實際裁切結果
        saved, _ = extract_ref.extract(src, chars, overwrite=True, out_dir=sglyphs)
    except SystemExit as e:
        return _err(f"裁字失敗:{e}", t)
    except Exception as e:
        return _err(f"裁字例外:{str(e)[:160]}", t)

    got = [c for c in chars if os.path.exists(os.path.join(sglyphs, f"{c}.png"))]
    n_ok, n_want = len(got), len(chars)
    status = (f'<span class="ok">✅ 切出 {n_ok}/{n_want} 字,數量吻合</span>'
              if n_ok == n_want else
              f'<span class="warn">⚠️ 切出 {n_ok}/{n_want} 字,數量不符——可能字黏連/雜訊,建議換更清楚的圖</span>')

    cells = ""
    for c in chars:
        gp = os.path.join(sglyphs, f"{c}.png")
        if os.path.exists(gp):
            cells += f'<div class="g"><img src="data:image/png;base64,{_b64(gp)}"><span>{c}</span></div>'
        else:
            cells += f'<div class="g" style="background:#3a1f1f"><span class="err">{c}✗</span></div>'

    body = f"""<div class="card">
<div>號碼 <b style="font-size:18px;letter-spacing:2px">{chars}</b> · {status}</div>
<div class="glyphs">{cells}</div>
<form action="/commit" method="post" style="display:inline">
<input type="hidden" name="t" value="{t}"><input type="hidden" name="sid" value="{sid}">
<button type="submit">✅ 採用進字庫（並更新覆蓋度）</button></form>
<a href="/?t={t}"><button type="button" class="ghost">✗ 丟棄，重新上傳</button></a>
<div><small>「採用」會把上面每個字元寫入正式 glyphs/(覆蓋同名舊字)、原圖存進 refs/、重發 atlas 覆蓋度。</small></div>
</div>{FORM.format(t=t)}"""
    return PAGE.format(body=body)


@app.post("/commit", response_class=HTMLResponse)
def commit(t: str = Form(""), sid: str = Form("")):
    if t != TOKEN:
        return HTMLResponse("forbidden", status_code=403)
    if not re.match(r"^[0-9]+-[0-9a-f]{6}$", sid):
        return _err("sid 不合法", t)
    sdir = os.path.join(STAGE_DIR, sid)
    sglyphs = os.path.join(sdir, "glyphs")
    if not os.path.isdir(sglyphs):
        return _err("找不到暫存(可能已逾時清掉),請重新上傳", t)
    os.makedirs(GLYPH_DIR, exist_ok=True)
    committed = []
    for fn in sorted(os.listdir(sglyphs)):
        if fn.endswith(".png"):
            shutil.copy2(os.path.join(sglyphs, fn), os.path.join(GLYPH_DIR, fn))
            committed.append(fn[:-4])
    # 原圖留底供日後重裁
    try:
        meta = json.load(open(os.path.join(sdir, "meta.json")))
        src = os.path.join(sdir, meta["src"])
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(REFS_DIR, f"ref-{meta['code']}{os.path.splitext(src)[1]}"))
    except Exception:
        pass
    shutil.rmtree(sdir, ignore_errors=True)
    try:
        where = publish_atlas.publish(publish_atlas.build())
        atlas = f'覆蓋度已更新 → {where}'
    except Exception as e:
        atlas = f'<span class="warn">字已入庫,但 atlas 重發失敗:{str(e)[:120]}</span>'
    body = f"""<div class="card">
<div class="ok">✅ 已採用 {len(committed)} 字進字庫:{' '.join(committed)}</div>
<div><small>{atlas}</small></div>
<a href="/?t={t}"><button type="button">再上傳一張 →</button></a>
</div>"""
    return PAGE.format(body=body)


def _err(msg, t):
    return HTMLResponse(PAGE.format(
        body=f'<div class="card err">{msg}</div>{FORM.format(t=t)}'))


@app.get("/health", response_class=PlainTextResponse)
def health():
    return "ok"


if __name__ == "__main__":
    print("存取碼 token:", TOKEN)
    print("啟動:REF_UPLOAD_TOKEN=%s python3 -m uvicorn ref_uploader:app --host 0.0.0.0 --port 8770" % TOKEN)
