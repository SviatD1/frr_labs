#!/bin/bash
# =====================================================================
# EVPN lab 08 - External Routing in EVPN using BGP
# node: r1   role: ext   variant: te
# Generated file. Apply on the VM as root:   bash r1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "08-external-routing-bgp/te/r1" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for r1 (lab 08, variant te)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 172.16.1.1/32 dev lo
ip link set eth1 up
ip addr add 172.16.31.1/24 dev eth1
ip link set eth2 up
ip addr add 172.16.41.1/24 dev eth2
ip link set eth3 up
ip addr add 172.16.15.1/24 dev eth3
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname r1
log syslog informational
service integrated-vtysh-config
!
ip prefix-list PREFER seq 5 permit 10.10.10.0/24
!
interface eth3
 ip ospf area 0
 ip ospf network point-to-point
exit
!
interface lo
 ip ospf area 0
 ip ospf passive
exit
!
router ospf
 ospf router-id 172.16.1.1
exit
!
route-map FROM-LEAF3 permit 10
 match ip address prefix-list PREFER
 set local-preference 200
exit
!
route-map FROM-LEAF3 permit 20
exit
!
router bgp 65001
 bgp router-id 172.16.1.1
 no bgp ebgp-requires-policy
 neighbor FABRIC peer-group
 neighbor FABRIC remote-as 65000
 neighbor IBGP peer-group
 neighbor IBGP remote-as 65001
 neighbor IBGP update-source lo
 neighbor 172.16.31.3 peer-group FABRIC
 neighbor 172.16.41.4 peer-group FABRIC
 neighbor 172.16.2.2 peer-group IBGP
 neighbor 172.16.15.5 remote-as 65001
 !
 address-family ipv4 unicast
  neighbor IBGP next-hop-self
  neighbor 172.16.15.5 next-hop-self
  maximum-paths 4
  maximum-paths ibgp 4
  neighbor 172.16.31.3 route-map FROM-LEAF3 in
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply r1
