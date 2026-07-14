package main

// 帳號切換的兩道防護:
//   1. write-back 保鮮：切換「離開」某帳號時，把它當前本機 .credentials.json
//      (claude 用過、refreshToken 已是最新輪換值) 寫回它的 SSM slot，避免下次
//      切回來時 SSM 存的是被輪換掉的舊 refreshToken(=失效)。
//   2. 防呆閘：切「進」某 slot 前，若其 accessToken 已過期就打 OAuth 端點做一次
//      refresh 驗活；確定失效(invalid_grant)→ 中止切換、不動現有帳號/session；
//      驗活成功順便自癒(把刷新後憑證寫回該 slot);網路/端點等非決定性錯誤→放行+警告。

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"
)

// Claude Code 官方 OAuth 參數(可用環境變數覆寫，避免日後端點異動時卡死)。
const (
	defaultOAuthBaseURL  = "https://console.anthropic.com"
	defaultOAuthClientID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
	oauthBetaHeader      = "oauth-2025-04-20"
	oauthTokenPath       = "/v1/oauth/token"
	// 過期判定的安全邊際:距到期不足此秒數就當「該刷新」。
	expirySkewSeconds = 120
)

func oauthBaseURL() string {
	if v := strings.TrimRight(os.Getenv("CLAUDE_OAUTH_BASE_URL"), "/"); v != "" {
		return v
	}
	return defaultOAuthBaseURL
}

func oauthClientID() string {
	if v := strings.TrimSpace(os.Getenv("CLAUDE_OAUTH_CLIENT_ID")); v != "" {
		return v
	}
	return defaultOAuthClientID
}

// envDisabled 回傳 true 表示該功能被明確關閉(值為 0/off/false/no)。預設(未設)= 啟用。
func envDisabled(name string) bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv(name))) {
	case "0", "off", "false", "no":
		return true
	}
	return false
}

func probeEnabled() bool     { return !envDisabled("ACCOUNT_SWITCH_PROBE") }
func writeBackEnabled() bool { return !envDisabled("ACCOUNT_SWITCH_WRITEBACK") }

// credentialExpiry 從 credentials-json 取出 claudeAiOauth.expiresAt(毫秒)並轉成時間。
// ok=false 表示沒有可解析的到期欄位(視為「不確定 → 需要驗活」)。
func credentialExpiry(credentialsJSON string) (t time.Time, ok bool) {
	var raw map[string]any
	if err := json.Unmarshal([]byte(credentialsJSON), &raw); err != nil {
		return time.Time{}, false
	}
	oauth, _ := raw["claudeAiOauth"].(map[string]any)
	if oauth == nil {
		return time.Time{}, false
	}
	ms, ok := oauth["expiresAt"].(float64)
	if !ok || ms <= 0 {
		return time.Time{}, false
	}
	return time.UnixMilli(int64(ms)), true
}

func credentialRefreshToken(credentialsJSON string) string {
	var raw map[string]any
	if err := json.Unmarshal([]byte(credentialsJSON), &raw); err != nil {
		return ""
	}
	oauth, _ := raw["claudeAiOauth"].(map[string]any)
	if oauth == nil {
		return ""
	}
	rt, _ := oauth["refreshToken"].(string)
	return strings.TrimSpace(rt)
}

// mergeRefreshedCredentials 把刷新拿到的新 token 併回原本的 credentials-json，
// 保留其餘欄位(scopes / subscriptionType 等)。newRefreshToken 為空則不覆寫舊值。
func mergeRefreshedCredentials(oldJSON, accessToken, newRefreshToken string, expiresInSeconds int64, now time.Time) (string, error) {
	var raw map[string]any
	if err := json.Unmarshal([]byte(oldJSON), &raw); err != nil {
		return "", fmt.Errorf("原 credentials-json 解析失敗: %w", err)
	}
	oauth, _ := raw["claudeAiOauth"].(map[string]any)
	if oauth == nil {
		return "", fmt.Errorf("credentials-json 缺少 claudeAiOauth")
	}
	if strings.TrimSpace(accessToken) == "" {
		return "", fmt.Errorf("刷新結果缺少 accessToken")
	}
	oauth["accessToken"] = accessToken
	if strings.TrimSpace(newRefreshToken) != "" {
		oauth["refreshToken"] = newRefreshToken
	}
	if expiresInSeconds > 0 {
		oauth["expiresAt"] = now.Add(time.Duration(expiresInSeconds) * time.Second).UnixMilli()
	}
	raw["claudeAiOauth"] = oauth
	out, err := json.Marshal(raw)
	if err != nil {
		return "", err
	}
	return string(out), nil
}

// oauthRefresh 用 refreshToken 打 OAuth 端點換新。
// definitiveDead=true 表示端點明確拒絕(invalid_grant/invalid_client)→ 憑證確定失效。
// 其餘錯誤(網路、404、5xx)只回 err，非決定性。
func oauthRefresh(refreshToken string, hc *http.Client) (accessToken, newRefreshToken string, expiresIn int64, definitiveDead bool, err error) {
	if strings.TrimSpace(refreshToken) == "" {
		return "", "", 0, true, fmt.Errorf("沒有 refreshToken 可用")
	}
	body, _ := json.Marshal(map[string]string{
		"grant_type":    "refresh_token",
		"refresh_token": refreshToken,
		"client_id":     oauthClientID(),
	})
	req, err := http.NewRequest(http.MethodPost, oauthBaseURL()+oauthTokenPath, bytes.NewReader(body))
	if err != nil {
		return "", "", 0, false, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("anthropic-beta", oauthBetaHeader)
	// 必帶非預設 UA，否則會被 Cloudflare 擋(error 1010)。
	req.Header.Set("User-Agent", "anthropic-sdk-typescript/0.60.0 userOAuthProvider")
	req.Header.Set("Accept", "application/json")

	resp, err := hc.Do(req)
	if err != nil {
		return "", "", 0, false, err
	}
	defer resp.Body.Close()
	respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))

	if resp.StatusCode == http.StatusOK {
		var tok struct {
			AccessToken  string `json:"access_token"`
			RefreshToken string `json:"refresh_token"`
			ExpiresIn    int64  `json:"expires_in"`
		}
		if err := json.Unmarshal(respBody, &tok); err != nil {
			return "", "", 0, false, fmt.Errorf("刷新回應解析失敗: %w", err)
		}
		if strings.TrimSpace(tok.AccessToken) == "" {
			return "", "", 0, false, fmt.Errorf("刷新回應缺少 access_token")
		}
		return tok.AccessToken, tok.RefreshToken, tok.ExpiresIn, false, nil
	}

	// 解析 OAuth 錯誤格式 {"error":"...","error_description":"..."}
	var oe struct {
		Error string `json:"error"`
		Desc  string `json:"error_description"`
	}
	_ = json.Unmarshal(respBody, &oe)
	dead := false
	switch oe.Error {
	case "invalid_grant", "invalid_client", "unauthorized_client":
		dead = true
	}
	msg := oe.Error
	if oe.Desc != "" {
		msg += ": " + oe.Desc
	}
	if msg == "" {
		msg = fmt.Sprintf("HTTP %d: %s", resp.StatusCode, firstLine(string(respBody)))
	}
	return "", "", 0, dead, fmt.Errorf("%s", msg)
}

// probeSlotLiveness 判定目標 slot 憑證是否可用。
//   - alive=true 且 refreshedJSON!="" → 剛刷新成功，refreshedJSON 是要用的新憑證(呼叫端應寫回 SSM 自癒)。
//   - alive=true 且 refreshedJSON=="" → accessToken 尚未過期，直接可用。
//   - dead=true → 憑證確定失效，呼叫端應中止切換。
//   - alive=false 且 dead=false → 無法判定(網路/端點異常)，呼叫端可放行但要警告。err 帶原因。
func probeSlotLiveness(credentialsJSON string, hc *http.Client, now time.Time) (alive bool, refreshedJSON string, dead bool, err error) {
	if exp, ok := credentialExpiry(credentialsJSON); ok {
		if exp.After(now.Add(expirySkewSeconds * time.Second)) {
			return true, "", false, nil // accessToken 仍有效，免刷新
		}
	}
	// 已過期或無法判定到期 → 做一次真實刷新驗活。
	rt := credentialRefreshToken(credentialsJSON)
	access, newRT, expiresIn, deadFlag, rerr := oauthRefresh(rt, hc)
	if deadFlag {
		return false, "", true, rerr
	}
	if rerr != nil {
		return false, "", false, rerr // 非決定性
	}
	merged, merr := mergeRefreshedCredentials(credentialsJSON, access, newRT, expiresIn, now)
	if merr != nil {
		return false, "", false, merr
	}
	return true, merged, false, nil
}

// ---- SSM 寫回 ----

// putSSMParameterSecure 用 --cli-input-json file:// 寫 SecureString，避免把憑證放進命令列
// 參數(會被 ps 看到)。value 必須是合法 JSON 字串。
func putSSMParameterSecure(name, value string) error {
	payload, err := json.Marshal(map[string]any{
		"Name":      name,
		"Value":     value,
		"Type":      "SecureString",
		"Overwrite": true,
	})
	if err != nil {
		return err
	}
	f, err := os.CreateTemp("", "ssmput-*.json")
	if err != nil {
		return err
	}
	tmp := f.Name()
	defer os.Remove(tmp)
	if err := os.Chmod(tmp, 0o600); err != nil {
		f.Close()
		return err
	}
	if _, err := f.Write(payload); err != nil {
		f.Close()
		return err
	}
	if err := f.Close(); err != nil {
		return err
	}
	_, err = runAWS("ssm", "put-parameter", "--cli-input-json", "file://"+tmp)
	return err
}

// persistCredsToSSM 把 credentialsJSON 寫回指定 slot 的 credentials-json 參數(先驗證)。
func persistCredsToSSM(slot, credentialsJSON string) error {
	if err := validateSlotName(slot); err != nil {
		return err
	}
	if err := validateCredentialsJSON(credentialsJSON); err != nil {
		return err
	}
	return putSSMParameterSecure(accountSlotParam(slot, "credentials-json"), credentialsJSON)
}

func readLocalCredentials() (string, error) {
	data, err := os.ReadFile(claudeHomePath(".claude", ".credentials.json"))
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// writeBackLeavingAccount 在切走某帳號前，把本機當前憑證寫回它的 SSM slot(best-effort)。
func writeBackLeavingAccount(prevSlot string) {
	if !writeBackEnabled() || prevSlot == "" {
		return
	}
	cur, err := readLocalCredentials()
	if err != nil {
		log.Printf("[account] write-back 略過(讀不到本機憑證): %v", err)
		return
	}
	if err := persistCredsToSSM(prevSlot, cur); err != nil {
		log.Printf("[account] write-back 到 slot %q 失敗(不影響切換): %v", prevSlot, err)
		return
	}
	log.Printf("[account] 已把離開中的帳號 %q 最新憑證寫回 SSM", prevSlot)
}

func oauthHTTPClient() *http.Client { return &http.Client{Timeout: 25 * time.Second} }
