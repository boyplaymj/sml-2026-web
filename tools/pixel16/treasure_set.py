"""
pixel16 精緻貴重物件組 —— 深化方向的成果展示。

一個「精緻金板」畫一次(套 parts/metal.py 的技法),shift_ramp 秒出四材質:
  金 / 銀(鋼) / 翡翠 / 紅寶  —— 光影、掃光、凹刻章面、寶石全保留。
證明:精緻化技法函式化後,高質感也能跑複利(一形狀 → 多貴重材質)。
"""
import os
from engine16 import add_outline, overlay, blank, make_sheet, render, shift_ramp
from parts.metal import plate, emboss_line, inset_panel, gem

OUT = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT, exist_ok=True)


def detailed_bar(ramp):
    """精緻金屬板:plate + 上下壓紋 + 中央凹刻章面 + 菱形寶石。"""
    w, h = 40, 26
    g = plate(ramp, w, h, rad=3, sheen=0.30)
    g = emboss_line(g, 5, w - 6, 4, ramp)
    g = emboss_line(g, 5, w - 6, h - 6, ramp)
    g = inset_panel(g, w // 2, h // 2, 9, 4, ramp)
    g = gem(g, w // 2, h // 2, 3, ramp)
    return g


def build():
    # 金板畫一次,shift_ramp 換材質(白色鏡面高光 '9' 不屬 ramp → 各材質都保留)
    gold = detailed_bar("gold")
    silver = shift_ramp(gold, "gold", "steel")
    jade = shift_ramp(gold, "gold", "mint")
    ruby = shift_ramp(gold, "gold", "coral")

    named = [("gold", gold), ("silver", silver), ("jade", jade), ("ruby", ruby)]
    frames = []
    for name, g in named:
        out = add_outline(g, diagonal=True)
        render(out, scale=12, path=os.path.join(OUT, "treasure_%s.png" % name))
        # 統一貼進 44×30 畫布排表
        canvas = overlay(blank(44, 30), g, 2, 2)
        frames.append(add_outline(canvas, diagonal=True))

    sheet = make_sheet(frames, cols=2, gap=3)
    render(sheet, scale=9, path=os.path.join(OUT, "treasure_sheet.png"))
    print("寫出: treasure_{gold,silver,jade,ruby}.png + treasure_sheet.png")


if __name__ == "__main__":
    build()
