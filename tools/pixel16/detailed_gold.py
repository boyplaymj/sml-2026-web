"""
pixel16 上限展示 —— 單體高質感金磚(和 cargo 的簡單三顆堆對照)。

同一支引擎、同一盤色,差別只在「堆多少細節」:
  大畫布 + 等角立體(頂面/前面/側面三面) + 對角鏡面反光 + 壓印章面
  + 邊緣受光(rim light) + 落地陰影。
證明「程式擺像素」的天花板遠高於前面的示範,只是每張手工更多。
"""
import os
from engine16 import add_outline, overlay, blank, render

OUT = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT, exist_ok=True)

W, H = 46, 34
# 金 ramp:a暗銅 b c d e亮  ；'9'=純白(金屬最強鏡面反光)
A, B, C, D, E, HI = "a", "b", "c", "d", "e", "9"


def _cv():
    return [["."] * W for _ in range(H)]


def _g(c):
    return ["".join(r) for r in c]


def px(c, x, y, ch):
    if 0 <= y < H and 0 <= x < W:
        c[y][x] = ch


def build_bar():
    """正面視角高質感金磚:圓角 + 浮凸邊框 + 對角掃光 + 凹刻章面 + 壓紋線。"""
    c = _cv()
    L, R, T, B_ = 6, 39, 5, 28          # 磚體外框
    cx = (L + R) / 2

    def rounded(x, y):
        """圓角矩形內?(四角各削 2px)。"""
        if not (L <= x <= R and T <= y <= B_):
            return False
        for (cxr, cyr) in [(L + 2, T + 2), (R - 2, T + 2), (L + 2, B_ - 2), (R - 2, B_ - 2)]:
            corner = (x < L + 2 and y < T + 2) or (x > R - 2 and y < T + 2) or \
                     (x < L + 2 and y > B_ - 2) or (x > R - 2 and y > B_ - 2)
            if corner and (x - cxr) ** 2 + (y - cyr) ** 2 > 2 * 2 + 1:
                return False
        return True

    # ── 底色 + 橫向柱面漸層(中央亮脊、兩側漸暗)──
    for y in range(T, B_ + 1):
        for x in range(L, R + 1):
            if not rounded(x, y):
                continue
            u = abs(x - (cx - 2)) / (R - L) * 2      # 0中央..1邊緣
            ch = E if u < 0.18 else D if u < 0.45 else C if u < 0.78 else B
            px(c, x, y, ch)

    # ── 浮凸邊框:左上受光亮邊、右下陰影暗邊 ──
    for y in range(T, B_ + 1):
        for x in range(L, R + 1):
            if not rounded(x, y):
                continue
            top_left = (not rounded(x - 1, y)) or (not rounded(x, y - 1))
            bot_right = (not rounded(x + 1, y)) or (not rounded(x, y + 1))
            if top_left:
                px(c, x, y, E)
            elif bot_right:
                px(c, x, y, A)

    # ── 對角鏡面掃光(金屬關鍵:亮帶 + 白核)──
    for y in range(T + 1, B_):
        for x in range(L + 1, R):
            if not rounded(x, y):
                continue
            band = (x - L) - (y - T) * 1.25 - (R - L) * 0.30
            if -2 <= band <= 3:
                c[y][x] = E
            if -0.5 <= band <= 1:
                c[y][x] = HI

    # ── 上下壓紋線(emboss:暗線+亮線=刻痕)──
    for x in range(L + 3, R - 2):
        if rounded(x, T + 3):
            px(c, x, T + 3, A); px(c, x, T + 4, E)
        if rounded(x, B_ - 3):
            px(c, x, B_ - 3, A); px(c, x, B_ - 2, E)

    # ── 中央凹刻章面 + 菱形寶石印記 ──
    pcx, pcy = int(cx), 17
    for yy in range(pcy - 4, pcy + 5):
        for xx in range(pcx - 8, pcx + 9):
            if not rounded(xx, yy):
                continue
            edge = xx in (pcx - 8, pcx + 8) or yy in (pcy - 4, pcy + 4)
            inner_hi = (xx == pcx - 7 or yy == pcy - 3)
            c[yy][xx] = A if edge else (D if inner_hi else C)   # 凹陷立體
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if abs(dx) + abs(dy) <= 3:
                px(c, pcx + dx, pcy + dy, HI if (dx + dy) < -1 else E if (dx + dy) < 1 else C)

    return _g(c)


def build():
    bar = add_outline(build_bar(), diagonal=True)

    # 落地陰影(在描邊後合成於下層,不被描邊包住)
    shadow = _cv()
    for x in range(9, 40):
        for y in range(29, 32):
            if (x - 24) ** 2 / 16 ** 2 + (y - 30) ** 2 / 1.5 ** 2 <= 1:
                shadow[y][x] = "1"                # steel 深色半透感
    scene = overlay(_g(shadow), bar, 0, 0)

    render(bar, scale=12, path=os.path.join(OUT, "gold_detailed.png"))
    render(scene, scale=12, path=os.path.join(OUT, "gold_detailed_scene.png"))
    print("寫出: gold_detailed.png / gold_detailed_scene.png")


if __name__ == "__main__":
    build()
