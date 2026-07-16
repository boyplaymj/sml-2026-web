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
	"syscall"
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
	claudeBin       = env("CLAUDE_BIN", "claude")
	workdir         = env("CLAUDE_WORKDIR", ".")
	channelWorkdirs = parseChannelWorkdirs(os.Getenv("CHANNEL_WORKDIRS"))
	timeoutMin      = envInt("CLAUDE_TIMEOUT_MIN", 25) // 單一訊息處理逾時(分鐘)

	mu       sync.Mutex
	sessions = map[string]string{} // channelID -> claude session id

	// 同頻道序列化：每個 channel 一把鎖，確保「一次只跑一個 claude」。
	// 否則使用者連發訊息時，discordgo 會各開 goroutine 同時起兩個 claude --resume（共用同一 session
	// 與工作目錄）→ 兩個實例互相覆蓋檔案、各跑重複建置、搶寫 registry。
	chanLocks sync.Map // channelID -> *sync.Mutex

	// 全域併發上限：跨「不同頻道」最多同時 N 個 claude。小機器(如 t4g.small 2GB)上,每個 claude 吃
	// 250-600MB,同時開 3+ 個會把記憶體榨爆 → 進程被 SIGKILL(stderr 空)→ 顯示「unknown error」。
	// 加這道閘,第 N+1 個任務會排隊等,而不是硬起來擠爆。預設 2,可用 CLAUDE_MAX_CONCURRENT 調。
	claudeSem = make(chan struct{}, envInt("CLAUDE_MAX_CONCURRENT", 2))
)

// chanLock 取得某頻道專屬的鎖（不存在就建立）。
func chanLock(channelID string) *sync.Mutex {
	v, _ := chanLocks.LoadOrStore(channelID, &sync.Mutex{})
	return v.(*sync.Mutex)
}

// 對談 session 持久化：存磁碟 → bridge 重啟不會丟失各頻道對話脈絡(否則重啟＝所有對話重置)。
func sessionsFile() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".claude", "bridge-sessions.json")
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

type claudeResult struct {
	Result    string `json:"result"`
	SessionID string `json:"session_id"`
	IsError   bool   `json:"is_error"`
}

// wasKilled 判斷 claude 是否被信號強殺(SIGKILL,例如記憶體壓力下被中止)。
// 這類失敗 stderr 通常是空的,值得等一下自動重試。
func wasKilled(err error) bool {
	if err == nil {
		return false
	}
	if ee, ok := err.(*exec.ExitError); ok {
		if ws, ok := ee.Sys().(syscall.WaitStatus); ok && ws.Signaled() {
			return true
		}
	}
	s := err.Error()
	return strings.Contains(s, "killed") || strings.Contains(s, "signal:")
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

// claudeArgs 組出 claude CLI 參數。
// 鐵律:所有 options(含 --resume)都必須在 `--` 之前;prompt 放最後、緊接在 `--` 之後。
// 若 --resume 落到 `--` 之後,會被當成 prompt 文字吞掉 → session 永遠不 resume(每則訊息失憶)。
// prompt 放 `--` 之後則保證以 "-" 開頭的內容不會被誤判成未知 option。
// buttonHint 注入 system prompt,讓「每個」session 都知道離散選項要用 [[BTN]] 按鈕
// (修「其他 session 幾乎不吐按鈕」——原本純靠軟記憶,觸發率近 0)。
// env BRIDGE_BUTTON_HINT 可覆蓋;設為空字串即停用。
var buttonHint = env("BRIDGE_BUTTON_HINT", "當你要使用者在少數(約2-5個)離散選項之間做選擇時,在回覆末尾用標記 [[BTN:顯示文字:custom_id]] 提供按鈕(內文要先逐項說明每個選項是什麼,不能只給標籤)。使用者可以點按鈕、也可以直接打字,兩條路都要能用,絕不卡著等按鈕。custom_id 不要用 b2b: 或 fwd: 開頭。開放式輸入(要對方打一段內容)不要用按鈕。")

func claudeArgs(sid, prompt string) []string {
	args := []string{"--output-format", "json", "--permission-mode", "bypassPermissions"}
	if h := strings.TrimSpace(buttonHint); h != "" {
		args = append(args, "--append-system-prompt", h)
	}
	if sid != "" {
		args = append(args, "--resume", sid)
	}
	return append(args, "-p", "--", prompt)
}

// runClaude 在工作目錄跑 headless claude,維持每個頻道的 session。
func runClaude(ctx context.Context, channelID, prompt string) string {
	// 同頻道序列化：一次只跑一個 claude。第二則訊息會在這裡等前一則跑完再進場，
	// 杜絕「兩個 claude --resume 同一 session、同一工作目錄」互相覆蓋檔案／搶寫 registry。
	lk := chanLock(channelID)
	lk.Lock()
	defer lk.Unlock()

	// 全域併發閘：跨頻道最多同時 claudeSem 容量個 claude。放在頻道鎖「之後」取,
	// 這樣同頻道排隊的第二則不會白佔一個併發槽。ctx 取消(逾時)時不卡死。
	select {
	case claudeSem <- struct{}{}:
		defer func() { <-claudeSem }()
	case <-ctx.Done():
		return "⚠️ 等待排隊逾時,請稍後再試。"
	}

	mu.Lock()
	sid := sessions[channelID]
	mu.Unlock()

	args := claudeArgs(sid, prompt)

	// 執行 claude,最多試 2 次:若進程被系統強殺(signal: killed,通常是記憶體壓力,stderr 空),
	// 等幾秒讓記憶體釋放後自動重試一次,避免使用者只看到無意義的「unknown error」。
	var out bytes.Buffer
	var runErr error
	var stderr string
	for attempt := 1; attempt <= 2; attempt++ {
		out.Reset()
		var errb bytes.Buffer
		cmd := exec.CommandContext(ctx, claudeBin, args...)
		cmd.Dir = workdirFor(channelID)
		// 把來源頻道 ID 注入 Claude 對話環境 → 讓 hook(如 crossroad 擁有權護欄)可依頻道決定放行/阻擋。
		cmd.Env = append(os.Environ(), "SML_DISCORD_CHANNEL="+channelID)
		cmd.Stdout, cmd.Stderr = &out, &errb
		runErr = cmd.Run()
		stderr = errb.String()
		if runErr == nil {
			break
		}
		log.Printf("claude error (attempt %d/2): %v | stderr: %s", attempt, runErr, stderr)
		// ctx 已逾時/取消就別重試;否則若像是被強殺,等 4 秒讓記憶體回收再試一次。
		if ctx.Err() != nil || attempt == 2 {
			break
		}
		if wasKilled(runErr) {
			time.Sleep(4 * time.Second)
		} else {
			break // 非「被殺」類錯誤(有實際 stderr)不重試,直接回報
		}
	}
	if runErr != nil {
		if ctx.Err() != nil {
			return "⚠️ 處理逾時(超過 " + strconv.Itoa(timeoutMin) + " 分鐘)被中止,請把任務拆小一點再試。"
		}
		// 用量/認證/額度等「做不了事」的已知原因 → 顯示清楚的中文原因,而非原始 stderr。
		// 這類訊息可能在 stderr,也可能在 stdout 的 JSON result 裡,兩邊都比對。
		if msg := blockMessage(classifyBlock(stderr+"\n"+out.String()), stderr+"\n"+out.String()); msg != "" {
			return msg
		}
		if wasKilled(runErr) && strings.TrimSpace(stderr) == "" {
			return "⚠️ 處理被系統中止(通常是同時任務太多、記憶體不足),已自動重試仍失敗。請稍等一下、或避免同時在多個頻道操作,再重試。"
		}
		return "⚠️ 執行出錯：" + firstLine(stderr)
	}
	var res claudeResult
	if err := json.Unmarshal(out.Bytes(), &res); err != nil {
		return strings.TrimSpace(out.String())
	}
	// 成功退出但 result 其實是「用量/認證/額度」阻擋訊息(claude 有時 is_error=true、
	// 有時仍 exit 0 只把原因塞進 result)→ 翻成清楚原因。
	if res.IsError {
		if msg := blockMessage(classifyBlock(res.Result), res.Result); msg != "" {
			return msg
		}
	}
	if res.SessionID != "" {
		mu.Lock()
		sessions[channelID] = res.SessionID
		saveSessionsLocked()
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

// claudeUsageToken 取查用量用的 OAuth token。
// 優先用環境變數(若有),否則讀 bridge 實際跑 claude 的認證檔 ~/.claude/.credentials.json。
// 注意:這個 token 只用於「查用量的 HTTP 呼叫」,不會被放進 claude -p 的環境,故不影響計費。
func claudeUsageToken() string {
	if t := os.Getenv("CLAUDE_CODE_OAUTH_TOKEN"); t != "" {
		return t
	}
	credPath := claudeHomePath(".claude", ".credentials.json")
	data, err := os.ReadFile(credPath)
	if err != nil {
		return ""
	}
	// access token 是短命的:帳號閒置到過期(尤其 backup 帳號平常不跑 session)時,
	// !用量/!帳號 會拿到已過期的 token → API 回 401 → 版面空白。讀出來用之前先確保新鮮,
	// 過期就用 refreshToken 換新、寫回磁碟(claude session 之外也能自我刷新)。
	credJSON := refreshLocalCredentialsIfStale(credPath, string(data))
	var c struct {
		ClaudeAiOauth struct {
			AccessToken string `json:"accessToken"`
		} `json:"claudeAiOauth"`
	}
	if json.Unmarshal([]byte(credJSON), &c) != nil {
		return ""
	}
	return c.ClaudeAiOauth.AccessToken
}

// refreshLocalCredentialsIfStale 若本機 access token 已過期(或即將到期),用 refreshToken 換新、
// 寫回 .credentials.json,並 best-effort 回寫 active slot 的 SSM(自癒:下次切回來不會又拿到過期值)。
// 任一步失敗都回傳原本的 credJSON——行為不會比現況差(頂多還是拿到舊 token)。
func refreshLocalCredentialsIfStale(credPath, credJSON string) string {
	now := time.Now()
	if exp, ok := credentialExpiry(credJSON); ok && exp.After(now.Add(expirySkewSeconds*time.Second)) {
		return credJSON // access token 仍有效,免刷新
	}
	access, newRT, expiresIn, _, err := oauthRefresh(credentialRefreshToken(credJSON), oauthHTTPClient())
	if err != nil {
		log.Printf("[usage] 本機 token 過期且刷新失敗(維持舊 token): %v", err)
		return credJSON
	}
	merged, err := mergeRefreshedCredentials(credJSON, access, newRT, expiresIn, now)
	if err != nil {
		log.Printf("[usage] 合併刷新憑證失敗(維持舊 token): %v", err)
		return credJSON
	}
	if err := writePrivateJSON(credPath, merged); err != nil {
		log.Printf("[usage] 寫回刷新後憑證失敗(維持舊 token): %v", err)
		return credJSON
	}
	if slot := readActiveAccount(); slot != "" {
		if err := persistCredsToSSM(slot, merged); err != nil {
			log.Printf("[usage] 刷新後回寫 SSM slot %q 失敗(不影響本次查詢): %v", slot, err)
		}
	}
	log.Printf("[usage] 本機 access token 已過期→已用 refreshToken 刷新並寫回")
	return merged
}

// claudeAccount 是 ~/.claude.json 的 oauthAccount(帳號/方案/計費資訊,供成本管控用)。
type claudeAccount struct {
	Email         string `json:"emailAddress"`
	DisplayName   string `json:"displayName"`
	OrgType       string `json:"organizationType"`
	RateLimitTier string `json:"organizationRateLimitTier"`
	ExtraUsage    bool   `json:"hasExtraUsageEnabled"`
	BillingType   string `json:"billingType"`
}

func readClaudeAccount() (claudeAccount, bool) {
	home, err := os.UserHomeDir()
	if err != nil {
		return claudeAccount{}, false
	}
	data, err := os.ReadFile(filepath.Join(home, ".claude.json"))
	if err != nil {
		return claudeAccount{}, false
	}
	var d struct {
		OauthAccount claudeAccount `json:"oauthAccount"`
	}
	if json.Unmarshal(data, &d) != nil || d.OauthAccount.Email == "" {
		return claudeAccount{}, false
	}
	return d.OauthAccount, true
}

// fetchAccountFromOAuth 用切換後的 token 打 /api/oauth/profile 拿「目前實際生效」的帳號。
// 這跟查用量用的是同一顆 token,所以切帳號後即時正確,不會像 ~/.claude.json 那樣停在舊帳號。
func fetchAccountFromOAuth(tok string) (claudeAccount, bool) {
	if tok == "" {
		return claudeAccount{}, false
	}
	req, err := http.NewRequest("GET", "https://api.anthropic.com/api/oauth/profile", nil)
	if err != nil {
		return claudeAccount{}, false
	}
	req.Header.Set("Authorization", "Bearer "+tok)
	req.Header.Set("anthropic-beta", "oauth-2025-04-20")
	resp, err := usageHTTP.Do(req)
	if err != nil {
		return claudeAccount{}, false
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode != 200 {
		log.Printf("oauth/profile http %d: %s", resp.StatusCode, firstLine(string(body)))
		return claudeAccount{}, false
	}
	var p struct {
		Account struct {
			Email       string `json:"email"`
			DisplayName string `json:"display_name"`
			FullName    string `json:"full_name"`
		} `json:"account"`
		Organization struct {
			OrgType       string `json:"organization_type"`
			RateLimitTier string `json:"rate_limit_tier"`
			BillingType   string `json:"billing_type"`
			ExtraUsage    bool   `json:"has_extra_usage_enabled"`
		} `json:"organization"`
	}
	if json.Unmarshal(body, &p) != nil || p.Account.Email == "" {
		return claudeAccount{}, false
	}
	dn := p.Account.DisplayName
	if dn == "" {
		dn = p.Account.FullName
	}
	return claudeAccount{
		Email:         p.Account.Email,
		DisplayName:   dn,
		OrgType:       p.Organization.OrgType,
		RateLimitTier: p.Organization.RateLimitTier,
		ExtraUsage:    p.Organization.ExtraUsage,
		BillingType:   p.Organization.BillingType,
	}, true
}

// currentAccount 取「目前實際生效」的帳號:優先用 token 打 profile(切帳號後即時正確),
// 打不到才退回讀 ~/.claude.json——但那個檔切帳號時不會被換,故回傳的 stale=true 代表可能是舊帳號。
func currentAccount(tok string) (acc claudeAccount, ok, stale bool) {
	if acc, ok := fetchAccountFromOAuth(tok); ok {
		return acc, true, false
	}
	acc, ok = readClaudeAccount()
	return acc, ok, ok
}

// maskEmail 保留 local part 前半 + 網域,其餘遮成 ***(能看懂但不全顯)。
func maskEmail(e string) string {
	at := strings.IndexByte(e, '@')
	if at <= 0 {
		return e
	}
	local, domain := e[:at], e[at:]
	keep := (len(local) + 1) / 2
	if keep >= len(local) {
		return e
	}
	return local[:keep] + "***" + domain
}

// prettyPlan 把 organizationType / rateLimitTier 轉成好讀的方案名(如 "Claude Max 20x")。
func prettyPlan(a claudeAccount) string {
	plan := a.OrgType
	switch {
	case strings.Contains(a.OrgType, "max") || strings.Contains(a.RateLimitTier, "max"):
		plan = "Claude Max"
	case strings.Contains(a.OrgType, "team"):
		plan = "Claude Team"
	case strings.Contains(a.OrgType, "pro"):
		plan = "Claude Pro"
	}
	if i := strings.LastIndex(a.RateLimitTier, "_"); i >= 0 {
		if suf := a.RateLimitTier[i+1:]; strings.HasSuffix(suf, "x") {
			plan += " " + suf // 例如 20x
		}
	}
	return plan
}

func handleUsageCommand(s *discordgo.Session, channelID string) {
	tok := claudeUsageToken()
	u := newUsageSnapshot()
	if tok == "" {
		u.note = "找不到可用的 OAuth token（環境變數與 ~/.claude/.credentials.json 皆無），無法查詢用量。"
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

	var fields []*discordgo.MessageEmbedField
	// 帳號/方案/計費(成本管控用):優先用 token 打 profile(與用量同源、切帳號後即時正確)。
	if acc, ok, stale := currentAccount(tok); ok {
		who := maskEmail(acc.Email)
		if acc.DisplayName != "" {
			who += "（" + acc.DisplayName + "）"
		}
		overage := "關閉（撞上限只會擋、不會多收費）"
		if acc.ExtraUsage {
			overage = "⚠️ 開啟（超額會另計費，注意預算）"
		}
		fields = append(fields,
			&discordgo.MessageEmbedField{Name: "👤 帳號", Value: who},
			&discordgo.MessageEmbedField{Name: "💳 方案", Value: prettyPlan(acc)},
			&discordgo.MessageEmbedField{Name: "🛡️ 超額計費", Value: overage},
		)
		if stale {
			u.note = strings.TrimSpace(u.note + " 帳號資訊讀自 ~/.claude.json,切帳號後可能非最新(profile API 無法取得)。")
		}
	}
	fields = append(fields,
		&discordgo.MessageEmbedField{Name: "🤖 版本", Value: ver},
		&discordgo.MessageEmbedField{Name: "⏳ 本次工作階段", Value: u.session.String()},
		&discordgo.MessageEmbedField{Name: "📅 每週上限（所有模型）", Value: u.weekAll.String()},
		&discordgo.MessageEmbedField{Name: "✨ 每週上限（Fable）", Value: u.fable.String()},
	)
	emb := &discordgo.MessageEmbed{
		Title:  "📊 SML_Claude 用量",
		Color:  0xf9a8d4,
		Fields: fields,
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
	loadSessions() // 還原各頻道對話 session（重啟不丟脈絡）
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
			} else if action, slot, ok := parseAccountCommand(stripped); ok {
				handleAccountCommand(s, m, action, slot)
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

		// bot↔bot 白名單下拉選單(b2b:enable / b2b:disable):即時改 JSON、重繪訊息,不進 claude。
		if strings.HasPrefix(customID, "b2b:") {
			handleWhitelistSelect(s, i, customID)
			return
		}
		// 「轉傳給對方」按鈕:把這則內容重貼成 @對方bot,不進 claude。
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
