#!/bin/bash
# =====================================================================
# EVPN lab 37 - DCI network for EVPN Multi-Fabric. MTU, BUM traffic, HA and Fault Isolation
# node: spine111   role: spine   variant: naive
# Generated file. Apply on the VM as root:   bash spine111.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "37-multi-fabric-dci-ha/naive/spine111" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for spine111 (lab 37, variant naive)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 111.111.111.111/32 dev lo
ip link set eth1 up
ip addr add 10.101.111.2/24 dev eth1
ip link set eth2 up
ip addr add 10.102.111.2/24 dev eth2

# --- DCI link to spine211 ---
ip link set eth10 up
ip addr add 10.111.211.1/24 dev eth10

# --- DCI link to spine212 ---
ip link set eth11 up
ip addr add 10.111.212.1/24 dev eth11
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname spine111
log syslog informational
service integrated-vtysh-config
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
 net 49.0001.0000.0000.0111.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
exit
!
router isis 1
 redistribute ipv4 bgp level-2
exit
!
router bgp 65001
 bgp router-id 111.111.111.111
 no bgp default ipv4-unicast
 bgp cluster-id 111.111.111.111
 neighbor LEAVES peer-group
 neighbor LEAVES remote-as 65001
 neighbor LEAVES update-source lo
 neighbor 101.101.101.101 peer-group LEAVES
 neighbor 102.102.102.102 peer-group LEAVES
 neighbor DCI peer-group
 neighbor DCI remote-as 65002
 neighbor 10.111.211.2 peer-group DCI
 neighbor 10.111.212.2 peer-group DCI
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
  redistribute isis
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply spine111
