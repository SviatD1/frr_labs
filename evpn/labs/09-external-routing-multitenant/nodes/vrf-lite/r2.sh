#!/bin/bash
# =====================================================================
# EVPN lab 09 - Multi-Tenant External Routing in EVPN
# node: r2   role: ext   variant: vrf-lite
# Generated file. Apply on the VM as root:   bash r2.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "09-external-routing-multitenant/vrf-lite/r2" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for r2 (lab 09, variant vrf-lite)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 172.16.2.2/32 dev lo
ip link set eth1 up
ip link add link eth1 name eth1.100 type vlan id 100
ip link set eth1.100 up
ip addr add 172.16.34.2/24 dev eth1.100
ip link add link eth1 name eth1.200 type vlan id 200
ip link set eth1.200 up
ip addr add 172.17.34.2/24 dev eth1.200
ip link set eth3 up
ip addr add 192.168.6.1/24 dev eth3
ip link set eth4 up
ip addr add 172.16.12.2/24 dev eth4
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname r2
log syslog informational
service integrated-vtysh-config
!
router bgp 65001
 bgp router-id 172.16.2.2
 no bgp ebgp-requires-policy
 neighbor 172.16.34.4 remote-as 65000
 neighbor 172.17.34.4 remote-as 65000
 neighbor 172.16.12.1 remote-as 65001
 !
 address-family ipv4 unicast
  redistribute connected
  neighbor 172.16.12.1 next-hop-self
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply r2
