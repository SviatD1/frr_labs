#!/bin/bash
# =====================================================================
# EVPN lab 37 - DCI network for EVPN Multi-Fabric. MTU, BUM traffic, HA and Fault Isolation
# node: host13   role: host   variant: oscillation
# Generated file. Apply on the VM as root:   bash host13.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "37-multi-fabric-dci-ha/oscillation/host13" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host13 (lab 37, variant oscillation)
lab-reset          # remove everything a previous lab created
set -x

# --- host interface ---
ip link set eth1 address 00:cc:cc:cc:cc:cc
ip link set eth1 mtu 1450 up
ip addr add 10.120.120.30/24 dev eth1
ip route add default via 10.120.120.1 dev eth1

# --- keep the leaf's ARP/ND entry for this host fresh (see lab 05 README) ---
pkill -f "lab-gw-keepalive-host13 -c" 2>/dev/null || true
setsid -f bash -c 'exec -a lab-gw-keepalive-host13 bash -c "while true; do ping -c1 -W1 10.120.120.1 >/dev/null 2>&1; sleep 20; done"' </dev/null >/dev/null 2>&1
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host13
