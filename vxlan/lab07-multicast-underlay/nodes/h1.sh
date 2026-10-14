#!/usr/bin/env bash
# Lab 07 - Understanding the multicast underlay (PIM-SM, IGMP, BUM via group)
# node: h1  (host)
# Run as root on the h1 VM. Safe to re-run: it wipes the previous lab first.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)

# ---------- reset whatever a previous lab left behind ----------
for t in vxlan bridge vrf vlan; do
  for d in $(ip -o link show type $t | awk -F': ' '{print $2}' | cut -d@ -f1); do
    ip link del "$d" 2>/dev/null || true
  done
done
for i in eth1; do
  ip addr flush dev $i
  ip link set $i nomaster 2>/dev/null || true
  ip link set $i mtu 1500 up
done
ip -4 addr flush dev lo; ip addr add 127.0.0.1/8 dev lo
for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done
sysctl -qw net.ipv4.ip_forward=0

# ---------- host addressing ----------
ip link set eth1 mtu 1450     # 1500 - 50 bytes VXLAN overhead
ip addr add 192.168.100.101/24 dev eth1

# ---------- hosts do not run FRR ----------
systemctl stop frr 2>/dev/null || true
echo "h1: lab config applied"
