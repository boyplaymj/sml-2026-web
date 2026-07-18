# sml-puzzle-arg — ARG 兔子洞階段閘門 Lambda

stage≥4 的 keystone 內文不烘進靜態檔（view-source 可繞），改由本閘門按**全服 stage** 發放。
見 `../PHASE2-DESIGN.md`（線 2a）與 `../VERIFY-gate.md`（2a-2 驗收）。

## 端點
```
GET /arg?case=<caseId>&node=<檔名>
→ 200 text/html  當 puzzle_stage.puzzleId==cases[case].puzzleId 且 stage>=node.minStage
→ 403            其餘一律鎖（未到階/跨案/未知節點/穿越/讀失敗），不回內文
```

## 檔案
| 檔 | 作用 |
|---|---|
| `index.js` | 閘門本體（Node 20.x，零 npm 依賴：https/fs/path） |
| `cases.json` | `caseId → { puzzleId }`；決定「哪個 case 在跑才發該 case 內文」 |
| `bundles/<case>.json` | 該 case build 的 `_secret_bundle.json`（`{檔名:{minStage,html}}`）；`package.sh` 同步 |
| `package.sh` | 同步 bundles + 壓 `sml-puzzle-arg.zip` |
| `test.js` | 離線測試（mock Firestore stage），`node test.js` 9 項 |

## env（皆有預設，可不設）
`FIREBASE_PROJECT`(sml2026newscore) / `FIREBASE_KEY`(公開讀 key) / `STAGE_TTL_MS`(45000) / `ALLOWED_ORIGINS`(https://image.boyplaymj.link)

## 本地測試
```
node test.js
```

## 打包 & 部署（2a-3，先別跑部署）
```
./package.sh
aws lambda update-function-code --function-name sml-puzzle-arg --zip-file fileb://sml-puzzle-arg.zip
```
上線拿到端點後 → 填 `../mingyan-world.json` 的 `config.gateUrl` → 重跑 `build.py` → 部署 S3 殼。

## 💰 成本
讀 stage（45s 快取）+ 回內文，量級極小、免費額度內、<$1/月；純比階段不燒 LLM；無新 DDB。見 PHASE2-DESIGN §G。
