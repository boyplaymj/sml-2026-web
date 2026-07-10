package main

// bot↔bot 互通白名單:runtime 可重載設定(免重啟)。
//
// 存於共享 mount /mnt/sml-brain/_runtime/bot-interop-channels.json,兩邊 bridge 讀同一份
// (單一真相源)。格式:
//   {"version":1,"updated_at":"...","channels":{"<id>":{"name":"..","bot_to_bot":true,"note":".."}}}
//
// 讀取用 mtime cache:每則訊息只 stat 一次,mtime 沒變就用快取,免每則重讀重解析。
// JSON 不存在/壞掉 → 退回 env 的 discussChannels(startup 值),確保 mount 掛掉也不炸。
// !白名單 指令用 embed + 按鈕即時切換,寫回 JSON → 下次讀立即生效,不必重啟。

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/bwmarrin/discordgo"
)

type interopChannel struct {
	Name     string `json:"name"`
	BotToBot bool   `json:"bot_to_bot"`
	Note     string `json:"note,omitempty"`
}

type interopConfig struct {
	Version   int                       `json:"version"`
	UpdatedAt string                    `json:"updated_at"`
	Channels  map[string]interopChannel `json:"channels"`
}

func interopPath() string {
	if p := os.Getenv("BOT_INTEROP_PATH"); p != "" {
		return p
	}
	return "/mnt/sml-brain/_runtime/bot-interop-channels.json"
}

var (
	interopMu     sync.Mutex
	interopMtime  time.Time
	interopCache  map[string]bool // channelID -> bot_to_bot=true
	interopLoaded bool
)

// botToBotSet 回傳目前啟用 bot↔bot 的頻道集合(mtime cache)。
// 讀不到 JSON 時退回 env 的 discussChannels,確保 mount 掛掉仍可運作。
func botToBotSet() map[string]bool {
	interopMu.Lock()
	defer interopMu.Unlock()
	fi, err := os.Stat(interopPath())
	if err != nil {
		if interopLoaded {
			return interopCache
		}
		return discussChannels
	}
	if interopLoaded && fi.ModTime().Equal(interopMtime) {
		return interopCache
	}
	cfg, err := readInterop()
	if err != nil {
		if interopLoaded {
			return interopCache
		}
		return discussChannels
	}
	set := map[string]bool{}
	for id, c := range cfg.Channels {
		if c.BotToBot {
			set[id] = true
		}
	}
	interopCache = set
	interopMtime = fi.ModTime()
	interopLoaded = true
	return set
}

func readInterop() (interopConfig, error) {
	var cfg interopConfig
	data, err := os.ReadFile(interopPath())
	if err != nil {
		return cfg, err
	}
	if err := json.Unmarshal(data, &cfg); err != nil {
		return cfg, err
	}
	if cfg.Channels == nil {
		cfg.Channels = map[string]interopChannel{}
	}
	return cfg, nil
}

// writeInterop 原子寫入(temp + rename),並讓下次 botToBotSet 強制重讀。
func writeInterop(cfg interopConfig) error {
	cfg.Version = 1
	cfg.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	p := interopPath()
	if dir := filepath.Dir(p); dir != "" {
		os.MkdirAll(dir, 0o755)
	}
	tmp := p + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	if err := os.Rename(tmp, p); err != nil {
		return err
	}
	interopMu.Lock()
	interopLoaded = false // 強制下次重讀
	interopMu.Unlock()
	return nil
}

// interopLockPath 跨 process 鎖檔路徑。兩個 bridge 同機共存,對「本機」檔案上 flock 即可可靠序列化;
// 刻意不對共享 mount(s3fs)上的 JSON 本身 flock —— 那類 FUSE mount 不保證支援 POSIX 鎖。
func interopLockPath() string {
	if p := os.Getenv("BOT_INTEROP_LOCK"); p != "" {
		return p
	}
	return filepath.Join(os.TempDir(), "sml-bot-interop.lock")
}

// withInteropLock 取得跨 process 排他鎖後執行 fn。拿不到鎖(檔案系統不支援等)時退化為直接執行,
// 至少不比原本無鎖差,並記一筆 log 供事後追。
func withInteropLock(fn func() error) error {
	f, err := os.OpenFile(interopLockPath(), os.O_CREATE|os.O_RDWR, 0o644)
	if err != nil {
		log.Printf("interop lock 開檔失敗(%v);以無鎖模式繼續", err)
		return fn()
	}
	defer f.Close()
	if err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX); err != nil {
		log.Printf("interop flock 失敗(%v);以無鎖模式繼續", err)
		return fn()
	}
	defer syscall.Flock(int(f.Fd()), syscall.LOCK_UN)
	return fn()
}

// mutateInterop 在跨 process 鎖內做「讀→改→原子寫」,是所有白名單寫入的唯一入口。
// 關鍵(修 review #2):readInterop 只有在檔案「不存在」時才當空設定;其他錯誤(JSON 壞掉、
// 權限、mount I/O)一律往上拋、不覆蓋整份白名單,避免把好好的設定洗成空。
// 鎖內重讀(修 review #3):兩顆 bridge 併發改也不會 lost update。
func mutateInterop(apply func(cfg *interopConfig)) error {
	return withInteropLock(func() error {
		cfg, err := readInterop()
		if err != nil {
			if !os.IsNotExist(err) {
				return err
			}
			cfg = interopConfig{Channels: map[string]interopChannel{}}
		}
		if cfg.Channels == nil {
			cfg.Channels = map[string]interopChannel{}
		}
		apply(&cfg)
		return writeInterop(cfg)
	})
}

// toggleInterop 切換某頻道的 bot_to_bot,回傳新狀態。
func toggleInterop(channelID, name string) (bool, error) {
	var newState bool
	err := mutateInterop(func(cfg *interopConfig) {
		c := cfg.Channels[channelID]
		c.BotToBot = !c.BotToBot
		if name != "" {
			c.Name = name
		}
		cfg.Channels[channelID] = c
		newState = c.BotToBot
	})
	if err != nil {
		return false, err
	}
	return newState, nil
}

// isBridgeAdmin 判斷是否為可管理白名單的管理員。
// 優先看 BRIDGE_ADMIN_USERS;未設則退回 ALLOWED_USERS;兩者皆未設則 fail-closed(拒絕)。
func isBridgeAdmin(userID string) bool {
	if admins := csvSet(os.Getenv("BRIDGE_ADMIN_USERS")); len(admins) > 0 {
		return admins[userID]
	}
	if len(allowedUsers) > 0 {
		return allowedUsers[userID]
	}
	// 縱深防禦:兩份名單都沒設時 fail-closed,避免任何人都能改 bot↔bot 白名單。
	// 正式環境 run.sh 一律注入 BRIDGE_ADMIN_USERS,故此分支僅在設定缺漏時生效。
	return false
}

// buildWhitelistMessage 組出 !白名單 的 embed + toggle 按鈕(當前 guild 的文字頻道)。
func buildWhitelistMessage(s *discordgo.Session, guildID string) *discordgo.MessageSend {
	set := botToBotSet()
	var chans []*discordgo.Channel
	if g, err := s.State.Guild(guildID); err == nil && len(g.Channels) > 0 {
		chans = g.Channels
	} else {
		chans, _ = s.GuildChannels(guildID)
	}
	var enabled []*discordgo.Channel
	textCount := 0
	for _, c := range chans {
		if c.Type != discordgo.ChannelTypeGuildText {
			continue
		}
		textCount++
		if set[c.ID] {
			enabled = append(enabled, c)
		}
	}
	sort.Slice(enabled, func(i, j int) bool { return enabled[i].Position < enabled[j].Position })

	var desc strings.Builder
	if len(enabled) == 0 {
		desc.WriteString("(目前沒有任何頻道開啟 bot↔bot 互@)\n")
	} else {
		for _, c := range enabled {
			fmt.Fprintf(&desc, "✅ <#%s>\n", c.ID)
		}
	}
	fmt.Fprintf(&desc, "\n共 %d/%d 個文字頻道開啟。", len(enabled), textCount)

	// 兩個原生頻道下拉:開啟 / 關閉。版面固定,頻道再多也不爆。
	minV := 1
	newSelect := func(id, placeholder string) discordgo.ActionsRow {
		return discordgo.ActionsRow{Components: []discordgo.MessageComponent{
			discordgo.SelectMenu{
				MenuType:     discordgo.ChannelSelectMenu,
				CustomID:     id,
				Placeholder:  placeholder,
				ChannelTypes: []discordgo.ChannelType{discordgo.ChannelTypeGuildText},
				MinValues:    &minV,
				MaxValues:    25,
			},
		}}
	}
	rows := []discordgo.MessageComponent{
		newSelect("b2b:enable", "✅ 選頻道 → 開啟 bot↔bot 互@"),
		newSelect("b2b:disable", "⬜ 選頻道 → 關閉 bot↔bot 互@"),
	}
	emb := &discordgo.MessageEmbed{
		Title:       "🤝 bot↔bot 互@ 白名單",
		Description: desc.String(),
		Color:       0xf9a8d4,
		Footer:      &discordgo.MessageEmbedFooter{Text: "用下方選單挑頻道即時開/關(免重啟)。上方列出目前已開啟的。"},
	}
	return &discordgo.MessageSend{Embeds: []*discordgo.MessageEmbed{emb}, Components: rows}
}

// handleWhitelistCommand 處理 !白名單:列出當前 guild 頻道 + 目前 bot↔bot 狀態 + toggle 按鈕。
func handleWhitelistCommand(s *discordgo.Session, m *discordgo.MessageCreate) {
	if m.GuildID == "" {
		s.ChannelMessageSend(m.ChannelID, "此指令需在伺服器頻道使用。")
		return
	}
	if !isBridgeAdmin(m.Author.ID) {
		s.ChannelMessageSend(m.ChannelID, "⛔ 只有管理員能檢視/管理 bot↔bot 白名單。")
		return
	}
	msg := buildWhitelistMessage(s, m.GuildID)
	if _, err := s.ChannelMessageSendComplex(m.ChannelID, msg); err != nil {
		log.Printf("!白名單 send error: %v", err)
	}
}

func ephemeralResp(msg string) *discordgo.InteractionResponse {
	return &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseChannelMessageWithSource,
		Data: &discordgo.InteractionResponseData{Content: msg, Flags: discordgo.MessageFlagsEphemeral},
	}
}

// peerName 對方 bot 的顯示名(discord-bridge 預設 Codex;codex-bridge 用 PEER_BOT_NAME=Claude)。
func peerName() string {
	return env("PEER_BOT_NAME", "Codex")
}

// forwardButtonRow 若該頻道已開 bot↔bot 且有設 peer,回傳「➡️ 轉傳給對方」按鈕列;否則 nil。
// 掛在每則 bot 回覆底部,讓使用者一鍵把這則轉給另一隻 bot。
func forwardButtonRow(channelID string) []discordgo.MessageComponent {
	if peerBotID == "" || !botToBotSet()[channelID] {
		return nil
	}
	return []discordgo.MessageComponent{
		discordgo.ActionsRow{Components: []discordgo.MessageComponent{
			discordgo.Button{
				Label:    "➡️ 轉傳給 " + peerName(),
				Style:    discordgo.SecondaryButton,
				CustomID: "fwd:peer",
			},
		}},
	}
}

// 回覆全文緩衝:分段送出時,按鈕掛在「最後一段」,但轉傳要抓「整段回覆」。
// 送出時把整段 clean text 以「掛按鈕那則的 messageID」為 key 存起來,handleForward 再回查。
// 有界(replyBufMax),FIFO 淘汰,避免無限長大。
var (
	replyBufMu    sync.Mutex
	replyBuf      = map[string]string{}
	replyBufOrder []string
)

const replyBufMax = 300

func rememberReply(msgID, full string) {
	if msgID == "" || strings.TrimSpace(full) == "" {
		return
	}
	replyBufMu.Lock()
	defer replyBufMu.Unlock()
	if _, ok := replyBuf[msgID]; !ok {
		replyBufOrder = append(replyBufOrder, msgID)
		for len(replyBufOrder) > replyBufMax {
			delete(replyBuf, replyBufOrder[0])
			replyBufOrder = replyBufOrder[1:]
		}
	}
	replyBuf[msgID] = full
}

func recallReply(msgID string) string {
	replyBufMu.Lock()
	defer replyBufMu.Unlock()
	return replyBuf[msgID]
}

// truncateRunes 以「字元」截斷(不切壞多位元組 CJK);Discord 單則上限約 2000 字元。
func truncateRunes(s string, max int) string {
	r := []rune(s)
	if len(r) <= max {
		return s
	}
	return string(r[:max]) + "…（內容過長已截斷）"
}

// handleForward 處理「轉傳給對方」按鈕:把整段回覆(非只按鈕那則)重貼成 @對方bot 的訊息 → 對方讀並回覆。
func handleForward(s *discordgo.Session, i *discordgo.InteractionCreate) {
	content := ""
	if i.Message != nil {
		// 優先取「整段回覆」;查不到才退回單則內容(舊訊息/非分段)。
		if full := recallReply(i.Message.ID); full != "" {
			content = full
		} else {
			content = i.Message.Content
		}
	}
	if strings.TrimSpace(content) == "" {
		s.InteractionRespond(i.Interaction, ephemeralResp("這則沒有可轉傳的文字內容。"))
		return
	}
	if peerBotID == "" {
		s.InteractionRespond(i.Interaction, ephemeralResp("未設定對方 bot,無法轉傳。"))
		return
	}
	// ACK,不改動原訊息(按鈕保留,可再次轉傳)。
	s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseDeferredMessageUpdate,
	})
	who := "有人"
	if i.Member != nil && i.Member.User != nil {
		who = i.Member.User.Username
	}
	// 人為轉傳=人為介入:重置本頻道 bot↔bot 計數,讓接力不會馬上撞上限。
	botExchMu.Lock()
	botExchange[i.ChannelID] = 0
	botExchMu.Unlock()
	fwd := truncateRunes(fmt.Sprintf("<@%s>\n(📨 %s 轉傳給你,請閱讀並回覆)\n%s", peerBotID, who, content), 1990)
	if _, err := s.ChannelMessageSend(i.ChannelID, fwd); err != nil {
		log.Printf("forward send error: %v", err)
	}
	log.Printf("FORWARD ch=%s by=%s len=%d", i.ChannelID, who, len(content))
}

// handleWhitelistSelect 處理 b2b:enable / b2b:disable 下拉:把選中的頻道批次設為開/關,重繪訊息。即時生效、免重啟。
func handleWhitelistSelect(s *discordgo.Session, i *discordgo.InteractionCreate, customID string) {
	uid := ""
	if i.Member != nil && i.Member.User != nil {
		uid = i.Member.User.ID
	}
	if !isBridgeAdmin(uid) {
		s.InteractionRespond(i.Interaction, ephemeralResp("⛔ 只有管理員能切換 bot↔bot 白名單。"))
		return
	}
	state := customID == "b2b:enable"
	values := i.MessageComponentData().Values
	if len(values) > 0 {
		err := mutateInterop(func(cfg *interopConfig) {
			for _, chID := range values {
				c := cfg.Channels[chID]
				c.BotToBot = state
				if ch, err := s.State.Channel(chID); err == nil && ch.Name != "" {
					c.Name = ch.Name
				}
				cfg.Channels[chID] = c
			}
		})
		if err != nil {
			log.Printf("b2b select write error: %v", err)
			s.InteractionRespond(i.Interaction, ephemeralResp("⚠️ 寫入失敗:"+err.Error()))
			return
		}
		log.Printf("B2B SELECT %s -> %v by %s", strings.Join(values, ","), state, uid)
	}
	msg := buildWhitelistMessage(s, i.GuildID)
	s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseUpdateMessage,
		Data: &discordgo.InteractionResponseData{Embeds: msg.Embeds, Components: msg.Components},
	})
}
