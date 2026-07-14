package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func credJSON(expiresAtMs int64, refresh string) string {
	m := map[string]any{"claudeAiOauth": map[string]any{
		"accessToken":      "sk-ant-oat01-old",
		"refreshToken":     refresh,
		"expiresAt":        expiresAtMs,
		"scopes":           []string{"user:inference"},
		"subscriptionType": "max",
	}}
	b, _ := json.Marshal(m)
	return string(b)
}

func TestCredentialExpiry(t *testing.T) {
	now := time.Now()
	exp, ok := credentialExpiry(credJSON(now.Add(time.Hour).UnixMilli(), "rt"))
	if !ok || exp.Before(now) {
		t.Fatalf("expected future expiry, got ok=%v exp=%v", ok, exp)
	}
	if _, ok := credentialExpiry(`{"claudeAiOauth":{"accessToken":"x"}}`); ok {
		t.Fatal("missing expiresAt should give ok=false")
	}
	if _, ok := credentialExpiry(`not json`); ok {
		t.Fatal("bad json should give ok=false")
	}
}

func TestCredentialRefreshToken(t *testing.T) {
	if got := credentialRefreshToken(credJSON(0, "  rt-123 ")); got != "rt-123" {
		t.Fatalf("got %q", got)
	}
	if got := credentialRefreshToken(`{"claudeAiOauth":{}}`); got != "" {
		t.Fatalf("expected empty, got %q", got)
	}
}

func TestMergeRefreshedCredentials(t *testing.T) {
	now := time.Unix(1_700_000_000, 0)
	old := credJSON(1, "old-rt")
	merged, err := mergeRefreshedCredentials(old, "new-access", "new-rt", 3600, now)
	if err != nil {
		t.Fatal(err)
	}
	var raw map[string]any
	if err := json.Unmarshal([]byte(merged), &raw); err != nil {
		t.Fatal(err)
	}
	o := raw["claudeAiOauth"].(map[string]any)
	if o["accessToken"] != "new-access" || o["refreshToken"] != "new-rt" {
		t.Fatalf("tokens not updated: %v", o)
	}
	if o["subscriptionType"] != "max" {
		t.Fatalf("subscriptionType lost: %v", o)
	}
	wantMs := float64(now.Add(3600 * time.Second).UnixMilli())
	if o["expiresAt"].(float64) != wantMs {
		t.Fatalf("expiresAt = %v want %v", o["expiresAt"], wantMs)
	}
	// 空 refreshToken 應保留舊值
	merged2, _ := mergeRefreshedCredentials(old, "new-access", "", 3600, now)
	json.Unmarshal([]byte(merged2), &raw)
	if raw["claudeAiOauth"].(map[string]any)["refreshToken"] != "old-rt" {
		t.Fatal("empty refresh should preserve old refreshToken")
	}
}

// 非過期憑證應直接判活,不打任何網路(client 給 nil 會 panic 就代表誤打了)。
func TestProbeSlotLivenessNotExpiredNoNetwork(t *testing.T) {
	now := time.Now()
	cred := credJSON(now.Add(time.Hour).UnixMilli(), "rt")
	alive, refreshed, dead, err := probeSlotLiveness(cred, nil, now)
	if !alive || refreshed != "" || dead || err != nil {
		t.Fatalf("got alive=%v refreshed=%q dead=%v err=%v", alive, refreshed, dead, err)
	}
}

func TestProbeSlotLivenessExpiredRefreshOK(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("anthropic-beta") != oauthBetaHeader {
			t.Errorf("missing anthropic-beta header")
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"access_token": "sk-new", "refresh_token": "rt-new", "expires_in": 3600,
		})
	}))
	defer srv.Close()
	t.Setenv("CLAUDE_OAUTH_BASE_URL", srv.URL)

	now := time.Now()
	cred := credJSON(now.Add(-time.Hour).UnixMilli(), "rt-old") // 已過期
	alive, refreshed, dead, err := probeSlotLiveness(cred, srv.Client(), now)
	if !alive || dead || err != nil || refreshed == "" {
		t.Fatalf("got alive=%v refreshed=%q dead=%v err=%v", alive, refreshed, dead, err)
	}
	if !strings.Contains(refreshed, "sk-new") {
		t.Fatalf("refreshed creds should contain new token: %s", refreshed)
	}
}

func TestProbeSlotLivenessDead(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]any{
			"error": "invalid_grant", "error_description": "Refresh token not found or invalid",
		})
	}))
	defer srv.Close()
	t.Setenv("CLAUDE_OAUTH_BASE_URL", srv.URL)

	now := time.Now()
	cred := credJSON(now.Add(-time.Hour).UnixMilli(), "rt-dead")
	alive, _, dead, err := probeSlotLiveness(cred, srv.Client(), now)
	if alive || !dead || err == nil {
		t.Fatalf("expected dead, got alive=%v dead=%v err=%v", alive, dead, err)
	}
}

func TestProbeSlotLivenessInconclusive(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("upstream boom"))
	}))
	defer srv.Close()
	t.Setenv("CLAUDE_OAUTH_BASE_URL", srv.URL)

	now := time.Now()
	cred := credJSON(now.Add(-time.Hour).UnixMilli(), "rt")
	alive, _, dead, err := probeSlotLiveness(cred, srv.Client(), now)
	if alive || dead || err == nil {
		t.Fatalf("5xx should be inconclusive (not alive, not dead, err!=nil), got alive=%v dead=%v err=%v", alive, dead, err)
	}
}

func TestEnvDisabled(t *testing.T) {
	t.Setenv("ACCOUNT_SWITCH_PROBE", "off")
	if probeEnabled() {
		t.Fatal("off should disable")
	}
	t.Setenv("ACCOUNT_SWITCH_PROBE", "")
	if !probeEnabled() {
		t.Fatal("unset should default enabled")
	}
}
