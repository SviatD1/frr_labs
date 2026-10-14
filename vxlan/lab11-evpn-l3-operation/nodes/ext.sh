#!/usr/bin/env bash
# Lab 11 - Understanding MP-BGP EVPN Layer 3 operation (symmetric IRB, RMAC, type-5, border leaf)
# node: ext  (router)
# Run as root on the ext VM. Safe to re-run: it wipes the previous lab first.
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
sysctl -qw net.ipv4.ip_forward=1

# ---------- 'the outside world' ----------
ip addr add 10.0.0.99/32 dev lo
ip addr add 172.16.1.1/32 dev lo   # pretend internet prefixes
ip addr add 172.16.2.1/32 dev lo
ip addr add 10.99.0.1/31 dev eth1

# ---------- routing protocols (FRR) ----------
if [ "${APPLY_FRR:-1}" = 1 ]; then
  "$HERE/../../00-setup/apply-frr.sh" "$HERE/ext.frr.conf"
fi
echo "ext: lab config applied"
