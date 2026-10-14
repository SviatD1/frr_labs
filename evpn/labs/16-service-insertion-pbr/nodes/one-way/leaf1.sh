#!/bin/bash
# =====================================================================
# EVPN lab 16 - Service Insertion in EVPN using PBR
# node: leaf1   role: leaf   variant: one-way
# Generated file. Apply on the VM as root:   bash leaf1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "16-service-insertion-pbr/one-way/leaf1" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf1 (lab 16, variant one-way)
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

# --- VNI 10010 <-> VLAN 10 ---
ip link add vxlan10010 type vxlan id 10010 local 1.1.1.1 dstport 4789 nolearning
ip link set vxlan10010 master br0 addrgenmode none
bridge vlan del dev vxlan10010 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10010 vid 10 pvid untagged
bridge link set dev vxlan10010 learning off neigh_suppress on
ip link set vxlan10010 up
ip link set eth1 master br0
bridge vlan add dev eth1 vid 10 pvid untagged
ip link set eth1 up

# --- VNI 10999 <-> VLAN 999 ---
ip link add vxlan10999 type vxlan id 10999 local 1.1.1.1 dstport 4789 nolearning
ip link set vxlan10999 master br0 addrgenmode none
bridge vlan del dev vxlan10999 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10999 vid 999 pvid untagged
bridge link set dev vxlan10999 learning off neigh_suppress on
ip link set vxlan10999 up

# --- VRF A (kernel routing table 1001) ---
ip link add A type vrf table 1001
ip link set A up

# --- SVI vlan10 in VRF A (anycast gw 10.10.10.1/24) ---
bridge vlan add dev br0 vid 10 self
ip link add vlan10 link br0 type vlan id 10
ip link set vlan10 address 00:00:5e:00:01:01
bridge fdb replace 00:00:5e:00:01:01 dev br0 vlan 10 self local
ip link set vlan10 master A
ip link set vlan10 up
ip addr add 10.10.10.1/24 dev vlan10

# --- VRF SVC (kernel routing table 1999) ---
ip link add SVC type vrf table 1999
ip link set SVC up

# --- service VLAN SVI in its own VRF without L3VNI -> no host routes for the fw ---
bridge vlan add dev br0 vid 999 self
ip link add vlan999 link br0 type vlan id 999
ip link set vlan999 address 00:00:5e:00:01:01
bridge fdb replace 00:00:5e:00:01:01 dev br0 vlan 999 self local
ip link set vlan999 master SVC
ip link set vlan999 up
ip addr add 10.100.100.1/24 dev vlan999

# --- L3VNI 10100 for VRF A (transit VLAN 4001, router-MAC = br0 MAC) ---

# --- VNI 10100 <-> VLAN 4001 ---
ip link add vxlan10100 type vxlan id 10100 local 1.1.1.1 dstport 4789 nolearning
ip link set vxlan10100 master br0 addrgenmode none
bridge vlan del dev vxlan10100 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10100 vid 4001 pvid untagged
bridge link set dev vxlan10100 learning off neigh_suppress on
ip link set vxlan10100 up
bridge vlan add dev br0 vid 4001 self
ip link add vlan4001 link br0 type vlan id 4001
ip link set vlan4001 master A addrgenmode none
ip link set vlan4001 up
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
 vni 10100
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
interface vlan10
 pbr-policy TO-FW
exit
!
router isis 1
 net 49.0001.0000.0000.0001.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
exit
!
pbr-map TO-FW seq 10
 match src-ip 10.10.10.0/24
 match dst-ip 10.20.20.0/24
 set nexthop 10.100.100.100 nexthop-vrf SVC
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
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply leaf1
