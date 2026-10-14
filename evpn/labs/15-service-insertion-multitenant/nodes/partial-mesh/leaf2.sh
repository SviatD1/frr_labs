#!/bin/bash
# =====================================================================
# EVPN lab 15 - Multitenant Service Insertion in EVPN. Advanced VRF Sandwich
# node: leaf2   role: leaf   variant: partial-mesh
# Generated file. Apply on the VM as root:   bash leaf2.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "15-service-insertion-multitenant/partial-mesh/leaf2" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf2 (lab 15, variant partial-mesh)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 2.2.2.2/32 dev lo

# --- uplinks to spines ---
ip link set eth11 up
ip addr add 10.2.11.2/24 dev eth11
ip link set eth12 up
ip addr add 10.2.12.2/24 dev eth12

# --- VLAN-aware bridge (one per switch, like a hardware switch's VLAN table) ---
ip link add br0 type bridge vlan_filtering 1 vlan_default_pvid 0 mcast_snooping 0 stp_state 0
ip link set br0 address 44:38:39:ff:00:02
ip link set br0 addrgenmode none
ip link set br0 up

# --- VNI 10020 <-> VLAN 20 ---
ip link add vxlan10020 type vxlan id 10020 local 2.2.2.2 dstport 4789 nolearning
ip link set vxlan10020 master br0 addrgenmode none
bridge vlan del dev vxlan10020 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10020 vid 20 pvid untagged
bridge link set dev vxlan10020 learning off neigh_suppress on
ip link set vxlan10020 up
ip link set eth1 master br0
bridge vlan add dev eth1 vid 20 pvid untagged
ip link set eth1 up

# --- VNI 10040 <-> VLAN 40 ---
ip link add vxlan10040 type vxlan id 10040 local 2.2.2.2 dstport 4789 nolearning
ip link set vxlan10040 master br0 addrgenmode none
bridge vlan del dev vxlan10040 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10040 vid 40 pvid untagged
bridge link set dev vxlan10040 learning off neigh_suppress on
ip link set vxlan10040 up
ip link set eth2 master br0
bridge vlan add dev eth2 vid 40 pvid untagged
ip link set eth2 up

# --- VRF B (kernel routing table 1002) ---
ip link add B type vrf table 1002
ip link set B up

# --- VRF D (kernel routing table 1004) ---
ip link add D type vrf table 1004
ip link set D up

# --- SVI vlan20 in VRF B (anycast gw 10.20.20.1/24) ---
bridge vlan add dev br0 vid 20 self
ip link add vlan20 link br0 type vlan id 20
ip link set vlan20 address 00:00:5e:00:01:01
bridge fdb replace 00:00:5e:00:01:01 dev br0 vlan 20 self local
ip link set vlan20 master B
ip link set vlan20 up
ip addr add 10.20.20.1/24 dev vlan20

# --- L3VNI 10200 for VRF B (transit VLAN 4020, router-MAC = br0 MAC) ---

# --- VNI 10200 <-> VLAN 4020 ---
ip link add vxlan10200 type vxlan id 10200 local 2.2.2.2 dstport 4789 nolearning
ip link set vxlan10200 master br0 addrgenmode none
bridge vlan del dev vxlan10200 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10200 vid 4020 pvid untagged
bridge link set dev vxlan10200 learning off neigh_suppress on
ip link set vxlan10200 up
bridge vlan add dev br0 vid 4020 self
ip link add vlan4020 link br0 type vlan id 4020
ip link set vlan4020 master B addrgenmode none
ip link set vlan4020 up

# --- SVI vlan40 in VRF D (anycast gw 10.40.40.1/24) ---
bridge vlan add dev br0 vid 40 self
ip link add vlan40 link br0 type vlan id 40
ip link set vlan40 address 00:00:5e:00:01:01
bridge fdb replace 00:00:5e:00:01:01 dev br0 vlan 40 self local
ip link set vlan40 master D
ip link set vlan40 up
ip addr add 10.40.40.1/24 dev vlan40

# --- L3VNI 10400 for VRF D (transit VLAN 4040, router-MAC = br0 MAC) ---

# --- VNI 10400 <-> VLAN 4040 ---
ip link add vxlan10400 type vxlan id 10400 local 2.2.2.2 dstport 4789 nolearning
ip link set vxlan10400 master br0 addrgenmode none
bridge vlan del dev vxlan10400 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10400 vid 4040 pvid untagged
bridge link set dev vxlan10400 learning off neigh_suppress on
ip link set vxlan10400 up
bridge vlan add dev br0 vid 4040 self
ip link add vlan4040 link br0 type vlan id 4040
ip link set vlan4040 master D addrgenmode none
ip link set vlan4040 up
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
vrf B
 vni 10200
exit-vrf
!
vrf D
 vni 10400
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
 neighbor 12.12.12.12 peer-group RR
 !
 address-family l2vpn evpn
  neighbor RR activate
  advertise-all-vni
 exit-address-family
exit
!
router bgp 65000 vrf B
 bgp router-id 2.2.2.2
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
router bgp 65000 vrf D
 bgp router-id 2.2.2.2
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
lab-apply leaf2
