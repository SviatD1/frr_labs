#!/bin/bash
# =====================================================================
# EVPN lab 32 - Limiting host route advertisement in EVPN. BGP Route Target Constraint
# node: spine1   role: spine   variant: rr-filter-rtc
# Generated file. Apply on the VM as root:   bash spine1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "32-limit-host-routes-rtc/rr-filter-rtc/spine1" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for spine1 (lab 32, variant rr-filter-rtc)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 11.11.11.11/32 dev lo

# --- fabric links to leaves ---
ip link set eth1 up
ip addr add 10.1.11.11/24 dev eth1
ip link set eth2 up
ip addr add 10.2.11.11/24 dev eth2
ip link set eth3 up
ip addr add 10.3.11.11/24 dev eth3
ip link set eth4 up
ip addr add 10.4.11.11/24 dev eth4
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname spine1
log syslog informational
service integrated-vtysh-config
!
bgp extcommunity-list standard VNI-10-20 seq 5 permit rt 65000:10010
bgp extcommunity-list standard VNI-10-20 seq 10 permit rt 65000:10020
bgp extcommunity-list standard VNI-30 seq 5 permit rt 65000:10030
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
interface eth3
 ip router isis 1
 isis network point-to-point
exit
!
interface eth4
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
 net 49.0001.0000.0000.0011.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
exit
!
route-map TO-RACK-10-20 deny 10
 match extcommunity VNI-30
exit
!
route-map TO-RACK-10-20 permit 20
exit
!
route-map TO-RACK-30 deny 10
 match extcommunity VNI-10-20
exit
!
route-map TO-RACK-30 permit 20
exit
!
router bgp 65000
 bgp router-id 11.11.11.11
 no bgp default ipv4-unicast
 bgp cluster-id 11.11.11.11
 neighbor RACK-10-20 peer-group
 neighbor RACK-10-20 remote-as 65000
 neighbor RACK-10-20 update-source lo
 neighbor 1.1.1.1 peer-group RACK-10-20
 neighbor 2.2.2.2 peer-group RACK-10-20
 neighbor RACK-30 peer-group
 neighbor RACK-30 remote-as 65000
 neighbor RACK-30 update-source lo
 neighbor 3.3.3.3 peer-group RACK-30
 neighbor 4.4.4.4 peer-group RACK-30
 !
 address-family l2vpn evpn
  neighbor RACK-10-20 activate
  neighbor RACK-10-20 route-reflector-client
  neighbor RACK-10-20 route-map TO-RACK-10-20 out
  neighbor RACK-30 activate
  neighbor RACK-30 route-reflector-client
  neighbor RACK-30 route-map TO-RACK-30 out
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply spine1
