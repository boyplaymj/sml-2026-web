"""
pixel8 — 8-bit 設計系統核心引擎 + 元件庫（可重用複利地基）

哲學：不「生成」圖，而用「確定性程式擺像素」組裝圖。
- 一套鎖定調色盤 PALETTE 保證跨遊戲風格統一。
- sprite = 字元網格（list[str]，每格=調色盤索引字元，'.'=透明）。
- 新資產 = 挑零件、鏡射、換色、疊圖 → 秒出、像素精準、天生同風格。

── 元件庫 API（讓第二款遊戲用「拼裝」而非「重畫」）────────────────
  mirror_h(left)          左半 → 完整左右對稱圖（對稱物件只畫一半）
  add_outline(g)          自動描邊（畫填色即可，描邊統一交給程式 → 風格一致）
  recolor(g, mapping)     換色出變體（一個底模 → 無限同風格配色變體）
  overlay(base, top,x,y)  疊圖組裝（底模 + 換帽子/道具/表情零件）
  flip_h / flip_v(g)      水平/垂直翻轉
  make_sheet(frames,...)  多幀 → 精靈表（動畫/批次匯出）
  render(g, scale, path)  網格 → PNG（最近鄰放大保硬邊）
"""
from PIL import Image

# ── SWEETIE-16 調色盤（GrafxKid，公有領域常用像素配色）─────────────
PALETTE = {
    ".": None,           # 透明
    "0": (26, 28, 44),   # 近黑 — 描邊主色
    "1": (93, 39, 93),   # 紫
    "2": (177, 62, 83),  # 紅
    "3": (239, 125, 87), # 橘 — 腮紅/暖色
    "4": (255, 205, 117),# 黃
    "5": (167, 240, 112),# 亮綠
    "6": (56, 183, 100), # 綠
    "7": (37, 113, 121), # 深青
    "8": (41, 54, 111),  # 深藍
    "9": (59, 93, 201),  # 藍
    "a": (65, 166, 246), # 亮藍
    "b": (115, 239, 247),# 青
    "c": (244, 244, 244),# 白 — 牙體主色
    "d": (148, 176, 194),# 淺灰 — 陰影/立體
    "e": (86, 108, 134), # 灰
    "f": (51, 60, 87),   # 深灰
}


# ── 網格幾何運算（純字串，無副作用）─────────────────────────────
def blank(w, h, fill="."):
    """空白畫布。"""
    return [fill * w for _ in range(h)]


def flip_h(grid):
    """水平翻轉。"""
    return [row[::-1] for row in grid]


def flip_v(grid):
    """垂直翻轉。"""
    return list(reversed(grid))


def mirror_h(left):
    """左半 → 完整左右對稱圖。對稱 sprite 只需畫一半，工作量減半。"""
    return [row + row[::-1] for row in left]


def recolor(grid, mapping):
    """換色。mapping={'c':'4'} → 白牙變金牙。一個底模秒出多款同風格變體。"""
    return ["".join(mapping.get(ch, ch) for ch in row) for row in grid]


def overlay(base, top, ox=0, oy=0, transparent="."):
    """把 top 疊到 base 上（top 的透明格保留 base）。= 換帽子/道具/表情的零件組裝。"""
    rows = [list(r) for r in base]
    H, W = len(rows), len(rows[0])
    for y, row in enumerate(top):
        for x, ch in enumerate(row):
            if ch == transparent:
                continue
            by, bx = oy + y, ox + x
            if 0 <= by < H and 0 <= bx < W:
                rows[by][bx] = ch
    return ["".join(r) for r in rows]


def add_outline(grid, ink="0", bg=".", diagonal=False):
    """自動描邊：在填色圖形外緣的透明格補上 ink。
    只畫填色、描邊交給程式 → 所有 sprite 的邊線粗細/顏色天生一致。"""
    h, w = len(grid), len(grid[0])
    nb = ([(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
          if diagonal else [(-1, 0), (1, 0), (0, -1), (0, 1)])
    rows = [list(r) for r in grid]
    for y in range(h):
        for x in range(w):
            if grid[y][x] != bg:
                continue
            for dy, dx in nb:
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and grid[ny][nx] not in (bg, ink):
                    rows[y][x] = ink
                    break
    return ["".join(r) for r in rows]


def make_sheet(frames, cols=None, gap=0, gap_fill="."):
    """多張同尺寸網格 → 精靈表（動畫幀 / 批次變體）。"""
    if not frames:
        return []
    fh, fw = len(frames[0]), len(frames[0][0])
    n = len(frames)
    cols = cols or n
    rows_of = (n + cols - 1) // cols
    sheet = []
    for r in range(rows_of):
        band = ["" for _ in range(fh)]
        for c in range(cols):
            idx = r * cols + c
            cell = frames[idx] if idx < n else blank(fw, fh, gap_fill)
            for y in range(fh):
                band[y] += cell[y] + (gap_fill * gap if c < cols - 1 else "")
        sheet.extend(band)
        if gap and r < rows_of - 1:
            sheet.extend([gap_fill * len(band[0]) for _ in range(gap)])
    return sheet


# ── 渲染 ─────────────────────────────────────────────────────
def render(grid, scale=16, path=None, bg=None, palette=None):
    """字元網格 → PNG。scale=放大倍數；bg=None 透明背景，或給調色盤字元當底色。
    palette=None 用內建 SWEETIE-16；傳入自訂 dict（如 pixel16 的漸層盤）即可同引擎渲染 16bit。"""
    pal = palette if palette is not None else PALETTE
    h, w = len(grid), len(grid[0])
    for i, row in enumerate(grid):
        if len(row) != w:
            raise ValueError(f"第 {i} 列長度 {len(row)} ≠ {w}（網格必須矩形）")
        for ch in row:
            if ch not in pal:
                raise ValueError(f"第 {i} 列有未定義字元 {ch!r}")
    base = (0, 0, 0, 0) if bg is None else (*pal[bg], 255)
    img = Image.new("RGBA", (w, h), base)
    px = img.load()
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            rgb = pal[ch]
            if rgb is not None:
                px[x, y] = (*rgb, 255)
    if scale != 1:
        img = img.resize((w * scale, h * scale), Image.NEAREST)
    if path:
        img.save(path)
    return img
