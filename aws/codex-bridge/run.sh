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

exec /opt/sml/codex-bridge
