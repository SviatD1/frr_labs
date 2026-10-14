#!/bin/bash
# =====================================================================
# EVPN lab 04 - EVPN Bridging Deep Dive: RD, RT, VNI, EVI, MAC-VRF, VLAN-Aware Bundle
# node: leaf2   role: leaf   variant: local-vlans
# Generated file. Apply on the VM as root:   bash leaf2.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "04-bridging-deep-dive/local-vlans/leaf2" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf2 (lab 04, variant local-vlans)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 2.2.2.2/32 dev lo

# --- uplinks to spines ---
ip link set eth11 up
ip addr add 10.2.11.2/24 dev eth11

# --- VLAN-aware bridge (one per switch, like a hardware switch's VLAN table) ---
ip link add br0 type bridge vlan_filtering 1 vlan_default_pvid 0 mcast_snooping 0 stp_state 0
ip link set br0 address 44:38:39:ff:00:02
ip link set br0 addrgenmode none
ip link set br0 up

# --- VNI 10010 <-> VLAN 110 ---
ip link add vxlan10010 type vxlan id 10010 local 2.2.2.2 dstport 4789 nolearning
ip link set vxlan10010 master br0 addrgenmode none
bridge vlan del dev vxlan10010 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10010 vid 110 pvid untagged
bridge link set dev vxlan10010 learning off neigh_suppress off
ip link set vxlan10010 up
ip link set eth1 master br0
bridge vlan add dev eth1 vid 110 pvid untagged
ip link set eth1 up

# --- VNI 10020 <-> VLAN 120 ---
ip link add vxlan10020 type vxlan id 10020 local 2.2.2.2 dstport 4789 nolearning
ip link set vxlan10020 master br0 addrgenmode none
bridge vlan del dev vxlan10020 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10020 vid 120 pvid untagged
bridge link set dev vxlan10020 learning off neigh_suppress off
ip link set vxlan10020 up
ip link set eth2 master br0
bridge vlan add dev eth2 vid 120 pvid untagged
ip link set eth2 up
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname leaf2
log syslog informational
service integrated-vtysh-config
!
interface eth11
 ip router isis 1
 isis network point-to-point
exit
!
interface lo
 ip router isis 1
 isis passive
exit
!
router isis 1
 net 49.0001.0000.0000.0002.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
exit
!
router bgp 65000
 bgp router-id 2.2.2.2
 no bgp default ipv4-unicast
 neighbor RR peer-group
 neighbor RR remote-as 65000
 neighbor RR update-source lo
 neighbor 11.11.11.11 peer-group RR
 !
 address-family l2vpn evpn
  neighbor RR activate
  advertise-all-vni
  vni 10010
   rd 2.2.2.2:10
   route-target import 10:10
   route-target export 10:10
  exit-vni
  vni 10020
   rd 2.2.2.2:20
   route-target import 20:20
   route-target export 20:20
  exit-vni
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply leaf2
