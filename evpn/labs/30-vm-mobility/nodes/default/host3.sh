#!/bin/bash
# =====================================================================
# EVPN lab 30 - EVPN Overlay Design for Virtual Machine Mobility in Data Center
# node: host3   role: host   variant: default
# Generated file. Apply on the VM as root:   bash host3.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "30-vm-mobility/default/host3" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host3 (lab 30, variant default)
lab-reset          # remove everything a previous lab created
set -x

# --- host interface ---
ip link set eth1 address 00:cc:cc:cc:cc:cc
ip link set eth1 mtu 1450 up
ip addr add 10.10.10.30/24 dev eth1
ip route add default via 10.10.10.1 dev eth1

# --- keep the leaf's ARP/ND entry for this host fresh (see lab 05 README) ---
pkill -f "lab-gw-keepalive-host3 -c" 2>/dev/null || true
setsid -f bash -c 'exec -a lab-gw-keepalive-host3 bash -c "while true; do ping -c1 -W1 10.10.10.1 >/dev/null 2>&1; sleep 20; done"' </dev/null >/dev/null 2>&1
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# helper files used in this lab
# ---------------------------------------------------------------------
install -d $(dirname /usr/local/bin/vm)
cat > /usr/local/bin/vm <<'__LAB_FILE__'
#!/bin/bash
# Pretend a VM (MAC 00:aa:aa:aa:aa:aa, IP 10.10.10.10) lives on this host.
# usage: vm up | vm down | vm status
SELF_IP=10.10.10.30/24; SELF_MAC=00:cc:cc:cc:cc:cc     # this server's own identity
case "$1" in
  up)   ip addr flush dev eth1; ip link set eth1 address 00:aa:aa:aa:aa:aa
        ip addr add 10.10.10.10/24 dev eth1; ip route replace default via 10.10.10.1
        arping -U -c 3 -I eth1 10.10.10.10 >/dev/null; ping -c 1 -W 1 10.10.10.1 >/dev/null
        echo "VM is now on $(hostname)";;
  down) ip addr flush dev eth1; ip link set eth1 address $SELF_MAC
        ip addr add $SELF_IP dev eth1; ip route replace default via 10.10.10.1
        echo "VM left $(hostname)";;
  *)    ip -br addr show eth1; ip -br link show eth1;;
esac
__LAB_FILE__
chmod 755 /usr/local/bin/vm

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host3
