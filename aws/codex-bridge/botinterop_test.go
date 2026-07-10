package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"unicode/utf8"
)

// TestMutateInteropDoesNotClobberOnCorruptJSON 釘住 review #2:
// readInterop 遇到「非不存在」的錯誤(這裡用壞掉的 JSON)時,寫入入口不得覆蓋原檔;
// toggleInterop 應回錯,且檔案內容保持原樣(不被洗成空白名單)。
func TestMutateInteropDoesNotClobberOnCorruptJSON(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "interop.json")
	corrupt := []byte("{ this is not valid json ")
	if err := os.WriteFile(p, corrupt, 0o644); err != nil {
		t.Fatal(err)
	}
	t.Setenv("BOT_INTEROP_PATH", p)
	t.Setenv("BOT_INTEROP_LOCK", filepath.Join(dir, "lock"))

	if _, err := toggleInterop("123", "x"); err == nil {
		t.Fatal("corrupt JSON 應回錯,結果卻是 nil(代表可能覆蓋了設定)")
	}
	got, _ := os.ReadFile(p)
	if string(got) != string(corrupt) {
		t.Fatalf("corrupt 檔被改寫了!應保持原內容不動。got=%q", got)
	}
}

// TestMutateInteropCreatesWhenMissing 檔案(含目錄)不存在時應視為空設定、建立成功。
func TestMutateInteropCreatesWhenMissing(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "sub", "interop.json") // 目錄也不存在,writeInterop 應自建
	t.Setenv("BOT_INTEROP_PATH", p)
	t.Setenv("BOT_INTEROP_LOCK", filepath.Join(dir, "lock"))

	on, err := toggleInterop("123", "x")
	if err != nil {
		t.Fatalf("檔案不存在時應建立成功,卻回錯: %v", err)
	}
	if !on {
		t.Fatal("首次 toggle 應為 true")
	}
	if _, err := os.Stat(p); err != nil {
		t.Fatalf("應已建立設定檔: %v", err)
	}
}

func resetReplyBufForTest() {
	replyBufMu.Lock()
	defer replyBufMu.Unlock()
	replyBuf = map[string]string{}
	replyBufOrder = nil
}

func TestRememberReplyRecallFullText(t *testing.T) {
	resetReplyBufForTest()

	rememberReply("msg-1", "第一段\n\n第二段")

	if got := recallReply("msg-1"); got != "第一段\n\n第二段" {
		t.Fatalf("recallReply = %q", got)
	}
}

func TestRememberReplyEvictsFIFO(t *testing.T) {
	resetReplyBufForTest()

	for i := 0; i < replyBufMax+1; i++ {
		rememberReply(string(rune('a'+i)), "x")
	}

	if got := len(replyBufOrder); got != replyBufMax {
		t.Fatalf("replyBufOrder len = %d, want %d", got, replyBufMax)
	}
	if got := recallReply("a"); got != "" {
		t.Fatalf("oldest entry should be evicted, got %q", got)
	}
}

func TestTruncateRunesKeepsUTF8Valid(t *testing.T) {
	input := strings.Repeat("測", 10)

	got := truncateRunes(input, 3)

	if !utf8.ValidString(got) {
		t.Fatalf("truncateRunes returned invalid UTF-8: %q", got)
	}
	if !strings.HasPrefix(got, "測測測") {
		t.Fatalf("truncateRunes prefix = %q", got)
	}
	if !strings.Contains(got, "截斷") {
		t.Fatalf("truncateRunes should append truncation notice: %q", got)
	}
}
