#!/bin/bash
# 新增 Discord 頻道到 ALLOWED_CHANNELS，並重啟 bridge 服務。
# 用法: ./add-channel.sh <channel_id> [備註名稱]
set -euo pipefail

REGION="${AWS_REGION:-ap-southeast-1}"
SSM_CHANNELS="/sml/discord-bridge/allowed-channels"
SERVICE="sml-discord-bridge"

if [[ $# -lt 1 ]]; then
  echo "用法: $0 <channel_id> [備註名稱]"
  echo "範例: $0 1234567890123456789 sml-視覺辨識系統"
  exit 1
fi

CHANNEL_ID="$1"
NOTE="${2:-}"

# 驗證格式(Discord ID 為純數字)
if ! [[ "$CHANNEL_ID" =~ ^[0-9]+$ ]]; then
  echo "錯誤: channel_id 應為純數字，收到: $CHANNEL_ID"
  exit 1
fi

echo "讀取目前 ALLOWED_CHANNELS..."
CURRENT="$(aws ssm get-parameter --name "$SSM_CHANNELS" --with-decryption \
  --region "$REGION" --query Parameter.Value --output text)"

# 檢查是否已存在
if echo "$CURRENT" | tr ',' '\n' | grep -qx "$CHANNEL_ID"; then
  echo "頻道 $CHANNEL_ID 已在清單中，無需重複新增。"
  exit 0
fi

# 組合新清單(過濾空值避免開頭多一個逗號)
if [[ -z "$CURRENT" ]]; then
  NEW="$CHANNEL_ID"
else
  NEW="${CURRENT},${CHANNEL_ID}"
fi

echo "更新 SSM: $SSM_CHANNELS"
echo "  舊值: $CURRENT"
echo "  新值: $NEW"
[[ -n "$NOTE" ]] && echo "  備註: $NOTE"

aws ssm put-parameter --name "$SSM_CHANNELS" --value "$NEW" \
  --type SecureString --overwrite --region "$REGION" > /dev/null

echo "重啟服務 $SERVICE..."
sudo systemctl restart "$SERVICE"

echo "等待服務啟動..."
sleep 3
if systemctl is-active --quiet "$SERVICE"; then
  echo "✅ 完成!頻道 $CHANNEL_ID 已加入，服務運行中。"
else
  echo "⚠️  服務啟動異常，請檢查: sudo journalctl -u $SERVICE -n 30"
  exit 1
fi
