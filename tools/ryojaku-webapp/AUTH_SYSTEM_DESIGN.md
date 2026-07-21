# 両雀 Ryōjaku — 完整帳號/註冊系統設計

> 2026-07-21 gameboy × Claude。把現行半成品的註冊系統補成完整、安全的帳號系統。
> 逆向自工程師源碼（`/opt/sml/ryojaku-src`）現況 + 設計缺口補完。
> 上位正典：[foundation](modules/foundation.md) §2.4「LINE 只提供身分+通知」、[assets](modules/assets.md) L0 身分橋。
> 關聯：[MIGRATION_PLAN.md](MIGRATION_PLAN.md)（接手遷移）、本檔的 Google/密碼登入**直接讓「拿不到 LINE 名冊」的 fallback 消失**。

---

## 0. 現況盤點（逆向自源碼，2026-07-21）

**現有 auth 端點只有 3 支**：`app_register`、`app_login`、`web_verify_user`(LINE 備援)。

| 能力 | 現況 | 判定 |
|---|---|---|
| Email+密碼註冊 | ✅ 有（bcrypt、min 8 字、暱稱、邀請碼、email-index 擋重複） | 堪用 |
| Email+密碼登入 | ✅ 有（bcrypt 比對、發 HS256 JWT 30 天） | 堪用 |
| LINE 備援登入 | ✅ 有（`encryptedLineId` 解密比對，`ENCRYPTION_KEY`） | 堪用 |
| **認證信（email 驗證）** | ❌ `emailVerified` 欄位存在但註冊寫死 `false`、**無 SES、無寄信、登入不檢查** = 死欄位 | **缺** |
| **忘記密碼/重設** | ❌ 無任何端點 | **缺** |
| **改密碼（登入態）** | ❌ 無任何端點 | **缺** |
| **Google / 社群登入** | ❌ 完全沒有 | **缺** |
| JWT 安全 | ⚠️ `JWT_SECRET` 有寫死 fallback 預設值（SOURCE_TRUTH 已標） | **要修** |
| 登出其他裝置 / 撤銷 token | ❌ 無（純無狀態 JWT，改密碼後舊 token 仍有效） | **缺** |
| 登入/註冊防暴力 | ❌ 無 rate limit | **缺** |

**User 資料模型（現有欄位，續用）**：`userId`(PK, `APP_xxx`)、`displayName`、`email`、`passwordHash`、`accountType`(`app`|`linebot`)、`lineId`/`encryptedLineId`、`points`、`isVerified`、`emailVerified`、`createdAt`…。GSI：`email-index`、`invitedBy-index`。

---

## 1. 目標：一套完整、安全的帳號系統

1. 信箱註冊 + **認證信**（真的寄、真的驗）。
2. **Google 一鍵登入 / 綁定**（社群登入，免密碼）。
3. **忘記密碼 → 重設**（寄信、限時、單次）。
4. **登入態改密碼** + 可「登出其他裝置」。
5. 一個帳號可**同時綁多種登入法**（密碼 / Google / LINE），任一種登入都進同一帳號、同一份點數。
6. 安全底線：防帳號枚舉、token 雜湊儲存 + TTL + 單次、rate limit、移除寫死密鑰。

---

## 2. 🔑 核心決策：身分模型 = 「一個帳號 · 多把鑰匙」

**現行是「一個帳號綁死一種登入法」→ 升級成「canonical 帳號 + 可掛載的多個登入身分」。**

- **canonical 帳號 = `userId`(`APP_xxx`)**，續用、不動。24 張表、JWT claims 全 key 在它，**絕不改**。
- **登入身分（identity）= 能解析到某個 userId 的一把鑰匙**，三種 provider：
  - `password`（email + bcrypt hash，存在 User 上）
  - `google`（Google `sub`）
  - `line`（`encryptedLineId`，既有）
- 一個 userId 可掛 **0..N 把鑰匙**（例：先密碼註冊，之後綁 Google，再綁 LINE，都進同一帳號）。

### 新表：`AuthIdentities`（登入身分索引）
| 欄位 | 說明 |
|---|---|
| **PK** `identity` | `google#<sub>` / `email#<lowercased>` / `line#<encryptedLineId>` |
| `userId` | 解析到的 canonical 帳號 |
| `provider` | `google`\|`password`\|`line` |
| `createdAt` | 綁定時間 |

- 登入=用 provider 身分組 PK 直接 `GetItem` → 拿 userId → 走既有發 JWT。**O(1)、不再靠掃 email-index。**
- 綁定=一次 `PutItem`（帶 `attribute_not_exists` 條件，擋「這把鑰匙已綁在別的帳號」）。
- email-index 續留（相容、找帳號用）。`AuthIdentities` 是登入的權威索引。

> 這個模型是整份設計的地基。以下所有流程都是「掛一把鑰匙 / 用一把鑰匙解析 userId」。

---

## 3. 大決策：自建 Go 擴充 vs 改用 AWS Cognito

| | **A. 擴充現有 Go 自建**（建議） | **B. 改用 Cognito** |
|---|---|---|
| 認證信/重設/Google | 自己寫（SES + token 表 + Google idtoken 驗證） | 內建、免寫 |
| 安全性 | 要自己顧邊角（枚舉/replay/timing） | 久經考驗 |
| **13k 用戶 + userId 耦合** | ✅ **零動搖**（userId 續當 PK，只加鑰匙） | 🔴 要把 userId 模型接到 Cognito `sub`，24 表全受牽連、遷移期高風險 |
| bcrypt 既有密碼 | ✅ 直接續用 | 要 migration trigger 搬 hash |
| 前端 | 改動小 | 換 Amplify/Hosted UI |
| 開發量 | 中（3~4 支新 Lambda + 2 表 + SES） | 前期省、但遷移改造大 |

**建議 A（自建擴充）**：因為 `userId=APP_xxx` 是 24 表的 PK、深度耦合，**在已經很危險的接手遷移期，不該再把身分層抽換成 Cognito**。自建是增量、低風險、重用現有可運作的 bcrypt/JWT/LINE 程式碼。Cognito 是「乾淨重build」路線，等遷移穩定後若要 MFA/企業級再評估，不是現在。

> 以下設計以 **A** 展開。若日後選 B，第 2 節身分模型仍成立（Cognito 只是換掉「怎麼驗鑰匙」）。

---

## 4. 新增資料表與欄位

### 4.1 `AuthIdentities`（見 §2）— 登入身分索引
### 4.2 `AuthTokens` — 認證信 / 重設密碼的一次性 token
| 欄位 | 說明 |
|---|---|
| **PK** `tokenHash` | 存 **token 的 SHA-256**，不存明碼（外洩表也無法反推連結） |
| `userId` | 對象帳號 |
| `purpose` | `verify_email` \| `reset_password` |
| `expiresAt`(TTL) | verify 24h / reset 30min，DynamoDB TTL 自動清 |
| `usedAt` | 用過即寫，單次性（用過再點失效） |

明碼 token 只出現在寄出的信裡；後端只留雜湊。驗證=把來的 token 雜湊後 `GetItem`。

### 4.3 `Users` 加欄位
- `pwChangedAt`（timestamp）：改密碼/重設後更新 → JWT 帶 `iat`，登入驗證時**拒絕 `iat < pwChangedAt` 的舊 token** = 「登出其他裝置」。
- `googleSub`（可選鏡像，方便後台看）；權威仍在 `AuthIdentities`。

### 成本
2 張小表全 **PAY_PER_REQUEST**（AuthTokens 有 TTL 自清、幾乎不長）。SES 寄信 ~$0.10/千封 = 可忽略。無 LLM、無付費 API → 不觸發 `COST_CONTROL.md` 四件套（那是給燒 LLM 的）。唯一前置：SES 網域驗證 + 申請移出 sandbox。

---

## 5. 各流程設計

### A. 信箱註冊 + 認證信
```
填 email/密碼/暱稱(+邀請碼)
 → 驗 email 格式、密碼≥8、AuthIdentities[email#..] 不存在
 → 建 User(accountType=app, emailVerified=false, points 依邀請規則)
 → 寫 AuthIdentities[email#..]→userId
 → 產 token → 存 AuthTokens(SHA256, purpose=verify_email, TTL 24h)
 → SES 寄「驗證你的信箱」含 https://app/verify?token=xxx
 → 直接發 JWT 讓他先進 App（不卡在門口，見門檻政策）
點信中連結 → /auth/verify-email?token → 雜湊比對+未過期+未用 → emailVerified=true、標記 usedAt
```
**認證門檻政策（建議＝軟門檻）**：未驗證**可登入、可逛**，但**不可做信任行為**（開團/報名入團）——對齊 foundation §6「申請人絕不卡住」+ §1「信任=護城河」。純硬擋登入會傷 onboarding；完全不擋又破壞封閉制信任 → 折衷擋在「信任動作」那一關。可後台切硬/軟。

### B. 登入（三法歸一）
```
email/密碼：AuthIdentities[email#..]→userId→取User→bcrypt比對→發JWT
Google：前端拿 Google ID token → 後端驗簽(Google 憑證/aud=我方clientId/exp)
        → 取 sub → AuthIdentities[google#sub]?
           有 → 登入該 userId
           無、但 google email 命中既有已驗證帳號 → 走「帳號合併」(§F)
           無 → 建新帳號(emailVerified=true，因 Google 已驗信箱，免認證信)
LINE：既有 encryptedLineId 流程不動
所有路徑最後都經 shared.GenerateToken(userId,email) 發 JWT(帶 iat)
```

### C. 忘記密碼 → 重設
```
POST /auth/forgot { email }
 → 一律回「若信箱存在，已寄出重設信」(防帳號枚舉，不透露存在與否)
 → 若真的存在：產 token → AuthTokens(reset_password, TTL 30min) → SES 寄重設連結
POST /auth/reset { token, newPassword }
 → 雜湊比對+未過期+未用 → 更新 passwordHash、pwChangedAt=now、標 usedAt
 → (pwChangedAt 更新 = 所有舊 JWT 失效，重設後全裝置要重登)
```

### D. 改密碼（登入態）
```
POST /auth/change-password (需 JWT) { currentPassword, newPassword }
 → 驗當前密碼 → 更新 passwordHash、pwChangedAt=now
 → 可選：回新 JWT 給當前裝置，其餘裝置因 iat<pwChangedAt 被登出
「登出所有裝置」= 單獨端點，只更新 pwChangedAt=now
```

### E. Google 綁定 / 解綁（登入態）
```
綁定：登入態發起 Google 流程 → 驗 token 取 sub
      → PutItem AuthIdentities[google#sub]→userId (attribute_not_exists 條件)
         成功=綁上；ConditionalCheckFailed=這個 Google 已綁別的帳號 → 擋+提示
解綁：刪 AuthIdentities[google#sub]
      ⚠️ 守衛：若這是該帳號「唯一一把鑰匙」→ 擋（否則變無法登入的孤兒帳號）
```
「至少保留一把可登入的鑰匙」是解綁的不變式。

### F. 帳號合併（email 撞號）
情境：某人先用 email/密碼註冊，之後用**同 email 的 Google** 登入。
- Google 的 email 是 **Google 已驗證**的 → 可信 → **自動把 `google#sub` 掛上既有 userId**（不建新帳號），並把該帳號 `emailVerified` 補 true。
- 反向（先 Google 後想設密碼）：登入態走 §D 設密碼即掛上 `password` 鑰匙。
- **絕不靠「未驗證的 email 字串相同」就合併**（那可被冒用）；只有 provider 已驗證的 email 才自動合。

---

## 6. 安全硬底線（屬於「完整」的一部分）
1. **移除 `JWT_SECRET` 寫死 fallback** → 強制從 SSM 讀，缺就啟動失敗（SOURCE_TRUTH 已列）。
2. **token 只存雜湊**（AuthTokens PK=SHA256），明碼只在信裡；TTL + 單次(`usedAt`)。
3. **防帳號枚舉**：註冊「email 已存在」與忘記密碼一律用不洩漏存在性的回應。
4. **rate limit**：login/register/forgot 按 IP+email 節流（APIGW usage plan 或計數表 + 冷卻），擋暴力/寄信轟炸。
5. **pwChangedAt 版本閘**：改密碼/重設使舊 JWT 失效。
6. bcrypt DefaultCost 續用；密碼 min 8（可加「擋常見弱密碼」清單，選配）。
7. Google ID token **一定要後端驗簽**（aud=我方 client id、iss、exp），不可只信前端。
8. SES 寄件網域 SPF/DKIM/DMARC 設好、退信(bounce/complaint)進 SNS 監控，保護寄件信譽。

---

## 7. 與遷移 / LINE fallback 的關係（一石二鳥）
- 這套一旦上線，**「拿不到 LINE 名冊」的 fallback 直接消失**：LINE-only 用戶可**綁 Google** 或**設密碼**接回原帳號（點數 key 在 userId 不動）。
- 建議在**現行 App 還能 LINE 登入的期間**推「補綁 Google / 設密碼」campaign（登入態直接掛鑰匙，零認領糾紛）→ 到切換日人人有替代登入法，LINE 依賴自然蒸發。
- 詳細三世界（拿到 key / 只剩 App 活著 / 全冷啟動）對應動作見 [MIGRATION_PLAN.md] 與前次討論；本設計是那份的「登入法」底座。

---

## 8. 端點與前端改動清單

**新增 Lambda（Go，沿用現有 shared/ 工具與 DDB 前綴慣例）**：
- `mahjongclub_auth_verify_email`（GET token）
- `mahjongclub_auth_forgot_password` / `mahjongclub_auth_reset_password`
- `mahjongclub_auth_change_password`（需 JWT）
- `mahjongclub_auth_google`（登入/註冊/綁定共用，驗 Google idtoken）
- `mahjongclub_auth_bind` / `mahjongclub_auth_unbind`（管鑰匙）
- 共用 `shared/email.go`（SES 寄信）、`shared/authtokens.go`（產/雜湊/驗 token）、`shared/identities.go`（AuthIdentities CRUD）
- 改 `app_register`：註冊後產 token + 寄認證信；`app_login`：加 pwChangedAt 版本閘。

**前端（React）**：註冊頁加「驗證信已寄出」狀態頁、忘記/重設密碼頁、設定頁「改密碼 / 綁定 Google / 登出其他裝置」、登入頁加「使用 Google 登入」鈕（Google Identity Services）。

**基礎建設**：SES 網域驗證 + 移出 sandbox；Google Cloud 建 OAuth client（拿 client id）；`AuthIdentities`/`AuthTokens` 兩表進 `infra/01-tables.yaml`（PAY_PER_REQUEST，AuthTokens 開 TTL）。

---

## 9. 待拍板（open decisions）
1. **自建 vs Cognito** → 建議自建（§3），待你點頭。
2. **認證門檻**：軟門檻（未驗證可逛、不可開團/入團，建議）還是硬門檻（不驗證不能登入）？
3. **Google 撞 email 自動合併**：接受「Google 已驗證 email 即自動掛上既有帳號」？（建議接受，見 §F）
4. **既有用戶回填**：要不要對現有一堆 `emailVerified=false` 的舊帳號補寄一次認證信 campaign？還是只對新註冊生效、舊的下次改密碼時順帶驗？
5. **登入法下限**：是否強制「每個帳號至少一把鑰匙」+ 解綁最後一把時擋（建議是）。

---

## 💰 成本控管（遵循 tools/COST_CONTROL.md）
- 成本源：SES 寄信（認證/重設，~$0.10/千封，可忽略）、2 張新 DDB 表（PAY_PER_REQUEST、AuthTokens 有 TTL 自清）。
- 無 LLM、無付費 API → **不需四件套**（四件套是給燒 LLM/付費 API 的功能）。
- 唯一要注意：SES 寄件量若被濫用（忘記密碼轟炸）→ 靠 §6.4 rate limit 擋；SES sandbox/寄件上限先設好。
