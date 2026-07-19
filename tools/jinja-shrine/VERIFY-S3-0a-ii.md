# ⛩️ 神社 S3-0a-ii（面板互動接線）· Codex 查驗交接單

> **範圍**：STAGE3 §8 第二格。把 S3-0a-i 純核心接成 Discord 面板 handler + discord.js 註冊。
> 實作＝Fable 5、已 Opus 覆核。依據:`HANDOFF-S3-0a.md §1/§5`。
> ⚠️ **互動流程無法離線測**(要 bot restart 手動點)→ Codex 查**程式正確性**;實機點測留 S2 部署窗口。

## 0. 讀哪些檔
權威 sweetbot-next commit `e9fe271`(未 push);Codex 讀 repo 唯讀副本 `tools/jinja-shrine/impl-s3/`:
```
impl-s3/model/shrine/Shrine.js       + imports/三陣列/handler(openEntrance/enter/bow/navigate)/component(_entranceRow/_bowInRow/_navComponents);S3-0a-i 純方法未動
impl-s3/test/shrinePanel.test.js     19 測(+4 component 組裝)
```
**discord.js 只加 5 行(未複製整檔;diff 見 §2)**。
**測試:`node --test test/shrinePanel.test.js` = 19 pass;全 shrine 套件 = 65 pass / 0 fail(既有零破壞)。**

## 1. 流程正確性
- [ ] `!神社`(command,criminalAccess:'block')→ `openEntrance`:公開 reply 一行 + `[⛩️ 甜甜神社へ]`(shrenter)。
- [ ] `shrenter` → `enter`:`openVisit(id,now)` 拿舊 lastVisit → `_shitsureiOnEnter` → 失礼則 `appendBuff` → **reply ephemeral:torii 圖 + 只給 `[🙇 一礼して入る]`(硬門,不給導覽)**;失礼附神職文字(無數字)。
- [ ] `shrbow`(args in/out)→ `bow`:`in` → update 給導覽下拉 + 退場鈕;`out` → `closeVisit` → update 清空 components(乾淨退場)。
- [ ] `shrnav`(select)→ `navigate`:`struct.values[0]` → update `_panel(locKey)` + 導覽。
- [ ] **openVisit 必先於 closeVisit**:closeVisit 巢狀路徑(`SET lastVisit.closed`),bow-out 只在 enter(openVisit)之後可按 → 安全。
- [ ] 所有 interaction.reply/update 帶 `.catch`;handler try/catch 降級不炸互動。
- [ ] 運氣黑箱:失礼只給文字、無數字。

## 2. discord.js（只加 5 行，零他改）
```
+const Shrine = require('./model/shrine/Shrine.js');
+const shrine = new Shrine(connectionPool, redis);
+      ...shrine.commands,   // commands 匯總
+        ...shrine.buttons,  // buttons 匯總
+        ...shrine.selects,  // selects 匯總
```
- [ ] `git diff discord.js` 僅此 5 加、無刪除、無他動。
- [ ] commit scope 僅 `discord.js` + `model/shrine/Shrine.js` + `test/shrinePanel.test.js`(**未含 PokingFun.js 等別 session 髒檔**)。

## 3. component 組裝(可測)
- [ ] `_entranceRow`/`_bowInRow`/`_navComponents` customId 用 `getCustomID`(shrenter/shrbow['in'|'out']/shrnav);下拉 9 選項＝navFacilities()。
- [ ] `_navComponents` 回 2 個 ActionRow(下拉 + 退場鈕)。

## 4. 已知/刻意(非 bug)
- buttons/selects 加 `usePermission:0`(對齊 codebase 慣例)。
- `getCustomID('shrnav',[])`→`'shrnav-'`(尾 tag),派發 `split` 後 name 正確(全站同款,測試有驗)。
- 未測=實機互動流程(reply/update/ephemeral/下拉),restart 後手動:`!神社`→進場→一礼→下拉換 9 景→退場礼;失礼路徑=進場後不退場再進場一次見斥責句。

## 5. Findings 回報
Blocking / Non-blocking / Nit。修正回 sweetbot-next 改後同步 `impl-s3/`。過了 → **S3-0a 完成**;之後 S3-0b(3 現成操作)/ S3-1(手水)/…,以及湊 S2+S3 一次 restart 手動驗收。
