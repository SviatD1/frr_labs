#!/usr/bin/env bash
# Make a node re-apply its lab config at every boot.
# Usage: persist.sh <lab-folder> <node>      e.g. persist.sh lab06-spine-leaf leaf1
#        persist.sh --off                      remove the boot hook
set -euo pipefail
unit=/etc/systemd/system/vxlan-lab.service
if [ "${1:-}" = "--off" ]; then
  systemctl disable --now vxlan-lab.service 2>/dev/null || true; rm -f "$unit"; systemctl daemon-reload; exit 0
fi
root=$(cd "$(dirname "$0")/.." && pwd)
script="$root/$1/nodes/$2.sh"
[ -x "$script" ] || { echo "not found: $script"; exit 1; }
cat > "$unit" <<EOF
[Unit]
Description=VXLAN lab config ($1 / $2)
After=network-online.target frr.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$script
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable vxlan-lab.service
echo "Will run $script at boot."
