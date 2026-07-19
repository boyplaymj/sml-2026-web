"""
pixel16 — 16-bit 設計系統(SNES / Mega Drive 世代風)。

與 pixel8 同一套哲學、同一支幾何引擎 —— 鏡射 / 描邊 / 疊圖 / 精靈表全部
「原封不動複用」 pixel8.engine(那些函式與調色盤無關)。16bit 只放寬兩處:

  1. 調色盤:16 色平塗 → **數十色、多階明暗 ramp**(受光→中間→陰影→反光)。
  2. 上色習慣:平塗色塊 → 沿 ramp 上多階光影,做出金屬反光/份量感。

── 8bit 沒有、16bit 才有的核心函式 ─────────────────────────────
  RAMPS              具名漸層(steel/enamel/gold/mint/coral/azure/violet/skin),
                     每條 = 由暗到亮的字元 list。手畫時照 ramp 階數上光影。
  shift_ramp(g,a,b)  把「用 ramp a 畫好光影」的底模,整條平移到 ramp b。
                     → 光影階數對齊保留,一個上好光的底模秒出金屬/薄荷/珊瑚變體。
                     這是 16bit 版的複利核心(8bit 的 recolor 只能平換單色)。

其餘 blank/flip_h/flip_v/mirror_h/recolor/overlay/add_outline/make_sheet/render
全部從 pixel8.engine import,零重寫。render 傳 palette=PALETTE16 即用本盤渲染。
"""
import os
import sys

# 複用 pixel8 引擎(同哲學、同函式,不重造輪子)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pixel8"))
from engine import (  # noqa: E402
    blank, flip_h, flip_v, mirror_h, recolor, overlay,
    add_outline, make_sheet, render as _render8,
)


# ── PALETTE16:多階漸層盤(33 色,索引 0-9 + a-w)──────────────────
# 每種材質是一條「暗→亮」ramp,故能上多階光影、也能整條平移換材質。
PALETTE16 = {
    ".": None,            # 透明
    # 鋼/中性 ramp(描邊 + 灰階陰影)—— '0' 是全系統統一描邊色
    "0": (13, 13, 22),    # 描邊/最深
    "1": (34, 32, 52),
    "2": (58, 54, 82),
    "3": (94, 90, 120),
    "4": (139, 138, 165),
    "5": (203, 204, 219),
    # 琺瑯/牙白 ramp(冷調高光,牙體主色)
    "6": (188, 204, 222),  # 陰影
    "7": (216, 228, 240),  # 中間
    "8": (244, 249, 253),  # 受光
    "9": (255, 255, 255),  # 反光高光
    # 金/金屬 ramp(高對比 + 鏡面反光 = 金屬感關鍵)
    "a": (92, 52, 20),     # 暗銅
    "b": (156, 100, 34),
    "c": (216, 154, 56),
    "d": (247, 206, 96),
    "e": (255, 242, 176),  # 鏡面高光
    # 薄荷/綠 ramp
    "f": (32, 90, 72),
    "g": (56, 150, 112),
    "h": (108, 214, 158),
    "i": (192, 247, 216),
    # 珊瑚/紅 ramp
    "j": (120, 32, 52),
    "k": (188, 58, 82),
    "l": (234, 106, 112),
    "m": (252, 174, 164),
    # 天藍 ramp
    "n": (26, 52, 108),
    "o": (46, 98, 182),
    "p": (88, 160, 242),
    "q": (172, 216, 250),
    # 紫 ramp
    "r": (70, 40, 104),
    "s": (128, 74, 170),
    "t": (198, 152, 226),
    # 膚/暖 ramp
    "u": (156, 86, 72),
    "v": (226, 152, 122),
    "w": (251, 208, 182),
}

# ── 具名 ramp:由暗到亮。手畫上光影就照這幾階挑字元 ──────────────
RAMPS = {
    "steel":  list("012345"),
    "enamel": list("6789"),
    "gold":   list("abcde"),
    "mint":   list("fghi"),
    "coral":  list("jklm"),
    "azure":  list("nopq"),
    "violet": list("rst"),
    "skin":   list("uvw"),
}


def shift_ramp(grid, src, dst):
    """把用 ramp `src` 畫好光影的底模,整條平移到 ramp `dst`,光影階數對齊保留。
    src/dst 可傳 RAMPS 的 key 字串或字元 list。長度不同時就近取端點。
    例:enamel 牙 → shift_ramp(g,'enamel','gold') = 上好光的金牙,高光陰影全在。"""
    s = RAMPS[src] if isinstance(src, str) else src
    d = RAMPS[dst] if isinstance(dst, str) else dst
    n = len(s)
    mapping = {}
    for i, ch in enumerate(s):
        # 把 src 的第 i 階,線性對映到 dst 對應階(長度不同時等比縮放)
        j = round(i * (len(d) - 1) / (n - 1)) if n > 1 else 0
        mapping[ch] = d[j]
    return recolor(grid, mapping)


def render(grid, scale=12, path=None, bg=None):
    """pixel16 專用渲染:同 pixel8.render,但預設吃 PALETTE16。"""
    return _render8(grid, scale=scale, path=path, bg=bg, palette=PALETTE16)


__all__ = [
    "blank", "flip_h", "flip_v", "mirror_h", "recolor", "overlay",
    "add_outline", "make_sheet", "render",
    "PALETTE16", "RAMPS", "shift_ramp",
]
