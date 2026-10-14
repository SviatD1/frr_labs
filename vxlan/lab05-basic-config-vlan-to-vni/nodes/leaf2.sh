#!/usr/bin/env bash
# Lab 05 - Basic VXLAN configuration (VLAN-to-VNI mapping, static ingress replication)
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
# ---------- one VLAN-aware bridge (like the Nexus VLAN database) ----------
ip link add br0 type bridge vlan_filtering 1 vlan_default_pvid 0
ip link set br0 up
# host port eth3 = 802.1Q trunk carrying VLAN 10 and 20  (switchport mode trunk)
ip link set eth3 master br0
bridge vlan add dev eth3 vid 10
bridge vlan add dev eth3 vid 20
# vlan 10 / vn-segment 10010  +  member vni 10010 ingress-replication static peer 10.0.0.11
ip link add vxlan10010 type vxlan id 10010 local 10.0.0.12 dstport 4789
ip link set vxlan10010 master br0
bridge vlan add dev vxlan10010 vid 10 pvid untagged   # VLAN 10 <-> VNI 10010
ip link set vxlan10010 up
bridge fdb append 00:00:00:00:00:00 dev vxlan10010 dst 10.0.0.11
# vlan 20 / vn-segment 10020  +  member vni 10020 ingress-replication static peer 10.0.0.11
ip link add vxlan10020 type vxlan id 10020 local 10.0.0.12 dstport 4789
ip link set vxlan10020 master br0
bridge vlan add dev vxlan10020 vid 20 pvid untagged   # VLAN 20 <-> VNI 10020
ip link set vxlan10020 up
bridge fdb append 00:00:00:00:00:00 dev vxlan10020 dst 10.0.0.11

# ---------- routing protocols (FRR) ----------
if [ "${APPLY_FRR:-1}" = 1 ]; then
  "$HERE/../../00-setup/apply-frr.sh" "$HERE/leaf2.frr.conf"
fi
echo "leaf2: lab config applied"
