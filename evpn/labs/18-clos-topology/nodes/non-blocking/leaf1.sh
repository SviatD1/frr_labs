#!/bin/bash
# =====================================================================
# EVPN lab 18 - Clos / Leaf-Spine-Leaf Topology for EVPN Data Center
# node: leaf1   role: leaf   variant: non-blocking
# Generated file. Apply on the VM as root:   bash leaf1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "18-clos-topology/non-blocking/leaf1" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf1 (lab 18, variant non-blocking)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 1.1.1.1/32 dev lo

# --- uplinks to spines ---
ip link set eth11 up
ip addr add 10.1.11.1/24 dev eth11
ip link set eth12 up
ip addr add 10.1.12.1/24 dev eth12

# --- rack subnet: hosts bridged locally, leaf routes (no VXLAN) ---
ip link add br0 type bridge
ip link set br0 up
ip addr add 10.10.10.1/24 dev br0
ip link set eth1 master br0
ip link set eth1 up
ip link set eth2 master br0
ip link set eth2 up

# --- shape links ---
tc qdisc replace dev eth11 root tbf rate 100mbit burst 32kb latency 20ms
tc qdisc replace dev eth12 root tbf rate 100mbit burst 32kb latency 20ms
tc qdisc replace dev eth1 root tbf rate 100mbit burst 32kb latency 20ms
tc qdisc replace dev eth2 root tbf rate 100mbit burst 32kb latency 20ms
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname leaf1
log syslog informational
service integrated-vtysh-config
!
interface eth11
 ip router isis 1
 isis network point-to-point
exit
!
interface eth12
 ip router isis 1
 isis network point-to-point
exit
!
interface lo
 ip router isis 1
 isis passive
exit
!
interface br0
 ip router isis 1
 isis passive
exit
!
router isis 1
 net 49.0001.0000.0000.0001.00
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
lab-apply leaf1
