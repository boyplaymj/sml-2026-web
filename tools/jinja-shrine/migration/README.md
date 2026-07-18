# ⛩️ 甜甜神社 migration — Codex review 副本

> **這裡是 review 快照,不是執行位置。**
>
> - **權威來源 & 實際執行位置**：`/opt/sml/sweetbot-next/migration/`（另一個 git `sweetbot-next.git`，含 aws-sdk 依賴與既有 migration 慣例）。跑法 `node migration/create_shrine_tables.js` 等。
> - **這裡（`sml-2026-web.git` 的 `tools/jinja-shrine/migration/`）** 只是把 3 支腳本複製過來，讓 Codex（其 checkout 只有本 repo、看不到 sweetbot-next）能讀原始碼查驗。
> - 兩地目前 byte-identical。**Codex 驗出的任何修正，同步改兩地後才跑真實 migration。** 定案後以 sweetbot-next 那份為準。

## S0 交付（規格見 `../STAGE0.md`）
- `create_shrine_tables.js` — 建 7 表，冪等，PAY_PER_REQUEST @ ap-southeast-1，零 GSI 零 TTL
- `seed_shrine_config.js` — 種 config（PK `key="main"`），`attribute_not_exists` 防覆蓋
- `seed_shrine_omikuji.js` — 11 常規階各 1 佔位籤 + 大大吉彩蛋，items 每項帶 axis+score
