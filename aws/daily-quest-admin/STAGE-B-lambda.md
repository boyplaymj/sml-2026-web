# 每日任務 — 階段 B：後台 Lambda + API（交 Codex 查驗）

## 已部署

| 項目 | 值 |
|---|---|
| Lambda | `sml-daily-quest-admin`（nodejs20.x, handler `index.handler`, timeout 15s, mem 256）@ ap-southeast-1 |
| IAM role | `sml-daily-quest-admin-role`（僅 `sweetbot-quest-config` 的 Scan/Get/Put/Delete/Query + logs） |
| HTTP API | `sml-daily-quest-admin-api`（ApiId `3v6m67eo5l`） |
| **端點** | `https://3v6m67eo5l.execute-api.ap-southeast-1.amazonaws.com` |
| Env | `FIREBASE_PROJECT=sml2026newscore` |

程式：`aws/daily-quest-admin/index.js`（改寫自 `sml-earthquake-admin` / `sml-random-events`）。

## Auth（照既有慣例）

- Firebase ID token RS256 驗證（Google securetoken 公鑰，無外部套件）：檢查 aud/iss/exp/email_verified + 簽章。
- 白名單同步遊戲館 `config/gameAdmins`（Firestore 公開讀，快取 5 分），`ALLOWED_EMAILS` 為緊急備援。
- 非白名單 email → 403；驗證失敗 → 401。

## Actions（POST body `{action,...}` + `Authorization: Bearer <idToken>`）

| action | 輸入 | 輸出 | 說明 |
|---|---|---|---|
| `list` | — | `{tasks:[...]}` | 全部任務模板（含 disabled），依 key 排序 |
| `saveTask` | `{task}` | `{key}` | 新增/更新；key 缺自動配 `q_custom_<n>`；**型別正規化** |
| `deleteTask` | `{key}` | `{ok}` | 刪一則 |
| `preview` | `{vipLevel?}` | `{drawCount,pool,totalWeight,difficultyMix,tasks:[{key,title,weight,appearProb}]}` | Monte Carlo（3000 次）模擬「依 weight 不重複抽 N=3+vip 張」的今日分佈 |

**saveTask 正規化**（防前端送字串進 DDB）：
- key 只允許 `[A-Za-z0-9_]`；title 不可空
- `event` 需匹配白名單正則（checkin / post_message / game_play:<key> / game_win:<key> / … 見 DESIGN §4）
- target≥1（Number）、weight≥0（Number）、rewardPoint/rewardExp≥0（Number）、enabled（Bool）
- rewardType 預設 `point`，`prop` 時帶 rewardPropId/rewardPropQty

## 冒煙測試（已跑）

- 無 token → 401 `no token` ✅
- 壞 token → 401 `malformed token` ✅
- OPTIONS 預檢 → 200 ✅
-（授權後的 CRUD 需真 Firebase 登入，留給階段 C 前端 + Codex 實測）

## Codex 查驗點

1. Lambda/role/API 存在且設定如上；role 權限僅限 config 表（最小權限）。
2. auth 邏輯與 `sml-earthquake-admin` 一致（aud/iss/exp/簽章/白名單）。
3. `saveTask` 正規化：型別強制、event 白名單、key 格式、autogen key 不撞號。
4. `preview` 的加權不重複抽樣正確（totalWeight=0 時 fallback 均勻、n>pool 不爆）。
5. 只碰 `sweetbot-quest-config`，不觸 daily-quest / streak（權責分離）。
6. 建議：拿真 Firebase 帳號登入後 list/saveTask/deleteTask/preview 各打一次確認端到端。

## 尚未做

- C：遊戲館後台管理頁（接本端點）+ NAV + 部署
- D/E：bot 引擎 + streak/VIP
