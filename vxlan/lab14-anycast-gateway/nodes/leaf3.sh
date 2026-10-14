#!/usr/bin/env bash
# Lab 14 - EVPN anycast distributed gateway (and host mobility)
# node: leaf3  (router)
# Run as root on the leaf3 VM. Safe to re-run: it wipes the previous lab first.
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
ip addr add 10.0.0.13/32 dev lo
# ---------- underlay point-to-point links ----------
ip addr add 10.1.13.1/31 dev eth1
ip addr add 10.2.13.1/31 dev eth2
# ---------- tenant VRF TENANT1 + L3VNI 4001 (symmetric IRB transit VNI) ----------
ip link add TENANT1 type vrf table 1001
ip link set TENANT1 up
ip link add br4001 type bridge
ip link set br4001 master TENANT1
ip link add vxlan4001 type vxlan id 4001 local 10.0.0.13 dstport 4789 nolearning
ip link set vxlan4001 master br4001
bridge link set dev vxlan4001 learning off
ip link set vxlan4001 up
ip link set br4001 up
# ---------- VNI 100 -> bridge br100 ----------
ip link add br100 type bridge
ip link add vxlan100 type vxlan id 100 local 10.0.0.13 dstport 4789 nolearning
ip link set vxlan100 master br100
bridge link set dev vxlan100 learning off neigh_suppress on
ip link set eth3 master br100
ip link set br100 master TENANT1
ip link set br100 address 02:00:5e:00:01:01   # same MAC on every leaf = anycast gateway
ip addr add 192.168.100.1/24 dev br100
ip link set vxlan100 up
ip link set br100 up
# ---------- VNI 200 -> bridge br200 ----------
ip link add br200 type bridge
ip link add vxlan200 type vxlan id 200 local 10.0.0.13 dstport 4789 nolearning
ip link set vxlan200 master br200
bridge link set dev vxlan200 learning off neigh_suppress on
ip link set br200 master TENANT1
ip link set br200 address 02:00:5e:00:01:01   # same MAC on every leaf = anycast gateway
ip addr add 192.168.200.1/24 dev br200
ip link set vxlan200 up
ip link set br200 up

# ---------- routing protocols (FRR) ----------
if [ "${APPLY_FRR:-1}" = 1 ]; then
  "$HERE/../../00-setup/apply-frr.sh" "$HERE/leaf3.frr.conf"
fi
echo "leaf3: lab config applied"
