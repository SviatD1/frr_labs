#!/bin/bash
# =====================================================================
# EVPN lab 28 - Mixed IPv4+IPv6 Underlay for EVPN. RFCs 5549 and 8950
# node: spine2   role: spine   variant: ipv6-core
# Generated file. Apply on the VM as root:   bash spine2.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "28-mixed-underlay-rfc5549/ipv6-core/spine2" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for spine2 (lab 28, variant ipv6-core)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip -6 addr add fc00::12/128 dev lo

# --- fabric links (no IPv4: BGP unnumbered over IPv6 link-local) ---
ip link set eth1 up
ip link set eth2 up
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
 neighbor eth1 interface peer-group LEAVES
 neighbor eth2 interface peer-group LEAVES
 !
 address-family ipv4 unicast
 exit-address-family
 !
 address-family l2vpn evpn
  neighbor LEAVES activate
 exit-address-family
 !
 address-family ipv6 unicast
  neighbor LEAVES activate
  network fc00::12/128
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply spine2
