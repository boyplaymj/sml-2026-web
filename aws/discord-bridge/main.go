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
	"log"
	"os"
	"os/exec"
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
	allowedUsers    = csvSet(os.Getenv("ALLOWED_USERS"))
	claudeBin       = env("CLAUDE_BIN", "claude")
	workdir         = env("CLAUDE_WORKDIR", ".")

	mu       sync.Mutex
	sessions = map[string]string{} // channelID -> claude session id
)

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
	cmd.Dir = workdir
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

func allowedMsg(m *discordgo.MessageCreate) bool {
	if len(allowedChannels) > 0 && !allowedChannels[m.ChannelID] {
		return false
	}
	if len(allowedUsers) > 0 && !allowedUsers[m.Author.ID] {
		return false
	}
	return true
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
	dg.Identify.Intents = discordgo.IntentsGuildMessages | discordgo.IntentMessageContent

	dg.AddHandler(func(s *discordgo.Session, m *discordgo.MessageCreate) {
		if m.Author.Bot || strings.TrimSpace(m.Content) == "" || !allowedMsg(m) {
			return
		}
		log.Printf("[ch %s] %s: %s", m.ChannelID, m.Author.Username, m.Content)
		s.ChannelTyping(m.ChannelID)

		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
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
		reply := runClaude(ctx, m.ChannelID, m.Content)
		close(done)
		sendChunked(s, m.ChannelID, reply)
	})

	if err := dg.Open(); err != nil {
		log.Fatal("discord open: ", err)
	}
	defer dg.Close()
	fmt.Println("SML Discord bridge running. allowed channels:", os.Getenv("ALLOWED_CHANNELS"))
	select {}
}
