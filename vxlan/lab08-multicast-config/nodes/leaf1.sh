#!/usr/bin/env bash
# Lab 08 - Multicast underlay configuration (two PIM spines, VNI-to-group mapping)
# node: leaf1  (router)
# Run as root on the leaf1 VM. Safe to re-run: it wipes the previous lab first.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)

# ---------- reset whatever a previous lab left behind ----------
for t in vxlan bridge vrf vlan; do
  for d in $(ip -o link show type $t | awk -F': ' '{print $2}' | cut -d@ -f1); do
    ip link del "$d" 2>/dev/null || true
  done
done
for i in eth1 eth3 eth4; do
  ip addr flush dev $i
  ip link set $i nomaster 2>/dev/null || true
  ip link set $i mtu 1500 up
done
ip -4 addr flush dev lo; ip addr add 127.0.0.1/8 dev lo
for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done
sysctl -qw net.ipv4.ip_forward=1

# ---------- loopback (router-id / VTEP source) ----------
ip addr add 10.0.0.11/32 dev lo
# ---------- underlay point-to-point links ----------
ip addr add 10.1.11.1/31 dev eth1
# NOTE: in these multicast labs the leaves are plain IGMP members (no pimd).
# The VTEP source is the leaf's uplink address, so the first-hop PIM router
# (the spine) sees the encapsulated BUM traffic as coming from a directly
# connected source and can register it / build (S,G) state for it.
# ---------- VNI 100 -> bridge br100 ----------
ip link add br100 type bridge
ip link add vxlan100 type vxlan id 100 local 10.1.11.1 dstport 4789 group 239.1.1.100 dev eth1 ttl 16
ip link set vxlan100 master br100
ip link set eth3 master br100
ip link set vxlan100 up
ip link set br100 up
# ---------- VNI 200 -> bridge br200 ----------
ip link add br200 type bridge
ip link add vxlan200 type vxlan id 200 local 10.1.11.1 dstport 4789 group 239.1.1.200 dev eth1 ttl 16
ip link set vxlan200 master br200
ip link set eth4 master br200
ip link set vxlan200 up
ip link set br200 up

# ---------- routing protocols (FRR) ----------
if [ "${APPLY_FRR:-1}" = 1 ]; then
  "$HERE/../../00-setup/apply-frr.sh" "$HERE/leaf1.frr.conf"
fi
echo "leaf1: lab config applied"
