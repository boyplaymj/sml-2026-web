# bug-scanner — bug 回報區自動判定

持有「天王里里民」身分組的成員在 Discord「🍍bug回報區」頻道(客戶可見的**回報入口**)用白話描述
遇到的 bug,系統每天 04:00(台灣)或手動掃描一次,把回報交給 headless `claude` 判定分類,
報告貼到**私人頻道**(`BUG_POST_CHANNEL`,預設 903327108451950692,客戶看不到)——入口頻道保持乾淨。

⚠️ 教訓(2026-07-18 首跑):報告最初貼回入口頻道 → 客戶看到內部診斷,已改貼私頻。AUTO_FIX 首跑
時 claude 在 worktree 亂刪無關已提交檔(且真正的 BJ bug 在 sweetbot-next 另一 repo、本 worktree
動不到)→ 已預設關閉,需更嚴圍欄才重開。

資格判定:作者(非 bot)必須持有身分組 `872861844388335617`(天王里里民)才算有效回報;抓訊息
不帶身分組資料,故逐個作者查一次 guild member(有快取)。

## 資料流

```
tenten 在頻道 1527659065281609828 發回報
        │
        ▼  (每天 04:00 台灣 systemd timer / 手動 systemctl start)
scan.py  ── SSM 拿 bot token → Discord 抓「游標之後」訊息 → 篩出「作者持天王里里民身分組」的
        │
        ├─ 無新回報 → 只推進游標,結束(不燒 claude)
        │
        ▼  有回報
建立隔離 git worktree(從乾淨 HEAD 拉出,碰不到主樹 WIP)
        │
        ▼
claude -p(bypassPermissions,cwd=worktree)逐則判定:
   ✅ 明確 bug     → (診斷模式)附修法+patch / (AUTO_FIX)在 bug-scan/<date> 分支 commit
   🤔 需要決策     → 整理成 問題/選項/建議 清單,不改 code
   ❓ 資訊不足     → 列出要追問的問題
        │
        ▼
報告貼回頻道(分段 <2000 字)→ 推進游標 → 移除 worktree(AUTO_FIX 保留分支)
```

## 判定邊界(安全鐵律)

- **隔離**:每次都在 `/tmp/bug-scan-*` 的獨立 worktree 跑,**碰不到主工作樹一堆未提交 WIP**(避開「併行快照吃 WIP」雷)。
- **永不 push、永不部署**。AUTO_FIX 開啟也只在 `bug-scan/<date>` 分支 commit,等人複核走正常部署流程。
- **保守分類**:模稜兩可一律歸「需要決策 / 需補充」,不亂改 code。
- **首次執行不回溯歷史**:第一次跑只記基準游標,只處理之後的新回報。

## 開關 / 操作

| 動作 | 指令 |
|---|---|
| 安裝 + 啟用 timer | `sudo tools/bug-scanner/install.sh` |
| 手動掃一次 | `sudo systemctl start sml-bug-scanner.service` 然後 `journalctl -u sml-bug-scanner -f` |
| 本機乾跑(不貼 Discord) | `BUG_SCANNER_DRY_RUN=1 python3 tools/bug-scanner/scan.py` |
| 打開自動修 code | service 檔改 `BUG_AUTO_FIX=1` → `daemon-reload` |
| kill switch | `sudo systemctl disable --now sml-bug-scanner.timer`(或 service 檔 `BUG_SCANNER_ENABLED=0`) |
| 看下次觸發 | `systemctl list-timers sml-bug-scanner.timer` |

環境變數清單見 `scan.py` 檔頭。游標狀態存 `~/.claude/bug-scanner/state.json`。

## 💰 成本控管(遵循 tools/COST_CONTROL.md)

- **成本來源**:只燒 **Claude Code Max 訂閱額度**(headless `claude -p` 判定回報);**無 Bedrock、無新 DDB 表、無付費 API**。Discord API 免費。
- **預估量級**:每次掃描約 50k–200k token(視回報則數 + 要翻多少 code);**每天最多一次**,故月量級小、可控。
- **煞車四道**(對應規範精神,無 Bedrock 故不套帳本表):
  1. **一天一次**(非即時、非每則訊息)—— 這是最大的省 token 設計。
  2. **無回報早退**:沒有新回報就不叫 claude,零花費。
  3. **單次上限** `BUG_MAX_REPORTS`(預設 20),爆量不會一次燒穿,剩的下次再掃。
  4. **kill switch** `BUG_SCANNER_ENABLED=0` / 停 timer,立即歸零。
- 因走訂閱非 Bedrock,故不建帳本表/月封頂 cap;若日後改走 Bedrock,回規範補齊四件套。
- 額度可視:`tools/token-usage/report.py` 可看本工具佔比。
