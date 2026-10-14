#!/bin/bash
# =====================================================================
# EVPN lab 37 - DCI network for EVPN Multi-Fabric. MTU, BUM traffic, HA and Fault Isolation
# node: spine212   role: spine   variant: fixed
# Generated file. Apply on the VM as root:   bash spine212.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "37-multi-fabric-dci-ha/fixed/spine212" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for spine212 (lab 37, variant fixed)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 212.212.212.212/32 dev lo
ip link set eth1 up
ip addr add 10.201.212.2/24 dev eth1
ip link set eth2 up
ip addr add 10.202.212.2/24 dev eth2

# --- DCI link to spine111 ---
ip link set eth10 up
ip addr add 10.111.212.2/24 dev eth10

# --- DCI link to spine112 ---
ip link set eth11 up
ip addr add 10.112.212.2/24 dev eth11
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname spine212
log syslog informational
service integrated-vtysh-config
!
ip prefix-list LOCAL-LOOPBACKS seq 5 permit 201.201.201.201/32
ip prefix-list LOCAL-LOOPBACKS seq 10 permit 202.202.202.202/32
ip prefix-list LOCAL-LOOPBACKS seq 15 permit 211.211.211.211/32
ip prefix-list LOCAL-LOOPBACKS seq 20 permit 212.212.212.212/32
!
interface eth1
 ip router isis 1
 isis network point-to-point
exit
!
interface eth2
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
 net 49.0002.0000.0000.0212.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
exit
!
route-map LOCAL-LOOPBACKS permit 10
 match ip address prefix-list LOCAL-LOOPBACKS
exit
!
route-map BGP-TO-ISIS permit 10
 set tag 999
exit
!
router isis 1
 redistribute ipv4 bgp level-2 route-map BGP-TO-ISIS
exit
!
router bgp 65002
 bgp router-id 212.212.212.212
 no bgp default ipv4-unicast
 bgp cluster-id 212.212.212.212
 neighbor LEAVES peer-group
 neighbor LEAVES remote-as 65002
 neighbor LEAVES update-source lo
 neighbor 201.201.201.201 peer-group LEAVES
 neighbor 202.202.202.202 peer-group LEAVES
 neighbor DCI peer-group
 neighbor DCI remote-as 65001
 neighbor 10.111.212.1 peer-group DCI
 neighbor 10.112.212.1 peer-group DCI
 !
 address-family l2vpn evpn
  neighbor LEAVES activate
  neighbor LEAVES route-reflector-client
  neighbor DCI activate
  neighbor DCI attribute-unchanged next-hop
 exit-address-family
 !
 address-family ipv4 unicast
  neighbor DCI activate
  maximum-paths 4
  redistribute isis route-map LOCAL-LOOPBACKS
  neighbor DCI route-map LOCAL-LOOPBACKS out
  distance bgp 20 200 200
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply spine212
