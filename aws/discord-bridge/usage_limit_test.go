package main

import (
	"strings"
	"testing"
)

func TestClassifyBlock(t *testing.T) {
	cases := []struct{ in, want string }{
		{"Claude AI usage limit reached|1752600000", "usage"},
		{"usage limit reached — check plan", "usage"},
		{`{"error":{"message":"Your credit balance is too low"}}`, "credit"},
		{"Please run /login to authenticate", "auth"},
		{"Invalid API key provided", "auth"},
		{"oauth token expired", "auth"},
		{"401 Unauthorized", "auth"},
		{"Overloaded, please retry", "overloaded"},
		{"normal assistant reply about cats", ""},
		{"", ""},
	}
	for _, c := range cases {
		if got := classifyBlock(c.in); got != c.want {
			t.Errorf("classifyBlock(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestDetectUsageLimitReset(t *testing.T) {
	if ts := detectUsageLimitReset("Claude AI usage limit reached|1752600000"); ts != 1752600000 {
		t.Errorf("got %d, want 1752600000", ts)
	}
	if ts := detectUsageLimitReset("usage limit reached — check plan"); ts != 0 {
		t.Errorf("no timestamp should give 0, got %d", ts)
	}
	if ts := detectUsageLimitReset("reached|not-a-number"); ts != 0 {
		t.Errorf("non-numeric should give 0, got %d", ts)
	}
	if ts := detectUsageLimitReset("reached|123"); ts != 0 {
		t.Errorf("too-small ts should be rejected, got %d", ts)
	}
}

func TestFmtResetTime(t *testing.T) {
	if s := fmtResetTime(0); s != "" {
		t.Errorf("0 should give empty, got %q", s)
	}
	// 1752600000 = 2025-07-15 22:40 UTC → CST(+8) 07/16 06:40
	if s := fmtResetTime(1752600000); !strings.Contains(s, "07/16") {
		t.Errorf("expected 07/16 date, got %q", s)
	}
}

func TestBlockMessageNonNetwork(t *testing.T) {
	if m := blockMessage("credit", "credit balance too low"); !strings.Contains(m, "餘額不足") {
		t.Errorf("credit message wrong: %q", m)
	}
	if m := blockMessage("auth", "please run /login"); !strings.Contains(m, "認證失效") {
		t.Errorf("auth message wrong: %q", m)
	}
	if m := blockMessage("overloaded", "overloaded"); !strings.Contains(m, "過載") {
		t.Errorf("overloaded message wrong: %q", m)
	}
	if m := blockMessage("", "whatever"); m != "" {
		t.Errorf("empty kind should give empty message, got %q", m)
	}
}
