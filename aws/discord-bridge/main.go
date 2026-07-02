// SML Discord <-> Claude Code bridge
//
// 收 Discord 訊息 -> 在 EC2 上跑 `claude -p`(headless,沿用同一個專案目錄與工具)
// -> 把回覆貼回頻道。每個頻道用 --resume 維持對話脈絡。
//
// 安全:只回應 ALLOWED_CHANNELS(必要)與 ALLOWED_USERS(選填)白名單內的訊息。
// 機密(Discord token / Claude OAuth token)由 run.sh 從 AWS SSM 讀進環境變數,不寫進 repo。
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
	claudeBin       = env("CLAUDE_BIN", "claude")
	workdir         = env("CLAUDE_WORKDIR", ".")
	channelWorkdirs = parseChannelWorkdirs(os.Getenv("CHANNEL_WORKDIRS"))
	timeoutMin      = envInt("CLAUDE_TIMEOUT_MIN", 25) // 單一訊息處理逾時(分鐘)

	mu       sync.Mutex
	sessions = map[string]string{} // channelID -> claude session id
)

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

type claudeResult struct {
	Result    string `json:"result"`
	SessionID string `json:"session_id"`
	IsError   bool   `json:"is_error"`
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

// runClaude 在工作目錄跑 headless claude,維持每個頻道的 session。
func runClaude(ctx context.Context, channelID, prompt string) string {
	mu.Lock()
	sid := sessions[channelID]
	mu.Unlock()

	args := []string{"-p", prompt, "--output-format", "json", "--permission-mode", "bypassPermissions"}
	if sid != "" {
		args = append(args, "--resume", sid)
	}
	cmd := exec.CommandContext(ctx, claudeBin, args...)
	cmd.Dir = workdirFor(channelID)
	cmd.Env = os.Environ()
	var out, errb bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &errb
	if err := cmd.Run(); err != nil {
		log.Printf("claude error: %v | stderr: %s", err, errb.String())
		return "⚠️ 執行出錯：" + firstLine(errb.String())
	}
	var res claudeResult
	if err := json.Unmarshal(out.Bytes(), &res); err != nil {
		return strings.TrimSpace(out.String())
	}
	if res.SessionID != "" {
		mu.Lock()
		sessions[channelID] = res.SessionID
		mu.Unlock()
	}
	if strings.TrimSpace(res.Result) == "" {
		return "(完成,但沒有文字輸出)"
	}
	return res.Result
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

// sendWithButtons 偵測按鈕標記後送出帶按鈕的訊息，否則退回純文字分段送出。
func sendWithButtons(s *discordgo.Session, channelID, text string) {
	clean, btns := parseButtons(text)
	if len(btns) == 0 {
		sendChunked(s, channelID, text)
		return
	}
	// Discord 每列最多 5 顆按鈕
	if len(btns) > 5 {
		btns = btns[:5]
	}
	var comps []discordgo.MessageComponent
	for _, b := range btns {
		comps = append(comps, discordgo.Button{
			Label:    b.label,
			Style:    discordgo.PrimaryButton,
			CustomID: b.id,
		})
	}
	msg := &discordgo.MessageSend{
		Content: clean,
		Components: []discordgo.MessageComponent{
			discordgo.ActionsRow{Components: comps},
		},
	}
	if _, err := s.ChannelMessageSendComplex(channelID, msg); err != nil {
		log.Printf("send with buttons error: %v — falling back to text", err)
		sendChunked(s, channelID, clean)
	}
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

func claudeVersion() string {
	out, err := exec.Command(claudeBin, "--version").Output()
	if err != nil {
		return "未知"
	}
	return strings.TrimSpace(string(out))
}

// currentModel 讀 ~/.claude/settings.json 的預設模型（best-effort）。
func currentModel() string {
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
		out.pct = *obj.Utilization * 100
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
	tok := os.Getenv("CLAUDE_CODE_OAUTH_TOKEN")
	u := newUsageSnapshot()
	if tok == "" {
		u.note = "找不到 CLAUDE_CODE_OAUTH_TOKEN，無法查詢用量。"
	} else if oauthU, ok := fetchUsageFromOAuth(tok); ok {
		u = oauthU
	} else {
		u = fetchUsageFromHeaders(tok)
		u.note = "逐模型（Fable）週上限需要具 user:profile 權限的 OAuth token；" +
			"目前 token 僅能提供工作階段與全模型週上限。"
	}

	ver := claudeVersion()
	if m := currentModel(); m != "" {
		ver += "・模型 " + m
	}

	emb := &discordgo.MessageEmbed{
		Title: "📊 SML_Claude 用量",
		Color: 0xf9a8d4,
		Fields: []*discordgo.MessageEmbedField{
			{Name: "🤖 版本", Value: ver},
			{Name: "⏳ 本次工作階段", Value: u.session.String()},
			{Name: "📅 每週上限（所有模型）", Value: u.weekAll.String()},
			{Name: "✨ 每週上限（Fable）", Value: u.fable.String()},
		},
	}
	if u.note != "" {
		emb.Footer = &discordgo.MessageEmbedFooter{Text: u.note}
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
	dg, err := discordgo.New("Bot " + token)
	if err != nil {
		log.Fatal(err)
	}
	dg.Identify.Intents = discordgo.IntentsGuilds | discordgo.IntentsGuildMessages | discordgo.IntentMessageContent

	dg.AddHandler(func(s *discordgo.Session, r *discordgo.Ready) {
		log.Printf("READY: 已登入為 %s,可見 %d 個伺服器", r.User.String(), len(r.Guilds))
		for chID := range allowedChannels {
			s.ChannelMessageSend(chID, "✅ SML Claude 已上線。大任務前先打「新對話」可清空脈絡、避免變慢；單則處理上限已拉長到 "+strconv.Itoa(timeoutMin)+" 分鐘。")
		}
	})
	dg.AddHandler(func(s *discordgo.Session, _ *discordgo.Disconnect) {
		log.Println("DISCONNECT: gateway 連線中斷(會自動重連)")
	})

	// ── 一般訊息處理 ──
	dg.AddHandler(func(s *discordgo.Session, m *discordgo.MessageCreate) {
		// 診斷:每則訊息都先記下來源頻道,再套用過濾
		log.Printf("MSG ch=%s author=%s bot=%v content=%q", m.ChannelID, m.Author.Username, m.Author.Bot, m.Content)
		if m.Author.Bot || !allowedMsg(s, m) {
			return
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
		reply := runClaude(ctx, m.ChannelID, prompt)
		close(done)
		// 清除暫存圖片
		for _, p := range tmpFiles {
			os.Remove(p)
		}
		sendWithButtons(s, m.ChannelID, reply)
	})

	// ── 按鈕互動處理 ──
	dg.AddHandler(func(s *discordgo.Session, i *discordgo.InteractionCreate) {
		if i.Type != discordgo.InteractionMessageComponent {
			return
		}
		// 權限檢查
		if len(allowedGuilds) > 0 {
			if !allowedGuilds[i.GuildID] {
				return
			}
		} else if len(allowedChannels) > 0 && !allowedChannels[i.ChannelID] {
			return
		}
		if len(allowedUsers) > 0 && !allowedUsers[i.Member.User.ID] {
			return
		}

		data := i.MessageComponentData()
		customID := data.CustomID

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

		// 先 ACK 這個 interaction，避免 Discord 顯示「互動失敗」
		s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
			Type: discordgo.InteractionResponseDeferredMessageUpdate,
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
		reply := runClaude(ctx, i.ChannelID, prompt)
		close(done)
		sendWithButtons(s, i.ChannelID, reply)
	})

	if err := dg.Open(); err != nil {
		log.Fatal("discord open: ", err)
	}
	defer dg.Close()
	fmt.Println("SML Discord bridge running. guilds:", os.Getenv("ALLOWED_GUILDS"), "| channels:", os.Getenv("ALLOWED_CHANNELS"))
	select {}
}
