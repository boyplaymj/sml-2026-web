package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func writeJSONL(t *testing.T, lines ...string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "session.jsonl")
	if err := os.WriteFile(path, []byte(strings.Join(lines, "\n")+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestTailFromJSONLFiltersConversationText(t *testing.T) {
	path := writeJSONL(t,
		`{"type":"queue-operation","message":{"content":"ignore"}}`,
		`{"type":"user","message":{"content":"!用量"}}`,
		`{"type":"user","message":{"content":"我們在做切帳號回憶"}}`,
		`{"type":"assistant","message":{"content":[{"type":"thinking","thinking":"secret"},{"type":"text","text":"已決定做 Layer 0"},{"type":"tool_use","name":"x"},{"type":"text","text":"下一步補 Codex worker"}]}}`,
		`{"type":"user","message":{"content":[{"type":"text","text":"記得不要重新自介"},{"type":"tool_result","content":"ignore"}]}}`,
	)

	got := tailFromJSONLWithLimits(path, 12, 6000)
	want := strings.Join([]string{
		"使用者: 我們在做切帳號回憶",
		"你(上一帳號): 已決定做 Layer 0\n下一步補 Codex worker",
		"使用者: 記得不要重新自介",
	}, "\n")
	if got != want {
		t.Fatalf("tailFromJSONLWithLimits() =\n%s\nwant\n%s", got, want)
	}
	if strings.Contains(got, "secret") || strings.Contains(got, "tool") || strings.Contains(got, "!用量") {
		t.Fatalf("tail included filtered content: %q", got)
	}
}

func TestTailFromJSONLLimitsTurnsAndChars(t *testing.T) {
	path := writeJSONL(t,
		`{"type":"user","message":{"content":"one"}}`,
		`{"type":"assistant","message":{"content":[{"type":"text","text":"two"}]}}`,
		`{"type":"user","message":{"content":"three"}}`,
		`{"type":"assistant","message":{"content":[{"type":"text","text":"four"}]}}`,
	)

	got := tailFromJSONLWithLimits(path, 2, 1000)
	if strings.Contains(got, "one") || strings.Contains(got, "two") {
		t.Fatalf("tail kept too many turns: %q", got)
	}
	if !strings.Contains(got, "three") || !strings.Contains(got, "four") {
		t.Fatalf("tail dropped recent turns: %q", got)
	}

	short := tailFromJSONLWithLimits(path, 4, 20)
	if len([]rune(short)) > 20 {
		t.Fatalf("tail exceeded char limit: %d %q", len([]rune(short)), short)
	}
	if !strings.Contains(short, "four") {
		t.Fatalf("tail should preserve most recent content: %q", short)
	}
}

func TestTailFromJSONLMissingFileIsEmpty(t *testing.T) {
	if got := tailFromJSONLWithLimits(filepath.Join(t.TempDir(), "missing.jsonl"), 12, 6000); got != "" {
		t.Fatalf("missing file tail = %q, want empty", got)
	}
}

func TestSnapshotAndInjectHandoffConsumesOnce(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("HANDOFF_ENABLED", "1")

	sid := "sid-abc"
	channelID := "12345"
	proj := filepath.Join(home, ".claude", "projects", "-opt-sml-repo")
	if err := os.MkdirAll(proj, 0o700); err != nil {
		t.Fatal(err)
	}
	jsonl := filepath.Join(proj, sid+".jsonl")
	if err := os.WriteFile(jsonl, []byte(`{"type":"user","message":{"content":"我們在做自動回憶"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"待辦是切到 backup1 後接續"}]}}
`), 0o600); err != nil {
		t.Fatal(err)
	}

	mu.Lock()
	oldSessions := sessions
	sessions = map[string]string{channelID: sid}
	mu.Unlock()
	t.Cleanup(func() {
		mu.Lock()
		sessions = oldSessions
		mu.Unlock()
	})

	snapshotHandoff()
	if _, err := os.Stat(handoffPath(channelID)); err != nil {
		t.Fatalf("handoff file missing after snapshot: %v", err)
	}

	got, injected := injectHandoffRecall(channelID, "剛剛講到哪?")
	if !injected {
		t.Fatal("expected handoff injection")
	}
	if !strings.Contains(got, "我們在做自動回憶") || !strings.Contains(got, "剛剛講到哪?") {
		t.Fatalf("injected prompt missing recall or new message: %q", got)
	}
	if _, err := os.Stat(handoffPath(channelID)); err != nil {
		t.Fatalf("handoff should remain until successful run, stat err=%v", err)
	}
	consumeHandoff(channelID)
	if _, err := os.Stat(handoffPath(channelID)); !os.IsNotExist(err) {
		t.Fatalf("handoff should be consumed after success, stat err=%v", err)
	}
	if got2, injected := injectHandoffRecall(channelID, "第二則"); injected || got2 != "第二則" {
		t.Fatalf("handoff injected twice: %q", got2)
	}
}
