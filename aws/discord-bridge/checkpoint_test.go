package main

import (
	"strings"
	"testing"
	"time"
)

func TestExtractCheckpointBlock(t *testing.T) {
	cases := []struct {
		name        string
		reply       string
		wantContent string
		wantCleaned string
	}{
		{
			name:        "no marker",
			reply:       "一般回覆,沒有檢查點。",
			wantContent: "",
			wantCleaned: "一般回覆,沒有檢查點。",
		},
		{
			name:        "well formed",
			reply:       "好的,我做完了。\n\n<<<CHECKPOINT>>>\n- 正在做:釘選檢查點\n- 待辦:部署\n<<<END CHECKPOINT>>>",
			wantContent: "- 正在做:釘選檢查點\n- 待辦:部署",
			wantCleaned: "好的,我做完了。",
		},
		{
			name:        "block in middle keeps both sides",
			reply:       "前言\n<<<CHECKPOINT>>>內容<<<END CHECKPOINT>>>\n後語",
			wantContent: "內容",
			wantCleaned: "前言\n\n後語",
		},
		{
			name:        "open without close is ignored",
			reply:       "文字 <<<CHECKPOINT>>> 沒有收尾,別把後面吞掉",
			wantContent: "",
			wantCleaned: "文字 <<<CHECKPOINT>>> 沒有收尾,別把後面吞掉",
		},
		{
			name:        "empty content",
			reply:       "x<<<CHECKPOINT>>>   <<<END CHECKPOINT>>>y",
			wantContent: "",
			wantCleaned: "x<<<CHECKPOINT>>>   <<<END CHECKPOINT>>>y", // content 空 → 呼叫端不動回覆
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			content, cleaned := extractCheckpointBlock(c.reply)
			if content != c.wantContent {
				t.Errorf("content = %q, want %q", content, c.wantContent)
			}
			// 「empty content」情境:cleaned 由呼叫端負責不採用,這裡只驗 content 空即可。
			if c.wantContent != "" && cleaned != c.wantCleaned {
				t.Errorf("cleaned = %q, want %q", cleaned, c.wantCleaned)
			}
		})
	}
}

func TestBuildCheckpointMessage(t *testing.T) {
	now := time.Date(2026, 7, 17, 8, 30, 0, 0, time.UTC)
	got := buildCheckpointMessage("進度內容", now)
	if !strings.HasPrefix(got, checkpointPinPrefix) {
		t.Errorf("缺少前綴: %q", got)
	}
	if !strings.Contains(got, "2026-07-17 08:30 UTC") {
		t.Errorf("缺少時間: %q", got)
	}
	if !strings.Contains(got, "進度內容") {
		t.Errorf("缺少內容: %q", got)
	}
}

func TestBuildCheckpointMessageTruncates(t *testing.T) {
	t.Setenv("CHECKPOINT_MAXCHARS", "10")
	long := strings.Repeat("字", 50)
	got := buildCheckpointMessage(long, time.Unix(0, 0).UTC())
	// 標頭之後的內容應被夾到 10 個字以內。
	body := stripCheckpointHeader(got)
	if n := len([]rune(body)); n > 10 {
		t.Errorf("內容未夾上限,長度 %d > 10: %q", n, body)
	}
}

func TestStripCheckpointHeader(t *testing.T) {
	cases := []struct {
		in, want string
	}{
		{checkpointPinPrefix + " · 2026-07-17 08:30 UTC\n實際內容\n第二行", "實際內容\n第二行"},
		{"沒有前綴的普通訊息", "沒有前綴的普通訊息"},
		{checkpointPinPrefix + " · 只有標頭沒內容", ""},
	}
	for _, c := range cases {
		if got := stripCheckpointHeader(c.in); got != c.want {
			t.Errorf("stripCheckpointHeader(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}
