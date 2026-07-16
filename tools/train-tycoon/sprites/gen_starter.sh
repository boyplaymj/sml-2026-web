#!/usr/bin/env bash
# 生一套「風格鎖定」starter sprite 集 → 全部走同一 STYLE 前綴(生成期一致性)
# 之後 pixelize.py 一次吃全部、共用 24 色調色盤(後處理期一致性)
# 用法: bash gen_starter.sh   (輸出到 /tmp/train-starter/*.png)
set -euo pipefail
cd "$(dirname "$0")"
OUT=${OUT:-/tmp/train-starter}
mkdir -p "$OUT"

# ── 鎖定風格錨:8-bit + 高角度俯瞰斜角(看不到天空的鳥瞰 iso)──
STYLE="8-bit pixel art sprite, high-angle top-down oblique bird's-eye view, steep isometric camera \
looking down from above at about 60 degrees, NO sky, NO horizon, object seen from directly above and \
slightly in front so its roof and top surface are clearly visible, sitting flat on the ground, \
retro NES aesthetic, chunky blocky pixels, very limited flat palette, hard flat cel shading, \
single centered object isolated on pure flat white background, no cast shadow, no text, no logo, no border"

gen () { # gen <name> <subject>
  local name="$1"; shift
  local subj="$*"
  echo "── gen $name"
  python3 bedrock_gen.py "$STYLE, $subj" "$OUT/$name.png" "1:1"
}

# ── 動力車(俯瞰:看得到車頂,沿軌斜放)──
gen loco_d51   "a black JR D51 steam locomotive seen from a high top-down angle, roof and boiler top visible, positioned diagonally along the track, white steam puffing from the top"
gen loco_ef210 "a blue-and-grey JR EF210 electric freight locomotive seen from a high top-down angle, roof with pantographs visible, positioned diagonally along the track"
gen loco_n700s "a sleek white JR N700S shinkansen seen from a high top-down angle, long rounded roof and blue stripe visible from above, positioned diagonally"

# ── 貨車廂(俯瞰:看得到裝載頂面)──
gen car_koki   "a JR KOKI container flatcar seen from a high top-down angle, tops of two stacked shipping containers visible, positioned diagonally along the track"

# ── 站房(俯瞰:看得到屋頂與月台佔地)──
gen sta_t1     "a very small rural wooden unmanned train stop seen from a high top-down angle, tiny slanted roof and a short single platform footprint visible from above"
gen sta_t3     "a regional city train station building seen from a high top-down angle, rooftop and multiple platform tracks footprint visible from above, brick and glass with a clock tower"

# ── 地面 tile(俯瞰菱形,無縫留程式/tile 包)──
gen tile_grass "a single flat isometric diamond ground tile seen straight top-down, green grass texture, one straight railway track segment crossing the middle"

echo "ALL DONE → $OUT"
ls -la "$OUT"/*.png
