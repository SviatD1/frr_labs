#!/bin/bash
# =====================================================================
# EVPN lab 24 - Routing Protocol Options for EVPN Underlay
# node: leaf4   role: leaf   variant: ospfv3
# Generated file. Apply on the VM as root:   bash leaf4.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "24-underlay-igp-options/ospfv3/leaf4" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf4 (lab 24, variant ospfv3)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip -6 addr add fc00::4/128 dev lo
ip link set eth11 up
ip -6 addr add fc00:10:4:11::4/64 dev eth11
ip link set eth12 up
ip -6 addr add fc00:10:4:12::4/64 dev eth12

# --- VLAN-aware bridge (one per switch, like a hardware switch's VLAN table) ---
ip link add br0 type bridge vlan_filtering 1 vlan_default_pvid 0 mcast_snooping 0 stp_state 0
ip link set br0 address 44:38:39:ff:00:04
ip link set br0 addrgenmode none
ip link set br0 up

# --- VNI 10010 <-> VLAN 10 ---
ip link add vxlan10010 type vxlan id 10010 local fc00::4 dstport 4789 nolearning
ip link set vxlan10010 master br0 addrgenmode none
bridge vlan del dev vxlan10010 vid 1 2>/dev/null || true
bridge vlan add dev vxlan10010 vid 10 pvid untagged
bridge link set dev vxlan10010 learning off neigh_suppress on
ip link set vxlan10010 up
ip link set eth1 master br0
bridge vlan add dev eth1 vid 10 pvid untagged
ip link set eth1 up
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname leaf4
log syslog informational
service integrated-vtysh-config
!
interface eth11
 ipv6 ospf6 area 0
 ipv6 ospf6 network point-to-point
exit
!
interface eth12
 ipv6 ospf6 area 0
 ipv6 ospf6 network point-to-point
exit
!
interface lo
 ipv6 ospf6 area 0
 ipv6 ospf6 passive
exit
!
router ospf6
 ospf6 router-id 4.4.4.4
exit
!
router bgp 65000
 bgp router-id 4.4.4.4
 no bgp default ipv4-unicast
 neighbor RR peer-group
 neighbor RR remote-as 65000
 neighbor RR update-source lo
 neighbor fc00::11 peer-group RR
 neighbor fc00::12 peer-group RR
 !
 address-family l2vpn evpn
  neighbor RR activate
  advertise-all-vni
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply leaf4
