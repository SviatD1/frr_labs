#!/usr/bin/env bash
# Lab 04 - VXLAN control plane operations (flood & learn)
# node: vtep2  (router)
# Run as root on the vtep2 VM. Safe to re-run: it wipes the previous lab first.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)

# ---------- reset whatever a previous lab left behind ----------
for t in vxlan bridge vrf vlan; do
  for d in $(ip -o link show type $t | awk -F': ' '{print $2}' | cut -d@ -f1); do
    ip link del "$d" 2>/dev/null || true
  done
done
for i in eth1 eth3; do
  ip addr flush dev $i
  ip link set $i nomaster 2>/dev/null || true
  ip link set $i mtu 1500 up
done
ip -4 addr flush dev lo; ip addr add 127.0.0.1/8 dev lo
for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done
sysctl -qw net.ipv4.ip_forward=1

# ---------- loopback (router-id / VTEP source) ----------
ip addr add 10.0.0.12/32 dev lo
# ---------- underlay point-to-point links ----------
ip addr add 10.1.12.1/31 dev eth1
# ---------- VNI 100 -> bridge br100 ----------
ip link add br100 type bridge
ip link add vxlan100 type vxlan id 100 local 10.0.0.12 dstport 4789 ageing 120
ip link set vxlan100 master br100
ip link set eth3 master br100
ip link set vxlan100 up
ip link set br100 up
bridge fdb append 00:00:00:00:00:00 dev vxlan100 dst 10.0.0.11   # head-end replication peer
bridge fdb append 00:00:00:00:00:00 dev vxlan100 dst 10.0.0.13   # head-end replication peer

# ---------- routing protocols (FRR) ----------
if [ "${APPLY_FRR:-1}" = 1 ]; then
  "$HERE/../../00-setup/apply-frr.sh" "$HERE/vtep2.frr.conf"
fi
echo "vtep2: lab config applied"
