#!/bin/bash
# =====================================================================
# EVPN lab 27 - iBGP as Underlay for EVPN in Data Center
# node: spine1   role: spine   variant: ibgp
# Generated file. Apply on the VM as root:   bash spine1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "27-ibgp-underlay/ibgp/spine1" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for spine1 (lab 27, variant ibgp)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 11.11.11.11/32 dev lo
ip link set eth1 up
ip addr add 10.1.11.11/24 dev eth1
ip link set eth2 up
ip addr add 10.2.11.11/24 dev eth2
ip link set eth3 up
ip addr add 10.3.11.11/24 dev eth3
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
router bgp 65000
 bgp router-id 11.11.11.11
 no bgp default ipv4-unicast
 bgp cluster-id 11.11.11.11
 neighbor LEAVES peer-group
 neighbor LEAVES remote-as internal
 neighbor 10.1.11.1 peer-group LEAVES
 neighbor 10.2.11.2 peer-group LEAVES
 neighbor 10.3.11.3 peer-group LEAVES
 !
 address-family ipv4 unicast
  neighbor LEAVES activate
  neighbor LEAVES route-reflector-client
  neighbor LEAVES next-hop-self force
  network 11.11.11.11/32
  maximum-paths ibgp 4
 exit-address-family
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
lab-apply spine1
