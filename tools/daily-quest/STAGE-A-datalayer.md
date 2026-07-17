# 每日任務 — 階段 A：資料層（交 Codex 查驗）

> 依 `DESIGN.md` §3 建置。region = **ap-southeast-1**，全 **PAY_PER_REQUEST**。

## 已建 3 張表

| 表 | PK | SK | 用途 |
|---|---|---|---|
| `sweetbot-quest-config` | `key` (S) | — | 任務模板池（後台可編輯） |
| `sweetbot-daily-quest` | `discordId` (S) | `date` (S, `YYYY-MM-DD` 以 05:00 重置切日) | 玩家每日進度（懶抽） |
| `sweetbot-quest-streak` | `discordId` (S) | — | 玩家連續達成天數 |

命名對齊現有 `sweetbot-player-point-log`（`discordId` camelCase）。

## config 欄位規格（seed 已灌 13 則 = DESIGN §10 P1 子集）

```
key         S   任務唯一鍵（q_checkin…）
title       S   顯示名
desc        S   說明
event       S   觸發事件字串（checkin / game_play:any / game_play:<key> / game_win:any / game_win:<key> / post_message）
target      N   目標數
difficulty  S   簡單 / 普通 / 挑戰
weight      N   抽取權重
rewardType  S   目前皆 "point"（預留 "prop"）
rewardPoint N   發放牙齒
rewardExp   N   發放經驗
enabled     BOOL 是否啟用
```

seed 清單（13）：q_checkin, q_play1, q_play3, q_play5, q_win1, q_win2, q_msg1, q_msg3, q_upw, q_sicbo, q_bjm, q_cross, q_poke。
獎勵：一般 150🦷+30EXP；挑戰級（q_play5/q_win2/q_bjm）250🦷+50EXP。

seed 檔：`tools/daily-quest/seed-config-p1.json`（batch-write 用）。

## Codex 查驗點

1. 3 表皆 ACTIVE、PAY_PER_REQUEST、region ap-southeast-1、key schema 如上。
2. `sweetbot-quest-config` 恰 13 筆，欄位/型別符合上表，enabled 全 true。
3. seed 數值對上 DESIGN §10 P1（target/weight/reward/difficulty）。
4. daily-quest 複合鍵能支撐「單玩家查當日 doc」與「懶抽寫入」。
5. 無多餘表 / 無遺漏欄位。

## 尚未做（後續階段）

- B：後台 Lambda + APIGW（config CRUD）
- C：遊戲館後台管理頁
- D：bot 引擎（QuestTracker + 懶抽 + `!每日任務` 面板 + 埋 4 事件）
- E：streak(P2) + VIP 加題(P3)
