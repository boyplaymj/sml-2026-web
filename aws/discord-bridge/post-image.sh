#!/bin/bash
# 把本機圖片(或任意檔案)上傳到指定 Discord 頻道。
# token 從 AWS SSM 讀(不落地)，沿用 bridge 同一顆 bot。
#
# 用法:
#   ./post-image.sh <channel_id> [可選訊息文字] <檔案1> [檔案2 ...]
# 例:
#   ./post-image.sh 1519538720066502657 "截圖如下" a.png b.png
set -euo pipefail
REGION="${AWS_REGION:-ap-southeast-1}"

CH="${1:?需要 channel_id}"; shift

# 第一個非檔案參數視為訊息文字(選填)
MSG=""
if [ $# -gt 0 ] && [ ! -f "$1" ]; then MSG="$1"; shift; fi

if [ $# -lt 1 ]; then echo "至少要一個檔案" >&2; exit 1; fi

TOKEN="$(aws ssm get-parameter --name /sml/discord-bot/token --with-decryption \
  --region "$REGION" --query Parameter.Value --output text)"

# 組 -F files[n]=@... 參數
ARGS=()
i=0
for f in "$@"; do
  [ -f "$f" ] || { echo "找不到檔案: $f" >&2; exit 1; }
  ARGS+=(-F "files[$i]=@${f}")
  i=$((i+1))
done

# payload_json 帶訊息文字(可空)
PAYLOAD=$(printf '{"content":%s}' "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$MSG")")

HTTP=$(curl -sS -w '%{http_code}' -o /tmp/discord_post_resp.json \
  -H "Authorization: Bot ${TOKEN}" \
  -F "payload_json=${PAYLOAD}" \
  "${ARGS[@]}" \
  "https://discord.com/api/v10/channels/${CH}/messages")

if [ "$HTTP" = "200" ] || [ "$HTTP" = "201" ]; then
  echo "✅ 已上傳 $i 個檔案到頻道 $CH (HTTP $HTTP)"
else
  echo "❌ 上傳失敗 HTTP $HTTP" >&2
  cat /tmp/discord_post_resp.json >&2; echo >&2
  exit 1
fi
