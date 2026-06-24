#!/bin/bash
# 啟動包裝:從 AWS SSM 讀機密進環境變數(機密不落地、不進 repo),再 exec bridge。
set -euo pipefail
REGION="${AWS_REGION:-ap-southeast-1}"

get() { aws ssm get-parameter --name "$1" --with-decryption --region "$REGION" --query Parameter.Value --output text; }

export DISCORD_TOKEN="$(get /sml/discord-bot/token)"
export CLAUDE_CODE_OAUTH_TOKEN="$(get /sml/claude/oauth-token)"
export ALLOWED_CHANNELS="$(get /sml/discord-bridge/allowed-channels)"
export CHANNEL_WORKDIRS="$(get /sml/discord-bridge/channel-workdirs)"
# 選填:整個伺服器允許(設了之後該伺服器所有頻道、含新開的都自動生效)
export ALLOWED_GUILDS="$(aws ssm get-parameter --name /sml/discord-bridge/allowed-guilds --region "$REGION" --query Parameter.Value --output text 2>/dev/null || true)"

exec /opt/sml/bridge
