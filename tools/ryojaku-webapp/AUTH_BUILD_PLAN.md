# 両雀帳號系統 — 實作任務分解（BUILD PLAN）

> 依 [AUTH_SYSTEM_DESIGN.md](AUTH_SYSTEM_DESIGN.md)（✅ 定稿）落地。Claude 主導建構。
> **程式碼 repo：`/opt/sml/ryojaku-src`（github `boyplaymj/ryojaku-src`）** — Go 後端 `backend/`、React 前端。設計冊在本 planning repo。
> 目標帳號：我方 AWS `380931373365`；先打 **staging**（`MahjongClubStg_` 前綴、CFN `ryojaku-tables-stg`）。
> 原則：每個任務切到「單次可完成、可獨立查驗」；標 🤖=適合切 Fable5 子代理（Claude 出規格+覆核）、🧠=Claude 親作（安全敏感/身分核心）、👤=使用者外部動作。**每階段末交 Codex 查驗**（🔎）才進下一階段。

---

## 依賴總圖
```
P0 基建 ─┬─(表/欄位)→ P1 共用底層 ─┬→ P2 註冊+認證信+登入
         │                          ├→ P3 忘記/改密碼
         │                          └→ P4 Google 登入/綁定
         └─(SES/Google client 外部)……………………………┐
P2/P3/P4 ─→ P5 前端 ─→ P6 rate limit + staging 部署 + E2E ←┘（P6 需 SES/Google 就緒）
```
可並行：P0.3（表定義）與 👤外部前置（P0.1 SES / P0.2 Google）同時進行；P2/P3/P4 後端在 P0.1/0.2 未就緒時仍可全寫完，只是 E2E 卡到 P6。

---

## Phase 0 — 前置基建
| # | 任務 | 誰 | 產出 |
|---|---|---|---|
| 0.1 | SES 網域驗證（jiomj.com 或 `*.boyplaymj`）+ 申請移出 sandbox + SPF/DKIM/DMARC | 👤 使用者 | 可寄信的寄件網域 |
| 0.2 | Google Cloud 建 OAuth 2.0 Client ID（Web），授權來源填前端網域，交回 **client_id** | 👤 使用者 | Google client_id |
| 0.3 | 兩張新表進 `infra/01-tables.yaml`：`AuthIdentities`(PK=identity)、`AuthTokens`(PK=tokenHash + **TTL** expiresAt)，全 PAY_PER_REQUEST；Users 免改（DDB schemaless，加欄位免動表） | 🧠 Claude | CFN 片段 |
| 0.4 | staging 套新表（`sam`/CFN 更新 `ryojaku-tables-stg`），驗 2 表 ACTIVE + TTL 開啟 | 🧠 Claude | staging 有表 |
| **0.🔎** | **Codex 查驗**：表 keys/TTL/PAY_PER_REQUEST 正確、命名前綴對、無破壞既有 25 表 | 🔎 | 過關才進 P1 |

---

## Phase 1 — 共用底層（`backend/cmd/lambdas/shared/`）
| # | 任務 | 誰 |
|---|---|---|
| 1.1 | `identities.go`：AuthIdentities CRUD — `Resolve(identity)→userId`、`Bind(identity,userId)`(帶 `attribute_not_exists` 防搶綁)、`Unbind`、`CountByUser`(解綁最後一把守衛用) | 🧠 Claude |
| 1.2 | `authtokens.go`：`Issue(userId,purpose,ttl)→明碼token`（存 SHA-256、TTL）、`Consume(token,purpose)→userId`（雜湊比對+未過期+未用→標 usedAt，單次） | 🧠 Claude |
| 1.3 | `email.go`：SES 寄信封裝 + 兩模板（verify_email / reset_password），連結帶明碼 token | 🧠 Claude（模板文案 🤖 Fable5 起草） |
| 1.4 | JWT 硬化：移除 `JWT_SECRET` 寫死 fallback（缺→啟動失敗，讀 SSM）；`GenerateToken` 帶 `iat`；新增 `VerifyToken` 檢查 `iat >= user.pwChangedAt`（版本閘） | 🧠 Claude |
| **1.🔎** | **Codex 查驗**：token 只存雜湊、單次性、Bind condition、JWT gate 邏輯、無寫死密鑰、SSM 讀取 | 🔎 |

---

## Phase 2 — 註冊 + 認證信 + 登入改造
| # | 任務 | 誰 |
|---|---|---|
| 2.1 | 改 `app_register`：建 User 後 → `Bind(email#..,userId)` → `Issue(verify_email)` → `email.SendVerify()`；仍發 JWT 讓人先進（軟門檻） | 🧠 Claude |
| 2.2 | 改 `app_login`：改走 `identities.Resolve(email#..)` 拿 userId（保留 email-index 相容）+ 套 `VerifyToken` 版本閘 | 🧠 Claude |
| 2.3 | 新 `mahjongclub_auth_verify_email`（GET token）：`Consume(verify_email)` → `emailVerified=true` | 🤖 Fable5 → 🧠 覆核 |
| 2.4 | 軟門檻閘：開團/入團端點（`web_create_game`/`web_accept_registration` 等）加「未驗證擋信任動作」檢查（後台可切硬/軟） | 🧠 Claude |
| **2.🔎** | **Codex 查驗**：註冊防枚舉、認證信端到端、登入解析正確、軟門檻只擋信任動作不擋登入 | 🔎 |

---

## Phase 3 — 忘記密碼 / 改密碼
| # | 任務 | 誰 |
|---|---|---|
| 3.1 | 新 `mahjongclub_auth_forgot_password`：一律回「若存在已寄出」（防枚舉）；存在才 `Issue(reset_password,30min)`+寄信 | 🤖 Fable5 → 🧠 覆核 |
| 3.2 | 新 `mahjongclub_auth_reset_password`：`Consume(reset_password)` → 更新 passwordHash + `pwChangedAt=now`（舊 JWT 全失效） | 🧠 Claude |
| 3.3 | 新 `mahjongclub_auth_change_password`（需 JWT）：驗當前密碼 → 換 hash + `pwChangedAt`；回新 JWT 給當前裝置 | 🤖 Fable5 → 🧠 覆核 |
| 3.4 | 新 `mahjongclub_auth_logout_all`（需 JWT）：只更新 `pwChangedAt=now` | 🤖 Fable5 → 🧠 覆核 |
| **3.🔎** | **Codex 查驗**：防枚舉、token 單次+TTL、pwChangedAt 讓舊 token 失效、改密碼需當前密碼 | 🔎 |

---

## Phase 4 — Google 登入 / 綁定
| # | 任務 | 誰 |
|---|---|---|
| 4.1 | 新 `mahjongclub_auth_google`：**後端驗 Google ID token**（Google 憑證/`aud=client_id`/`iss`/`exp`）→ 取 sub+email | 🧠 Claude |
| 4.2 | Google 解析分流：`Resolve(google#sub)` 有→登入；無但 email 命中既有已驗證帳號→合併掛鑰匙；皆無→建號(emailVerified=true) | 🧠 Claude |
| 4.3 | 綁定/解綁：`auth_bind`（登入態掛 google，`attribute_not_exists` 防搶）、`auth_unbind`（`CountByUser>1` 才准，防孤兒） | 🧠 Claude |
| **4.🔎** | **Codex 查驗**：idtoken 後端驗簽、合併僅限已驗 email、綁定 condition、解綁孤兒守衛 | 🔎 |

---

## Phase 5 — 前端（React）
| # | 任務 | 誰 |
|---|---|---|
| 5.1 | 「認證信已寄出」狀態頁 + `verify?token=` landing（成功/過期/已用三態） | 🤖 Fable5 → 🧠 覆核 |
| 5.2 | 忘記密碼頁 + 重設密碼頁（`reset?token=`） | 🤖 Fable5 → 🧠 覆核 |
| 5.3 | 設定頁：改密碼 / 綁定 Google / 登出其他裝置 | 🤖 Fable5 → 🧠 覆核 |
| 5.4 | 登入頁「使用 Google 登入」鈕（Google Identity Services，帶 client_id） | 🧠 Claude |
| 5.5 | 文案一律走 UI 文字（i18n，不內嵌圖，遵 feedback） | 🤖 Fable5 |
| **5.🔎** | **Codex 查驗**：串接/錯誤態/狀態頁、Google GIS 流程、文字不內嵌圖 | 🔎 |

---

## Phase 6 — rate limit + 部署 + E2E
| # | 任務 | 誰 |
|---|---|---|
| 6.1 | rate limit：login/register/forgot 按 IP+email 節流（計數表+冷卻 或 APIGW usage plan），擋暴力+寄信轟炸 | 🧠 Claude |
| 6.2 | infra 接線：新 Lambda 進 `functions.manifest.json` → `gen_app_template.py` 重生 `02-app.generated.yaml`（route+IAM 對 2 新表） | 🧠 Claude |
| 6.3 | 部署 staging（build 各 bootstrap→S3→`sam deploy`）+ 機密 put `/ryojaku/stg/*` SSM（含 GOOGLE_CLIENT_ID、JWT_SECRET） | 🧠 Claude |
| 6.4 | E2E（staging）：註冊→收信→驗證→登入→忘記→重設→改密碼→Google 登入→綁定→解綁孤兒守衛→rate limit 觸發 | 🧠 Claude |
| **6.🔎** | **Codex 查驗**：全鏈路 staging 綠、§6 安全清單逐項、無回歸既有登入 | 🔎 |

---

## Fable5 子代理任務彙整（Claude 出規格 + 覆核）
2.3 verify_email · 3.1 forgot · 3.3 change_pw · 3.4 logout_all · 5.1–5.3/5.5 前端頁 · 1.3/email 文案。
→ 特徵：邏輯直、規格明確、非安全核心。**安全核心（token/JWT/身分/Google 驗簽/rate limit）一律 Claude 親作。**

## 交付節奏
- 一次推進**一個 Phase**，Phase 內任務可連做；Phase 末**停下交 Codex 查驗**，過關才續。
- 每 Phase 完成在 ryojaku-src commit（分 Phase commit，方便 Codex 逐段審）。
- 外部前置（0.1 SES / 0.2 Google）由使用者並行處理，卡到 P6 才成硬依賴。
