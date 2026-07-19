"""
pixel16 通用零件庫 —— 沉澱下來的可重用幾何原件(飛輪:第二款遊戲直接拼)。

每個函式回傳一張「用某條 ramp 上好光影」的字元網格(未描邊,交給 add_outline)。
因為都用具名 ramp 畫,套 shift_ramp 就能換材質、光影全保留。
"""
from engine16 import RAMPS


def _canvas(w, h):
    return [["."] * w for _ in range(h)]


def _grid(c):
    return ["".join(r) for r in c]


def bar(ramp="gold", w=16, h=8):
    """發亮的金屬條 / 錠(頂面高光 + 前面漸層 + 左右倒角)。金錠/鋼錠/銀錠共用。"""
    r = RAMPS[ramp]                 # 暗→亮
    dark, mid, lite, hi = r[0], r[max(0, len(r) - 3)], r[-2], r[-1]
    c = _canvas(w, h)
    for y in range(h):
        for x in range(w):
            # 梯形:頂窄底寬(等角錠)
            inset = (h - 1 - y) // 2
            if x < inset or x >= w - inset:
                continue
            if y == 0:
                ch = hi                       # 頂面高光邊
            elif y == 1:
                ch = lite
            elif x <= inset + 1:
                ch = lite                     # 左倒角受光
            elif x >= w - inset - 2:
                ch = dark                     # 右倒角陰影
            elif y == h - 1:
                ch = dark                     # 底邊陰影
            else:
                ch = mid                      # 前面主色
            c[y][x] = ch
    return _grid(c)


def drum(ramp="steel", band="gold", w=16, h=20):
    """圓桶 / 鐵桶(圓柱體積:中央高光縱脊 + 左右漸暗 + 頂橢圓蓋 + 兩道箍)。油桶/水桶共用。"""
    r = RAMPS[ramp]
    b = RAMPS[band]
    c = _canvas(w, h)
    cx = (w - 1) / 2
    for y in range(h):
        # 上下各留 2 列做橢圓頂/底
        for x in range(w):
            edge = 1 if (y in (0, h - 1)) else 0   # 頂底縮一格成圓角
            if x < edge or x >= w - edge:
                continue
            # 圓柱橫向光影:中央偏左最亮,兩側漸暗
            t = abs(x - (cx - 1)) / cx             # 0(高光脊)..1(邊)
            idx = min(len(r) - 1, 1 + int(t * (len(r) - 1)))
            ch = r[len(r) - 1 - idx] if False else r[max(1, len(r) - 1 - int(t * (len(r) - 2)))]
            c[y][x] = ch
        # 頂蓋(第 1~2 列)提亮成蓋面
        if y in (1, 2):
            for x in range(w):
                if c[y][x] != ".":
                    c[y][x] = r[-1] if y == 1 else r[-2]
    # 兩道深色箍
    for by in (int(h * 0.35), int(h * 0.68)):
        for x in range(w):
            if 0 <= by < h and c[by][x] != ".":
                c[by][x] = b[max(0, len(b) - 3)]
    return _grid(c)
