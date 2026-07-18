package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestHandoffTailFromJSONLForWorker(t *testing.T) {
	path := filepath.Join(t.TempDir(), "session.jsonl")
	lines := []string{
		`{"type":"user","message":{"content":"!帳號"}}`,
		`{"type":"user","message":{"content":"目前在做 backup1 登入流程"}}`,
		`{"type":"assistant","message":{"content":[{"type":"thinking","thinking":"skip"},{"type":"text","text":"先保存 main,再建立 backup1"},{"type":"tool_use","name":"skip"}]}}`,
	}
	if err := os.WriteFile(path, []byte(strings.Join(lines, "\n")+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}

	got := tailFromJSONLWithLimits(path, 12, 6000)
	if strings.Contains(got, "!帳號") || strings.Contains(got, "thinking") || strings.Contains(got, "tool_use") {
		t.Fatalf("tail included filtered content: %q", got)
	}
	if !strings.Contains(got, "目前在做 backup1 登入流程") || !strings.Contains(got, "先保存 main") {
		t.Fatalf("tail missing expected content: %q", got)
	}
}
