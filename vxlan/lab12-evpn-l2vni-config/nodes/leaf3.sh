#!/usr/bin/env bash
# Lab 12 - Configuring MP-BGP EVPN for L2VNIs (VLAN-aware bridge, RD/RT, ARP suppression)
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
# ---------- VLAN-aware bridge = the switch's VLAN table ----------
ip link add br0 type bridge vlan_filtering 1 vlan_default_pvid 0
ip link set br0 up
ip link set eth3 master br0
bridge vlan add dev eth3 vid 10      # trunk: tagged VLAN 10
bridge vlan add dev eth3 vid 20      # trunk: tagged VLAN 20
# vlan 10 vn-segment 10010
ip link add vxlan10010 type vxlan id 10010 local 10.0.0.13 dstport 4789 nolearning
ip link set vxlan10010 master br0
bridge vlan add dev vxlan10010 vid 10 pvid untagged
bridge link set dev vxlan10010 learning off
ip link set vxlan10010 up
# vlan 20 vn-segment 10020
ip link add vxlan10020 type vxlan id 10020 local 10.0.0.13 dstport 4789 nolearning
ip link set vxlan10020 master br0
bridge vlan add dev vxlan10020 vid 20 pvid untagged
bridge link set dev vxlan10020 learning off
ip link set vxlan10020 up

# ---------- routing protocols (FRR) ----------
if [ "${APPLY_FRR:-1}" = 1 ]; then
  "$HERE/../../00-setup/apply-frr.sh" "$HERE/leaf3.frr.conf"
fi
echo "leaf3: lab config applied"
