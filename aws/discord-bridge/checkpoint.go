package main

import (
	"log"
	"strings"
	"time"

	"github.com/bwmarrin/discordgo"
)

// ── 全自動釘選檢查點(channel checkpoint)──────────────────────────────
//
// 目的:切帳號 / 重啟 bridge 會清空所有頻道 session。jsonl handoff 只在「切帳號」
// 那一刻快照(見 handoff.go),對「純重啟」無效,而且逐字稿只在本機硬碟。
// 這裡再加一層「Discord 端持久」的保底:
//
//   產出(全自動):Claude 判斷一個段落結束時,在回覆裡夾一段
//        <<<CHECKPOINT>>> ... <<<END CHECKPOINT>>>
//     bridge 把它抽出來、從使用者看到的回覆中移除,然後在該頻道維持「唯一一則」
//     置頂檢查點訊息(有舊的就原地編輯、多餘的清掉)。
//
//   讀取(全自動):任何頻道開新 session(sid==""、且沒有 handoff 可注入)時,
//     bridge 抓該頻道置頂訊息,挑出 bot 自己發的檢查點,注入到第一個 prompt。
//
// 免疫額度滿(讀置頂不呼叫 LLM)、免疫切帳號、免疫重啟、免疫本機掉檔。

const checkpointPinPrefix = "📌CHECKPOINT"

// Claude 在回覆中夾帶檢查點內容的標記(用 <<< >>> 避免和按鈕語法 [[BTN:]] 撞)。
const (
	checkpointOpen  = "<<<CHECKPOINT>>>"
	checkpointClose = "<<<END CHECKPOINT>>>"
)

func checkpointEnabled() bool {
	return envBool("CHECKPOINT_ENABLED", true)
}

// 置頂檢查點訊息的字數上限(Discord 單訊息硬上限 2000,留餘裕給前綴)。
func checkpointMaxChars() int {
	return envInt("CHECKPOINT_MAXCHARS", 1800)
}

// extractCheckpointBlock 從 Claude 回覆中抽出檢查點內容,並回傳「移除該區塊後」
// 給使用者看的乾淨回覆。純函式,方便測試。
//   - content:標記之間的內容(已 Trim);沒有標記或內容空 → ""。
//   - cleaned:把整個標記區塊(含標記本身)拿掉後的回覆。
func extractCheckpointBlock(reply string) (content, cleaned string) {
	i := strings.Index(reply, checkpointOpen)
	if i < 0 {
		return "", reply
	}
	rest := reply[i+len(checkpointOpen):]
	j := strings.Index(rest, checkpointClose)
	if j < 0 {
		// 只有開標記、沒有收尾 → 視為不完整,不動回覆(避免把後半段訊息吞掉)。
		return "", reply
	}
	content = strings.TrimSpace(rest[:j])
	cleaned = strings.TrimSpace(reply[:i] + rest[j+len(checkpointClose):])
	return content, cleaned
}

// buildCheckpointMessage 組出要置頂的訊息本體(前綴 + 時間 + 內容,並夾字數上限)。
func buildCheckpointMessage(content string, now time.Time) string {
	body := strings.TrimSpace(content)
	max := checkpointMaxChars()
	if r := []rune(body); len(r) > max {
		body = strings.TrimSpace(string(r[:max]))
	}
	return checkpointPinPrefix + " · " + now.UTC().Format("2006-01-02 15:04 UTC") + "\n" + body
}

// isBotCheckpointPin 判斷一則置頂訊息是不是「本 bot 發的檢查點」——雙重過濾:
// 作者是自己 + 內容開頭是檢查點前綴,避免誤抓頻道裡其他的置頂訊息。
func isBotCheckpointPin(s *discordgo.Session, m *discordgo.Message) bool {
	if m == nil || m.Author == nil {
		return false
	}
	selfID := ""
	if s.State != nil && s.State.User != nil {
		selfID = s.State.User.ID
	}
	if selfID == "" || m.Author.ID != selfID {
		return false
	}
	return strings.HasPrefix(strings.TrimSpace(m.Content), checkpointPinPrefix)
}

// updatePinnedCheckpoint 是「產出端」。若回覆含檢查點區塊,就:
//  1. 把區塊從使用者可見回覆移除(回傳 cleaned)。
//  2. 在該頻道維持唯一一則置頂檢查點:有舊的就原地編輯並確保釘住、多餘的清掉;沒有就發新的並釘上。
//
// 全程 best-effort:任何 Discord API 失敗只 log,絕不影響正常回覆(照樣回傳 cleaned)。
func updatePinnedCheckpoint(s *discordgo.Session, channelID, reply string) string {
	if !checkpointEnabled() {
		return reply
	}
	content, cleaned := extractCheckpointBlock(reply)
	if content == "" {
		return reply // 沒有檢查點區塊 → 原封不動
	}

	body := buildCheckpointMessage(content, time.Now())

	pins, err := s.ChannelMessagesPinned(channelID)
	if err != nil {
		log.Printf("checkpoint list pins ch=%s: %v", channelID, err)
		pins = nil
	}

	// 收集本 bot 既有的檢查點置頂(可能因併發/歷史殘留不只一則)。
	var existing []*discordgo.Message
	for _, m := range pins {
		if isBotCheckpointPin(s, m) {
			existing = append(existing, m)
		}
	}

	if len(existing) == 0 {
		// 沒有既存 → 發新訊息並釘上。
		msg, err := s.ChannelMessageSend(channelID, body)
		if err != nil {
			log.Printf("checkpoint send ch=%s: %v", channelID, err)
			return cleaned
		}
		if err := s.ChannelMessagePin(channelID, msg.ID); err != nil {
			log.Printf("checkpoint pin ch=%s msg=%s: %v", channelID, msg.ID, err)
		} else {
			log.Printf("checkpoint created ch=%s msg=%s chars=%d", channelID, msg.ID, len([]rune(content)))
		}
		return cleaned
	}

	// 留最後一則(Discord pins 依時間新→舊排序,index 0 最新)當「現役」,原地編輯內容。
	keep := existing[0]
	if _, err := s.ChannelMessageEdit(channelID, keep.ID, body); err != nil {
		log.Printf("checkpoint edit ch=%s msg=%s: %v", channelID, keep.ID, err)
	} else {
		log.Printf("checkpoint updated ch=%s msg=%s chars=%d", channelID, keep.ID, len([]rune(content)))
	}
	// 保險:確保現役那則仍在置頂(理論上本來就是)。
	if err := s.ChannelMessagePin(channelID, keep.ID); err != nil {
		log.Printf("checkpoint re-pin ch=%s msg=%s: %v", channelID, keep.ID, err)
	}
	// 清掉多餘的舊檢查點(解除釘選 + 刪訊息),讓頻道只留一則。
	for _, m := range existing[1:] {
		if err := s.ChannelMessageUnpin(channelID, m.ID); err != nil {
			log.Printf("checkpoint unpin-old ch=%s msg=%s: %v", channelID, m.ID, err)
		}
		if err := s.ChannelMessageDelete(channelID, m.ID); err != nil {
			log.Printf("checkpoint delete-old ch=%s msg=%s: %v", channelID, m.ID, err)
		}
	}
	return cleaned
}

// injectPinnedCheckpoint 是「讀取端」。開新 session 時抓該頻道置頂,挑出本 bot 最新的
// 檢查點,注入 prompt。回傳 (新prompt, 是否有注入)。best-effort:失敗就回原 prompt。
func injectPinnedCheckpoint(s *discordgo.Session, channelID, prompt string) (string, bool) {
	if !checkpointEnabled() {
		return prompt, false
	}
	pins, err := s.ChannelMessagesPinned(channelID)
	if err != nil {
		log.Printf("checkpoint recall list ch=%s: %v", channelID, err)
		return prompt, false
	}
	for _, m := range pins { // pins 新→舊,取第一則本 bot 檢查點即最新
		if !isBotCheckpointPin(s, m) {
			continue
		}
		body := stripCheckpointHeader(m.Content)
		if body == "" {
			continue
		}
		log.Printf("checkpoint recall ch=%s msg=%s chars=%d", channelID, m.ID, len([]rune(body)))
		return "【本頻道的釘選檢查點(重啟/切帳號前的進度快照),請據此無縫接續,不要重新自我介紹;若與使用者新訊息無關可略過】\n" +
			body + "\n\n【使用者的新訊息】\n" + prompt, true
	}
	return prompt, false
}

// stripCheckpointHeader 去掉置頂訊息的「📌CHECKPOINT · 時間」標頭那一行,只留內容本體。
func stripCheckpointHeader(content string) string {
	c := strings.TrimSpace(content)
	if !strings.HasPrefix(c, checkpointPinPrefix) {
		return c
	}
	if nl := strings.IndexByte(c, '\n'); nl >= 0 {
		return strings.TrimSpace(c[nl+1:])
	}
	return "" // 只有標頭、沒有內容
}
