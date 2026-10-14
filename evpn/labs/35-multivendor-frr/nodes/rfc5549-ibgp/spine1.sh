#!/bin/bash
# =====================================================================
# EVPN lab 35 - Multi-vendor EVPN design using Arista and FRR
# node: spine1   role: spine   variant: rfc5549-ibgp
# Generated file. Apply on the VM as root:   bash spine1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "35-multivendor-frr/rfc5549-ibgp/spine1" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for spine1 (lab 35, variant rfc5549-ibgp)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 11.11.11.11/32 dev lo

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
hostname spine1
log syslog informational
service integrated-vtysh-config
!
router bgp 65000
 bgp router-id 11.11.11.11
 no bgp ebgp-requires-policy
 bgp bestpath as-path multipath-relax
 neighbor LEAVES peer-group
 neighbor LEAVES remote-as internal
 neighbor eth1 interface peer-group LEAVES
 neighbor eth2 interface peer-group LEAVES
 bgp cluster-id 11.11.11.11
 !
 address-family ipv4 unicast
  network 11.11.11.11/32
  neighbor LEAVES route-reflector-client
  neighbor LEAVES next-hop-self force
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
