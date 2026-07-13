// SML Discord <-> OpenAI Codex bridge（SML_Claude 的搭檔）
//
// 收 Discord 訊息 -> 在 EC2 上跑 `codex exec`(headless,沿用同一個專案目錄與工具)
// -> 把回覆貼回頻道。每個頻道用 `codex exec resume <thread_id>` 維持對話脈絡。
//
// 與 claude 版共用同一套 Discord 處理(mention 路由、附件、按鈕、分段),只換掉後端執行層:
//
//	claude -p --output-format json      →  codex exec --json（JSONL 事件流）
//	res.session_id                       →  thread.started 事件的 thread_id
//	--resume <sid>                       →  exec resume <thread_id>
//	--permission-mode bypassPermissions  →  --dangerously-bypass-approvals-and-sandbox
//
// 安全:只回應 ALLOWED_CHANNELS(必要)與 ALLOWED_USERS(選填)白名單內、且 @ 到「本 bot」的訊息。
// 兩支 bot 各認各的 botID → 同頻道 @codex 只有這支醒、@claude 只有那支醒,天生不打架。
// 機密(Discord token)由 run.sh 從 AWS SSM 讀進環境變數,不寫進 repo。
// Codex 認證走 `codex login`(存 ~/.codex),不需 API key。
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"
)

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func envInt(k string, def int) int {
	if v := os.Getenv(k); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return def
}

// 「開新對話」指令關鍵字(清空該頻道 session)
var resetCmds = map[string]bool{
	"new": true, "reset": true, "/new": true, "/reset": true,
	"清空": true, "重來": true, "開新對話": true, "新對話": true, "重新開始": true,
}

// stripMention 去掉 bot 的 @mention(含身分組 mention),回傳純文字內容。
func stripMention(content, botID string, roleIDs map[string]bool) string {
	content = strings.ReplaceAll(content, "<@"+botID+">", "")
	content = strings.ReplaceAll(content, "<@!"+botID+">", "")
	for id := range roleIDs {
		content = strings.ReplaceAll(content, "<@&"+id+">", "")
	}
	return strings.TrimSpace(content)
}

// botRoleIDs 回傳 bot 在該 guild 的身分組 ID 集合。
// Discord 的 @ 選單常讓人選到 bot 的「整合身分組」而不是 bot 使用者,兩種 tag 都要視為觸發。
func botRoleIDs(s *discordgo.Session, guildID string) map[string]bool {
	set := map[string]bool{}
	if guildID == "" {
		return set
	}
	member, err := s.State.Member(guildID, s.State.User.ID)
	if err != nil {
		if member, err = s.GuildMember(guildID, s.State.User.ID); err != nil {
			return set
		}
	}
	for _, r := range member.Roles {
		set[r] = true
	}
	return set
}

func csvSet(s string) map[string]bool {
	m := map[string]bool{}
	for _, p := range strings.Split(s, ",") {
		if p = strings.TrimSpace(p); p != "" {
			m[p] = true
		}
	}
	return m
}

var (
	allowedChannels = csvSet(os.Getenv("ALLOWED_CHANNELS"))
	allowedGuilds   = csvSet(os.Getenv("ALLOWED_GUILDS"))
	allowedUsers    = csvSet(os.Getenv("ALLOWED_USERS"))
	// bot↔bot 互通:只有 PEER_BOT_ID 這顆 AI bot、且在 DISCUSS_CHANNELS 白名單頻道,才准跨 bot 觸發本 bot。
	peerBotID       = os.Getenv("PEER_BOT_ID")
	discussChannels = csvSet(os.Getenv("DISCUSS_CHANNELS"))
	maxBotExchanges = envInt("MAX_BOT_EXCHANGES", 3) // 兩則人類訊息間,bot↔bot 最多來回幾次
	botExchMu       sync.Mutex
	botExchange     = map[string]int{} // channelID -> 連續 bot↔bot 來回計數(人類發言歸零)
	readTargetBotID = env("READ_TARGET_BOT_ID", peerBotID)
	readFetchLimit  = envInt("READ_FETCH_LIMIT", 50)
	registerCmdOnce sync.Once
	// codex CLI 裝在 nvm 的 node22 底下(與系統 node18 隔離)。run.sh 會用絕對路徑覆蓋，
	// 這裡的預設值是保險：直接指向 nvm 那顆，即使 PATH 沒帶到也能跑。
	codexBin        = env("CODEX_BIN", "/home/smlbot/.nvm/versions/node/v22.23.1/bin/codex")
	codexModel      = env("CODEX_MODEL", "") // 空 = 用 codex 設定檔預設模型
	workdir         = env("CLAUDE_WORKDIR", ".")
	channelWorkdirs = parseChannelWorkdirs(os.Getenv("CHANNEL_WORKDIRS"))
	timeoutMin      = envInt("CLAUDE_TIMEOUT_MIN", 25) // 單一訊息處理逾時(分鐘)

	mu       sync.Mutex
	sessions = map[string]string{} // channelID -> codex thread id

	// 同頻道序列化：每個 channel 一把鎖，確保「一次只跑一個 claude」。
	// 否則使用者連發訊息時，discordgo 會各開 goroutine 同時起兩個 claude --resume（共用同一 session
	// 與工作目錄）→ 兩個實例互相覆蓋檔案、各跑重複建置、搶寫 registry。
	chanLocks sync.Map // channelID -> *sync.Mutex
)

// chanLock 取得某頻道專屬的鎖（不存在就建立）。
func chanLock(channelID string) *sync.Mutex {
	v, _ := chanLocks.LoadOrStore(channelID, &sync.Mutex{})
	return v.(*sync.Mutex)
}

// 對談 session 持久化：存磁碟 → bridge 重啟不會丟失各頻道對話脈絡(否則重啟＝所有對話重置)。
func sessionsFile() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".claude", "codex-bridge-sessions.json")
}

func loadSessions() {
	data, err := os.ReadFile(sessionsFile())
	if err != nil {
		return
	}
	mu.Lock()
	defer mu.Unlock()
	_ = json.Unmarshal(data, &sessions)
}

// 呼叫端須已持有 mu。
func saveSessionsLocked() {
	data, err := json.Marshal(sessions)
	if err != nil {
		return
	}
	_ = os.WriteFile(sessionsFile(), data, 0600)
}

func parseChannelWorkdirs(s string) map[string]string {
	m := map[string]string{}
	for _, part := range strings.Split(s, ",") {
		part = strings.TrimSpace(part)
		if idx := strings.IndexByte(part, '='); idx > 0 {
			m[part[:idx]] = part[idx+1:]
		}
	}
	return m
}

func workdirFor(channelID string) string {
	if d, ok := channelWorkdirs[channelID]; ok {
		return d
	}
	return workdir
}

func sharedBrainRoot() string {
	return env("SML_BRAIN_ROOT", "/mnt/sml-brain")
}

func readSmallFile(path string, maxBytes int) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	truncated := false
	if maxBytes > 0 && len(data) > maxBytes {
		data = data[:maxBytes]
		truncated = true
	}
	text := strings.TrimSpace(string(data))
	if text == "" {
		return ""
	}
	if truncated {
		text += "\n...[truncated]"
	}
	return text
}

func containsAnyFold(text string, terms ...string) bool {
	lower := strings.ToLower(text)
	for _, term := range terms {
		if strings.Contains(lower, strings.ToLower(term)) {
			return true
		}
	}
	return false
}

func shouldLoadAgentPractices(prompt string) bool {
	return containsAnyFold(prompt,
		"debug", "root cause", "error", "failed", "failure", "bug", "broken", "verify", "verification",
		"test", "deploy", "journalctl", "systemctl", "unknown error", "trace", "regression",
		"除錯", "錯誤", "失敗", "壞掉", "問題", "驗證", "測試", "修", "修好", "上線", "部署", "看下",
	)
}

func shouldLoadSharedMemoryPolicy(prompt string) bool {
	return containsAnyFold(prompt,
		"sml-brain", "shared brain", "shared memory", "agent-practices", "write-policy", "s3 files",
		"/mnt/sml-brain", "global/hot", "inbox", "handoff",
		"共享大腦", "共享記憶", "寫入", "記住", "沉澱", "記憶", "共用目錄",
	)
}

func sharedBrainContext(prompt string, newThread bool) string {
	root := sharedBrainRoot()
	if root == "" {
		return ""
	}

	type item struct {
		label string
		path  string
		limit int
	}
	items := []item{}

	// New threads get only lightweight routing indexes so Codex can discover
	// durable shared memory without loading every hot file on every turn.
	if newThread {
		items = append(items,
			item{"INDEX.claude.md", filepath.Join(root, "INDEX.claude.md"), 2500},
			item{"INDEX.codex.md", filepath.Join(root, "INDEX.codex.md"), 2500},
		)
	}

	if shouldLoadAgentPractices(prompt) {
		items = append(items,
			item{"global/hot/agent-practices.md", filepath.Join(root, "global", "hot", "agent-practices.md"), 5000},
		)
	}

	if shouldLoadSharedMemoryPolicy(prompt) {
		items = append(items,
			item{"global/hot/write-policy.md", filepath.Join(root, "global", "hot", "write-policy.md"), 6500},
			item{"global/hot/collaboration.md", filepath.Join(root, "global", "hot", "collaboration.md"), 4500},
		)
	}

	seen := map[string]bool{}
	parts := []string{}
	for _, it := range items {
		if seen[it.path] {
			continue
		}
		seen[it.path] = true
		text := readSmallFile(it.path, it.limit)
		if text == "" {
			continue
		}
		parts = append(parts, "## "+it.label+"\n"+text)
	}
	if len(parts) == 0 {
		return ""
	}
	return "Shared-brain context from " + root + " (read-only; explicit user instructions and current repo state win):\n\n" +
		strings.Join(parts, "\n\n---\n\n")
}

func augmentPromptWithSharedBrain(channelID, prompt string, newThread bool) string {
	ctx := sharedBrainContext(prompt, newThread)
	if ctx == "" {
		return prompt
	}
	log.Printf("shared-brain context injected ch=%s new_thread=%v bytes=%d", channelID, newThread, len(ctx))
	return ctx + "\n\n---\n\nUser request:\n" + prompt
}

// codexEvent 是 `codex exec --json` JSONL 串流裡的一個事件。
// 我們只需要兩種：thread.started（第一行，帶 thread_id → 存為該頻道 session）、
// 以及 error（把訊息撈出來回報）。最終回覆文字改用 `-o <file>` 直接落地，較穩。
type codexEvent struct {
	Type     string `json:"type"`
	ThreadID string `json:"thread_id"`
	Message  string `json:"message"`
}

func firstLine(s string) string {
	s = strings.TrimSpace(s)
	if i := strings.IndexByte(s, '\n'); i > 0 {
		return s[:i]
	}
	if s == "" {
		return "unknown error"
	}
	return s
}

// runCodex 在工作目錄跑 headless `codex exec`,維持每個頻道的 thread(對話脈絡)。
func runCodex(ctx context.Context, channelID, prompt string) string {
	// 同頻道序列化：一次只跑一個 codex。第二則訊息會在這裡等前一則跑完再進場，
	// 杜絕「兩個 codex resume 同一 thread、同一工作目錄」互相覆蓋檔案／搶寫。
	lk := chanLock(channelID)
	lk.Lock()
	defer lk.Unlock()

	mu.Lock()
	sid := sessions[channelID]
	mu.Unlock()
	prompt = augmentPromptWithSharedBrain(channelID, prompt, sid == "")

	// 最終回覆用 -o 寫到暫存檔（比從 JSONL 掃最後一則 agent 訊息穩）。
	tmp, err := os.CreateTemp("", "codex-out-*.txt")
	if err != nil {
		return "⚠️ 無法建立暫存檔：" + err.Error()
	}
	outFile := tmp.Name()
	tmp.Close()
	defer os.Remove(outFile)

	// 組指令：
	//   首次   codex exec        --json --dangerously-... [-m model] -o <file> -   (prompt 走 stdin)
	//   續接   codex exec resume <thread_id> --json --dangerously-... [-m model] -o <file> -   (prompt 走 stdin)
	var args []string
	if sid != "" {
		args = []string{"exec", "resume", sid}
	} else {
		args = []string{"exec"}
	}
	args = append(args, "--json", "--dangerously-bypass-approvals-and-sandbox", "-o", outFile)
	if codexModel != "" {
		args = append(args, "-m", codexModel)
	}
	// 用 "-" 讓 codex 從 stdin 讀 prompt(官方文件保證:exec / exec resume 的 [PROMPT] 給 "-" 即讀 stdin),
	// 而不是把 prompt 當 argv 位置參數。這樣即使 prompt 以 "-" 開頭也不會被 clap 誤判成 option,
	// 對稱 claude 版把 prompt 放在 `--` 之後的保護。
	args = append(args, "-")

	cmd := exec.CommandContext(ctx, codexBin, args...)
	cmd.Dir = workdirFor(channelID)
	cmd.Stdin = strings.NewReader(prompt)
	// 把來源頻道 ID 注入對話環境(與 claude 版一致,供 hook 依頻道判斷)。
	// 同時把 nvm node22 的 bin 掛進 PATH,確保 codex 及其相依可被解析。
	nodeBin := filepath.Dir(codexBin)
	cmd.Env = append(os.Environ(),
		"SML_DISCORD_CHANNEL="+channelID,
		"PATH="+nodeBin+":"+os.Getenv("PATH"),
	)
	var out, errb bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &errb
	if err := cmd.Run(); err != nil {
		log.Printf("codex error: %v | stderr: %s", err, errb.String())
		msg := codexErrorMsg(out.Bytes())
		if msg == "" {
			msg = firstLine(errb.String())
		}
		return "⚠️ 執行出錯：" + msg
	}

	// 掃 JSONL 拿 thread_id(第一次對話時才會需要存起來)。
	if tid := parseThreadID(out.Bytes()); tid != "" && tid != sid {
		mu.Lock()
		sessions[channelID] = tid
		saveSessionsLocked()
		mu.Unlock()
	}

	// 讀最終回覆。
	reply, _ := os.ReadFile(outFile)
	text := strings.TrimSpace(string(reply))
	if text == "" {
		return "(完成,但沒有文字輸出)"
	}
	return text
}

// parseThreadID 從 codex JSONL 串流找第一個 thread.started 事件的 thread_id。
func parseThreadID(jsonl []byte) string {
	for _, line := range strings.Split(string(jsonl), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		var ev codexEvent
		if json.Unmarshal([]byte(line), &ev) != nil {
			continue
		}
		if ev.Type == "thread.started" && ev.ThreadID != "" {
			return ev.ThreadID
		}
	}
	return ""
}

// codexErrorMsg 從 JSONL 串流撈 error 事件的訊息(cmd 失敗時用)。
func codexErrorMsg(jsonl []byte) string {
	for _, line := range strings.Split(string(jsonl), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		var ev codexEvent
		if json.Unmarshal([]byte(line), &ev) != nil {
			continue
		}
		if ev.Type == "error" && ev.Message != "" {
			return ev.Message
		}
	}
	return ""
}

func allowedMsg(s *discordgo.Session, m *discordgo.MessageCreate) bool {
	// 範圍:有設 ALLOWED_GUILDS 就允許「整個伺服器」的所有頻道(新開頻道自動生效);
	// 另外仍尊重逐頻道白名單 ALLOWED_CHANNELS —— 這樣可以放行「不在允許伺服器、
	// 但明確列進白名單的單一頻道」(例如跨伺服器的股市收件匣頻道)。
	if len(allowedGuilds) > 0 {
		if !allowedGuilds[m.GuildID] && !allowedChannels[m.ChannelID] {
			return false
		}
	} else if len(allowedChannels) > 0 && !allowedChannels[m.ChannelID] {
		return false
	}
	if len(allowedUsers) > 0 && !allowedUsers[m.Author.ID] {
		return false
	}
	// 只回應 mention bot(使用者或其身分組)或回覆 bot 訊息的情況
	botID := s.State.User.ID
	if strings.Contains(m.Content, "<@"+botID+">") || strings.Contains(m.Content, "<@!"+botID+">") {
		return true
	}
	if len(m.MentionRoles) > 0 {
		roles := botRoleIDs(s, m.GuildID)
		for _, r := range m.MentionRoles {
			if roles[r] {
				return true
			}
		}
	}
	if m.MessageReference != nil && m.MessageReference.MessageID != "" {
		ref, err := s.ChannelMessage(m.ChannelID, m.MessageReference.MessageID)
		if err == nil && ref.Author.ID == botID {
			return true
		}
	}
	return false
}

// downloadAttachment 把 Discord 附件下載到暫存檔,回傳路徑。
func downloadAttachment(url, filename string) (string, error) {
	resp, err := http.Get(url) //nolint:gosec
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	ext := filepath.Ext(filename)
	tmp, err := os.CreateTemp("", "discord-att-*"+ext)
	if err != nil {
		return "", err
	}
	defer tmp.Close()
	if _, err := io.Copy(tmp, resp.Body); err != nil {
		os.Remove(tmp.Name())
		return "", err
	}
	return tmp.Name(), nil
}

// downloadTextContent 把 Discord 文字附件下載並以字串回傳(最多 200KB)。
func downloadTextContent(url string) (string, error) {
	resp, err := http.Get(url) //nolint:gosec
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	const maxSize = 200 * 1024
	b, err := io.ReadAll(io.LimitReader(resp.Body, maxSize))
	if err != nil {
		return "", err
	}
	return string(b), nil
}

var textExts = map[string]bool{
	".txt": true, ".html": true, ".htm": true,
	".js": true, ".css": true, ".json": true,
	".md": true, ".yaml": true, ".yml": true,
	".py": true, ".go": true, ".ts": true,
	".tsx": true, ".jsx": true, ".xml": true,
	".sh": true, ".sql": true, ".csv": true,
}

// sendChunked 因應 Discord 單則 2000 字上限,分段送出。
func sendChunked(s *discordgo.Session, channelID, text string) {
	const max = 1900
	for len(text) > 0 {
		n := len(text)
		if n > max {
			n = max
			if idx := strings.LastIndexByte(text[:max], '\n'); idx > 200 {
				n = idx
			}
		}
		if _, err := s.ChannelMessageSend(channelID, text[:n]); err != nil {
			log.Printf("send error: %v", err)
		}
		text = text[n:]
	}
}

// ── 互動按鈕支援 ──────────────────────────────────────────────────────────────
//
// Claude 回應中可以用 [[BTN:顯示文字:custom_id]] 插入按鈕，例如：
//   要發布更新日誌嗎？
//   [[BTN:✅ 發布:publish]][[BTN:✏️ 修改:edit]][[BTN:❌ 取消:cancel]]
//
// Bridge 會把標記去除，並附上實體按鈕。
// 使用者點按鈕後，Bridge 把 「[按鈕點擊] 使用者名稱 點了「顯示文字」(custom_id)」
// 送回給 Claude，讓對話繼續。

var btnRe = regexp.MustCompile(`\[\[BTN:([^:\]]+):([^\]]+)\]\]`)

type btnDef struct{ label, id string }

// parseButtons 從文字中提取所有 [[BTN:...]] 標記，回傳乾淨文字與按鈕列表。
func parseButtons(text string) (string, []btnDef) {
	var btns []btnDef
	clean := btnRe.ReplaceAllStringFunc(text, func(m string) string {
		sub := btnRe.FindStringSubmatch(m)
		if len(sub) == 3 {
			id := sub[2]
			if len(id) > 100 {
				id = id[:100]
			}
			btns = append(btns, btnDef{label: sub[1], id: id})
		}
		return ""
	})
	return strings.TrimSpace(clean), btns
}

// sendWithButtons 送出回覆:解析 [[BTN]] 標記,並在 bot↔bot 頻道底部自動加「轉傳給對方」按鈕。
func sendWithButtons(s *discordgo.Session, channelID, text string) {
	clean, btns := parseButtons(text)
	var rows []discordgo.MessageComponent
	// Discord 每列最多 5 顆按鈕
	if len(btns) > 5 {
		btns = btns[:5]
	}
	if len(btns) > 0 {
		var comps []discordgo.MessageComponent
		for _, b := range btns {
			comps = append(comps, discordgo.Button{Label: b.label, Style: discordgo.PrimaryButton, CustomID: b.id})
		}
		rows = append(rows, discordgo.ActionsRow{Components: comps})
	}
	// bot↔bot 頻道:回覆底部自動掛「➡️ 轉傳給對方」按鈕。
	if fwd := forwardButtonRow(channelID); fwd != nil {
		rows = append(rows, fwd...)
	}
	if len(rows) == 0 {
		sendChunked(s, channelID, clean)
		return
	}
	sendChunkedWithComponents(s, channelID, clean, rows)
}

// sendChunkedWithComponents 分段送出文字,把 components(按鈕)掛在最後一段。
func sendChunkedWithComponents(s *discordgo.Session, channelID, text string, rows []discordgo.MessageComponent) {
	full := text // 整段回覆(轉傳要用),先存;下面分段會把 text 切掉。
	const max = 1900
	for len(text) > max {
		n := max
		if idx := strings.LastIndexByte(text[:max], '\n'); idx > 200 {
			n = idx
		}
		if _, err := s.ChannelMessageSend(channelID, text[:n]); err != nil {
			log.Printf("send error: %v", err)
		}
		text = text[n:]
	}
	if strings.TrimSpace(text) == "" {
		text = "⬇️"
	}
	msg := &discordgo.MessageSend{Content: text, Components: rows}
	sent, err := s.ChannelMessageSendComplex(channelID, msg)
	if err != nil {
		log.Printf("send with components error: %v — fallback text", err)
		sendChunked(s, channelID, text)
		return
	}
	if sent != nil {
		rememberReply(sent.ID, full) // 讓「轉傳給對方」抓得到整段回覆,不只最後一段
	}
}

// disableChoiceButtons 回傳「把選項鈕反灰」後的 components:點過的選項鈕禁用(選中的轉綠標示),
// 但轉傳(fwd:)與白名單(b2b:)鈕保留可點(那些本來就要重複互動)。用於選項按鈕點擊後避免重送。
func disableChoiceButtons(msg *discordgo.Message, clickedID string) []discordgo.MessageComponent {
	if msg == nil {
		return nil
	}
	var rows []discordgo.MessageComponent
	for _, row := range msg.Components {
		ar, ok := row.(discordgo.ActionsRow)
		if !ok {
			rows = append(rows, row)
			continue
		}
		var comps []discordgo.MessageComponent
		for _, comp := range ar.Components {
			btn, ok := comp.(discordgo.Button)
			if !ok {
				comps = append(comps, comp)
				continue
			}
			if btn.CustomID == "fwd:peer" || strings.HasPrefix(btn.CustomID, "b2b:") {
				comps = append(comps, btn) // 轉傳/白名單鈕保持可點
				continue
			}
			btn.Disabled = true
			if btn.CustomID == clickedID {
				btn.Style = discordgo.SuccessButton // 標出使用者選了哪個
			}
			comps = append(comps, btn)
		}
		rows = append(rows, discordgo.ActionsRow{Components: comps})
	}
	return rows
}

// ─────────────────────────────────────────────────────────────────────────────
// 設定檔驅動的固定指令(commands.json)：使用者自己加 !指令 → 推 Embed。
// 每次呼叫都重讀檔案，所以改 commands.json 立即生效、不用重編譯/重啟。
type bridgeCmd struct {
	Cmd    string `json:"cmd"`
	Title  string `json:"title"`
	Desc   string `json:"desc"`
	URL    string `json:"url"`
	Color  int    `json:"color"`
	Fields []struct {
		Name   string `json:"name"`
		Value  string `json:"value"`
		Inline bool   `json:"inline"`
	} `json:"fields"`
}

func commandsPath() string {
	if p := os.Getenv("BRIDGE_COMMANDS"); p != "" {
		return p
	}
	return "/opt/sml/repo/aws/discord-bridge/commands.json"
}

// tryBridgeCommand：若 stripped 的第一個 token 命中 commands.json 的指令，送 Embed 並回傳 true。
func tryBridgeCommand(s *discordgo.Session, m *discordgo.MessageCreate, stripped string) bool {
	cmd := strings.TrimSpace(stripped)
	if i := strings.IndexAny(cmd, " \t\n"); i >= 0 {
		cmd = cmd[:i]
	}
	data, err := os.ReadFile(commandsPath())
	if err != nil {
		return false
	}
	var cmds []bridgeCmd
	if err := json.Unmarshal(data, &cmds); err != nil {
		log.Printf("commands.json parse error: %v", err)
		return false
	}
	for _, c := range cmds {
		if c.Cmd != cmd {
			continue
		}
		color := c.Color
		if color == 0 {
			color = 0xf9a8d4
		}
		emb := &discordgo.MessageEmbed{Title: c.Title, Description: c.Desc, URL: c.URL, Color: color}
		for _, f := range c.Fields {
			emb.Fields = append(emb.Fields, &discordgo.MessageEmbedField{Name: f.Name, Value: f.Value, Inline: f.Inline})
		}
		if _, err := s.ChannelMessageSendEmbed(m.ChannelID, emb); err != nil {
			log.Printf("bridge command embed send error: %v", err)
		}
		return true
	}
	return false
}

func allowedInteraction(i *discordgo.InteractionCreate) bool {
	if len(allowedGuilds) > 0 {
		if !allowedGuilds[i.GuildID] && !allowedChannels[i.ChannelID] {
			return false
		}
	} else if len(allowedChannels) > 0 && !allowedChannels[i.ChannelID] {
		return false
	}
	if len(allowedUsers) == 0 {
		return true
	}
	if i.Member != nil && i.Member.User != nil {
		return allowedUsers[i.Member.User.ID]
	}
	if i.User != nil {
		return allowedUsers[i.User.ID]
	}
	return false
}

func registerApplicationCommands(s *discordgo.Session, guilds []*discordgo.Guild) {
	cmd := &discordgo.ApplicationCommand{
		Name:        "read",
		Description: "讀取 SML_Claude 在本頻道最近一段文字,並交給 SML_Codex 回覆",
		Options: []*discordgo.ApplicationCommandOption{
			{
				Type:        discordgo.ApplicationCommandOptionString,
				Name:        "q",
				Description: "你要 SML_Codex 針對該訊息做什麼",
				Required:    true,
			},
			{
				Type:        discordgo.ApplicationCommandOptionUser,
				Name:        "target",
				Description: "要讀取的 bot,預設為 SML_Claude",
				Required:    false,
			},
		},
	}

	guildIDs := map[string]bool{}
	if len(allowedGuilds) > 0 {
		for id := range allowedGuilds {
			guildIDs[id] = true
		}
	} else {
		for _, g := range guilds {
			if g != nil && g.ID != "" {
				guildIDs[g.ID] = true
			}
		}
	}
	for guildID := range guildIDs {
		if _, err := s.ApplicationCommandCreate(s.State.User.ID, guildID, cmd); err != nil {
			log.Printf("slash command register error guild=%s: %v", guildID, err)
			continue
		}
		log.Printf("slash command /read registered guild=%s", guildID)
	}
}

func optionUserID(opt *discordgo.ApplicationCommandInteractionDataOption) string {
	if opt == nil || opt.Value == nil {
		return ""
	}
	if s, ok := opt.Value.(string); ok {
		return s
	}
	return fmt.Sprint(opt.Value)
}

func latestTextBlockFromMessages(messages []*discordgo.Message, targetID string) (string, []*discordgo.Message) {
	var block []*discordgo.Message
	var newest time.Time
	for _, msg := range messages {
		if msg == nil || msg.Author == nil {
			continue
		}
		content := strings.TrimSpace(msg.Content)
		if msg.Author.ID == targetID && content != "" {
			if len(block) == 0 {
				newest = msg.Timestamp
			} else if !newest.IsZero() && !msg.Timestamp.IsZero() && newest.Sub(msg.Timestamp) > 2*time.Minute {
				break
			}
			block = append(block, msg)
			continue
		}
		if len(block) > 0 {
			break
		}
	}
	if len(block) == 0 {
		return "", nil
	}
	for i, j := 0, len(block)-1; i < j; i, j = i+1, j-1 {
		block[i], block[j] = block[j], block[i]
	}
	parts := make([]string, 0, len(block))
	for _, msg := range block {
		parts = append(parts, strings.TrimSpace(msg.Content))
	}
	return strings.Join(parts, "\n\n"), block
}

func fetchLatestTextBlock(s *discordgo.Session, channelID, targetID string) (string, []*discordgo.Message, error) {
	limit := readFetchLimit
	if limit <= 0 {
		limit = 50
	}
	if limit > 100 {
		limit = 100
	}
	msgs, err := s.ChannelMessages(channelID, limit, "", "", "")
	if err != nil {
		return "", nil, err
	}
	text, block := latestTextBlockFromMessages(msgs, targetID)
	if text == "" {
		return "", nil, fmt.Errorf("找不到指定 bot 在最近 %d 則內的文字訊息", limit)
	}
	return text, block, nil
}

func interactionTextOption(data discordgo.ApplicationCommandInteractionData, name string) string {
	for _, opt := range data.Options {
		if opt.Name == name {
			return strings.TrimSpace(opt.StringValue())
		}
	}
	return ""
}

func interactionUserOption(data discordgo.ApplicationCommandInteractionData, name string) string {
	for _, opt := range data.Options {
		if opt.Name == name {
			return optionUserID(opt)
		}
	}
	return ""
}

func splitDiscordChunk(text string, max int) (string, string) {
	if len(text) <= max {
		return text, ""
	}
	n := max
	if idx := strings.LastIndexByte(text[:max], '\n'); idx > 200 {
		n = idx
	}
	return text[:n], text[n:]
}

func editInteractionChunked(s *discordgo.Session, i *discordgo.InteractionCreate, text string) {
	text = strings.TrimSpace(text)
	if text == "" {
		text = "(完成,但沒有文字輸出)"
	}
	first, rest := splitDiscordChunk(text, 1900)
	if _, err := s.InteractionResponseEdit(i.Interaction, &discordgo.WebhookEdit{Content: &first}); err != nil {
		log.Printf("interaction edit error: %v", err)
		sendChunked(s, i.ChannelID, text)
		return
	}
	sendChunked(s, i.ChannelID, rest)
}

func discordMessageURL(guildID, channelID, messageID string) string {
	if guildID == "" {
		guildID = "@me"
	}
	return fmt.Sprintf("https://discord.com/channels/%s/%s/%s", guildID, channelID, messageID)
}

func handleReadCommand(s *discordgo.Session, i *discordgo.InteractionCreate) {
	data := i.ApplicationCommandData()
	request := interactionTextOption(data, "q")
	if request == "" {
		// 相容舊版 /read request:... 指令資料。
		request = interactionTextOption(data, "request")
	}
	targetID := interactionUserOption(data, "target")
	if targetID == "" {
		targetID = readTargetBotID
	}
	if targetID == "" {
		editInteractionChunked(s, i, "⚠️ 尚未設定 READ_TARGET_BOT_ID 或 PEER_BOT_ID,無法判斷要讀哪一顆 bot。")
		return
	}

	text, block, err := fetchLatestTextBlock(s, i.ChannelID, targetID)
	if err != nil {
		editInteractionChunked(s, i, "⚠️ "+err.Error())
		return
	}
	sourceURL := ""
	if len(block) > 0 {
		sourceURL = discordMessageURL(i.GuildID, i.ChannelID, block[len(block)-1].ID)
	}
	prompt := fmt.Sprintf(`請閱讀以下 Discord 頻道中指定 bot 最近一段文字,再依照使用者需求回覆。

[來源]
channel_id: %s
target_bot_id: %s
message_url: %s

[指定 bot 最近訊息]
%s

[使用者需求]
%s`, i.ChannelID, targetID, sourceURL, text, request)

	s.ChannelTyping(i.ChannelID)
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutMin)*time.Minute)
	defer cancel()
	done := make(chan struct{})
	go func() {
		t := time.NewTicker(8 * time.Second)
		defer t.Stop()
		for {
			select {
			case <-done:
				return
			case <-t.C:
				s.ChannelTyping(i.ChannelID)
			}
		}
	}()
	reply := runCodex(ctx, i.ChannelID, prompt)
	close(done)
	editInteractionChunked(s, i, reply)
}

// ─────────────────────────────────────────────────────────────────────────────
// !用量：顯示 Claude 版本與用量上限（工作階段 / 全模型週上限 / Fable 週上限）。
//
// 版本用 `claude --version`。用量優先打 OAuth /api/oauth/usage（需 user:profile
// 權限的 token，能一次拿到逐模型上限含 Fable）；拿不到（例如 setup-token 只有
// user:inference 權限、會回 403）時，退回用一次 1-token 推論、讀回應標頭
// anthropic-ratelimit-unified-*（只有 5h 與 7d 全模型，沒有逐模型 Fable）。
var (
	cstZone   = time.FixedZone("CST", 8*3600)
	usageHTTP = &http.Client{Timeout: 15 * time.Second}
)

func codexVersion() string {
	out, err := exec.Command(codexBin, "--version").Output()
	if err != nil {
		return "未知"
	}
	return strings.TrimSpace(string(out))
}

// codexConfigValue 讀 ~/.codex/config.toml 頂層某個 key 的值（best-effort，只掃到第一個 [section] 為止，
// 避免撈到 [projects."..."] 表底下的同名鍵）。精確比對 key，故 "model" 不會誤中 "model_reasoning_effort"。
func codexConfigValue(key string) string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	data, err := os.ReadFile(filepath.Join(home, ".codex", "config.toml"))
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "[") { // 進到 [section]，頂層區結束
			break
		}
		eq := strings.IndexByte(line, '=')
		if eq < 0 {
			continue
		}
		if strings.TrimSpace(line[:eq]) == key {
			return strings.Trim(strings.TrimSpace(line[eq+1:]), "\"'")
		}
	}
	return ""
}

// currentModel 回傳目前使用的 codex 模型（CODEX_MODEL 覆蓋，否則為 codex 設定檔預設）。
func currentModel() string {
	if codexModel != "" {
		return codexModel
	}
	return codexConfigValue("model")
}

// currentReasoningEffort 回傳 config.toml 的 model_reasoning_effort（沒設回空 → codex 用模型預設）。
func currentReasoningEffort() string {
	return codexConfigValue("model_reasoning_effort")
}

// currentModelLegacy 保留 claude 版舊實作的殼(未使用),避免大改動;實際走上面的 codex 版。
func currentModelLegacy() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	data, err := os.ReadFile(filepath.Join(home, ".claude", "settings.json"))
	if err != nil {
		return ""
	}
	var s struct {
		Model string `json:"model"`
	}
	if json.Unmarshal(data, &s) != nil {
		return ""
	}
	return s.Model
}

// limitLine 是一條用量上限：使用百分比 + 重置時間。
type limitLine struct {
	pct   float64 // 使用百分比 0-100；<0 代表無資料
	reset int64   // 重置 unix 秒；0 代表無資料
}

func (l limitLine) String() string {
	if l.pct < 0 {
		return "—（無資料）"
	}
	out := fmt.Sprintf("%.0f%%", l.pct)
	if l.reset > 0 {
		out += fmt.Sprintf("（重置 %s）", time.Unix(l.reset, 0).In(cstZone).Format("01/02 15:04"))
	}
	return out
}

type usageSnapshot struct {
	session limitLine // 本次工作階段（5h）
	weekAll limitLine // 每週・所有模型（7d）
	fable   limitLine // 每週・Fable 逐模型
	note    string    // 補充說明（例如提示換 token）
}

func newUsageSnapshot() usageSnapshot {
	return usageSnapshot{
		session: limitLine{pct: -1},
		weekAll: limitLine{pct: -1},
		fable:   limitLine{pct: -1},
	}
}

// parseReset 容忍 resets_at 是 unix 秒或 RFC3339 字串兩種格式。
func parseReset(raw json.RawMessage) int64 {
	if len(raw) == 0 {
		return 0
	}
	var n int64
	if json.Unmarshal(raw, &n) == nil {
		return n
	}
	var str string
	if json.Unmarshal(raw, &str) == nil {
		if t, err := time.Parse(time.RFC3339, str); err == nil {
			return t.Unix()
		}
	}
	return 0
}

func readLimit(m map[string]json.RawMessage, key string) limitLine {
	out := limitLine{pct: -1}
	raw, ok := m[key]
	if !ok {
		return out
	}
	var obj struct {
		Utilization    *float64        `json:"utilization"`
		UsedPercentage *float64        `json:"used_percentage"`
		ResetsAt       json.RawMessage `json:"resets_at"`
		Reset          json.RawMessage `json:"reset"`
	}
	if json.Unmarshal(raw, &obj) != nil {
		return out
	}
	switch {
	case obj.UsedPercentage != nil:
		out.pct = *obj.UsedPercentage
	case obj.Utilization != nil:
		// /api/oauth/usage 的 utilization 本身就是百分比(例如 8.0 = 8%),不要再 ×100。
		// (標頭法的 utilization 才是 0-1 小數,那條在 headerLimit 另外處理。)
		out.pct = *obj.Utilization
	}
	if r := parseReset(obj.ResetsAt); r != 0 {
		out.reset = r
	} else {
		out.reset = parseReset(obj.Reset)
	}
	return out
}

// fetchUsageFromOAuth 打 /api/oauth/usage（需 user:profile 權限）。成功回傳 true。
func fetchUsageFromOAuth(tok string) (usageSnapshot, bool) {
	u := newUsageSnapshot()
	req, err := http.NewRequest("GET", "https://api.anthropic.com/api/oauth/usage", nil)
	if err != nil {
		return u, false
	}
	req.Header.Set("Authorization", "Bearer "+tok)
	req.Header.Set("anthropic-beta", "oauth-2025-04-20")
	resp, err := usageHTTP.Do(req)
	if err != nil {
		return u, false
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode != 200 {
		log.Printf("oauth/usage http %d: %s", resp.StatusCode, firstLine(string(body)))
		return u, false
	}
	var raw map[string]json.RawMessage
	if json.Unmarshal(body, &raw) != nil {
		return u, false
	}
	// 上限可能包在 rate_limits 底下，也可能直接在頂層。
	buckets := raw
	if rl, ok := raw["rate_limits"]; ok {
		var inner map[string]json.RawMessage
		if json.Unmarshal(rl, &inner) == nil {
			buckets = inner
		}
	}
	u.session = readLimit(buckets, "five_hour")
	u.weekAll = readLimit(buckets, "seven_day")
	// Fable 逐模型上限：新版可能叫 seven_day_fable，沿用舊命名則是 seven_day_opus。
	if u.fable = readLimit(buckets, "seven_day_fable"); u.fable.pct < 0 {
		u.fable = readLimit(buckets, "seven_day_opus")
	}
	return u, u.session.pct >= 0 || u.weekAll.pct >= 0
}

func headerLimit(h http.Header, span string) limitLine {
	out := limitLine{pct: -1}
	if v := h.Get("anthropic-ratelimit-unified-" + span + "-utilization"); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			out.pct = f * 100
		}
	}
	if v := h.Get("anthropic-ratelimit-unified-" + span + "-reset"); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil {
			out.reset = n
		}
	}
	return out
}

// fetchUsageFromHeaders 用一次 1-token 推論讀 anthropic-ratelimit-unified-* 標頭。
// 只拿得到 5h 與 7d（全模型），沒有逐模型 Fable 上限。
func fetchUsageFromHeaders(tok string) usageSnapshot {
	u := newUsageSnapshot()
	payload := `{"model":"claude-haiku-4-5-20251001","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}`
	req, err := http.NewRequest("POST", "https://api.anthropic.com/v1/messages", strings.NewReader(payload))
	if err != nil {
		return u
	}
	req.Header.Set("Authorization", "Bearer "+tok)
	req.Header.Set("anthropic-beta", "oauth-2025-04-20")
	req.Header.Set("anthropic-version", "2023-06-01")
	req.Header.Set("Content-Type", "application/json")
	resp, err := usageHTTP.Do(req)
	if err != nil {
		return u
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, io.LimitReader(resp.Body, 1<<16))
	if resp.StatusCode != 200 {
		return u
	}
	u.session = headerLimit(resp.Header, "5h")
	u.weekAll = headerLimit(resp.Header, "7d")
	return u
}

func handleUsageCommand(s *discordgo.Session, channelID string) {
	// Codex(ChatGPT 登入)沒有像 Anthropic 那樣的公開用量 API,所以這裡先只顯示版本與模型。
	// 之後若要接 codex 的用量查詢,再擴充這裡。
	model := currentModel()
	if model == "" {
		model = "(codex 設定檔預設)"
	}
	effort := currentReasoningEffort()
	if effort == "" {
		effort = "(模型預設)"
	}
	emb := &discordgo.MessageEmbed{
		Title: "📊 SML_Codex 資訊",
		Color: 0x10a37f, // OpenAI 綠
		Fields: []*discordgo.MessageEmbedField{
			{Name: "🤖 版本", Value: codexVersion()},
			{Name: "🧠 模型", Value: model},
			{Name: "🔬 推理強度", Value: effort},
		},
		Footer: &discordgo.MessageEmbedFooter{Text: "Codex 走 ChatGPT 登入,暫無公開用量上限查詢。模型/強度即時讀自 ~/.codex/config.toml。"},
	}
	if _, err := s.ChannelMessageSendEmbed(channelID, emb); err != nil {
		log.Printf("usage embed send error: %v", err)
	}
}

func main() {
	token := os.Getenv("DISCORD_TOKEN")
	if token == "" {
		log.Fatal("DISCORD_TOKEN not set")
	}
	loadSessions() // 還原各頻道對話 session（重啟不丟脈絡）
	dg, err := discordgo.New("Bot " + token)
	if err != nil {
		log.Fatal(err)
	}
	dg.Identify.Intents = discordgo.IntentsGuilds | discordgo.IntentsGuildMessages | discordgo.IntentMessageContent

	dg.AddHandler(func(s *discordgo.Session, r *discordgo.Ready) {
		log.Printf("READY: 已登入為 %s,可見 %d 個伺服器", r.User.String(), len(r.Guilds))
		registerCmdOnce.Do(func() {
			registerApplicationCommands(s, r.Guilds)
		})
		for chID := range allowedChannels {
			s.ChannelMessageSend(chID, "✅ SML Codex 已上線(@我或回覆我即可)。大任務前先打「新對話」可清空脈絡；單則處理上限 "+strconv.Itoa(timeoutMin)+" 分鐘。")
		}
	})
	dg.AddHandler(func(s *discordgo.Session, _ *discordgo.Disconnect) {
		log.Println("DISCONNECT: gateway 連線中斷(會自動重連)")
	})

	// ── 一般訊息處理 ──
	dg.AddHandler(func(s *discordgo.Session, m *discordgo.MessageCreate) {
		// 診斷:每則訊息都先記下來源頻道,再套用過濾
		log.Printf("MSG ch=%s author=%s bot=%v content=%q", m.ChannelID, m.Author.Username, m.Author.Bot, m.Content)
		// ── bot↔bot 互通(僅限白名單頻道 + 對方那顆 AI bot)──
		// 白名單改讀 runtime JSON(免重啟即時生效);讀不到才退回 env 的 discussChannels。
		b2b := botToBotSet()
		// 預設仍擋掉所有 bot;唯一例外:對方 AI bot 在白名單頻道。
		isPeerBot := m.Author.Bot && peerBotID != "" && m.Author.ID == peerBotID && b2b[m.ChannelID]
		if m.Author.Bot && !isPeerBot {
			return
		}
		// 迴圈閘門:人類一發言就把該頻道的 bot↔bot 計數歸零(人類=斷路器)。
		if !m.Author.Bot && b2b[m.ChannelID] {
			botExchMu.Lock()
			botExchange[m.ChannelID] = 0
			botExchMu.Unlock()
		}
		if !allowedMsg(s, m) {
			return
		}
		// 對方 bot 觸發:超過來回上限就閉嘴,直到人類再開口(防 ping-pong 無限迴圈)。
		if isPeerBot {
			botExchMu.Lock()
			n := botExchange[m.ChannelID]
			if n >= maxBotExchanges {
				botExchMu.Unlock()
				log.Printf("bot↔bot 來回已達上限 %d(ch=%s),暫停回應對方 bot 直到人類發言", maxBotExchanges, m.ChannelID)
				return
			}
			botExchange[m.ChannelID] = n + 1
			botExchMu.Unlock()
		}
		// 文字與附件都空白就忽略
		if strings.TrimSpace(m.Content) == "" && len(m.Attachments) == 0 {
			return
		}
		// ! 前綴指令：先看 commands.json 有沒有設定(有就推 Embed)；沒設定就照舊交給 sweetbot、bridge 不介入
		botRoles := botRoleIDs(s, m.GuildID)
		if stripped := stripMention(m.Content, s.State.User.ID, botRoles); strings.HasPrefix(stripped, "!") {
			cmd := stripped
			if i := strings.IndexAny(cmd, " \t\n"); i >= 0 {
				cmd = cmd[:i]
			}
			// !用量 是動態資訊（版本＋即時用量），不走 commands.json 的固定 Embed。
			if cmd == "!用量" {
				s.ChannelTyping(m.ChannelID)
				handleUsageCommand(s, m.ChannelID)
			} else if action, ok := parseB2BCommand(stripped); ok {
				handleB2BCommand(s, m, action)
			} else {
				tryBridgeCommand(s, m, stripped)
			}
			return
		}
		// 「開新對話」指令:清空該頻道 session,不跑 claude
		if len(m.Attachments) == 0 && resetCmds[stripMention(m.Content, s.State.User.ID, botRoles)] {
			mu.Lock()
			delete(sessions, m.ChannelID)
			mu.Unlock()
			s.ChannelMessageSend(m.ChannelID, "🆕 已開新對話、清空脈絡。接下來會是全新的 session(處理大量內容前先這樣做最不會卡)。")
			return
		}
		s.ChannelTyping(m.ChannelID)

		// 下載附件：圖片存暫存檔、文字類直接讀內容
		var tmpFiles []string
		var imageLines []string
		var textBlocks []string
		for _, att := range m.Attachments {
			ct := att.ContentType
			ext := strings.ToLower(filepath.Ext(att.Filename))
			if strings.HasPrefix(ct, "image/") {
				path, err := downloadAttachment(att.URL, att.Filename)
				if err != nil {
					log.Printf("attachment download error %s: %v", att.Filename, err)
					continue
				}
				tmpFiles = append(tmpFiles, path)
				imageLines = append(imageLines, path)
				log.Printf("downloaded image %s -> %s", att.Filename, path)
			} else if strings.HasPrefix(ct, "text/") || strings.Contains(ct, "json") || strings.Contains(ct, "xml") || textExts[ext] {
				content, err := downloadTextContent(att.URL)
				if err != nil {
					log.Printf("text attachment download error %s: %v", att.Filename, err)
					continue
				}
				textBlocks = append(textBlocks, fmt.Sprintf("=== 附件: %s ===\n%s", att.Filename, content))
				log.Printf("downloaded text attachment %s (%d bytes)", att.Filename, len(content))
			}
		}

		prompt := m.Content
		if len(imageLines) > 0 {
			prompt += "\n\n[使用者附上了以下圖片，請用 Read 工具查看後再回答：\n" +
				strings.Join(imageLines, "\n") + "]"
		}
		if len(textBlocks) > 0 {
			prompt += "\n\n[使用者附上了以下文字附件，內容如下：\n\n" +
				strings.Join(textBlocks, "\n\n") + "]"
		}

		ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutMin)*time.Minute)
		defer cancel()
		// claude 工作期間持續顯示「輸入中…」
		done := make(chan struct{})
		go func() {
			t := time.NewTicker(8 * time.Second)
			defer t.Stop()
			for {
				select {
				case <-done:
					return
				case <-t.C:
					s.ChannelTyping(m.ChannelID)
				}
			}
		}()
		reply := runCodex(ctx, m.ChannelID, prompt)
		close(done)
		// 清除暫存圖片
		for _, p := range tmpFiles {
			os.Remove(p)
		}
		sendWithButtons(s, m.ChannelID, reply)
	})

	// ── 按鈕互動處理 ──
	dg.AddHandler(func(s *discordgo.Session, i *discordgo.InteractionCreate) {
		// 權限檢查
		if !allowedInteraction(i) {
			return
		}

		if i.Type == discordgo.InteractionApplicationCommand {
			data := i.ApplicationCommandData()
			if data.Name != "read" {
				return
			}
			if err := s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
				Type: discordgo.InteractionResponseDeferredChannelMessageWithSource,
			}); err != nil {
				log.Printf("slash command ack error: %v", err)
				return
			}
			handleReadCommand(s, i)
			return
		}

		if i.Type != discordgo.InteractionMessageComponent {
			return
		}

		data := i.MessageComponentData()
		customID := data.CustomID

		// bot↔bot 白名單下拉選單(b2b:enable / b2b:disable):即時改 JSON、重繪訊息,不進 codex。
		if strings.HasPrefix(customID, "b2b:") {
			handleWhitelistSelect(s, i, customID)
			return
		}
		// 「轉傳給對方」按鈕:把這則內容重貼成 @對方bot,不進 codex。
		if customID == "fwd:peer" {
			handleForward(s, i)
			return
		}

		// 從原始訊息找 button label
		btnLabel := customID
		if i.Message != nil {
			for _, row := range i.Message.Components {
				if ar, ok := row.(discordgo.ActionsRow); ok {
					for _, comp := range ar.Components {
						if btn, ok := comp.(discordgo.Button); ok && btn.CustomID == customID {
							btnLabel = btn.Label
						}
					}
				}
			}
		}

		// ACK 並把「選項鈕」反灰(避免重送);轉傳/白名單鈕保留可點。
		s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
			Type: discordgo.InteractionResponseUpdateMessage,
			Data: &discordgo.InteractionResponseData{
				Content:    i.Message.Content,
				Embeds:     i.Message.Embeds,
				Components: disableChoiceButtons(i.Message, customID),
			},
		})

		userName := i.Member.User.Username
		prompt := fmt.Sprintf("[按鈕點擊] %s 點了「%s」(%s)", userName, btnLabel, customID)
		log.Printf("BUTTON ch=%s user=%s id=%s label=%s", i.ChannelID, userName, customID, btnLabel)

		s.ChannelTyping(i.ChannelID)
		ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutMin)*time.Minute)
		defer cancel()
		done := make(chan struct{})
		go func() {
			t := time.NewTicker(8 * time.Second)
			defer t.Stop()
			for {
				select {
				case <-done:
					return
				case <-t.C:
					s.ChannelTyping(i.ChannelID)
				}
			}
		}()
		reply := runCodex(ctx, i.ChannelID, prompt)
		close(done)
		sendWithButtons(s, i.ChannelID, reply)
	})

	if err := dg.Open(); err != nil {
		log.Fatal("discord open: ", err)
	}
	defer dg.Close()
	fmt.Println("SML Codex bridge running. guilds:", os.Getenv("ALLOWED_GUILDS"), "| channels:", os.Getenv("ALLOWED_CHANNELS"))
	select {}
}
