# 交接：報稅系統 P3 扶養扣除 — 進度打包（2026-07-17）

> 為「多頻道討論同一件事 → 合併到單一頻道」而寫的進度快照。
> 到新頻道貼上本文件內容、或說「讀 `tools/tax-system/HANDOFF-p3-dependent.md`」即可接續。
> 相關：[[project_tax_system]]、[[project_tooth_stock_game]]、[[project_sweetbot_jail_system]]、[[project_vip_entitlements]]。
> P5 上線細節另見同目錄 `HANDOFF-criminal-gate-deploy.md`。

## 一句話現況
P3 扶養扣除 **a–c 三階段功能全部寫完 + 已 commit**，`sweetbot-dependent` 表已建，**但尚未 restart**（線上還按不到 `!扶養`、稅單還沒真的算扶養）。P3a/P3b 已 Codex 複驗畢，**P3c 待 Codex 查驗**。

## 這條線本日已完成（在 /opt/sml/sweetbot-next）

| 階段 | 內容 | commit | Codex |
|---|---|---|---|
| **P3a 資料層** | `sweetbot-dependent` 表(PK dependentID+SK taxYear+GSI supporterID-index/PAY_PER_REQUEST，已建 ACTIVE)+ `DependentDAO` | `0d81bc9` | ✅ 無 finding |
| **P3b 綁定流程** | `model/Dependent.js`(面板/邀請/雙方同意/解除/取消)+`DependentRules.js`+測試+discord.js 接線 | `def4f14` | — |
| **P3b 修正** | Codex 抓 2 Medium+1 design：拒絕誤刪 active→`rejectPending` 只刪 pending／額度改 active+pending 防多張 pending 突破／面板加取消鈕 | `03bb2dc` | ✅ 二複無 finding |
| **P3c 接入稅單** | `Tax.js computeBill` 接真扶養數(只 active/fail-safe)；核定路徑刻意維持 0 | `b6aeb56` | ⏳ **待查驗** |

- 測試：全套 **59/59 pass**、eslint clean。
- git 歷史線性安全（`0d81bc9` 在 HEAD 內）。

## 關鍵設計決策（已定案）
1. **活躍帳號**＝該稅年 point-log 有任一筆即算（防養殭屍分身，免新表）。
2. **VVIP 驗證** v1 直讀 `player.vipLevel>=2`；未來搬去 VIP 特權集中管理 `vipPerk()`（本為其試點）。
3. **解除/取消走 embed 按鈕**（非 `!解除扶養` 指令）——`!扶養` 一指令開場、其餘全按鈕。
4. **pending 也佔額度**（active+pending ≤ 5），發起人可從面板「取消邀請」釋出名額。
5. **自動核定不給扶養扣除**（`dependentCount:0`）：扶養與公職/認真里民同屬「申報時主張」扣抵，不申報不給＝逼玩家 5 月來申報；只有 `!報稅` 試算/申報才接真值。
6. 已標記可接受殘留：同一人「近乎同時」連發 invite 的 TOCTOU 可短暫超額，但 `TaxCalculator` `Math.min(dependentCount, maxDependents)` 夾住＝無經濟影響、僅面板短暫顯示超額；完整原子化需計數器/交易，暫緩（Codex 認同）。

## 待辦 / 下一步（接續討論從這裡開始）
- [ ] **P3c 交 Codex 查驗**（`b6aeb56`）：computeBill fail-safe、核定維持 0 的設計認同、2 新測試涵蓋。
- [ ] **P3d（選做）**：防濫用其實 P3b 已做齊（活躍/VVIP/額度、VVIP 掉階當年仍有效不可新增天然滿足）；只剩 **tax_admin 後台扶養總覽** nice-to-have。
- [ ] **P4 勳功偉業扣稅** + 連年徽章：報稅扣抵面最後一塊。
- [ ] **restart 上線**（⚠️ 需跨 session 協調）：P3b+P3c 要重啟才生效。但主 branch HEAD 已被並行 session 推進（每日任務/麻將 WIP + P5 繳費路徑修正 `3b08cc6/9cfa14e/8b9a98f` 未部署），restart 會一併帶上 → **不宜單方觸發**，先協調安全 commit 點。完整 P5 部署清單（migrations/IAM/enforcement 全關軟上線/smoke）見 `HANDOFF-criminal-gate-deploy.md`。

## 本日其他已上線（同一稅務專案，非 P3）
- 股市 criminal gate + 稅務赦免/假釋：已 restart 上線（HEAD `5a5de1f`）。
- P6 後台：Lambda `sml-tax`(API `ep7c8zkin5`)+ 遊戲館「🧾報稅管理」頁已部署；config P5 欄位 + 天降紅包歸類 migration 已跑；帳本 backfill 93 人已跑。
- ⚠️ 但 `5a5de1f` 缺 P5 繳費路徑 3 修正 → 被鎖權者補繳即赦目前不可用，待 redeploy（見 P5 HANDOFF）。
