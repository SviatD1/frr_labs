#!/bin/bash
# =====================================================================
# EVPN lab 24 - Routing Protocol Options for EVPN Underlay
# node: spine2   role: spine   variant: ospfv3
# Generated file. Apply on the VM as root:   bash spine2.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "24-underlay-igp-options/ospfv3/spine2" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for spine2 (lab 24, variant ospfv3)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip -6 addr add fc00::12/128 dev lo

# --- fabric links (ipv6-numbered) ---
ip link set eth1 up
ip -6 addr add fc00:10:1:12::12/64 dev eth1
ip link set eth2 up
ip -6 addr add fc00:10:2:12::12/64 dev eth2
ip link set eth3 up
ip -6 addr add fc00:10:3:12::12/64 dev eth3
ip link set eth4 up
ip -6 addr add fc00:10:4:12::12/64 dev eth4
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname spine2
log syslog informational
service integrated-vtysh-config
!
interface eth1
 ipv6 ospf6 area 0
 ipv6 ospf6 network point-to-point
exit
!
interface eth2
 ipv6 ospf6 area 0
 ipv6 ospf6 network point-to-point
exit
!
interface eth3
 ipv6 ospf6 area 0
 ipv6 ospf6 network point-to-point
exit
!
interface eth4
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
 ospf6 router-id 12.12.12.12
exit
!
router bgp 65000
 bgp router-id 12.12.12.12
 no bgp default ipv4-unicast
 bgp cluster-id 12.12.12.12
 neighbor LEAVES peer-group
 neighbor LEAVES remote-as 65000
 neighbor LEAVES update-source lo
 neighbor fc00::1 peer-group LEAVES
 neighbor fc00::2 peer-group LEAVES
 neighbor fc00::3 peer-group LEAVES
 neighbor fc00::4 peer-group LEAVES
 !
 address-family l2vpn evpn
  neighbor LEAVES activate
  neighbor LEAVES route-reflector-client
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply spine2
