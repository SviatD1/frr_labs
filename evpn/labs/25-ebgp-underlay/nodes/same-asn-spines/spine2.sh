#!/bin/bash
# =====================================================================
# EVPN lab 25 - eBGP as Underlay for EVPN in Data Center
# node: spine2   role: spine   variant: same-asn-spines
# Generated file. Apply on the VM as root:   bash spine2.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "25-ebgp-underlay/same-asn-spines/spine2" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for spine2 (lab 25, variant same-asn-spines)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 12.12.12.12/32 dev lo

# --- fabric links ---
ip link set eth1 up
ip addr add 10.1.12.12/24 dev eth1
ip link set eth2 up
ip addr add 10.2.12.12/24 dev eth2
ip link set eth3 up
ip addr add 10.3.12.12/24 dev eth3
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
router bgp 65100
 bgp router-id 12.12.12.12
 no bgp ebgp-requires-policy
 bgp bestpath as-path multipath-relax
 neighbor LEAVES peer-group
 neighbor LEAVES remote-as external
 neighbor 10.1.12.1 peer-group LEAVES
 neighbor 10.2.12.2 peer-group LEAVES
 neighbor 10.3.12.3 peer-group LEAVES
 !
 address-family ipv4 unicast
  network 12.12.12.12/32
 exit-address-family
 !
 address-family l2vpn evpn
  neighbor LEAVES activate
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply spine2
