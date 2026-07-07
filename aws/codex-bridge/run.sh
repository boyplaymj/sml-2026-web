#!/bin/bash
# 啟動包裝(codex 版):從 AWS SSM 讀機密進環境變數(不落地、不進 repo),再 exec codex-bridge。
#
# 與 claude 版的差異:
#  - 後端是 codex CLI(裝在 nvm node22,與系統 node18 隔離)→ 這裡把 node22 的 bin 掛進 PATH。
#  - Codex 認證走 `codex login`(存 ~/.codex),所以不需要 CODEX_API_KEY。
#  - 用獨立的 SSM 參數 /sml/codex-bridge/*;頻道/伺服器若沒單獨設,回退沿用 claude 版的白名單(同頻道)。
set -euo pipefail
REGION="${AWS_REGION:-ap-southeast-1}"

# nvm node22 的 bin(codex 就在這裡);掛進 PATH 供 bridge 內 exec codex 用。
NODE22_BIN="/home/smlbot/.nvm/versions/node/v22.23.1/bin"
export PATH="$NODE22_BIN:$PATH"
export CODEX_BIN="$NODE22_BIN/codex"

get()    { aws ssm get-parameter --name "$1" --with-decryption --region "$REGION" --query Parameter.Value --output text; }
getopt() { aws ssm get-parameter --name "$1" --with-decryption --region "$REGION" --query Parameter.Value --output text 2>/dev/null || true; }

# 必填:codex 專屬的 Discord bot token(gameboy 提供後存進此參數)。
export DISCORD_TOKEN="$(get /sml/codex-bridge/token)"

# 頻道/伺服器白名單:優先用 codex 專屬參數,沒設就回退沿用 claude 版(達成「同頻道」)。
export ALLOWED_CHANNELS="$(getopt /sml/codex-bridge/allowed-channels)"
[ -z "$ALLOWED_CHANNELS" ] && export ALLOWED_CHANNELS="$(getopt /sml/discord-bridge/allowed-channels)"
export ALLOWED_GUILDS="$(getopt /sml/codex-bridge/allowed-guilds)"
[ -z "$ALLOWED_GUILDS" ] && export ALLOWED_GUILDS="$(getopt /sml/discord-bridge/allowed-guilds)"
export CHANNEL_WORKDIRS="$(getopt /sml/codex-bridge/channel-workdirs)"

# 選填:指定 codex 模型(空 = 用 ~/.codex/config.toml 的預設)。
export CODEX_MODEL="$(getopt /sml/codex-bridge/model)"

# bot↔bot 互通(測試):對方 AI bot = SML_Claude,僅限測試頻道 1522731838458822808。
# 非機密故直接帶預設值;要改頻道/停用改這裡即可。
# DISCUSS_CHANNELS 只是「runtime JSON 讀不到時的 startup fallback」→ 只留測試頻道(修 review #4)。
# 正式頻道一律走 runtime JSON(/mnt/sml-brain/_runtime/bot-interop-channels.json、!白名單 管理),
# 這樣 mount 掛掉/JSON 壞掉時,bot↔bot 只會退回測試頻道,不會在正式頻道自動開。
export PEER_BOT_ID="${PEER_BOT_ID:-1519422799238664415}"
export PEER_BOT_NAME="${PEER_BOT_NAME:-Claude}"
export DISCUSS_CHANNELS="${DISCUSS_CHANNELS:-1522731838458822808}"
export MAX_BOT_EXCHANGES="${MAX_BOT_EXCHANGES:-3}"
export BRIDGE_ADMIN_USERS="${BRIDGE_ADMIN_USERS:-662666377923919881,165872613757943808}"

# /read:按需讀取指定 bot 在目前頻道最近一段文字。預設讀 SML_Claude。
export READ_TARGET_BOT_ID="${READ_TARGET_BOT_ID:-$PEER_BOT_ID}"
export READ_FETCH_LIMIT="${READ_FETCH_LIMIT:-50}"

exec /opt/sml/codex-bridge
