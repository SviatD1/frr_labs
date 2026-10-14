#!/bin/bash
# =====================================================================
# EVPN lab 34 - IPv6 Endpoints in EVPN
# node: host3   role: host   variant: static
# Generated file. Apply on the VM as root:   bash host3.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "34-ipv6-endpoints/static/host3" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host3 (lab 34, variant static)
lab-reset          # remove everything a previous lab created
set -x

# --- host interface ---
ip link set eth1 address 00:cc:cc:cc:cc:cc
ip link set eth1 mtu 1450 up
ip addr add 10.20.20.30/24 dev eth1
ip -6 addr add fd00:20::30/64 dev eth1 nodad
ip route add default via 10.20.20.1 dev eth1
ip -6 route add default via fd00:20::1 dev eth1

# --- keep the leaf's ARP/ND entry for this host fresh (see lab 05 README) ---
pkill -f "lab-gw-keepalive-host3 -c" 2>/dev/null || true
setsid -f bash -c 'exec -a lab-gw-keepalive-host3 bash -c "while true; do ping -c1 -W1 10.20.20.1 >/dev/null 2>&1; ping -c1 -W1 fd00:20::1 >/dev/null 2>&1; sleep 20; done"' </dev/null >/dev/null 2>&1
sysctl -w net.ipv6.conf.eth1.accept_ra=0
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host3
