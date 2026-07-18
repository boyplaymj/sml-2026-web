package main

import (
	"bufio"
	"encoding/json"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

const handoffTTL = 24 * time.Hour

type handoffRecord struct {
	Channel   string    `json:"channel"`
	SID       string    `json:"sid"`
	JSONL     string    `json:"jsonl"`
	CreatedAt time.Time `json:"created_at"`
	Note      *string   `json:"note"`
}

type handoffLine struct {
	role string
	text string
}

func envBool(k string, def bool) bool {
	v := strings.TrimSpace(strings.ToLower(os.Getenv(k)))
	if v == "" {
		return def
	}
	switch v {
	case "1", "true", "yes", "y", "on", "enable", "enabled":
		return true
	case "0", "false", "no", "n", "off", "disable", "disabled":
		return false
	default:
		return def
	}
}

func handoffEnabled() bool {
	return envBool("HANDOFF_ENABLED", true)
}

func handoffTailTurns() int {
	return envInt("HANDOFF_TAIL_TURNS", 12)
}

func handoffTailMaxChars() int {
	return envInt("HANDOFF_TAIL_MAXCHARS", 6000)
}

func handoffHome() string {
	home, err := os.UserHomeDir()
	if err != nil || home == "" {
		return "/home/smlbot"
	}
	return home
}

func handoffDir() string {
	return filepath.Join(handoffHome(), ".claude", "bridge-handoff")
}

func handoffPath(channelID string) string {
	return filepath.Join(handoffDir(), channelID+".json")
}

func atomicWriteJSON(path string, v any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	tmp, err := os.CreateTemp(filepath.Dir(path), filepath.Base(path)+".*.tmp")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Chmod(0o600); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := os.Rename(tmpName, path); err != nil {
		return err
	}
	return os.Chmod(path, 0o600)
}

func findSessionJSONL(sid string) string {
	if sid == "" {
		return ""
	}
	pattern := filepath.Join(handoffHome(), ".claude", "projects", "*", sid+".jsonl")
	matches, err := filepath.Glob(pattern)
	if err != nil || len(matches) == 0 {
		return ""
	}
	sort.Strings(matches)
	return matches[0]
}

func snapshotHandoff() {
	if !handoffEnabled() {
		return
	}
	mu.Lock()
	copied := make(map[string]string, len(sessions))
	for ch, sid := range sessions {
		copied[ch] = sid
	}
	mu.Unlock()

	now := time.Now().UTC()
	for channelID, sid := range copied {
		if strings.TrimSpace(channelID) == "" || strings.TrimSpace(sid) == "" {
			continue
		}
		jsonl := findSessionJSONL(sid)
		if jsonl == "" {
			log.Printf("handoff snapshot skip ch=%s sid=%s: jsonl not found", channelID, sid)
			continue
		}
		rec := handoffRecord{
			Channel:   channelID,
			SID:       sid,
			JSONL:     jsonl,
			CreatedAt: now,
			Note:      nil,
		}
		if err := atomicWriteJSON(handoffPath(channelID), rec); err != nil {
			log.Printf("handoff snapshot write ch=%s sid=%s: %v", channelID, sid, err)
			continue
		}
		log.Printf("handoff snapshot ch=%s sid=%s jsonl=%s", channelID, sid, jsonl)
	}
}

func loadHandoff(channelID string) (handoffRecord, bool) {
	if !handoffEnabled() {
		return handoffRecord{}, false
	}
	path := handoffPath(channelID)
	data, err := os.ReadFile(path)
	if err != nil {
		return handoffRecord{}, false
	}
	var rec handoffRecord
	if err := json.Unmarshal(data, &rec); err != nil {
		_ = os.Remove(path)
		log.Printf("handoff invalid ch=%s: %v", channelID, err)
		return handoffRecord{}, false
	}
	if rec.CreatedAt.IsZero() || time.Since(rec.CreatedAt) > handoffTTL {
		_ = os.Remove(path)
		log.Printf("handoff expired ch=%s", channelID)
		return handoffRecord{}, false
	}
	return rec, true
}

func consumeHandoff(channelID string) {
	if err := os.Remove(handoffPath(channelID)); err != nil && !os.IsNotExist(err) {
		log.Printf("handoff consume ch=%s: %v", channelID, err)
	}
}

func injectHandoffRecall(channelID, prompt string) (string, bool) {
	rec, ok := loadHandoff(channelID)
	if !ok {
		return prompt, false
	}

	source := "tail"
	recall := ""
	if rec.Note != nil && strings.TrimSpace(*rec.Note) != "" {
		source = "note"
		recall = strings.TrimSpace(*rec.Note)
	} else {
		recall = tailFromJSONL(rec.JSONL)
	}
	if strings.TrimSpace(recall) == "" {
		log.Printf("handoff empty ch=%s sid=%s", channelID, rec.SID)
		consumeHandoff(channelID)
		return prompt, false
	}
	log.Printf("handoff injected ch=%s sid=%s source=%s chars=%d", channelID, rec.SID, source, len([]rune(recall)))
	return "【接續前一個帳號的對話,以下是切換前的脈絡回顧,請據此無縫接續,不要重新自我介紹】\n" +
		recall + "\n\n【使用者的新訊息】\n" + prompt, true
}

func tailFromJSONL(path string) string {
	return tailFromJSONLWithLimits(path, handoffTailTurns(), handoffTailMaxChars())
}

func tailFromJSONLWithLimits(path string, turns, maxChars int) string {
	if turns <= 0 || maxChars <= 0 || strings.TrimSpace(path) == "" {
		return ""
	}
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()

	var lines []handoffLine
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for sc.Scan() {
		if ln := parseHandoffJSONLine(sc.Bytes()); ln.text != "" {
			lines = append(lines, ln)
		}
	}
	if len(lines) == 0 {
		return ""
	}
	if len(lines) > turns {
		lines = lines[len(lines)-turns:]
	}
	return formatHandoffLines(lines, maxChars)
}

func parseHandoffJSONLine(line []byte) handoffLine {
	var obj struct {
		Type    string `json:"type"`
		Message struct {
			Content any `json:"content"`
		} `json:"message"`
	}
	if json.Unmarshal(line, &obj) != nil {
		return handoffLine{}
	}
	switch obj.Type {
	case "user":
		text := extractHandoffText(obj.Message.Content, false)
		text = strings.TrimSpace(text)
		if text == "" || strings.HasPrefix(text, "!") {
			return handoffLine{}
		}
		return handoffLine{role: "使用者", text: text}
	case "assistant":
		text := strings.TrimSpace(extractHandoffText(obj.Message.Content, true))
		if text == "" {
			return handoffLine{}
		}
		return handoffLine{role: "你(上一帳號)", text: text}
	default:
		return handoffLine{}
	}
}

func extractHandoffText(content any, assistant bool) string {
	switch v := content.(type) {
	case string:
		return v
	case []any:
		var parts []string
		for _, item := range v {
			m, ok := item.(map[string]any)
			if !ok {
				continue
			}
			typ, _ := m["type"].(string)
			if typ != "text" {
				continue
			}
			txt, _ := m["text"].(string)
			if strings.TrimSpace(txt) != "" {
				parts = append(parts, txt)
			}
		}
		return strings.Join(parts, "\n")
	case map[string]any:
		if assistant {
			if typ, _ := v["type"].(string); typ != "" && typ != "text" {
				return ""
			}
		}
		txt, _ := v["text"].(string)
		return txt
	default:
		return ""
	}
}

func formatHandoffLines(lines []handoffLine, maxChars int) string {
	formatted := make([]string, 0, len(lines))
	for _, ln := range lines {
		text := strings.TrimSpace(ln.text)
		if text == "" {
			continue
		}
		formatted = append(formatted, ln.role+": "+text)
	}
	if len(formatted) == 0 {
		return ""
	}
	var kept []string
	total := 0
	for i := len(formatted) - 1; i >= 0; i-- {
		n := len([]rune(formatted[i]))
		if total > 0 {
			n++
		}
		if total+n > maxChars && len(kept) > 0 {
			break
		}
		kept = append(kept, formatted[i])
		total += n
		if total >= maxChars {
			break
		}
	}
	for i, j := 0, len(kept)-1; i < j; i, j = i+1, j-1 {
		kept[i], kept[j] = kept[j], kept[i]
	}
	out := strings.Join(kept, "\n")
	r := []rune(out)
	if len(r) > maxChars {
		out = string(r[len(r)-maxChars:])
	}
	return strings.TrimSpace(out)
}
