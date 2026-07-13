#!/usr/bin/env python3
"""照標籤從一張車牌參考圖裁出字元,併進字庫 glyphs/。

參考資料庫的 EC2 端管線:給(圖, 正確號碼)→ 透視校正(選)→ 裁字 → 存 glyphs/<字>.png。
用法:python3 extract_ref.py <image> <CODE> [--overwrite]
例  :python3 extract_ref.py refs/ref-ABC5678.png ABC-5678
"""
import os
import re
import sys
import numpy as np
import cv2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GLYPH_DIR = os.path.join(BASE_DIR, "glyphs")
os.makedirs(GLYPH_DIR, exist_ok=True)


def dewarp(gray):
    """偵測白牌四角拉正;找不到清楚四角就原圖回傳(已是正面裁好的圖)。"""
    _, th = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return gray
    c = max(cnts, key=cv2.contourArea)
    H, W = gray.shape
    if cv2.contourArea(c) < 0.35 * W * H:          # 白牌太小 → 不是整塊牌,放棄校正
        return gray
    peri = cv2.arcLength(c, True)
    quad = None
    for eps in (0.02, 0.03, 0.04, 0.05):
        ap = cv2.approxPolyDP(c, eps * peri, True)
        if len(ap) == 4:
            quad = ap.reshape(4, 2).astype(np.float32)
            break
    if quad is None:
        return gray
    s = quad.sum(1); d = np.diff(quad, axis=1).ravel()
    tl, br = quad[np.argmin(s)], quad[np.argmax(s)]
    tr, bl = quad[np.argmin(d)], quad[np.argmax(d)]
    ow, oh = 1600, 760
    M = cv2.getPerspectiveTransform(
        np.float32([tl, tr, br, bl]),
        np.float32([[0, 0], [ow, 0], [ow, oh], [0, oh]]))
    return cv2.warpPerspective(gray, M, (ow, oh))


def normalize_glyph(image_path, char, out_dir=None, target_h=240, pad=12, max_deskew=20):
    """單字元模式:吃使用者 PS 去背好的透明 PNG(角度/大小不拘)→ 擺正+統一尺寸→存字庫。

    使用者只負責去背;大小與角度由這裡判定:
      1. 取 alpha 遮罩(沒去背則從白底黑字抽深字 alpha)
      2. minAreaRect 量傾斜角 → 轉正(角度誇張[>max_deskew]不敢轉,避免圓字誤判)
      3. 裁到字的 bbox、縮到一致高度 target_h、加透明邊
    """
    out_dir = out_dir or GLYPH_DIR
    os.makedirs(out_dir, exist_ok=True)
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"讀不到圖:{image_path}")

    # 取 alpha:有去背用其 alpha 通道;沒去背(白底黑字)則抽深字 alpha
    if img.ndim == 3 and img.shape[2] == 4 and int(img[:, :, 3].max()) > 0:
        bgr, alpha = img[:, :, :3].copy(), img[:, :, 3].copy()
    else:
        bgr = img[:, :, :3] if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        alpha = np.clip((150 - gray.astype(float)) / 90, 0, 1)
        alpha = (alpha * 255).astype("uint8")

    ys, xs = np.where(alpha > 40)
    if len(xs) < 10:
        raise SystemExit("去背後幾乎沒有內容,請確認圖是單一字元且非全透明")

    # 擺正:用字的像素量最小外接矩形角度
    rect = cv2.minAreaRect(np.column_stack([xs, ys]).astype(np.float32))
    ang = rect[-1]
    if ang < -45:
        ang += 90
    elif ang > 45:
        ang -= 90
    if abs(ang) > max_deskew:
        ang = 0.0                                  # 角度誇張多半是圓字誤判,寧可不轉
    H, W = alpha.shape
    if abs(ang) > 0.5:
        M = cv2.getRotationMatrix2D((W / 2.0, H / 2.0), ang, 1.0)
        bgr = cv2.warpAffine(bgr, M, (W, H), flags=cv2.INTER_CUBIC, borderValue=(0, 0, 0))
        alpha = cv2.warpAffine(alpha, M, (W, H), flags=cv2.INTER_CUBIC, borderValue=0)
        ys, xs = np.where(alpha > 40)

    # 裁 bbox → 縮到一致高度 → 加透明邊
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    crop = np.dstack([bgr, alpha])[y0:y1 + 1, x0:x1 + 1]
    ch, cw = crop.shape[:2]
    scale = target_h / float(ch)
    crop = cv2.resize(crop, (max(1, round(cw * scale)), target_h), interpolation=cv2.INTER_AREA)
    out = np.zeros((crop.shape[0] + 2 * pad, crop.shape[1] + 2 * pad, 4), "uint8")
    out[pad:-pad, pad:-pad] = crop
    path = os.path.join(out_dir, f"{char}.png")
    cv2.imwrite(path, out)
    return round(ang, 1)


def extract(image_path, code, overwrite=False, out_dir=None):
    out_dir = out_dir or GLYPH_DIR                       # 預設進正式字庫;預覽時給暫存夾
    os.makedirs(out_dir, exist_ok=True)
    chars = re.sub(r"[^A-Z0-9]", "", code.upper())      # 去分隔,只留字元
    img = cv2.imread(image_path)
    if img is None:
        raise SystemExit(f"讀不到圖:{image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = dewarp(gray)
    color = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)      # 統一來源(校正後)
    H, W = gray.shape

    # 深字 alpha(黑字白底)
    Tlo, Thi = 60, 150
    alpha = np.clip((Thi - gray.astype(float)) / (Thi - Tlo), 0, 1)
    mx = int(W * 0.02); alpha[:, :mx] = 0; alpha[:, -mx:] = 0

    # 最高文字帶(列投影最長連續高列)
    rowsum = alpha.sum(axis=1); on = rowsum > rowsum.max() * 0.25
    runs = []; cur = None
    for i, v in enumerate(list(on) + [False]):
        if v and cur is None: cur = i
        if not v and cur is not None: runs.append((cur, i)); cur = None
    if not runs:
        raise SystemExit("找不到文字帶")
    ty0, ty1 = max(runs, key=lambda r: r[1] - r[0]); bandH = ty1 - ty0

    # 欄位切字
    colsum = alpha[ty0:ty1].sum(axis=0); on = colsum > colsum.max() * 0.05
    segs = []; cur = None
    for i, v in enumerate(list(on) + [False]):
        if v and cur is None: cur = i
        if not v and cur is not None:
            if i - cur >= max(2, int(W * 0.004)): segs.append([cur, i])
            cur = None
    # 濾矮(分隔點/雜訊):字高需 > 帶高 45%
    kept = []
    for x0, x1 in segs:
        g = alpha[ty0:ty1, x0:x1]
        rr = np.where(g.sum(axis=1) > g.sum(axis=1).max() * 0.2)[0]
        if len(rr) and (rr.max() - rr.min()) > bandH * 0.45:
            kept.append([x0, x1])
    # 過寬÷median 自動切分
    if not kept:
        raise SystemExit("切不出字元")
    med = np.median([x1 - x0 for x0, x1 in kept])
    final = []
    for x0, x1 in kept:
        n = max(1, round((x1 - x0) / med))
        step = (x1 - x0) / n
        for k in range(n):
            final.append((int(x0 + k * step), int(x0 + (k + 1) * step)))

    if len(final) != len(chars):
        print(f"⚠️ 切出 {len(final)} 段但標籤有 {len(chars)} 字（{chars}）——"
              f"可能黏連/雜訊,請換更清楚的圖或人工檢查。仍嘗試對應。")

    saved, skipped = [], []
    pad = 4
    for (x0, x1), ch in zip(final, chars):
        path = os.path.join(out_dir, f"{ch}.png")
        if os.path.exists(path) and not overwrite:
            skipped.append(ch); continue
        g = alpha[ty0:ty1, x0:x1]
        rr = np.where(g.sum(axis=1) > 0.5)[0]
        if not len(rr): continue
        y0, y1 = ty0 + rr.min(), ty0 + rr.max()
        rgb = color[y0:y1 + 1, x0:x1]
        al = (alpha[y0:y1 + 1, x0:x1] * 255).astype("uint8")
        rgba = np.dstack([rgb, al])
        out = np.zeros((rgba.shape[0] + 2 * pad, rgba.shape[1] + 2 * pad, 4), "uint8")
        out[pad:-pad, pad:-pad] = rgba
        cv2.imwrite(path, out)
        saved.append(ch)
    return saved, skipped


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--overwrite"]
    overwrite = "--overwrite" in sys.argv
    if len(args) < 2:
        print(__doc__); sys.exit(1)
    saved, skipped = extract(args[0], args[1], overwrite)
    print(f"✅ 裁字完成:新增 {saved}｜已有跳過 {skipped}")
