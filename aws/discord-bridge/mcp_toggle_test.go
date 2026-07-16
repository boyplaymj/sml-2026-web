package main

import (
	"path/filepath"
	"testing"
)

func TestParseNotionCommand(t *testing.T) {
	cases := []struct {
		in     string
		action string
		ok     bool
	}{
		{"!notion", "status", true},
		{"!notion 狀態", "status", true},
		{"!notion on", "on", true},
		{"!notion 開", "on", true},
		{"!notion 開啟", "on", true},
		{"!NOTION ON", "on", true},
		{"!notion off", "off", true},
		{"!notion 關閉", "off", true},
		{"!notion-mcp on", "on", true},
		{"!notion garbage", "status", true},
		{"!切帳號 x", "", false},
		{"!notionfoo", "", false},
		{"", "", false},
	}
	for _, c := range cases {
		action, ok := parseNotionCommand(c.in)
		if ok != c.ok || action != c.action {
			t.Errorf("parseNotionCommand(%q) = (%q,%v), want (%q,%v)", c.in, action, ok, c.action, c.ok)
		}
	}
}

func TestNotionMCPToggleRoundTrip(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("MCP_TOGGLE_PATH", filepath.Join(dir, "mcp-toggles.json"))
	// 重置 cache 狀態,避免受其他測試/預設值影響
	mcpMu.Lock()
	mcpLoaded = false
	mcpMu.Unlock()

	// 檔案不存在 → 視為關
	if notionMCPEnabled() {
		t.Fatal("expected disabled when flag file absent")
	}
	// 開
	if err := setNotionMCP(true); err != nil {
		t.Fatalf("setNotionMCP(true): %v", err)
	}
	if !notionMCPEnabled() {
		t.Fatal("expected enabled after setNotionMCP(true)")
	}
	// 關
	if err := setNotionMCP(false); err != nil {
		t.Fatalf("setNotionMCP(false): %v", err)
	}
	if notionMCPEnabled() {
		t.Fatal("expected disabled after setNotionMCP(false)")
	}
}

func TestNotionMCPConfigPathDefault(t *testing.T) {
	t.Setenv("NOTION_MCP_CONFIG", "")
	p := notionMCPConfigPath()
	if filepath.Base(p) != "mcp-notion.json" {
		t.Errorf("notionMCPConfigPath base = %q, want mcp-notion.json", filepath.Base(p))
	}
}
