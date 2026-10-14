#!/usr/bin/env bash
# Lab 05 - Basic VXLAN configuration (VLAN-to-VNI mapping, static ingress replication)
# node: h2  (host)
# Run as root on the h2 VM. Safe to re-run: it wipes the previous lab first.
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
# trunk towards the leaf: one 802.1Q sub-interface per VLAN
ip link set eth1 mtu 1450
ip link add link eth1 name eth1.10 type vlan id 10
ip link set eth1.10 mtu 1450 up
ip addr add 192.168.10.102/24 dev eth1.10
ip link add link eth1 name eth1.20 type vlan id 20
ip link set eth1.20 mtu 1450 up
ip addr add 192.168.20.102/24 dev eth1.20

# ---------- hosts do not run FRR ----------
systemctl stop frr 2>/dev/null || true
echo "h2: lab config applied"
