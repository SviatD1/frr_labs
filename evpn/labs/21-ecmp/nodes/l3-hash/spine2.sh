#!/bin/bash
# =====================================================================
# EVPN lab 21 - Why ECMP Algorithm is Critical in Data Center Networks
# node: spine2   role: spine   variant: l3-hash
# Generated file. Apply on the VM as root:   bash spine2.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "21-ecmp/l3-hash/spine2" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for spine2 (lab 21, variant l3-hash)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 12.12.12.12/32 dev lo

# --- fabric links to leaves ---
ip link set eth1 up
ip addr add 10.1.12.12/24 dev eth1
ip link set eth2 up
ip addr add 10.2.12.12/24 dev eth2
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
 ip router isis 1
 isis network point-to-point
exit
!
interface eth2
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
 net 49.0001.0000.0000.0012.00
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
lab-apply spine2
