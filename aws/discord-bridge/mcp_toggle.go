package main

// Notion MCP 按需開關:runtime 可重載(免重啟即時生效)。
//
// 背景:Notion MCP 原本掛在 ~/.claude/settings.json，每個 claude session 都 cold-start 一個
// notion-mcp-server 進程(吃 60–120MB + 握手延遲),三條並行時把小主機拖慢。2026-07-16 已從
// settings.json 移除、預設不載。本模組讓站主用 `!notion on/off` 隨時把它接回來,不必動 settings、
// 不必重啟:claudeArgs() 讀本 flag,若 on 就對 claude 加 `--mcp-config <notionMCPConfigPath>`。
//
// flag 存於共享 mount /mnt/sml-brain/_runtime/mcp-toggles.json,格式:
//   {"version":1,"updated_at":"...","notion":true}
// 讀取用 mtime cache(每則訊息只 stat 一次),讀不到/壞掉 → 視為關(fail-safe:寧可不載也不炸)。

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"
)

type mcpToggles struct {
	Version   int    `json:"version"`
	UpdatedAt string `json:"updated_at"`
	Notion    bool   `json:"notion"`
}

func mcpTogglePath() string {
	if p := os.Getenv("MCP_TOGGLE_PATH"); p != "" {
		return p
	}
	return "/mnt/sml-brain/_runtime/mcp-toggles.json"
}

// notionMCPConfigPath 是 --mcp-config 要載入的設定檔(含 notion server + token)。
func notionMCPConfigPath() string {
	if p := os.Getenv("NOTION_MCP_CONFIG"); p != "" {
		return p
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".claude", "mcp-notion.json")
}

var (
	mcpMu     sync.Mutex
	mcpMtime  time.Time
	mcpCache  mcpToggles
	mcpLoaded bool
)

// notionMCPEnabled 回傳目前是否要載入 Notion MCP(mtime cache)。
// flag 檔不存在/讀不到/壞掉 → 一律視為關(預設安全:不載、不拖慢、不炸)。
func notionMCPEnabled() bool {
	mcpMu.Lock()
	defer mcpMu.Unlock()
	fi, err := os.Stat(mcpTogglePath())
	if err != nil {
		return false
	}
	if mcpLoaded && fi.ModTime().Equal(mcpMtime) {
		return mcpCache.Notion
	}
	cfg, err := readMCPToggles()
	if err != nil {
		return false
	}
	mcpCache = cfg
	mcpMtime = fi.ModTime()
	mcpLoaded = true
	return cfg.Notion
}

func readMCPToggles() (mcpToggles, error) {
	var cfg mcpToggles
	data, err := os.ReadFile(mcpTogglePath())
	if err != nil {
		return cfg, err
	}
	if err := json.Unmarshal(data, &cfg); err != nil {
		return cfg, err
	}
	return cfg, nil
}

// setNotionMCP 原子寫入 flag(temp + rename),並讓下次 notionMCPEnabled 強制重讀。
func setNotionMCP(on bool) error {
	cfg := mcpToggles{Version: 1, UpdatedAt: time.Now().UTC().Format(time.RFC3339), Notion: on}
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	p := mcpTogglePath()
	if dir := filepath.Dir(p); dir != "" {
		os.MkdirAll(dir, 0o755)
	}
	tmp := p + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	if err := os.Rename(tmp, p); err != nil {
		return err
	}
	mcpMu.Lock()
	mcpLoaded = false // 強制下次重讀
	mcpMu.Unlock()
	return nil
}

// parseNotionCommand 解析 !notion 系列指令。回傳 action ∈ {status, on, off}。
func parseNotionCommand(stripped string) (action string, ok bool) {
	fields := strings.Fields(strings.TrimSpace(stripped))
	if len(fields) == 0 {
		return "", false
	}
	switch strings.ToLower(fields[0]) {
	case "!notion", "!notionmcp", "!notion-mcp":
	default:
		return "", false
	}
	if len(fields) < 2 {
		return "status", true
	}
	switch strings.ToLower(fields[1]) {
	case "on", "enable", "enabled", "true", "1", "開", "開啟", "啟用", "打開":
		return "on", true
	case "off", "disable", "disabled", "false", "0", "關", "關閉", "停用":
		return "off", true
	default:
		return "status", true
	}
}

func handleNotionCommand(s *discordgo.Session, m *discordgo.MessageCreate, action string) {
	if !isBridgeAdmin(m.Author.ID) {
		s.ChannelMessageSend(m.ChannelID, "⛔ 只有管理員能切換 Notion MCP。")
		return
	}
	switch action {
	case "on":
		if err := setNotionMCP(true); err != nil {
			s.ChannelMessageSend(m.ChannelID, "⚠️ 開啟失敗: "+err.Error())
			return
		}
		s.ChannelMessageSend(m.ChannelID, "✅ Notion MCP 已**開啟**。接下來每個新對話(或開新對話後)都會載入 Notion 工具。\n＊記憶體/速度會回到有 Notion 的狀態;用完記得 `!notion off`。")
	case "off":
		if err := setNotionMCP(false); err != nil {
			s.ChannelMessageSend(m.ChannelID, "⚠️ 關閉失敗: "+err.Error())
			return
		}
		s.ChannelMessageSend(m.ChannelID, "✅ Notion MCP 已**關閉**。下一則新對話起不再載入,回到省記憶體/快速模式。")
	default: // status
		state := "🔴 關閉(省記憶體/快速模式)"
		if notionMCPEnabled() {
			state = "🟢 開啟(每個新對話會載入 Notion 工具)"
		}
		s.ChannelMessageSend(m.ChannelID, "🔌 **Notion MCP 目前:** "+state+"\n用法:`!notion on` 開啟 · `!notion off` 關閉 · `!notion` 查狀態。\n切換即時生效(免重啟),對「切換後」開始的對話生效。")
	}
}
