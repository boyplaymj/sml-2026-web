# 火車大亨 · 車庫「正面圖」生成規格（Gemini 用）

車庫大畫面用的**正面 3/4 視角**車輛素材規格。與側視 emoji tile 是兩套並存：
側視 tile 用於文字 consist（在途/派車/發車），**正面圖只用於車庫疊圖大畫面**。

## 🎯 最高原則：角度鎖死
每一台車都必須用**完全相同**的相機角度、高度、取景、光照方向、比例，否則排在一起會歪、
無法連續重疊。**先生 D51 當「錨圖」，之後每一台都叫 Gemini「沿用上一張的完全相同視角」**
（同一對話接續生成，或把錨圖當參考圖附上），只換車型/塗裝。

## 固定 Prompt 模板
把 `[SUBJECT]` 換成下面各車的描述，其餘一字不改：

```
Pixel art, 16-bit retro railroad tycoon game style. Three-quarter FRONT view of a single [SUBJECT].
Camera is slightly above the roof line looking gently down. The FRONT of the vehicle faces the viewer,
rotated about 30 degrees so the LEFT side recedes into the distance (front face on the right, side on the left).
The whole vehicle is fully visible and centered, occupying most of the frame height, wheels near the bottom edge.
Rich cel shading, thick clean dark outline, crisp detail, consistent top-left light source.
Pure flat WHITE background, studio isolated. No ground, no tracks, no shadow, no scenery, no people, no text, no border.
Square 1:1 composition.
```

## 各車 `[SUBJECT]`
**車頭（5）**
- `tt_d51_front`　— a black JR Class D51 steam locomotive, round smokebox door on the front, red buffer beam, brass details
- `tt_kiha40_front` — a JR KiHa 40 diesel railcar, cream/ivory body with a bright vermilion-red waistband stripe, boxy cab front with two windows
- `tt_dd51_front`　— a JR Class DD51 diesel locomotive, vermilion-red body with a grey lower skirt and thin white stripes, boxy cab
- `tt_ef210_front` — a JR EF210 electric freight locomotive, blue body with white stripes and light-grey lower band, a pantograph on the roof
- `tt_eh500_front` — a JR EH500 twin-unit electric locomotive, dark crimson-red and black body with gold accent lines, pantographs on roof

**車廂（依需要）**
- `tt_koki_front`　— a JR flat wagon carrying one bright RED rectangular shipping container
- `tt_koki_blue_front` — a JR flat wagon carrying one BLUE rectangular shipping container
- `tt_chi_front`　— a JR low flat wagon, dark steel deck with short side stakes, no load (a low platform seen from the front corner)
- `tt_wamu_front`　— a brown/tan covered boxcar with a sliding side door
- `tt_taki_front`　— a silver-grey cylindrical tank wagon on a black underframe
- `tt_remu_front`　— a white insulated refrigerated reefer boxcar with a sliding door

## 輸出要求
- **正方形 1:1**、解析度 ≥ 512px（越大越好，我這端會縮）。
- **純白或透明底**、單一主體、整台入鏡、車輪貼近下緣。
- 檔名 `tt_<id>_front.png`。一張張或一起丟都行。

## 我這端會做
去背 → 依車輪基線統一縮放/對齊 → 疊進機關庫背景、連續重疊排版 → 依車隊簽章快取成一張 PNG。
所以你只要顧**角度一致**；輕微的比例/位置我可校正，但**角度事後救不了**，這是你生成時的唯一硬要求。

## 一致性小技巧（Gemini）
1. 先生 `tt_d51_front` 當錨圖，滿意再繼續。
2. 之後每台：同一對話接著說「**same exact camera angle, height, framing, lighting and pixel style as the previous image, white background — now generate [下一台 SUBJECT]**」，或把錨圖當參考圖附上。
3. 若某台角度飄了就重生，別將就（歪一台整排就毀）。
