#!/bin/bash
# =====================================================================
# EVPN lab 09 - Multi-Tenant External Routing in EVPN
# node: r1   role: ext   variant: shared
# Generated file. Apply on the VM as root:   bash r1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "09-external-routing-multitenant/shared/r1" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for r1 (lab 09, variant shared)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 172.16.1.1/32 dev lo
ip link set eth1 up
ip addr add 172.16.33.1/24 dev eth1
ip link set eth3 up
ip addr add 192.168.5.1/24 dev eth3
ip link set eth4 up
ip addr add 172.16.12.1/24 dev eth4
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
 bgp router-id 172.16.1.1
 no bgp ebgp-requires-policy
 neighbor 172.16.33.3 remote-as 65000
 neighbor 172.16.12.2 remote-as 65001
 !
 address-family ipv4 unicast
  neighbor 172.16.33.3 default-originate
  redistribute connected
  neighbor 172.16.12.2 next-hop-self
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply r1
