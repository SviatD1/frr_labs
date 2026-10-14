#!/bin/bash
# =====================================================================
# EVPN lab 21 - Why ECMP Algorithm is Critical in Data Center Networks
# node: leaf2   role: leaf   variant: l3-hash
# Generated file. Apply on the VM as root:   bash leaf2.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "21-ecmp/l3-hash/leaf2" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf2 (lab 21, variant l3-hash)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 2.2.2.2/32 dev lo

# --- uplinks to spines ---
ip link set eth11 up
ip addr add 10.2.11.2/24 dev eth11
ip link set eth12 up
ip addr add 10.2.12.2/24 dev eth12
ip link set eth13 up
ip addr add 10.2.13.2/24 dev eth13
ip link set eth14 up
ip addr add 10.2.14.2/24 dev eth14

# --- rack subnet: hosts bridged locally, leaf routes (no VXLAN) ---
ip link add br0 type bridge
ip link set br0 up
ip addr add 10.20.20.1/24 dev br0
ip link set eth1 master br0
ip link set eth1 up

# --- ECMP hash policy ---
sysctl -w net.ipv4.fib_multipath_hash_policy=0
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname leaf2
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
interface eth13
 ip router isis 1
 isis network point-to-point
exit
!
interface eth14
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
 net 49.0001.0000.0000.0002.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# helper files used in this lab
# ---------------------------------------------------------------------
install -d $(dirname /usr/local/bin/ecmp-test)
cat > /usr/local/bin/ecmp-test <<'__LAB_FILE__'
#!/bin/bash
# Which uplink does each flow take?  usage: ecmp-test <dst> <src> [count]
dst=${1:-10.20.20.20}; src=${2:-10.10.10.10}; n=${3:-100}
for p in $(seq 1 $n); do
  ip route get $dst from $src iif eth1 ipproto tcp sport $((10000+p)) dport 80 2>/dev/null | grep -o 'dev eth[0-9]*'
done | sort | uniq -c
__LAB_FILE__
chmod 755 /usr/local/bin/ecmp-test

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply leaf2
