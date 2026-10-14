#!/bin/bash
# =====================================================================
# EVPN lab 35 - Multi-vendor EVPN design using Arista and FRR
# node: spine2   role: spine   variant: ipv6-lla-isis-ibgp
# Generated file. Apply on the VM as root:   bash spine2.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "35-multivendor-frr/ipv6-lla-isis-ibgp/spine2" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for spine2 (lab 35, variant ipv6-lla-isis-ibgp)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip -6 addr add fc00::12/128 dev lo

# --- fabric links (ipv6-lla) ---
ip link set eth1 up
ip link set eth2 up
ip addr add 12.12.12.12/32 dev lo
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
 ipv6 router isis 1
 isis network point-to-point
exit
!
interface eth2
 ipv6 router isis 1
 isis network point-to-point
exit
!
interface lo
 ipv6 router isis 1
 isis passive
exit
!
router isis 1
 net 49.0001.0000.0000.0012.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
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
