# 參考資料庫(字元參考庫)· Codex 交接 spec

目的:老司機後台讓 staff **上傳車牌圖 + 標註正確號碼**,存起來供 EC2 裁字建字庫。與號碼庫(要發的番號)分開。

沿用既有 `sml-laoshiji-admin` Lambda(同 auth/CORS/env 權威白名單)+ 同 API,加以下:

## 新 DynamoDB 表(請建)
`sml-plate-refs`(ap-southeast-1, PAY_PER_REQUEST, PK=`refId`)
- refId(S, 產生:時間戳+亂數)/ code(S, 正規化後的標籤)/ imageKey(S3 key)/ imageUrl(S)
- status(S: pending|processed|error)/ createdAt(S ISO)

## S3
存 `s3://boyplaymj-image/plate-refs/<refId>.<ext>`;URL `https://image.boyplaymj.link/plate-refs/<refId>.<ext>`。
Lambda role 需加 `s3:PutObject`、`s3:DeleteObject`(限 `plate-refs/*`)。

## 上傳方式:base64 經 Lambda(避開 S3 bucket CORS)
車牌圖不大,用 base64 進 Lambda 再 PutObject,不用設 bucket CORS(比 presigned 簡單)。

## 加的 API routes(同 requireAdmin 授權)
| Method | Path | Body | 回傳 |
|---|---|---|---|
| POST | `/refs` | `{code, imageBase64, contentType}` | `{refId, imageUrl, code}` |
| GET | `/refs` | — | `{items:[{refId,code,imageUrl,status,createdAt}]}`（createdAt 新→舊）|
| DELETE | `/refs/{refId}` | — | `{ok:true}` |

- POST:`code` 先 `normalizeCode`,非法回 400;decode base64→PutObject 到 S3(帶 contentType)→寫 DDB status=pending→回 imageUrl。imageBase64 可含或不含 `data:...;base64,` 前綴都要處理。限制大小(如 >6MB 回 400)。
- APIGW 這三條 route 指同一 integration;Lambda invoke 權限沿用。

## 前端(laoshiji_admin.html 加新分頁)
新分頁「🔠 字元參考庫」(放在字庫覆蓋旁):
- 上傳區:file input(image)+ 號碼 input + 「上傳」鈕。流程:讀檔成 base64 → `api('/refs',{POST, body:{code,imageBase64,contentType}})` → 成功後刷新列表。
- 列表:縮圖 + 號碼標籤 + status(pending/processed)+ 刪除鈕(DELETE /refs/{refId})。
- 沿用現有 `api()` 帶 idToken。

## 驗收
- [ ] 未登入/非白名單 → 403
- [ ] POST:上傳圖+號碼 → S3 有物件、DDB 有 pending item、回 imageUrl 可讀
- [ ] code 非法(如 "xyz")→ 400
- [ ] GET:列出、新→舊、含縮圖與 status
- [ ] DELETE:S3 物件 + DDB item 都刪掉
- [ ] CORS 對遊戲館 origin;OPTIONS 過
- [ ] check-conflict.sh → deploy.sh 部署前端

## 不要做(Claude EC2 端負責)
- 裁字/建字庫:Claude 的 `extract_ref.py` + 待做 `process_refs.py`(抓 pending refs→裁字→標 processed→republish atlas)。你只要把「圖+標籤+status」存好即可。

回報:逐項對照驗收 + 端點/表名,交回 Claude vet。
