package main

import (
	"encoding/json"
	"net/http"
	"testing"
	"time"

	"github.com/bwmarrin/discordgo"
)

func TestReadLimitOAuthUtilizationIsAlreadyPercent(t *testing.T) {
	buckets := map[string]json.RawMessage{
		"five_hour": json.RawMessage(`{"utilization":8.5,"resets_at":1893456000}`),
	}

	got := readLimit(buckets, "five_hour")

	if got.pct != 8.5 {
		t.Fatalf("pct = %v, want 8.5", got.pct)
	}
	if got.reset != 1893456000 {
		t.Fatalf("reset = %v, want 1893456000", got.reset)
	}
}

func TestReadLimitUsedPercentage(t *testing.T) {
	buckets := map[string]json.RawMessage{
		"seven_day": json.RawMessage(`{"used_percentage":42,"reset":"2030-01-01T00:00:00Z"}`),
	}

	got := readLimit(buckets, "seven_day")

	if got.pct != 42 {
		t.Fatalf("pct = %v, want 42", got.pct)
	}
	if got.reset != 1893456000 {
		t.Fatalf("reset = %v, want 1893456000", got.reset)
	}
}

func TestHeaderLimitUtilizationIsFraction(t *testing.T) {
	h := http.Header{}
	h.Set("anthropic-ratelimit-unified-5h-utilization", "0.125")
	h.Set("anthropic-ratelimit-unified-5h-reset", "1893456000")

	got := headerLimit(h, "5h")

	if got.pct != 12.5 {
		t.Fatalf("pct = %v, want 12.5", got.pct)
	}
	if got.reset != 1893456000 {
		t.Fatalf("reset = %v, want 1893456000", got.reset)
	}
}

func TestLatestTextBlockFromMessagesFindsNewestTargetBlock(t *testing.T) {
	base := time.Unix(1893456000, 0)
	messages := []*discordgo.Message{
		{ID: "4", Author: &discordgo.User{ID: "human"}, Content: "/read request:看這段", Timestamp: base.Add(4 * time.Second)},
		{ID: "3", Author: &discordgo.User{ID: "claude"}, Content: "第二段", Timestamp: base.Add(3 * time.Second)},
		{ID: "2", Author: &discordgo.User{ID: "claude"}, Content: "第一段", Timestamp: base.Add(2 * time.Second)},
		{ID: "1", Author: &discordgo.User{ID: "human"}, Content: "前一輪", Timestamp: base.Add(1 * time.Second)},
	}

	got, block := latestTextBlockFromMessages(messages, "claude")

	if got != "第一段\n\n第二段" {
		t.Fatalf("text = %q, want joined newest target block", got)
	}
	if len(block) != 2 || block[0].ID != "2" || block[1].ID != "3" {
		t.Fatalf("block ids = %#v, want [2 3]", block)
	}
}

func TestLatestTextBlockFromMessagesStopsAtOtherAuthor(t *testing.T) {
	base := time.Unix(1893456000, 0)
	messages := []*discordgo.Message{
		{ID: "4", Author: &discordgo.User{ID: "claude"}, Content: "最新", Timestamp: base.Add(4 * time.Second)},
		{ID: "3", Author: &discordgo.User{ID: "human"}, Content: "插話", Timestamp: base.Add(3 * time.Second)},
		{ID: "2", Author: &discordgo.User{ID: "claude"}, Content: "舊訊息", Timestamp: base.Add(2 * time.Second)},
	}

	got, block := latestTextBlockFromMessages(messages, "claude")

	if got != "最新" {
		t.Fatalf("text = %q, want latest only", got)
	}
	if len(block) != 1 || block[0].ID != "4" {
		t.Fatalf("block ids = %#v, want [4]", block)
	}
}

func TestDisableChoiceButtonsDisablesChoicesButKeepsForward(t *testing.T) {
	msg := &discordgo.Message{
		Components: []discordgo.MessageComponent{
			discordgo.ActionsRow{Components: []discordgo.MessageComponent{
				discordgo.Button{Label: "A", CustomID: "choice:a", Style: discordgo.PrimaryButton},
				discordgo.Button{Label: "B", CustomID: "choice:b", Style: discordgo.PrimaryButton},
			}},
			discordgo.ActionsRow{Components: []discordgo.MessageComponent{
				discordgo.Button{Label: "轉傳", CustomID: "fwd:peer", Style: discordgo.SecondaryButton},
			}},
		},
	}

	rows := disableChoiceButtons(msg, "choice:b")

	if len(rows) != 2 {
		t.Fatalf("rows len = %d, want 2", len(rows))
	}
	choiceRow := rows[0].(discordgo.ActionsRow)
	a := choiceRow.Components[0].(discordgo.Button)
	b := choiceRow.Components[1].(discordgo.Button)
	if !a.Disabled || !b.Disabled {
		t.Fatalf("choice buttons should be disabled: a=%v b=%v", a.Disabled, b.Disabled)
	}
	if b.Style != discordgo.SuccessButton {
		t.Fatalf("clicked button style = %v, want SuccessButton", b.Style)
	}
	fwdRow := rows[1].(discordgo.ActionsRow)
	fwd := fwdRow.Components[0].(discordgo.Button)
	if fwd.Disabled {
		t.Fatal("fwd:peer button should remain enabled")
	}
}
