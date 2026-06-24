#!/bin/bash
# 啟動包裝:從 AWS SSM 讀機密進環境變數(機密不落地、不進 repo),再 exec bridge。
set -euo pipefail
REGION="${AWS_REGION:-ap-southeast-1}"

get() { aws ssm get-parameter --name "$1" --with-decryption --region "$REGION" --query Parameter.Value --output text; }

export DISCORD_TOKEN="$(get /sml/discord-bot/token)"
export CLAUDE_CODE_OAUTH_TOKEN="$(get /sml/claude/oauth-token)"
export ALLOWED_CHANNELS="$(get /sml/discord-bridge/allowed-channels)"
export CHANNEL_WORKDIRS="$(get /sml/discord-bridge/channel-workdirs)"

exec /opt/sml/bridge
