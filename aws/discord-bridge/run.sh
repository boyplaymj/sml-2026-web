#!/bin/bash
# 啟動包裝:從 AWS SSM 讀機密進環境變數(機密不落地、不進 repo),再 exec bridge。
set -euo pipefail
REGION="${AWS_REGION:-ap-southeast-1}"

get() { aws ssm get-parameter --name "$1" --with-decryption --region "$REGION" --query Parameter.Value --output text; }

export DISCORD_TOKEN="$(get /sml/discord-bot/token)"
# Do not force CLAUDE_CODE_OAUTH_TOKEN here.
# The bridge should use the interactive Claude Code login stored under
# HOME=/home/smlbot. A stale SSM OAuth token can override that login and fail
# with spend-limit/auth errors even after `sudo -u smlbot -H claude /login`.
export ALLOWED_CHANNELS="$(get /sml/discord-bridge/allowed-channels)"
export CHANNEL_WORKDIRS="$(get /sml/discord-bridge/channel-workdirs)"
# 選填:整個伺服器允許(設了之後該伺服器所有頻道、含新開的都自動生效)
export ALLOWED_GUILDS="$(aws ssm get-parameter --name /sml/discord-bridge/allowed-guilds --region "$REGION" --query Parameter.Value --output text 2>/dev/null || true)"

# bot↔bot 互通(測試):對方 AI bot = Codex(Neku_codex),僅限測試頻道 1522731838458822808。
# 非機密故直接帶預設值;要改頻道/停用改這裡即可。
export PEER_BOT_ID="${PEER_BOT_ID:-1522705533918773349}"
export DISCUSS_CHANNELS="${DISCUSS_CHANNELS:-1522731838458822808,1519443528831336629,1523844413821026455}"
export MAX_BOT_EXCHANGES="${MAX_BOT_EXCHANGES:-3}"
export BRIDGE_ADMIN_USERS="${BRIDGE_ADMIN_USERS:-662666377923919881,165872613757943808}"

exec /opt/sml/bridge
