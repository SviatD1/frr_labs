#!/bin/bash
# =====================================================================
# EVPN lab 17 - Explaining all BGP EVPN Route Types for Data Center
# node: r1   role: ext   variant: default
# Generated file. Apply on the VM as root:   bash r1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "17-all-route-types/default/r1" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for r1 (lab 17, variant default)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 10.100.100.100/32 dev lo
ip link set eth1 up
ip addr add 172.16.41.1/24 dev eth1
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
router bgp 65001
 bgp router-id 10.100.100.100
 no bgp ebgp-requires-policy
 neighbor 172.16.41.4 remote-as 65000
 !
 address-family ipv4 unicast
  network 10.100.100.100/32
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply r1
