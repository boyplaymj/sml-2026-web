# Codex 複驗交接 · 每日車牌 app(tools/plate-daily)

**背景**:每日推 4 張車牌圖(號碼=番號)的 app,先在 Discord 跑。分級鐵律=**只發年齡限制封閉頻道**,程式不得弱化這點。後端全 Python;渲染走 HTML+playwright / PIL 合成。

請複驗以下 Python(未 commit),重點=**正確性 / 邊界 / 安全 / 資源**。逐檔給 findings(severity + 檔:行 + 建議),不用改檔,交回我來修。

## 檔案與職責
- `db.py` — DynamoDB `sml-plate-codes`(ap-southeast-1)資料層:normalize_code / add_codes(去重寫入)/ count / pick_for_today / mark_posted / set_image_url
- `ingest.py` — 灌號碼 CLI(參數 / -f 檔 / stdin)
- `render.py` — ensure_plate(code):本地快取權威→上傳圖床→回填 imageUrl;字庫齊用 montage、缺字走字型 fallback
- `daily.py` — 每日管線:pick 4→ensure_plate→make_collage→post-image.sh 發頻道→mark_posted
- `montage.py` — 拼字合成器(真字元圖→疊到 car_base3 牌面)
- `clean_glyphs.py` — 字元清理(cv2 上採/平滑/浮凸)

## 我自己已標的可疑處(請重點查證)
1. **指令/字串注入**:`render._font_fallback` 把 `code` 用 f-string 插進 `python3 -c` 的原始碼 + URL query;`daily.post` 走 `post-image.sh`。理論上 code 已經 `normalize_code`(僅 `^[A-Z]{2,6}-\d{2,5}$`)才會到這,但請確認**所有進入 subprocess/HTML/JS 的 code 都保證正規化過**,無旁路。
2. **同號=同圖**:ensure_plate 以「本地 cache 檔存在」為準則重用。若 cache 存在但 DB `imageUrl` 未回填(例如先前 --dry upload=False),正式跑會**跳過上傳、永不回填**。這是漏洞嗎?要不要改成「檔在但無 imageUrl 時補上傳」?
3. **pick_for_today**:全表 scan 後 in-memory 排序(postedCount↑, lastPostedAt↑,空字串優先);同分用 random.shuffle。表大時 scan 成本/分頁?排序穩定性?
4. **add_codes 去重**:ConditionExpression attribute_not_exists(code) + 批內 seen set。ClientError 只攔 ConditionalCheckFailed,其餘 raise。正確?
5. **mark_posted**:逐筆 update_item(if_not_exists+ +1),非交易。4 筆中途失敗會半套,要緊嗎?
6. **make_collage 字型**:寫死 NotoSansCJK 路徑,找不到退 load_default(CJK 會變豆腐)。要不要 fail-loud?
7. **normalize_code 邊界**:全形空白、前導零保留、前綴 2–6 字母上限(NEWCODE 7 字被判無效,合理?);番號有 6+ 字母或帶尾碼(如 SSIS-698R)的要不要支援?

## 驗收點(Codex 回報時對照)
- [ ] normalize/dedup:大小寫、無分隔、全形、重複、格式錯 → 分類正確
- [ ] 快取重用:同 code 二次不重生、不覆蓋既有 imageUrl
- [ ] 輪播:已推過的排到最後、沒推過優先
- [ ] 無注入面:code 進 shell/JS/HTML 前必經正規化
- [ ] 分級不外洩:daily 預設不會發到公開頻道(TEST_CHANNEL/--channel)
- [ ] 資源:scan 有分頁、無明顯 N+1 / 併發競態致命傷

## 不在本輪範圍
- 破圖/字型美觀(靠更好來源,另議)
- 完整字庫 A-Z+0-9(待素材)
- 爬蟲(選配,未做)
