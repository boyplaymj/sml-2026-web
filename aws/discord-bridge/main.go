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

// stripMention 去掉 bot 的 @mention,回傳純文字內容。
func stripMention(content, botID string) string {
	content = strings.ReplaceAll(content, "<@"+botID+">", "")
	content = strings.ReplaceAll(content, "<@!"+botID+">", "")
	return strings.TrimSpace(content)
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
	// 否則退回 ALLOWED_CHANNELS 逐頻道白名單。
	if len(allowedGuilds) > 0 {
		if !allowedGuilds[m.GuildID] {
			return false
		}
	} else if len(allowedChannels) > 0 && !allowedChannels[m.ChannelID] {
		return false
	}
	if len(allowedUsers) > 0 && !allowedUsers[m.Author.ID] {
		return false
	}
	// 只回應 mention bot 或回覆 bot 訊息的情況
	botID := s.State.User.ID
	if strings.Contains(m.Content, "<@"+botID+">") {
		return true
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
		// 「開新對話」指令:清空該頻道 session,不跑 claude
		if len(m.Attachments) == 0 && resetCmds[stripMention(m.Content, s.State.User.ID)] {
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
		sendChunked(s, m.ChannelID, reply)
	})

	if err := dg.Open(); err != nil {
		log.Fatal("discord open: ", err)
	}
	defer dg.Close()
	fmt.Println("SML Discord bridge running. guilds:", os.Getenv("ALLOWED_GUILDS"), "| channels:", os.Getenv("ALLOWED_CHANNELS"))
	select {}
}
