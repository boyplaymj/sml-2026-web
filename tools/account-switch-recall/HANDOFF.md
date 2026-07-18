# 交接稿:切帳號失憶 → 自動回憶(Layer 0 保底 + Layer 1 Codex 抄寫員)

**收件人**:Neku_codex
**目標**:`!切帳號` 後全頻道 session 被清空 → 每個頻道下一則訊息時,自動把「切換前的對話脈絡」餵回新 session,讓對話無縫接續。即使 main 額度已滿也要能運作。

---

## 0. 背景(為什麼是這個做法)

- `!切帳號`→`applyAccountSlot()`→`clearBridgeSessionsFile()`(`aws/discord-bridge/account_switch.go:221`)**故意**把整張 `sessions` 表清成 `{}`。原因:Claude session 綁在開它的帳號 org 上,跨帳號 `--resume` 會被伺服器拒。所以**不能靠保留 session id 續接**,只能把「內容」餵進新 session。
- 逐字稿 `<sid>.jsonl` 是對話中**即時 append 到本地硬碟**的。切換那一刻就算 main 額度 100% 滿、一個字都吐不出,到上一則成功回合為止的歷史**早已在硬碟上**。所以回憶**不需要在切換當下寫任何 LLM 產物**,事後讀檔即可 → 免疫「額度滿寫不了便條」。
- **Layer 0(保底,零 LLM)**:讀 jsonl 尾巴原文注入。任何額度狀態都能用,是最終保底。
- **Layer 1(升級)**:尾巴太雜時,交 Codex 壓成精煉便條。**Codex 是 OpenAI 獨立池**(後端 `@openai/codex`、認證 `~/.codex/auth.json`,與 Claude 的 `~/.claude` 不同源),所以 main+backup1 兩個 Anthropic 帳號同時見底也不影響 Codex。
- **降級鏈**:Codex 便條 → 原始尾巴 → 略過。任一環死了都有下一環,永不整個失敗。

---

## 1. 資料流與檔案

單一產物目錄:`$HOME/.claude/bridge-handoff/`(0700)。每個「切換前有 live session」的頻道一個檔:

`bridge-handoff/<channelID>.json`(0600,atomic 寫=先寫 `.tmp` 再 rename):
```json
{
  "channel": "1526452122504134798",
  "sid": "9e721a91-87bf-49f3-b204-20fa7583a566",
  "jsonl": "/home/smlbot/.claude/projects/-opt-sml-repo/9e721a91-....jsonl",
  "created_at": "2026-07-14T06:30:00Z",
  "note": null
}
```
- `note==null` → Codex 還沒摘要(或 Layer 1 停用)。注入端此時走 Layer 0 讀 jsonl 尾巴。
- `note=="<200字便條>"` → Codex 已寫好。注入端優先用它。

> `jsonl` 路徑取法:**不要硬編** project 目錄名。用 glob 找 `$HOME/.claude/projects/*/<sid>.jsonl`,取存在的那個(Claude 內部的路徑編碼規則不保證穩定)。

---

## 2. 主 bridge(discord-bridge,Go)要改的三處

### 2a. 切換前快照(account_switch.go)
在 `applyAccountSlot()` 內、呼叫 `clearBridgeSessionsFile()` **之前**,新增 `snapshotHandoff()`:
- `mu.Lock()` 讀當前 `sessions`(`map[channelID]sid`)複本後 unlock。
- 對每個 entry:glob 出 jsonl 路徑;寫 `bridge-handoff/<channelID>.json`(`note:null`)。
- 全程 best-effort:任何頻道失敗只 log、不擋切換主流程。
- (Layer 1 開啟時)同時把該檔視為 Codex 的工作佇列項——Codex 端輪詢這個目錄即可,不另開 queue 目錄。

### 2b. 注入(main.go,runClaude)
在 `main.go:240` 取 `sid := sessions[channelID]` 之後、`args := claudeArgs(...)` 之前:
```
若 sid == ""(新 session):
    h := loadHandoff(channelID)          // 讀 bridge-handoff/<channelID>.json
    若 h 存在:
        recall := h.note 若非空,否則 tailFromJSONL(h.jsonl)
        若 recall 非空:
            prompt = "【接續前一個帳號的對話,以下是切換前的脈絡回顧,請據此無縫接續,不要重新自我介紹】\n" + recall + "\n\n【使用者的新訊息】\n" + prompt
        consumeHandoff(channelID)         // 刪檔,消費一次(見護欄)
```
只在 `sid==""` 觸發 → 每頻道切換後只注入一次,之後新 session 自帶脈絡。

### 2c. jsonl 尾巴擷取器(新函式 tailFromJSONL)
逐行 parse jsonl,只保留 `type in {"user","assistant"}`:
- `user`:取 `message.content`(字串)。跳過以 `!` 開頭的 bridge 指令行與空字串。
- `assistant`:`message.content` 是陣列,**只串接 `block.type=="text"` 的 `text`**;丟掉 `thinking` 與 `tool_use`/`tool_result`。
- 其餘 type(`queue-operation`/`attachment`/`ai-title`/`last-prompt`/`system`…)一律跳過。
- 取**最後 N 輪**(建議 `HANDOFF_TAIL_TURNS`=12,一輪=一則 user 或一則 assistant),組成:
  ```
  使用者:...
  你(上一帳號):...
  ```
- **總長度上限** `HANDOFF_TAIL_MAXCHARS`(建議 6000 字元):超過就從尾端往前砍,保留最近的。
- 檔不存在 / parse 全失敗 → 回空字串(注入端就略過,靜默降級)。

---

## 3. Codex 端(codex-bridge)—— Layer 1 抄寫員

新增一個輕量 worker(可在 codex-bridge 開機起一條 goroutine,或獨立小程式 + systemd timer;**擇一,別兩份**):
- 每 ~20s 掃 `$HOME/.claude/bridge-handoff/*.json`,挑 `note==null` 的。
- 對每個:讀其 `jsonl` → 取尾巴原文(同 §2c 規則,可較長,如 12000 字元)→ 丟給 codex:
  > 「把以下 Discord 頻道對話壓成 ≤200 字的交接便條,給『接手同一個頻道、但失憶了的你自己』看。只保留:當前在做什麼、已決定/待辦、關鍵 ID 或檔名。用第二人稱、條列、繁中。」
- 拿到便條 → **原子改寫**該 json 的 `note` 欄(open→確認檔還在→寫 `.tmp`→rename)。
- 用 Codex 自己的 `codex exec`(OpenAI 池),不碰 Claude 額度。
- worker 失敗 / Codex 也滿 → 不改 `note`,留 `null` → 注入端自動退回 Layer 0 尾巴。

---

## 4. 護欄 / 邊界

1. **消費一次**:注入後刪 `bridge-handoff/<channelID>.json`。若 Codex worker 正好在此之後才寫回 `note`→變孤兒檔,無害(下次切換覆蓋);另加 **TTL 清理**:注入端與 worker 遇到 `created_at` 超過 24h 的檔直接刪。
2. **原子寫**:所有寫入走 `.tmp`→`rename`,權限 0600,目錄 0700。
3. **best-effort**:快照、摘要、注入任一步失敗都只 log,**絕不擋**切換或正常對話。
4. **jsonl 不存在**:glob 找不到就跳過該頻道(靜默)。
5. **不改切換的既有安全行為**:備份、清表、restart 全部照舊,只在「清表前」多一步快照、「起新 session 前」多一步注入。
6. **env 旋鈕**:`HANDOFF_ENABLED`(預設 on)、`HANDOFF_TAIL_TURNS=12`、`HANDOFF_TAIL_MAXCHARS=6000`、`HANDOFF_L1_CODEX`(Layer 1 開關,預設 on;關掉就純 Layer 0)。

---

## 5. 驗收(請實測,不要只看 code)

1. **保底(Layer 0,主場景)**:在某頻道跟 main 聊 3–4 輪且有明確主題/待辦 → `!切帳號 backup1` → 該頻道發一句「我們剛剛講到哪?」→ **新帳號的回覆要能講出切換前的主題與待辦**,且沒有重新自我介紹。
2. **額度滿也行**:模擬 main 已滿(或直接測「切換當下不呼叫任何 Claude」)→ 回憶仍成立(因為只讀檔)。
3. **Layer 1**:切換後等 worker 跑完 → `bridge-handoff/<id>.json` 的 `note` 非空 → 注入用的是精煉便條而非長尾巴(log 標明走哪條)。
4. **降級**:把 `HANDOFF_L1_CODEX` 關掉 → 仍能用 Layer 0 尾巴接續。
5. **不回歸**:切換的備份/清表/restart 行為不變;未切換的正常對話完全不受影響(`sid!=""` 不進注入分支)。
6. **一次性**:切換後同頻道第 2、3 則訊息不再重複注入回顧。

---

## 6. 改動檔案清單
- `aws/discord-bridge/account_switch.go`:`snapshotHandoff()` + 在 `applyAccountSlot` 清表前呼叫。
- `aws/discord-bridge/main.go`:`runClaude` 注入分支;`tailFromJSONL()`、`loadHandoff()`/`consumeHandoff()` 工具函式。
- `aws/codex-bridge/`:handoff worker(goroutine 或獨立 timer 程式)。
- 新增 `_test.go`:`tailFromJSONL` 對 §2c 各 type 的擷取、長度上限、空檔降級。

部署:兩支 bridge 各自 `go build`→換 binary→重啟(**codex-bridge 部署要完整 build→cp→start,別停在半路**)。先上主 bridge 的 Layer 0(可獨立驗收),再上 Codex worker 的 Layer 1。
