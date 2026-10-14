#!/usr/bin/env bash
# One-time preparation of the Debian 12 template VM used for EVERY node
# (hosts and routers). Run as root on the template, then shut it down and
# use it as a GNS3 "linked base" template.
#
#   - renames NICs to eth0, eth1, ... (all labs rely on these names)
#   - eth0 = management (GNS3 NAT cloud, DHCP) - never used by the labs
#   - installs FRR (Debian 12 ships FRR 8.4.4 - the version these labs were tested with)
#   - installs troubleshooting tools
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }

echo "[1/5] Packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y frr frr-pythontools iproute2 bridge-utils tcpdump tshark \
  iputils-ping traceroute iperf3 mtr-tiny ethtool net-tools arping curl vim less \
  linux-image-amd64

echo "[2/5] Classic interface names (eth0, eth1, ...)"
if ! grep -q 'net.ifnames=0' /etc/default/grub; then
  sed -i 's/^GRUB_CMDLINE_LINUX="\(.*\)"/GRUB_CMDLINE_LINUX="\1 net.ifnames=0 biosdevname=0"/' /etc/default/grub
  update-grub
fi

echo "[3/5] eth0 = DHCP management, stop cloud-init rewriting the network"
mkdir -p /etc/cloud/cloud.cfg.d
echo 'network: {config: disabled}' > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
rm -f /etc/network/interfaces.d/50-cloud-init* 2>/dev/null || true
cat > /etc/network/interfaces.d/eth0 <<'EOF'
auto eth0
iface eth0 inet dhcp
EOF

echo "[4/5] Kernel modules needed by the labs"
cat > /etc/modules-load.d/vxlan-labs.conf <<'EOF'
vxlan
vrf
8021q
bridge
EOF
for m in vxlan vrf 8021q bridge; do modprobe "$m" || echo "WARNING: module $m missing (use the full linux-image-amd64 kernel, not -cloud)"; done

echo "[5/5] Sysctls common to all nodes"
cat > /etc/sysctl.d/90-vxlan-labs.conf <<'EOF'
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.ipv4.conf.all.rp_filter = 0
net.ipv4.conf.default.rp_filter = 0
net.ipv4.fib_multipath_hash_policy = 1
net.ipv4.conf.all.ignore_routes_with_linkdown = 1
EOF
sysctl --system >/dev/null

# FRR starts with no daemons; apply-frr.sh enables what each lab needs.
systemctl enable frr

echo
echo "Done. Copy the 'vxlan' folder to /root/vxlan, reboot once to check that"
echo "'ip -br link' shows eth0, eth1, ..., then shut down and use as template."
