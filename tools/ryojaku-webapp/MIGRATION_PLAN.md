# 両雀 Ryōjaku — 接手 & 遷移計畫（Claude 主導）

> 2026-07-17 起：使用者決定把工程師的服務接手，由 Claude 續開發。
> 目標三件事：①程式碼收進我們掌控 ②補上先前討論結論（foundation/modules 設計）③把線上服務搬到我們 AWS（帳號 `380931373365`）。
> ⚠️ **這是有 13,416 真實用戶、真實點數餘額的 production 服務** → 遷移必須零資料遺失、可回滾、分階段閘門。

## 0. 現況（source of truth = SOURCE_TRUTH.md）
- 後端：Go，~47 顆 Lambda（`mahjongclub-backend`），在**工程師的 AWS 帳號**（主GW `yg7y0xkb50` / WS `ek5dythoh9` / 券 `00pox0hvv4`，皆 ap-southeast-1）。
- 資料：24 張 `MahjongClub_*` DynamoDB 表（含 13,416 用戶、點數、團局、記帳、聊天）＋ LineBot-User-Profiles。
- 前端：App（`d1wa3w4dmfwqc7.cloudfront.net` + `jiomj.boyplaymj.com`）、後台（`admin.jiomj.com`）。
- 機密：`JWT_SECRET`、`ENCRYPTION_KEY`(加密 LINE ID)、VAPID、Gemini key、OpenAI key。

## 1. 🔴 動工前必須先拿到/決定的（BLOCKERS）
1. **AWS 存取路徑**：我們是拿到**工程師帳號的 IAM 唯讀權**做匯出？還是工程師**交付資料匯出檔**？還是**純用源碼重建 + 匯入資料**？→ 決定整個做法。
2. **機密交付**：`ENCRYPTION_KEY` **必須拿到原值**（否則所有 LINE 綁定帳號解不開＝壞掉）；`JWT_SECRET`（換掉＝全用戶被登出，可接受但要挑時機）；VAPID（換掉＝推播訂閱失效要重訂）；Gemini / OpenAI key（用工程師的還是換我們自己的帳單）。
3. **網域**：`jiomj.com` 在工程師手上（不在我們 Route53）。切換時 App/後台網域要嘛遷 DNS、要嘛改用我們的 `*.boyplaymj.com`。
4. **成本核准**：新增到我們帳號的常態成本＝24 表 PAY_PER_REQUEST + 47 Lambda + 3 API GW + WS + S3 圖床 + 兩套外部 AI（Gemini/OpenAI 付費）。依 `tools/COST_CONTROL.md` 要先估量級。
5. **切換窗口**：13k 用戶要不要停機窗口？建議「平行架站→影子測試→短凍結窗口做最終資料同步→切 DNS→可回滾」。

## 2. 階段計畫（每階段一個閘門，Claude 執行、使用者/Codex 查驗）
**S0 — 保全源碼（✅ 本地完成 2026-07-17，待推 GitHub）**：
- 乾淨源碼在 **`/opt/sml/ryojaku-src`**（已脫離易失的 /tmp）：401 檔 / 11M，去 node_modules/vendor/編譯產物/機密，已 `git init`+commit（本地 history）。
- 機密隔離於 **`/opt/sml/ryojaku-secrets`**（chmod 700，**不進 git**）：frontend/.env、lambda-config.json、PUSH_KEYS.md、environment-config.json（含 JWT_SECRET/ENCRYPTION_KEY/VAPID/Gemini/OpenAI）→ 遷移時進 SSM。`lambda-config-template.json`（`{{佔位}}`）有留在源碼，可看 env 形狀。
- 遠端：**✅ 已推上 `boyplaymj/ryojaku-src`（private，master，單一乾淨 commit 401 檔）**。deploy key `~/.ssh/ryojaku-src-deploy` + alias `github-ryojaku-src`。
- 🔴 **推送時發現工程師源碼硬編碼了 2 把 AWS IAM 金鑰**（前端/後端各一，在 .ps1/.md 部署腳本），已從我們的 repo 遮蔽、原值隔離於 `ryojaku-secrets/LEAKED_AWS_KEYS_engineer.txt`。**GitHub push protection 也擋過一次**。→ 這是工程師帳號的憑證，**強烈建議請工程師輪換/停用這兩把 key**（可能已外流）。
**S1 — IaC 化（✅ 骨架完成 2026-07-17，未部署）**：在 `ryojaku-src/infra/`（已 push）：
- `01-tables.yaml` = **25 表 CloudFormation**（keys 取自工程師 setup 腳本、GSI 取自 Go 源碼 IndexName、全 PAY_PER_REQUEST）。
- `functions.manifest.json` = **61 Lambda 路由正典** → `gen_app_template.py` 產 `02-app.generated.yaml`（**61 function + REST + HTTP + WebSocket API**，1496 行）。
- 機密走 SSM SecureString(`resolve:ssm-secure`)、DDB IAM 對前綴全域、Makefile 61 build 目標、samconfig(staging)、README。
- 兩份 YAML 已語法驗證通過。工程師帳號實為 `228304098112`；我們帳號 `380931373365`（EC2 role `sml-claude-ec2`）。
- **✅ 資料層已部署到我們 staging（2026-07-17）**：CFN stack `ryojaku-tables-stg`（ap-southeast-1），**25 表全 ACTIVE、PAY_PER_REQUEST、GSI 正確**（空表≈$0，可 `aws cloudformation delete-stack` 回滾）。前綴 `MahjongClubStg_`（+ `LineBot-*-Stg`）。
- 🔶 **計算層未部署**：本機無 SAM CLI（Go 1.25 arm64 有）。下一步＝裝 SAM 或手動 `package`（build 61 顆 bootstrap→S3）＋機密 put 進 `/ryojaku/stg/*` SSM，才能 `sam deploy` 02-app。
- **✅ S2修 LineBot-* 表名 env-driven（2026-07-18）**：原 `internal/services/{user_profile,consultant,conversation,openai,session}.go` 硬編 6 張 `LineBot-*` 表名（無前綴），同帳號 stg/prod 會撞名。已改：①新增 `internal/services/tables.go` 的 `lineBotTable(base)`＝讀 `LINEBOT_TABLE_PREFIX`（預設 `LineBot-`）+ base，37 處字面量全改走它（`go build ./internal/services/` 綠）②`01-tables.yaml` 加 `LineBotTablePrefix` 參數（stg 預設 `LineBotStg-`）、2 張 LineBot 表改 `!Sub`③`gen_app_template.py` 加全域 env `LINEBOT_TABLE_PREFIX` + IAM 由寫死 `LineBot-*` 改 `${LineBotTablePrefix}*`，已重生 `02-app.generated.yaml`④`samconfig.toml` stg 帶 `LineBotTablePrefix=LineBotStg-`。⚠️ **重部署提醒**：現行 `ryojaku-tables-stg` 已用舊名建了 2 張空表，套新模板時 CFN 會因改 `TableName` 做**替換**（刪舊建新 `LineBotStg-*`）——空表無損。⚠️ **仍缺 4 張**：code 另用 `LineBot-Consultants / -Consultation-Sessions / -Conversation-Records / -OpenAI-Config`，CFN 未定義（但此 4 表所屬 AI 顧問 service **未接進 61 顆已部署 Lambda 任何一顆**，故非 staging blocker；日後接線前需補建，schema 取自 Go 的 Key 用法）。改動在 `/opt/sml/ryojaku-src`（github `boyplaymj/ryojaku-src`），待 commit+push。
**S2 — 影子部署驗證**：staging 用假資料端到端測（登入/開團/報名/記帳/點數/聊天/推播），確認源碼在我們帳號可跑。
**S3 — 資料遷移演練**：DynamoDB → S3 export → import 到我們帳號；驗證筆數、點數餘額加總、抽樣比對；量測全量耗時。
**S4 — 機密/金鑰接管**：`ENCRYPTION_KEY` 等原值進我們 SSM；決定 JWT/VAPID 換不換（換＝配套通知用戶）。
**S5 — 正式切換**：公告維護窗口 → 凍結寫入 → 最終增量同步 → 切 DNS/CloudFront → 觀察 → 保留舊站可回滾 N 天。
**S6 — 接手續開發**：在我們掌控的源碼上，把 foundation/modules 討論結論（記帳升格/信譽/RPG/反托/LINE-first LIFF/雀幣 grant()）逐一實作。

## 3. 建議的第一刀
先做 **S0（保全源碼）** —— 純資料搬運、零風險、且 `/tmp` 隨時可能被清掉，這件事本身有急迫性。其餘 S1~S5 需要 §1 的 blockers 到齊才動。
在 blockers 補齊前，Claude 可先平行推進 **S1 IaC 化**（純寫程式、不碰線上、不花錢）。

## 4. 待使用者拍板
- 源碼保全放哪：新開私有 GitHub repo？我們 AWS？先本機打包？
- 遷移做法：拿工程師 AWS 權限匯出，還是請工程師給匯出檔，還是源碼重建+資料匯入？
- 網域：沿用 jiomj.com（要遷 DNS）還是改掛 `*.boyplaymj.com`？
