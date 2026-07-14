package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/bwmarrin/discordgo"
)

const accountSwitchService = "sml-discord-bridge"

var slotNameRe = regexp.MustCompile(`^[A-Za-z0-9._-]{1,64}$`)

func accountSSMPrefix() string {
	if p := strings.TrimRight(os.Getenv("CLAUDE_ACCOUNT_SSM_PREFIX"), "/"); p != "" {
		return p
	}
	return "/sml/claude/accounts"
}

func awsRegion() string {
	if r := os.Getenv("AWS_REGION"); r != "" {
		return r
	}
	if r := os.Getenv("AWS_DEFAULT_REGION"); r != "" {
		return r
	}
	return "ap-southeast-1"
}

func parseAccountCommand(stripped string) (action, slot string, ok bool) {
	fields := strings.Fields(strings.TrimSpace(stripped))
	if len(fields) == 0 {
		return "", "", false
	}
	switch fields[0] {
	case "!帳號", "!claude帳號", "!claude-account":
		if len(fields) >= 2 {
			arg := strings.ToLower(fields[1])
			switch arg {
			case "list", "列表", "slots", "slot":
				return "list", "", true
			}
		}
		return "status", "", true
	case "!帳號列表", "!claude帳號列表":
		return "list", "", true
	case "!切帳號", "!切換帳號", "!claude切帳號", "!switch-claude":
		if len(fields) < 2 {
			return "help", "", true
		}
		return "switch", fields[1], true
	default:
		return "", "", false
	}
}

func accountCommandHelp() string {
	return "用法: `!帳號` 查看目前帳號、`!帳號列表` 查看可切槽位、`!切帳號 backup1` 切換到指定 Claude 帳號槽位。"
}

func validateSlotName(slot string) error {
	if !slotNameRe.MatchString(slot) {
		return fmt.Errorf("slot 名稱只能包含英數、點、底線、連字號,長度 1-64")
	}
	return nil
}

func runAWS(args ...string) (string, error) {
	args = append(args, "--region", awsRegion())
	cmd := exec.Command("aws", args...)
	cmd.Env = os.Environ()
	out, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("%v: %s", err, firstLine(string(out)))
	}
	return strings.TrimSpace(string(out)), nil
}

func accountSlotParam(slot, leaf string) string {
	return accountSSMPrefix() + "/" + slot + "/" + leaf
}

func extractAccountSlots(paramNames []string, prefix string) []string {
	prefix = strings.TrimRight(prefix, "/") + "/"
	set := map[string]bool{}
	for _, name := range paramNames {
		name = strings.TrimSpace(name)
		if !strings.HasPrefix(name, prefix) || !strings.HasSuffix(name, "/credentials-json") {
			continue
		}
		rest := strings.TrimSuffix(strings.TrimPrefix(name, prefix), "/credentials-json")
		if rest != "" && !strings.Contains(rest, "/") {
			set[rest] = true
		}
	}
	var out []string
	for slot := range set {
		out = append(out, slot)
	}
	sort.Strings(out)
	return out
}

func listAccountSlots() ([]string, error) {
	out, err := runAWS("ssm", "get-parameters-by-path",
		"--path", accountSSMPrefix(),
		"--recursive",
		"--query", "Parameters[].Name",
		"--output", "text")
	if err != nil {
		return nil, err
	}
	if out == "" {
		return nil, nil
	}
	return extractAccountSlots(strings.Fields(out), accountSSMPrefix()), nil
}

func getSSMParameter(name string, decrypt bool) (string, error) {
	args := []string{"ssm", "get-parameter", "--name", name, "--query", "Parameter.Value", "--output", "text"}
	if decrypt {
		args = append(args, "--with-decryption")
	}
	return runAWS(args...)
}

func readAccountSlot(slot string) (credentialsJSON, claudeJSON string, err error) {
	if err := validateSlotName(slot); err != nil {
		return "", "", err
	}
	credentialsJSON, err = getSSMParameter(accountSlotParam(slot, "credentials-json"), true)
	if err != nil {
		return "", "", fmt.Errorf("讀取 slot %q 的 credentials-json 失敗: %w", slot, err)
	}
	if err := validateCredentialsJSON(credentialsJSON); err != nil {
		return "", "", err
	}
	claudeJSON, _ = getSSMParameter(accountSlotParam(slot, "claude-json"), true) // optional
	if strings.TrimSpace(claudeJSON) != "" && !json.Valid([]byte(claudeJSON)) {
		return "", "", fmt.Errorf("slot %q 的 claude-json 不是合法 JSON", slot)
	}
	return credentialsJSON, claudeJSON, nil
}

func validateCredentialsJSON(s string) error {
	var raw map[string]any
	if err := json.Unmarshal([]byte(s), &raw); err != nil {
		return fmt.Errorf("credentials-json 不是合法 JSON: %w", err)
	}
	oauth, ok := raw["claudeAiOauth"].(map[string]any)
	if !ok {
		return fmt.Errorf("credentials-json 缺少 claudeAiOauth")
	}
	accessToken, ok := oauth["accessToken"].(string)
	if !ok || strings.TrimSpace(accessToken) == "" {
		return fmt.Errorf("credentials-json 缺少 claudeAiOauth.accessToken")
	}
	return nil
}

func claudeHomePath(parts ...string) string {
	home, err := os.UserHomeDir()
	if err != nil || home == "" {
		home = "/home/smlbot"
	}
	all := append([]string{home}, parts...)
	return filepath.Join(all...)
}

func backupFileIfExists(path, label string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}
	dir := claudeHomePath(".claude", "backups")
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}
	dst := filepath.Join(dir, fmt.Sprintf("%s.%s", label, time.Now().UTC().Format("20060102-150405")))
	return os.WriteFile(dst, data, 0o600)
}

func writePrivateJSON(path, content string) error {
	if !json.Valid([]byte(content)) {
		return fmt.Errorf("%s 不是合法 JSON", filepath.Base(path))
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, []byte(content), 0o600); err != nil {
		return err
	}
	if err := os.Rename(tmp, path); err != nil {
		return err
	}
	return os.Chmod(path, 0o600)
}

func clearBridgeSessionsFile() error {
	path := sessionsFile()
	if err := backupFileIfExists(path, "bridge-sessions.json"); err != nil {
		return err
	}
	if err := writePrivateJSON(path, "{}"); err != nil {
		return err
	}
	mu.Lock()
	sessions = map[string]string{}
	saveSessionsLocked()
	mu.Unlock()
	return nil
}

func writeActiveAccount(slot string) error {
	return os.WriteFile(claudeHomePath(".claude", "active-account"), []byte(slot+"\n"), 0o600)
}

func readActiveAccount() string {
	data, err := os.ReadFile(claudeHomePath(".claude", "active-account"))
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(data))
}

func applyAccountSlot(slot string) error {
	// write-back 保鮮:切走目前帳號前,把它的最新本機憑證寫回自己的 SSM slot,
	// 避免 refreshToken 輪換後 SSM 存的舊值失效。best-effort,失敗只 log 不擋。
	if prev := readActiveAccount(); prev != "" && prev != slot {
		writeBackLeavingAccount(prev)
	}

	credentialsJSON, claudeJSON, err := readAccountSlot(slot)
	if err != nil {
		return err
	}

	// 防呆閘:切進去前先驗活。確定失效就中止,絕不在此之後才發現死帳號
	// (那時 session 已被清空)。驗活成功且有刷新→用刷新後憑證並寫回 SSM 自癒。
	if probeEnabled() {
		alive, refreshed, dead, perr := probeSlotLiveness(credentialsJSON, oauthHTTPClient(), time.Now())
		switch {
		case dead:
			return fmt.Errorf("slot %q 的憑證已失效(refresh 被拒: %v)。請先重新登入該帳號再切換;目前帳號與所有 session 未受影響", slot, perr)
		case perr != nil:
			log.Printf("[account] slot %q 驗活無法判定(%v),仍繼續切換", slot, perr)
		case refreshed != "":
			credentialsJSON = refreshed
			if err := persistCredsToSSM(slot, refreshed); err != nil {
				log.Printf("[account] slot %q 自癒寫回 SSM 失敗(不影響本次切換): %v", slot, err)
			} else {
				log.Printf("[account] slot %q 已刷新並寫回 SSM(自癒)", slot)
			}
		default:
			_ = alive // accessToken 仍有效,直接用
		}
	}

	credPath := claudeHomePath(".claude", ".credentials.json")
	if err := backupFileIfExists(credPath, ".credentials.json"); err != nil {
		return fmt.Errorf("備份 credentials 失敗: %w", err)
	}
	if err := writePrivateJSON(credPath, credentialsJSON); err != nil {
		return fmt.Errorf("寫入 credentials 失敗: %w", err)
	}
	if strings.TrimSpace(claudeJSON) != "" {
		claudePath := claudeHomePath(".claude.json")
		if err := backupFileIfExists(claudePath, ".claude.json"); err != nil {
			return fmt.Errorf("備份 .claude.json 失敗: %w", err)
		}
		if err := writePrivateJSON(claudePath, claudeJSON); err != nil {
			return fmt.Errorf("寫入 .claude.json 失敗: %w", err)
		}
	}
	if err := clearBridgeSessionsFile(); err != nil {
		return fmt.Errorf("清空 bridge session 失敗: %w", err)
	}
	if err := writeActiveAccount(slot); err != nil {
		return fmt.Errorf("寫入 active-account 失敗: %w", err)
	}
	return nil
}

func scheduleBridgeRestart() error {
	cmd := exec.Command("sh", "-c", "sleep 2; sudo systemctl restart "+accountSwitchService)
	cmd.Stdout = ioDiscard{}
	cmd.Stderr = ioDiscard{}
	return cmd.Start()
}

type ioDiscard struct{}

func (ioDiscard) Write(p []byte) (int, error) { return len(p), nil }

func accountStatusText() string {
	active := readActiveAccount()
	if active == "" {
		active = "(未記錄)"
	}
	lines := []string{"📌 Claude 帳號狀態", "active slot: `" + active + "`"}
	if acc, ok, stale := currentAccount(claudeUsageToken()); ok {
		who := maskEmail(acc.Email)
		if acc.DisplayName != "" {
			who += " (" + acc.DisplayName + ")"
		}
		lines = append(lines,
			"account: "+who,
			"plan: "+prettyPlan(acc),
			fmt.Sprintf("overage: %v", acc.ExtraUsage),
		)
		if stale {
			lines = append(lines, "⚠️ 帳號資訊讀自 ~/.claude.json,切帳號後可能非最新")
		}
	} else {
		lines = append(lines, "account: (讀不到)")
	}
	if _, err := os.Stat(claudeHomePath(".claude", ".credentials.json")); err == nil {
		lines = append(lines, "credentials: present")
	} else {
		lines = append(lines, "credentials: missing")
	}
	return strings.Join(lines, "\n")
}

func handleAccountCommand(s *discordgo.Session, m *discordgo.MessageCreate, action, slot string) {
	if !isBridgeAdmin(m.Author.ID) {
		s.ChannelMessageSend(m.ChannelID, "⛔ 只有管理員能檢視/切換 Claude 帳號。")
		return
	}
	switch action {
	case "status":
		s.ChannelMessageSend(m.ChannelID, accountStatusText())
	case "list":
		slots, err := listAccountSlots()
		if err != nil {
			log.Printf("account list error: %v", err)
			s.ChannelMessageSend(m.ChannelID, "⚠️ 讀取帳號槽位失敗: "+err.Error())
			return
		}
		if len(slots) == 0 {
			s.ChannelMessageSend(m.ChannelID, "目前沒有找到帳號槽位。預期 SSM 路徑: `"+accountSSMPrefix()+"/<slot>/credentials-json`")
			return
		}
		s.ChannelMessageSend(m.ChannelID, "可切換帳號槽位:\n- `"+strings.Join(slots, "`\n- `")+"`")
	case "switch":
		if err := applyAccountSlot(slot); err != nil {
			log.Printf("account switch error slot=%s: %v", slot, err)
			s.ChannelMessageSend(m.ChannelID, "⚠️ 切換失敗: "+err.Error())
			return
		}
		s.ChannelMessageSend(m.ChannelID, "✅ 已切換 Claude 帳號槽位 `"+slot+"`，已備份舊憑證並清空 bridge sessions。bridge 將在 2 秒後重啟。")
		if err := scheduleBridgeRestart(); err != nil {
			log.Printf("schedule restart error: %v", err)
			s.ChannelMessageSend(m.ChannelID, "⚠️ 帳號已切換，但排程重啟失敗: "+err.Error()+"。請手動重啟 `sml-discord-bridge`。")
		}
	default:
		s.ChannelMessageSend(m.ChannelID, accountCommandHelp())
	}
}
