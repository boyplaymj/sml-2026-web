package main

import (
	"bytes"
	"context"
	"encoding/json"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

func handoffL1Enabled() bool {
	return handoffEnabled() && envBool("HANDOFF_L1_CODEX", true)
}

func startHandoffWorker() {
	if !handoffL1Enabled() {
		log.Printf("handoff worker disabled")
		return
	}
	go handoffWorkerLoop()
}

func handoffWorkerLoop() {
	interval := time.Duration(envInt("HANDOFF_L1_INTERVAL_SEC", 20)) * time.Second
	if interval < 5*time.Second {
		interval = 5 * time.Second
	}
	processHandoffQueue()
	t := time.NewTicker(interval)
	defer t.Stop()
	for range t.C {
		processHandoffQueue()
	}
}

func processHandoffQueue() {
	matches, err := filepath.Glob(filepath.Join(handoffDir(), "*.json"))
	if err != nil {
		log.Printf("handoff worker glob: %v", err)
		return
	}
	for _, path := range matches {
		processHandoffFile(path)
	}
}

func processHandoffFile(path string) {
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	var rec handoffRecord
	if err := json.Unmarshal(data, &rec); err != nil {
		_ = os.Remove(path)
		log.Printf("handoff worker invalid %s: %v", path, err)
		return
	}
	if rec.CreatedAt.IsZero() || time.Since(rec.CreatedAt) > handoffTTL {
		_ = os.Remove(path)
		log.Printf("handoff worker expired %s", path)
		return
	}
	if rec.Note != nil {
		return
	}
	raw := tailFromJSONLWithLimits(rec.JSONL, envInt("HANDOFF_L1_TAIL_TURNS", 24), envInt("HANDOFF_L1_TAIL_MAXCHARS", 12000))
	if strings.TrimSpace(raw) == "" {
		return
	}
	note, err := summarizeHandoff(raw)
	if err != nil {
		log.Printf("handoff worker summarize ch=%s sid=%s: %v", rec.Channel, rec.SID, err)
		return
	}
	note = truncateHandoffNote(strings.TrimSpace(note), 200)
	if note == "" {
		return
	}
	fresh, ok := readHandoffFile(path)
	if !ok || fresh.Note != nil {
		return
	}
	fresh.Note = &note
	if err := atomicWriteJSON(path, fresh); err != nil {
		log.Printf("handoff worker write ch=%s sid=%s: %v", rec.Channel, rec.SID, err)
		return
	}
	log.Printf("handoff worker noted ch=%s sid=%s chars=%d", rec.Channel, rec.SID, len([]rune(note)))
}

func readHandoffFile(path string) (handoffRecord, bool) {
	if _, err := os.Stat(path); err != nil {
		return handoffRecord{}, false
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return handoffRecord{}, false
	}
	var rec handoffRecord
	if json.Unmarshal(data, &rec) != nil {
		return handoffRecord{}, false
	}
	return rec, true
}

func summarizeHandoff(raw string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(envInt("HANDOFF_L1_TIMEOUT_MIN", 10))*time.Minute)
	defer cancel()

	tmp, err := os.CreateTemp("", "handoff-note-*.txt")
	if err != nil {
		return "", err
	}
	outFile := tmp.Name()
	tmp.Close()
	defer os.Remove(outFile)

	prompt := "把以下 Discord 頻道對話壓成 ≤200 字的交接便條,給「接手同一個頻道、但失憶了的你自己」看。只保留:當前在做什麼、已決定/待辦、關鍵 ID 或檔名。用第二人稱、條列、繁中。\n\n" + raw
	args := []string{"exec", "--json", "--dangerously-bypass-approvals-and-sandbox", "-o", outFile}
	if codexModel != "" {
		args = append(args, "-m", codexModel)
	}
	args = append(args, "-")

	cmd := exec.CommandContext(ctx, codexBin, args...)
	cmd.Dir = workdir
	cmd.Stdin = strings.NewReader(prompt)
	nodeBin := filepath.Dir(codexBin)
	cmd.Env = append(os.Environ(), "PATH="+nodeBin+":"+os.Getenv("PATH"))
	var out, errb bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &errb
	if err := cmd.Run(); err != nil {
		msg := codexErrorMsg(out.Bytes())
		if msg == "" {
			msg = firstLine(errb.String())
		}
		return "", errWithMsg(err, msg)
	}
	reply, err := os.ReadFile(outFile)
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(reply)), nil
}

type handoffWorkerError struct {
	err error
	msg string
}

func errWithMsg(err error, msg string) error {
	return handoffWorkerError{err: err, msg: msg}
}

func (e handoffWorkerError) Error() string {
	if e.msg == "" {
		return e.err.Error()
	}
	return e.err.Error() + ": " + e.msg
}

func truncateHandoffNote(s string, max int) string {
	if max <= 0 {
		return ""
	}
	r := []rune(strings.TrimSpace(s))
	if len(r) <= max {
		return string(r)
	}
	return strings.TrimSpace(string(r[:max]))
}
