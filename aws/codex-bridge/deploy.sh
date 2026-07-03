#!/bin/bash
# codex-bridge 部署:重編 → 換 binary/run.sh → 重啟 service。
#
# 注意:codex bridge 是獨立 service(sml-codex-bridge),與 claude bridge(sml-discord-bridge)
# 不同 cgroup。所以就算由 claude 這邊觸發,重啟 codex bridge 也不會自殺 → 可直接 restart。
set -euo pipefail
cd "$(dirname "$0")"

echo "==> go build"
go build -o sml-codex-bridge .

echo "==> 停服務(避免 Text file busy)"
sudo systemctl stop sml-codex-bridge 2>/dev/null || true

echo "==> 換 binary 與 run.sh 就位"
cp sml-codex-bridge /opt/sml/codex-bridge
cp run.sh /opt/sml/codex-run.sh
chmod +x /opt/sml/codex-run.sh

echo "==> 安裝/更新 systemd unit"
sudo cp sml-codex-bridge.service /etc/systemd/system/sml-codex-bridge.service
sudo systemctl daemon-reload

echo "==> 重啟 sml-codex-bridge"
sudo systemctl restart sml-codex-bridge

sleep 2
systemctl status sml-codex-bridge --no-pager | head -6
