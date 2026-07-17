# 火車大亨 — 後台 Lambda + API(階段 A,交 Codex 查驗)

## 已部署(2026-07-17)

| 項目 | 值 |
|---|---|
| Lambda | `sml-train-tycoon-admin`(nodejs20.x, handler `index.handler`, timeout 15s, mem 256）@ ap-southeast-1 |
| IAM role | `sml-train-tycoon-admin-role`（inline policy `train-config-access`：僅 `train-tycoon-config` 的 GetItem/PutItem + logs） |
| HTTP API | `sml-train-tycoon-admin-api`（ApiId `ayfgbazell`，quick-create：$default route → Lambda proxy，CORS `*`/POST,OPTIONS） |
| **端點** | `https://ayfgbazell.execute-api.ap-southeast-1.amazonaws.com` |
| Env | `FIREBASE_PROJECT=sml2026newscore`、`TABLE_NAME=train-tycoon-config` |

程式：`aws/train-tycoon-admin/index.js`。**改寫自 `sml-mahjong-tycoon`**（同 `section`+`state` / `draft`+`published` 模型），僅兩處遊戲相關差異：
- `SECTIONS = ['catalogs','destinations','balance']`（麻將是 districts/events/catalogs/balance）
- `TABLE_NAME` env → `train-tycoon-config`

其餘（Firebase RS256 token 驗證、gameAdmins 白名單同步、listConfig/saveSection/publishConfig/revertDraft、CORS）**與麻將 Lambda 逐行一致**，未改邏輯。

## 資料層（已存在，S1/S2 建好）

- 表 `train-tycoon-config`（PAY_PER_REQUEST，PK=`section`、SK=`state`）@ ap-southeast-1
- 已灌種：catalogs/destinations/balance 各 `draft`+`published` 共 6 item（`version` 未設 → publicItem 視為 0）
- config source of truth：`tools/train-tycoon/seed/config_seed.json`

## Auth（照既有慣例）

- Firebase ID token RS256 驗證（Google securetoken 公鑰，無外部套件）：aud/iss/exp/email_verified + 簽章。
- 白名單同步遊戲館 Firestore `config/gameAdmins`（公開讀，快取 5 分），`ALLOWED_EMAILS` env 為緊急備援。
- 非白名單 email → 403；token 驗證失敗 → 401。

## Actions（POST body `{action,...}` + `Authorization: Bearer <idToken>`）

| action | 輸入 | 輸出 | 說明 |
|---|---|---|---|
| `listConfig` | — | `{sections:{[sec]:{draft,published,version,updatedAt,updatedBy}}}` | 三 section 的 draft+published |
| `saveSection` | `{section,data}` | `{updatedAt}` | 覆寫該 section 的 draft（data 必須是 object） |
| `publishConfig` | `{section?}` | `{versions:{[sec]:n}}` | draft→published，version+1；省略 section 則全部 |
| `revertDraft` | `{section}` | `{ok}` | published→draft |

## 冒煙測試（已驗）

- 無 token POST → `401 {"ok":false,"error":"auth failed: no token"}`（路由通、Lambda 沒崩、認證閘生效）
- OPTIONS 預檢 → `200`（CORS 通）

## 待查驗點（給 Codex）

1. Lambda 與麻將 `sml-mahjong-tycoon` 邏輯逐行一致（只該差 SECTIONS + TABLE_NAME）→ 確認沒帶進麻將專屬碼。
2. IAM role 權限最小化（只 train-tycoon-config 的 Get/Put + logs，無其他表）。
3. `assertSection` 擋非白名單 section（防寫入亂 section 汙染表）。
4. publishConfig 冪等/版號遞增正確；saveSection 型別檢查（data 非 object → 400）。
5. 端點/env/role 綁定與本文件一致。

## 後續階段

- 階段 B（HTML）：`train_tycoon_admin.html`（B1 骨架+balance+destinations、B2 catalogs）
- 階段 C：遊戲館 NAV + 部署（S3 + CloudFront）
