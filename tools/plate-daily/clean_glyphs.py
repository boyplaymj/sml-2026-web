#!/usr/bin/env python3
"""字元清理:把毛邊點陣字 → 平滑輪廓 + 均勻字色 + 程式浮凸。

讀 glyphs/*.png(原始裁字),輸出 glyphs_clean/*.png(乾淨版)。
用 cv2 高倍上採 + 高斯平滑 + 重新描邊,消鋸齒;再加斜角浮凸。
"""
import os
import glob
import numpy as np
import cv2

SRC = "glyphs"
DST = "glyphs_clean"
NAVY = (36, 30, 26)          # BGR 深藍黑(車牌字色)
UP = 5                        # 上採倍率

os.makedirs(DST, exist_ok=True)


def deskew(alpha):
    """用最小外接旋轉矩形估傾角,轉正(只校正輕微旋轉)。"""
    ys, xs = np.where(alpha > 40)
    if len(xs) < 20:
        return alpha
    rect = cv2.minAreaRect(np.column_stack([xs, ys]).astype(np.float32))
    ang = rect[-1]
    if ang > 45:
        ang -= 90
    ang = max(-12, min(12, ang))          # 只修小角度,避免整字歪掉
    h, w = alpha.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    return cv2.warpAffine(alpha, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=0)


def smooth_mask(alpha):
    """上採 + 高斯 + 門檻,得到平滑邊緣的二值遮罩(高解析)。"""
    a = cv2.resize(alpha, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
    k = max(3, int(a.shape[0] * 0.012) | 1)
    a = cv2.GaussianBlur(a, (k, k), 0)
    _, m = cv2.threshold(a, 128, 255, cv2.THRESH_BINARY)
    # 開運算去孤立雜點、閉運算補小洞
    kk = np.ones((5, 5), np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kk)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kk)
    # 再一次輕平滑做抗鋸齒 alpha
    m = cv2.GaussianBlur(m, (3, 3), 0)
    return m


def emboss(mask):
    """由平滑遮罩產生浮凸 RGBA:均勻字色 + 左上高光 + 右下陰影。"""
    h, w = mask.shape
    alpha = mask.astype(np.float32) / 255.0
    inner = (alpha > 0.5).astype(np.float32)

    def shift(img, dx, dy):
        return np.roll(np.roll(img, dy, axis=0), dx, axis=1)

    d = max(2, int(h * 0.010))
    hl = np.clip(inner - shift(inner, d, d), 0, 1)      # 左上邊 → 高光
    sh = np.clip(inner - shift(inner, -d, -d), 0, 1)    # 右下邊 → 陰影
    hl = cv2.GaussianBlur(hl, (0, 0), d)
    sh = cv2.GaussianBlur(sh, (0, 0), d)

    rgb = np.zeros((h, w, 3), np.float32)
    rgb[:] = np.array(NAVY[::-1], np.float32)           # RGB
    rgb += hl[..., None] * np.array([70, 74, 82]) * 0.9  # 高光提亮
    rgb -= sh[..., None] * np.array([20, 18, 16])        # 陰影壓暗
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    out = np.dstack([rgb, (alpha * 255).astype(np.uint8)])
    return out


def process(path):
    ch = os.path.splitext(os.path.basename(path))[0]
    rgba = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if rgba is None:
        print(f"  ⚠️ 跳過 {ch}:讀檔失敗")
        return None
    if rgba.ndim < 3 or rgba.shape[2] < 4:
        print(f"  ⚠️ 跳過 {ch}:無 alpha 通道")
        return None
    alpha = rgba[:, :, 3]
    if not (alpha > 40).any():
        print(f"  ⚠️ 跳過 {ch}:空白圖")
        return None
    alpha = deskew(alpha)
    mask = smooth_mask(alpha)
    out = emboss(mask)
    # 裁到內容邊界
    ys, xs = np.where(out[:, :, 3] > 10)
    if len(ys) == 0:
        print(f"  ⚠️ 跳過 {ch}:清理後空遮罩")
        return None
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    pad = 8
    out = cv2.copyMakeBorder(out[y0:y1 + 1, x0:x1 + 1], pad, pad, pad, pad,
                             cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
    cv2.imwrite(f"{DST}/{ch}.png", out)
    return ch, out.shape[1], out.shape[0]


if __name__ == "__main__":
    for p in sorted(glob.glob(f"{SRC}/*.png")):
        r = process(p)
        if r:
            ch, w, h = r
            print(f"  {ch}: {w}x{h}")
    print("→ glyphs_clean/")
