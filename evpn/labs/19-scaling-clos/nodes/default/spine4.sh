#!/bin/bash
# =====================================================================
# EVPN lab 19 - Scaling Clos fabrics in Data Center
# node: spine4   role: spine   variant: default
# Generated file. Apply on the VM as root:   bash spine4.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "19-scaling-clos/default/spine4" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for spine4 (lab 19, variant default)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 14.14.14.14/32 dev lo
ip link set eth1 up
ip addr add 10.3.14.14/24 dev eth1
ip link set eth2 up
ip addr add 10.4.14.14/24 dev eth2
ip link set eth10 up
ip addr add 10.21.4.4/24 dev eth10
ip link set eth11 up
ip addr add 10.22.4.4/24 dev eth11
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname spine4
log syslog informational
service integrated-vtysh-config
!
interface eth1
 ip router isis 1
 isis network point-to-point
exit
!
interface eth2
 ip router isis 1
 isis network point-to-point
exit
!
interface eth10
 ip router isis 1
 isis network point-to-point
exit
!
interface eth11
 ip router isis 1
 isis network point-to-point
exit
!
interface lo
 ip router isis 1
 isis passive
exit
!
router isis 1
 net 49.0001.0000.0000.0014.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply spine4
