#!/usr/bin/env bash
# Lab 06 - Spine and leaf architecture (ECMP underlay, BFD)
# node: spine1  (router)
# Run as root on the spine1 VM. Safe to re-run: it wipes the previous lab first.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)

# ---------- reset whatever a previous lab left behind ----------
for t in vxlan bridge vrf vlan; do
  for d in $(ip -o link show type $t | awk -F': ' '{print $2}' | cut -d@ -f1); do
    ip link del "$d" 2>/dev/null || true
  done
done
for i in eth1 eth2 eth3; do
  ip addr flush dev $i
  ip link set $i nomaster 2>/dev/null || true
  ip link set $i mtu 1500 up
done
ip -4 addr flush dev lo; ip addr add 127.0.0.1/8 dev lo
for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done
sysctl -qw net.ipv4.ip_forward=1

# ---------- loopback (router-id / VTEP source) ----------
ip addr add 10.0.0.1/32 dev lo
# ---------- underlay point-to-point links ----------
ip addr add 10.1.11.0/31 dev eth1
ip addr add 10.1.12.0/31 dev eth2
ip addr add 10.1.13.0/31 dev eth3
sysctl -qw net.ipv4.fib_multipath_hash_policy=1   # hash on L4 ports -> VXLAN src-port entropy spreads flows

# ---------- routing protocols (FRR) ----------
if [ "${APPLY_FRR:-1}" = 1 ]; then
  "$HERE/../../00-setup/apply-frr.sh" "$HERE/spine1.frr.conf"
fi
echo "spine1: lab config applied"
