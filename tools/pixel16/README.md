# pixel16 — 16-bit(SNES / Mega Drive 世代)像素風產線

`pixel8` 的大哥。**同一套方法、同一支幾何引擎**,只放寬兩處拿到 16bit 份量感:

| | pixel8(8bit) | pixel16(16bit) |
|---|---|---|
| 色數 | SWEETIE-16 鎖 16 色、平塗 | 33 色**多階漸層盤**、上多階光影 |
| 立體 | 描邊 + 1~2 階陰影 | 4~5 階明暗 **ramp** + 鏡面反光 |
| 尺寸 | 16×16 常見 | 28×28、32×32 起,細節更多 |
| 味道 | 卡通色塊、可愛 | 金屬反光、材質、圓弧體積、有份量 |

## 為什麼幾乎沒重寫程式
`mirror_h / add_outline / recolor / overlay / flip / make_sheet` 全部**與調色盤無關**,
`engine16.py` 直接從 `../pixel8/engine.py` import 複用。`render()` 只是把 pixel8 那支
加了 `palette=` 參數後,綁上 `PALETTE16` 的薄包裝。16bit 真正新增的只有兩樣東西 👇

## 16bit 專屬 API(8bit 沒有)
```python
from engine16 import RAMPS, shift_ramp, render, mirror_h, add_outline, overlay, make_sheet

RAMPS            # 具名漸層:steel/enamel/gold/mint/coral/azure/violet/skin
                 # 每條 = 由暗到亮的字元 list。手畫時照 ramp 階數上光影。

shift_ramp(g, 'enamel', 'gold')
    # 把「用 enamel ramp 畫好光影」的底模,整條平移到 gold ramp,
    # 光影階數對齊保留 → 一個上好光的底模秒出金屬/薄荷/珊瑚變體。
    # 這是 16bit 版的複利核心:8bit 的 recolor 只能平換單色,
    # shift_ramp 換的是「整條光影梯度」,材質變了、光還在。
```

## 做新 16bit 資產的流程
1. **挑 ramp**：物件主材質對到 `RAMPS`(牙=enamel、金幣=gold、藥水=mint…)。
2. **只畫一半**(對稱物件)：沿 ramp 由暗到亮上多階光影,想好受光方向(中央頂部最亮 = 圓弧體積)。
3. `mirror_h` 補另一半 → `add_outline(..., diagonal=True)` 統一描邊。
4. `shift_ramp` 一行一個材質變體(全保留光影)。
5. `overlay` 疊鏡面反光小星 / 配件。
6. `make_sheet` + `render(scale=..)` 出精靈表 PNG。

範例見 `mascot_tooth_16.py`(牙齒吉祥物 🦷 16bit 風格錨):
只手工定義輪廓 + 受光,元件庫自動長出白牙 + 金/薄荷/珊瑚三材質變體 + 對照精靈表。
```bash
cd tools/pixel16 && python3 mascot_tooth_16.py   # 產物在 out/(不入庫)
```

## 8bit vs 16bit 怎麼選
- **Discord emoji、小圖示、可愛吉祥物** → `pixel8`(小巧、辨識度高、色塊乾淨)。
- **道具/怪物/招牌 sprite,要金屬感、材質、份量** → `pixel16`。
- 兩者共用同一批幾何函式,**同一個人畫完 8bit 再上 16bit 幾乎零學習成本**。
