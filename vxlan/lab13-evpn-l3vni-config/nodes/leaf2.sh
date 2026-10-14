#!/usr/bin/env bash
# Lab 13 - Configuring MP-BGP EVPN for L3VNIs (two tenants, symmetric IRB)
# node: leaf2  (router)
# Run as root on the leaf2 VM. Safe to re-run: it wipes the previous lab first.
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
ip addr add 10.0.0.12/32 dev lo
# ---------- underlay point-to-point links ----------
ip addr add 10.1.12.1/31 dev eth1
ip addr add 10.2.12.1/31 dev eth2
# ---------- tenant VRF RED + L3VNI 50001 (symmetric IRB transit VNI) ----------
ip link add RED type vrf table 1001
ip link set RED up
ip link add br50001 type bridge
ip link set br50001 master RED
ip link add vxlan50001 type vxlan id 50001 local 10.0.0.12 dstport 4789 nolearning
ip link set vxlan50001 master br50001
bridge link set dev vxlan50001 learning off
ip link set vxlan50001 up
ip link set br50001 up
# ---------- VNI 10020 -> bridge br10020 ----------
ip link add br10020 type bridge
ip link add vxlan10020 type vxlan id 10020 local 10.0.0.12 dstport 4789 nolearning
ip link set vxlan10020 master br10020
bridge link set dev vxlan10020 learning off neigh_suppress on
ip link set eth3 master br10020
ip link set br10020 master RED
ip link set br10020 address 02:00:5e:00:01:01   # same MAC on every leaf = anycast gateway
ip addr add 192.168.20.1/24 dev br10020
ip link set vxlan10020 up
ip link set br10020 up

# ---------- routing protocols (FRR) ----------
if [ "${APPLY_FRR:-1}" = 1 ]; then
  "$HERE/../../00-setup/apply-frr.sh" "$HERE/leaf2.frr.conf"
fi
echo "leaf2: lab config applied"
