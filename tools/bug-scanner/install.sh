#!/bin/bash
# 安裝/更新 bug-scanner 的 systemd timer。需 sudo。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

sudo cp "$HERE/sml-bug-scanner.service" /etc/systemd/system/
sudo cp "$HERE/sml-bug-scanner.timer"   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sml-bug-scanner.timer

echo "== timer 狀態 =="
systemctl status sml-bug-scanner.timer --no-pager | head -6
echo
echo "下次觸發:"
systemctl list-timers sml-bug-scanner.timer --no-pager | head -3
echo
echo "手動掃一次:  sudo systemctl start sml-bug-scanner.service && journalctl -u sml-bug-scanner -f"
echo "停用(kill):  sudo systemctl disable --now sml-bug-scanner.timer"
