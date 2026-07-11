package main

import "testing"

func TestParseAccountCommand(t *testing.T) {
	cases := []struct {
		in     string
		action string
		slot   string
		ok     bool
	}{
		{"!帳號", "status", "", true},
		{"!帳號 list", "list", "", true},
		{"!帳號列表", "list", "", true},
		{"!切帳號 backup1", "switch", "backup1", true},
		{"!切換帳號 main", "switch", "main", true},
		{"!切帳號", "help", "", true},
		{"!白名單", "", "", false},
	}
	for _, tc := range cases {
		action, slot, ok := parseAccountCommand(tc.in)
		if action != tc.action || slot != tc.slot || ok != tc.ok {
			t.Fatalf("parseAccountCommand(%q) = (%q,%q,%v), want (%q,%q,%v)", tc.in, action, slot, ok, tc.action, tc.slot, tc.ok)
		}
	}
}

func TestValidateSlotName(t *testing.T) {
	valid := []string{"main", "backup1", "backup-1", "backup_1", "zz.max20x"}
	for _, v := range valid {
		if err := validateSlotName(v); err != nil {
			t.Fatalf("validateSlotName(%q) unexpected error: %v", v, err)
		}
	}
	invalid := []string{"", "../secret", "a/b", "有中文", "space name"}
	for _, v := range invalid {
		if err := validateSlotName(v); err == nil {
			t.Fatalf("validateSlotName(%q) should fail", v)
		}
	}
}

func TestExtractAccountSlots(t *testing.T) {
	names := []string{
		"/sml/claude/accounts/main/credentials-json",
		"/sml/claude/accounts/main/claude-json",
		"/sml/claude/accounts/backup1/credentials-json",
		"/sml/claude/accounts/nested/bad/credentials-json",
		"/sml/claude/other/backup2/credentials-json",
	}
	got := extractAccountSlots(names, "/sml/claude/accounts")
	if len(got) != 2 || got[0] != "backup1" || got[1] != "main" {
		t.Fatalf("extractAccountSlots = %#v, want [backup1 main]", got)
	}
}

func TestValidateCredentialsJSON(t *testing.T) {
	good := `{"claudeAiOauth":{"accessToken":"tok","refreshToken":"ref"}}`
	if err := validateCredentialsJSON(good); err != nil {
		t.Fatalf("validateCredentialsJSON(good) unexpected error: %v", err)
	}
	bad := []string{
		`{`,
		`{"other":{}}`,
		`{"claudeAiOauth":{}}`,
	}
	for _, s := range bad {
		if err := validateCredentialsJSON(s); err == nil {
			t.Fatalf("validateCredentialsJSON(%s) should fail", s)
		}
	}
}
