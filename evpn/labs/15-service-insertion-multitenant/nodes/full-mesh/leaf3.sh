#!/bin/bash
# =====================================================================
# EVPN lab 15 - Multitenant Service Insertion in EVPN. Advanced VRF Sandwich
# node: leaf3   role: leaf   variant: full-mesh
# Generated file. Apply on the VM as root:   bash leaf3.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "15-service-insertion-multitenant/full-mesh/leaf3" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf3 (lab 15, variant full-mesh)
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

# --- VRF A (kernel routing table 1001) ---
ip link add A type vrf table 1001
ip link set A up

# --- VRF B (kernel routing table 1002) ---
ip link add B type vrf table 1002
ip link set B up

# --- VRF C (kernel routing table 1003) ---
ip link add C type vrf table 1003
ip link set C up

# --- VRF D (kernel routing table 1004) ---
ip link add D type vrf table 1004
ip link set D up

# --- L3VNI 10100 for VRF A (transit VLAN 4010, router-MAC = br0 MAC) ---

# --- VNI 10100 <-> VLAN 4010 ---
ip link add vxlan10100 type vxlan id 10100 local 3.3.3.3 dstport 4789 nolearning
ip link set vxlan10100 master br0 addrgenmode none
bridge vlan del dev vxlan10100 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10100 vid 4010 pvid untagged
bridge link set dev vxlan10100 learning off neigh_suppress on
ip link set vxlan10100 up
bridge vlan add dev br0 vid 4010 self
ip link add vlan4010 link br0 type vlan id 4010
ip link set vlan4010 master A addrgenmode none
ip link set vlan4010 up

# --- L3VNI 10200 for VRF B (transit VLAN 4020, router-MAC = br0 MAC) ---

# --- VNI 10200 <-> VLAN 4020 ---
ip link add vxlan10200 type vxlan id 10200 local 3.3.3.3 dstport 4789 nolearning
ip link set vxlan10200 master br0 addrgenmode none
bridge vlan del dev vxlan10200 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10200 vid 4020 pvid untagged
bridge link set dev vxlan10200 learning off neigh_suppress on
ip link set vxlan10200 up
bridge vlan add dev br0 vid 4020 self
ip link add vlan4020 link br0 type vlan id 4020
ip link set vlan4020 master B addrgenmode none
ip link set vlan4020 up

# --- L3VNI 10300 for VRF C (transit VLAN 4030, router-MAC = br0 MAC) ---

# --- VNI 10300 <-> VLAN 4030 ---
ip link add vxlan10300 type vxlan id 10300 local 3.3.3.3 dstport 4789 nolearning
ip link set vxlan10300 master br0 addrgenmode none
bridge vlan del dev vxlan10300 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10300 vid 4030 pvid untagged
bridge link set dev vxlan10300 learning off neigh_suppress on
ip link set vxlan10300 up
bridge vlan add dev br0 vid 4030 self
ip link add vlan4030 link br0 type vlan id 4030
ip link set vlan4030 master C addrgenmode none
ip link set vlan4030 up

# --- L3VNI 10400 for VRF D (transit VLAN 4040, router-MAC = br0 MAC) ---

# --- VNI 10400 <-> VLAN 4040 ---
ip link add vxlan10400 type vxlan id 10400 local 3.3.3.3 dstport 4789 nolearning
ip link set vxlan10400 master br0 addrgenmode none
bridge vlan del dev vxlan10400 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10400 vid 4040 pvid untagged
bridge link set dev vxlan10400 learning off neigh_suppress on
ip link set vxlan10400 up
bridge vlan add dev br0 vid 4040 self
ip link add vlan4040 link br0 type vlan id 4040
ip link set vlan4040 master D addrgenmode none
ip link set vlan4040 up

# --- service VRFs: OUT faces the fw inside, IN faces the fw outside ---

# --- VRF OUT (kernel routing table 1100) ---
ip link add OUT type vrf table 1100
ip link set OUT up

# --- VRF IN (kernel routing table 1101) ---
ip link add IN type vrf table 1101
ip link set IN up
ip link set eth1 master OUT
ip link set eth1 up
ip addr add 172.16.31.3/24 dev eth1
ip link set eth2 master IN
ip link set eth2 up
ip addr add 172.16.32.3/24 dev eth2
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
ip prefix-list TO-A seq 5 permit 10.20.20.0/24
ip prefix-list TO-A seq 10 permit 10.30.30.0/24
ip prefix-list TO-A seq 15 permit 10.40.40.0/24
ip prefix-list TO-B seq 5 permit 10.10.10.0/24
ip prefix-list TO-B seq 10 permit 10.30.30.0/24
ip prefix-list TO-B seq 15 permit 10.40.40.0/24
ip prefix-list TO-C seq 5 permit 10.10.10.0/24
ip prefix-list TO-C seq 10 permit 10.20.20.0/24
ip prefix-list TO-C seq 15 permit 10.40.40.0/24
ip prefix-list TO-D seq 5 permit 10.10.10.0/24
ip prefix-list TO-D seq 10 permit 10.20.20.0/24
ip prefix-list TO-D seq 15 permit 10.30.30.0/24
ip prefix-list SUBNETS seq 5 permit 10.0.0.0/8 le 24
!
vrf A
 vni 10100
exit-vrf
!
vrf B
 vni 10200
exit-vrf
!
vrf C
 vni 10300
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
 net 49.0001.0000.0000.0003.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
exit
!
route-map FROM-IN-TO-A permit 10
 match ip address prefix-list TO-A
exit
!
route-map FROM-IN-TO-B permit 10
 match ip address prefix-list TO-B
exit
!
route-map FROM-IN-TO-C permit 10
 match ip address prefix-list TO-C
exit
!
route-map FROM-IN-TO-D permit 10
 match ip address prefix-list TO-D
exit
!
route-map SUBNETS-ONLY permit 10
 match ip address prefix-list SUBNETS
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
 exit-address-family
exit
!
router bgp 65000 vrf A
 bgp router-id 3.3.3.3
 !
 address-family l2vpn evpn
  advertise ipv4 unicast
 exit-address-family
 !
 address-family ipv4 unicast
  import vrf route-map FROM-IN-TO-A
  import vrf IN
 exit-address-family
exit
!
router bgp 65000 vrf B
 bgp router-id 3.3.3.3
 !
 address-family l2vpn evpn
  advertise ipv4 unicast
 exit-address-family
 !
 address-family ipv4 unicast
  import vrf route-map FROM-IN-TO-B
  import vrf IN
 exit-address-family
exit
!
router bgp 65000 vrf C
 bgp router-id 3.3.3.3
 !
 address-family l2vpn evpn
  advertise ipv4 unicast
 exit-address-family
 !
 address-family ipv4 unicast
  import vrf route-map FROM-IN-TO-C
  import vrf IN
 exit-address-family
exit
!
router bgp 65000 vrf D
 bgp router-id 3.3.3.3
 !
 address-family l2vpn evpn
  advertise ipv4 unicast
 exit-address-family
 !
 address-family ipv4 unicast
  import vrf route-map FROM-IN-TO-D
  import vrf IN
 exit-address-family
exit
!
router bgp 65000 vrf OUT
 bgp router-id 3.3.3.3
 neighbor 172.16.31.1 remote-as 100
 !
 address-family ipv4 unicast
  import vrf route-map SUBNETS-ONLY
  import vrf A
  import vrf B
  import vrf C
  import vrf D
  neighbor 172.16.31.1 route-map SUBNETS-ONLY out
 exit-address-family
exit
!
router bgp 65000 vrf IN
 bgp router-id 3.3.3.3
 neighbor 172.16.32.1 remote-as 100
 !
 address-family ipv4 unicast
  neighbor 172.16.32.1 route-map SUBNETS-ONLY in
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply leaf3
