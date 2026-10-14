#!/bin/bash
# =====================================================================
# EVPN lab 35 - Multi-vendor EVPN design using Arista and FRR
# node: host1   role: host   variant: rfc5549-ibgp
# Generated file. Apply on the VM as root:   bash host1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "35-multivendor-frr/rfc5549-ibgp/host1" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host1 (lab 35, variant rfc5549-ibgp)
lab-reset          # remove everything a previous lab created
set -x

# --- host interface ---
ip link set eth1 address 00:aa:aa:aa:aa:aa
ip link set eth1 mtu 1450 up
ip addr add 10.10.10.10/24 dev eth1
ip route add default via 10.10.10.1 dev eth1

# --- keep the leaf's ARP/ND entry for this host fresh (see lab 05 README) ---
pkill -f "lab-gw-keepalive-host1 -c" 2>/dev/null || true
setsid -f bash -c 'exec -a lab-gw-keepalive-host1 bash -c "while true; do ping -c1 -W1 10.10.10.1 >/dev/null 2>&1; sleep 20; done"' </dev/null >/dev/null 2>&1
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host1
