package main

import "testing"

func idxOf(s []string, v string) int {
	for i, x := range s {
		if x == v {
			return i
		}
	}
	return -1
}

// TestClaudeArgsResumeBeforeTerminator 釘住迴歸:--resume 必須在 `--` 之前,
// prompt 必須是最後一個位置參數。若 --resume 跑到 `--` 之後,session 會失憶。
func TestClaudeArgsResumeBeforeTerminator(t *testing.T) {
	// prompt 故意以 "-" 開頭,驗證它被 `--` 保護、不會被當 option。
	args := claudeArgs("sess-abc", "-rf 刪一下")

	dd := idxOf(args, "--")
	rs := idxOf(args, "--resume")
	if rs < 0 {
		t.Fatalf("--resume 應存在: %v", args)
	}
	if dd < 0 {
		t.Fatalf("-- 應存在: %v", args)
	}
	if rs > dd {
		t.Fatalf("--resume(idx %d)必須在 --(idx %d)之前,否則 session 不會 resume: %v", rs, dd, args)
	}
	if args[rs+1] != "sess-abc" {
		t.Fatalf("--resume 後應緊接 session id: %v", args)
	}
	if args[len(args)-1] != "-rf 刪一下" {
		t.Fatalf("prompt 必須是最後一個位置參數: %v", args)
	}
}

// TestClaudeArgsNoSession 沒有 session 時不應帶 --resume。
func TestClaudeArgsNoSession(t *testing.T) {
	args := claudeArgs("", "hello")
	if idxOf(args, "--resume") != -1 {
		t.Fatalf("sid 為空時不應出現 --resume: %v", args)
	}
	if args[len(args)-1] != "hello" {
		t.Fatalf("prompt 必須是最後一個位置參數: %v", args)
	}
	if idxOf(args, "--") != len(args)-2 {
		t.Fatalf("-- 應緊接在 prompt 之前: %v", args)
	}
}
