#!/bin/bash
# =====================================================================
# EVPN lab 07 - External Routing in EVPN using OSPF. Mutual redistribution and loop avoidance
# node: r2   role: ext   variant: naive
# Generated file. Apply on the VM as root:   bash r2.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "07-external-routing-ospf/naive/r2" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for r2 (lab 07, variant naive)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 172.16.2.2/32 dev lo
ip link set eth2 up
ip addr add 172.16.32.2/24 dev eth2
ip link set eth1 up
ip addr add 172.16.42.2/24 dev eth1
ip link set eth3 up
ip addr add 172.16.25.2/24 dev eth3
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
interface eth1
 ip ospf area 0
 ip ospf network point-to-point
exit
!
interface eth2
 ip ospf area 0
 ip ospf network point-to-point
exit
!
router ospf
 ospf router-id 172.16.2.2
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply r2
