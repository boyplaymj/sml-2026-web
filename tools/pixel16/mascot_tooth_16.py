"""
pixel16 風格錨 —— 牙齒吉祥物 🦷 的 16-bit 版。

示範「同 pixel8 方法、拿到 16bit 份量感」:
  只算左半 → 沿 enamel ramp 上多階光影 → mirror_h → add_outline → 底模
  → shift_ramp 秒出金/薄荷/珊瑚變體(光影階數保留,非平塗換色)
  → overlay 鏡面反光 → make_sheet 對照表。
只手工定義「形狀輪廓 + 受光方向」,其餘全由元件庫長出來。
"""
import os
from engine16 import (
    mirror_h, add_outline, shift_ramp, overlay, make_sheet, render, RAMPS,
)

OUT = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT, exist_ok=True)

# ── 左半牙齒輪廓:每列 (xl, xr) = 該列填色的欄區間(0..13,col13=中線)──
# 上段=牙冠(圓潤漸寬),下段=牙根(中線讓出縫隙,鏡射後成臼齒雙根)。
HW = 14  # 半寬(含中線)
HALF_SPAN = [
    (6, 13), (4, 13), (3, 13), (2, 13), (1, 13), (1, 13),   # 牙冠頂→漸寬
    (0, 13), (0, 13), (0, 13),                               # 最寬
    (1, 13), (1, 13), (2, 13), (3, 13),                      # 牙冠收窄
    (4, 13),                                                 # 牙頸
    (4, 11), (4, 10), (4, 9), (5, 9), (5, 8), (6, 8), (6, 7), (7, 7),  # 牙根
]
H = len(HALF_SPAN)

ENAMEL = RAMPS["enamel"]  # ['6','7','8','9'] 暗→亮


def shaded_half():
    """建左半牙:沿對角受光(左上最亮)把 enamel ramp 上成多階光影。"""
    rows = []
    for y, (xl, xr) in enumerate(HALF_SPAN):
        row = []
        for x in range(HW):
            if not (xl <= x <= xr):
                row.append(".")
                continue
            # 圓潤受光:中央頂部最亮、外緣與下方漸暗 → 鏡射後成圓弧體積高光脊
            t = ((HW - 1 - x) / (HW - 1)) * 0.5 + (y / (H - 1)) * 0.5
            idx = 3 - min(3, int(t * 4))
            if y >= 13:            # 牙根整體壓暗一階(離光源遠)
                idx = max(0, idx - 1)
            if (HW - 1 - x) + y <= 4:   # 中央頂部鏡面高光點
                idx = 3
            row.append(ENAMEL[idx])
        rows.append("".join(row))
    return rows


def build():
    half = shaded_half()
    base = add_outline(mirror_h(half), diagonal=True)   # 對稱 + 統一描邊 = 白牙底模

    # 一個上好光的底模 → 整條 ramp 平移,秒出同光影的材質變體
    gold = shift_ramp(base, "enamel", "gold")
    mint = shift_ramp(base, "enamel", "mint")
    coral = shift_ramp(base, "enamel", "coral")

    # 鏡面反光小星(疊在左上高光處)——金牙用金高光 'e',其餘用白 '9'
    W = len(base[0])
    spark = ["." * W for _ in base]
    def put(g, sx, sy, c):
        star = [".{}.".format(c), "{}{}{}".format(c, c, c), ".{}.".format(c)]
        return overlay(g, star, sx, sy)
    base = put(base, 12, 2, "9")
    gold = put(gold, 12, 2, "e")
    mint = put(mint, 12, 2, "9")
    coral = put(coral, 12, 2, "9")

    # 單張放大 + 四款對照精靈表
    for name, g in [("tooth16", base), ("tooth16_gold", gold),
                    ("tooth16_mint", mint), ("tooth16_coral", coral)]:
        render(g, scale=12, path=os.path.join(OUT, name + ".png"))

    sheet = make_sheet([base, gold, mint, coral], cols=4, gap=2)
    render(sheet, scale=10, path=os.path.join(OUT, "tooth16_sheet.png"))
    print("寫出:", os.listdir(OUT))


if __name__ == "__main__":
    build()
