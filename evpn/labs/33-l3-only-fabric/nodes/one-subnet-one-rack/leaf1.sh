#!/bin/bash
# =====================================================================
# EVPN lab 33 - Layer 3 Only Fabric with EVPN
# node: leaf1   role: leaf   variant: one-subnet-one-rack
# Generated file. Apply on the VM as root:   bash leaf1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "33-l3-only-fabric/one-subnet-one-rack/leaf1" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf1 (lab 33, variant one-subnet-one-rack)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 1.1.1.1/32 dev lo

# --- uplinks to spines ---
ip link set eth11 up
ip addr add 10.1.11.1/24 dev eth11
ip link set eth12 up
ip addr add 10.1.12.1/24 dev eth12

# --- VLAN-aware bridge (one per switch, like a hardware switch's VLAN table) ---
ip link add br0 type bridge vlan_filtering 1 vlan_default_pvid 0 mcast_snooping 0 stp_state 0
ip link set br0 address 44:38:39:ff:00:01
ip link set br0 addrgenmode none
ip link set br0 up

# --- VRF A (kernel routing table 1001) ---
ip link add A type vrf table 1001
ip link set A up

# --- VRF B (kernel routing table 1002) ---
ip link add B type vrf table 1002
ip link set B up
# eth1: rack subnet, routed port
ip link set eth1 master A
ip link set eth1 up
ip addr add 10.1.10.1/24 dev eth1

# --- L3VNI 1000 for VRF A (transit VLAN 4001, router-MAC = br0 MAC) ---

# --- VNI 1000 <-> VLAN 4001 ---
ip link add vxlan1000 type vxlan id 1000 local 1.1.1.1 dstport 4789 nolearning
ip link set vxlan1000 master br0 addrgenmode none
bridge vlan del dev vxlan1000 vid 1 2>/dev/null || true
bridge vlan add dev vxlan1000 vid 4001 pvid untagged
bridge link set dev vxlan1000 learning off neigh_suppress on
ip link set vxlan1000 up
bridge vlan add dev br0 vid 4001 self
ip link add vlan4001 link br0 type vlan id 4001
ip link set vlan4001 master A addrgenmode none
ip link set vlan4001 up

# --- L3VNI 2000 for VRF B (transit VLAN 4002, router-MAC = br0 MAC) ---

# --- VNI 2000 <-> VLAN 4002 ---
ip link add vxlan2000 type vxlan id 2000 local 1.1.1.1 dstport 4789 nolearning
ip link set vxlan2000 master br0 addrgenmode none
bridge vlan del dev vxlan2000 vid 1 2>/dev/null || true
bridge vlan add dev vxlan2000 vid 4002 pvid untagged
bridge link set dev vxlan2000 learning off neigh_suppress on
ip link set vxlan2000 up
bridge vlan add dev br0 vid 4002 self
ip link add vlan4002 link br0 type vlan id 4002
ip link set vlan4002 master B addrgenmode none
ip link set vlan4002 up
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname leaf1
log syslog informational
service integrated-vtysh-config
!
vrf A
 vni 1000
exit-vrf
!
vrf B
 vni 2000
exit-vrf
!
interface eth11
 ip router isis 1
 isis network point-to-point
exit
!
interface eth12
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
 net 49.0001.0000.0000.0001.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
exit
!
router bgp 65000
 bgp router-id 1.1.1.1
 no bgp default ipv4-unicast
 neighbor RR peer-group
 neighbor RR remote-as 65000
 neighbor RR update-source lo
 neighbor 11.11.11.11 peer-group RR
 neighbor 12.12.12.12 peer-group RR
 !
 address-family l2vpn evpn
  neighbor RR activate
  advertise-all-vni
 exit-address-family
exit
!
router bgp 65000 vrf A
 bgp router-id 1.1.1.1
 !
 address-family ipv4 unicast
  redistribute connected
 exit-address-family
 !
 address-family l2vpn evpn
  advertise ipv4 unicast
 exit-address-family
exit
!
router bgp 65000 vrf B
 bgp router-id 1.1.1.1
 !
 address-family ipv4 unicast
  redistribute connected
 exit-address-family
 !
 address-family l2vpn evpn
  advertise ipv4 unicast
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply leaf1
