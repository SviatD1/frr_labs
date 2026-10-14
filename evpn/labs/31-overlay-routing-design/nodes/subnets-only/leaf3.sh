#!/bin/bash
# =====================================================================
# EVPN lab 31 - EVPN Overlay Design for Routing in Data Center
# node: leaf3   role: leaf   variant: subnets-only
# Generated file. Apply on the VM as root:   bash leaf3.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "31-overlay-routing-design/subnets-only/leaf3" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf3 (lab 31, variant subnets-only)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 3.3.3.3/32 dev lo

# --- uplinks to spines ---
ip link set eth11 up
ip addr add 10.3.11.3/24 dev eth11
ip link set eth12 up
ip addr add 10.3.12.3/24 dev eth12

# --- VLAN-aware bridge (one per switch, like a hardware switch's VLAN table) ---
ip link add br0 type bridge vlan_filtering 1 vlan_default_pvid 0 mcast_snooping 0 stp_state 0
ip link set br0 address 44:38:39:ff:00:03
ip link set br0 addrgenmode none
ip link set br0 up

# --- VNI 10030 <-> VLAN 30 ---
ip link add vxlan10030 type vxlan id 10030 local 3.3.3.3 dstport 4789 nolearning
ip link set vxlan10030 master br0 addrgenmode none
bridge vlan del dev vxlan10030 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10030 vid 30 pvid untagged
bridge link set dev vxlan10030 learning off neigh_suppress on
ip link set vxlan10030 up
ip link set eth1 master br0
bridge vlan add dev eth1 vid 30 pvid untagged
ip link set eth1 up

# --- VRF A (kernel routing table 1001) ---
ip link add A type vrf table 1001
ip link set A up

# --- SVI vlan30 in VRF A (anycast gw 10.30.30.1/24) ---
bridge vlan add dev br0 vid 30 self
ip link add vlan30 link br0 type vlan id 30
ip link set vlan30 address 00:00:5e:00:01:01
bridge fdb replace 00:00:5e:00:01:01 dev br0 vlan 30 self local
ip link set vlan30 master A
ip link set vlan30 up
ip addr add 10.30.30.1/24 dev vlan30

# --- L3VNI 1000 for VRF A (transit VLAN 4001, router-MAC = br0 MAC) ---

# --- VNI 1000 <-> VLAN 4001 ---
ip link add vxlan1000 type vxlan id 1000 local 3.3.3.3 dstport 4789 nolearning
ip link set vxlan1000 master br0 addrgenmode none
bridge vlan del dev vxlan1000 vid 1 2>/dev/null || true
bridge vlan add dev vxlan1000 vid 4001 pvid untagged
bridge link set dev vxlan1000 learning off neigh_suppress on
ip link set vxlan1000 up
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
hostname leaf3
log syslog informational
service integrated-vtysh-config
!
vrf A
 vni 1000
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
 net 49.0001.0000.0000.0003.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
exit
!
bgp extcommunity-list standard L3VNI-RT seq 5 permit rt 65000:1000
!
route-map NO-HOST-ROUTES permit 10
 match evpn route-type macip
 set extcomm-list L3VNI-RT delete
exit
!
route-map NO-HOST-ROUTES permit 20
exit
!
router bgp 65000
 bgp router-id 3.3.3.3
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
  neighbor RR route-map NO-HOST-ROUTES in
 exit-address-family
exit
!
router bgp 65000 vrf A
 bgp router-id 3.3.3.3
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
lab-apply leaf3
