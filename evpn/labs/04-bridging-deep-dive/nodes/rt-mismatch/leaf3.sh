#!/bin/bash
# =====================================================================
# EVPN lab 04 - EVPN Bridging Deep Dive: RD, RT, VNI, EVI, MAC-VRF, VLAN-Aware Bundle
# node: leaf3   role: leaf   variant: rt-mismatch
# Generated file. Apply on the VM as root:   bash leaf3.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "04-bridging-deep-dive/rt-mismatch/leaf3" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf3 (lab 04, variant rt-mismatch)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 3.3.3.3/32 dev lo

# --- uplinks to spines ---
ip link set eth11 up
ip addr add 10.3.11.3/24 dev eth11

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
bridge link set dev vxlan10030 learning off neigh_suppress off
ip link set vxlan10030 up
ip link set eth1 master br0
bridge vlan add dev eth1 vid 30 pvid untagged
ip link set eth1 up
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
 net 49.0001.0000.0000.0003.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
exit
!
router bgp 65000
 bgp router-id 3.3.3.3
 no bgp default ipv4-unicast
 neighbor RR peer-group
 neighbor RR remote-as 65000
 neighbor RR update-source lo
 neighbor 11.11.11.11 peer-group RR
 !
 address-family l2vpn evpn
  neighbor RR activate
  advertise-all-vni
  vni 10030
   rd 3.3.3.3:30
   route-target import 30:30
   route-target export 30:30
  exit-vni
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply leaf3
