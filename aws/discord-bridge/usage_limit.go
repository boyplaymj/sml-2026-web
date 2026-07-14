package main

// 把 claude -p 因「用量/認證/額度」被擋而失敗的原始輸出,翻譯成看得懂的中文原因。
// 原本 runClaude 只會回「⚠️ 執行出錯：<stderr 首行>」或直接吐原始 result,
// 使用者撞到用量上限時只看到看不懂的字串(如 "usage limit reached|1752600000")。

import (
	"strconv"
	"strings"
	"time"
)

// classifyBlock 從 claude 的輸出(result 或 stderr)判斷是否為「做不了事」的已知阻擋原因。
// 回傳空字串表示不是已知阻擋(交回原本的錯誤處理)。
// 比對字串取自 claude 官方辨識清單(binary 內建 regex)。
func classifyBlock(text string) string {
	lt := strings.ToLower(text)
	switch {
	case strings.Contains(lt, "usage limit reached"):
		return "usage"
	case strings.Contains(lt, "credit balance") && strings.Contains(lt, "too low"):
		return "credit"
	case strings.Contains(lt, "please run /login"),
		strings.Contains(lt, "invalid api key"),
		strings.Contains(lt, "authentication failed"),
		strings.Contains(lt, "oauth token expired"),
		strings.Contains(lt, "oauth token revoked"),
		strings.Contains(lt, "401 unauthorized"),
		strings.Contains(lt, "bad credentials"):
		return "auth"
	case strings.Contains(lt, "overloaded"), strings.Contains(lt, "\"529\""), strings.Contains(lt, " 529"):
		return "overloaded"
	}
	return ""
}

// detectUsageLimitReset 從用量上限訊息擷取重置 unix 時間戳。
// claude 常見格式:"Claude AI usage limit reached|1752600000"(管道後面是重置秒數)。
// 沒有就回 0。
func detectUsageLimitReset(text string) int64 {
	if i := strings.LastIndex(text, "|"); i >= 0 && i+1 < len(text) {
		if ts, err := strconv.ParseInt(strings.TrimSpace(text[i+1:]), 10, 64); err == nil && ts > 1_000_000_000 {
			return ts
		}
	}
	return 0
}

// fmtResetTime 把 unix 秒格式化成台灣時間字串;0 回空字串。
func fmtResetTime(ts int64) string {
	if ts <= 0 {
		return ""
	}
	return time.Unix(ts, 0).In(cstZone).Format("01/02 15:04")
}

// usageLimitDetail 查一次用量,判斷是「5 小時階段」還是「每週」上限滿了,並取重置時間。
// resetHint 是從訊息擷取到的重置戳(可能為 0);查不到用量時就靠它。
// 純資訊查詢(GET /api/oauth/usage,不燒 LLM token)。回傳:窗口說明、重置戳。
func usageLimitDetail(resetHint int64) (window string, reset int64) {
	reset = resetHint
	snap, ok := fetchUsageFromOAuth(claudeUsageToken())
	if !ok {
		return "", reset
	}
	// 已滿門檻抓 95%,同時滿則以每週為主(較嚴重、恢復較慢)。
	switch {
	case snap.weekAll.pct >= 95:
		window = "每週用量(7 天)"
		if reset == 0 {
			reset = snap.weekAll.reset
		}
	case snap.session.pct >= 95:
		window = "5 小時階段用量"
		if reset == 0 {
			reset = snap.session.reset
		}
	default:
		// 兩窗都沒到 95% 卻仍被擋:挑百分比較高者當提示,重置取對應窗。
		if snap.weekAll.pct >= snap.session.pct && snap.weekAll.pct >= 0 {
			if reset == 0 {
				reset = snap.weekAll.reset
			}
		} else if snap.session.pct >= 0 && reset == 0 {
			reset = snap.session.reset
		}
	}
	return window, reset
}

// blockMessage 依阻擋種類產生給使用者看的中文說明。kind 空字串回空字串。
func blockMessage(kind, raw string) string {
	switch kind {
	case "usage":
		window, reset := usageLimitDetail(detectUsageLimitReset(raw))
		var b strings.Builder
		b.WriteString("🚫 這個 Claude 帳號的用量已達上限,暫時無法處理。")
		if window != "" {
			b.WriteString("\n• 卡在:**" + window + "** 已用滿")
		}
		if r := fmtResetTime(reset); r != "" {
			b.WriteString("\n• 約於 **" + r + "**(台灣時間)恢復")
		}
		b.WriteString("\n可用 `!切帳號 backup1` 切到備用帳號繼續,或等額度重置後再試。")
		return b.String()
	case "credit":
		return "🚫 這個 Claude 帳號的額度餘額不足(credit balance too low),無法處理。請儲值,或用 `!切帳號` 換到有額度的帳號。"
	case "auth":
		return "🔑 Claude 認證失效(需重新登入或 token 已過期/被撤),無法處理。請重新登入該帳號,或用 `!切帳號` 換到有效帳號。"
	case "overloaded":
		return "⏳ Claude 伺服器暫時過載(overloaded),不是你的問題。請稍等一下再重試同一句話即可。"
	}
	return ""
}
