#!/bin/bash
# =====================================================================
# EVPN lab 08 - External Routing in EVPN using BGP
# node: host3   role: host   variant: basic
# Generated file. Apply on the VM as root:   bash host3.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "08-external-routing-bgp/basic/host3" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host3 (lab 08, variant basic)
lab-reset          # remove everything a previous lab created
set -x

# --- host interface ---
ip link set eth1 address 00:cc:cc:cc:cc:cc
ip link set eth1 mtu 1450 up
ip addr add 10.20.20.30/24 dev eth1
ip route add default via 10.20.20.1 dev eth1

# --- keep the leaf's ARP/ND entry for this host fresh (see lab 05 README) ---
pkill -f "lab-gw-keepalive-host3 -c" 2>/dev/null || true
setsid -f bash -c 'exec -a lab-gw-keepalive-host3 bash -c "while true; do ping -c1 -W1 10.20.20.1 >/dev/null 2>&1; sleep 20; done"' </dev/null >/dev/null 2>&1
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host3
