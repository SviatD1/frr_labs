#!/bin/bash
# =====================================================================
# EVPN lab 27 - iBGP as Underlay for EVPN in Data Center
# node: leaf1   role: leaf   variant: ibgp
# Generated file. Apply on the VM as root:   bash leaf1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "27-ibgp-underlay/ibgp/leaf1" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf1 (lab 27, variant ibgp)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 1.1.1.1/32 dev lo
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
router bgp 65000
 bgp router-id 1.1.1.1
 no bgp default ipv4-unicast
 neighbor SPINES peer-group
 neighbor SPINES remote-as internal
 neighbor 10.1.11.11 peer-group SPINES
 neighbor 10.1.12.12 peer-group SPINES
 !
 address-family ipv4 unicast
  neighbor SPINES activate
  network 1.1.1.1/32
  maximum-paths ibgp 4
 exit-address-family
 !
 address-family l2vpn evpn
  neighbor SPINES activate
  advertise-all-vni
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply leaf1
