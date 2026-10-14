#!/bin/bash
# =====================================================================
# EVPN lab 13 - EVPN Multihoming. Auto Discovery Routes. Fast Convergence. Aliasing.
# node: host6   role: host   variant: lacp
# Generated file. Apply on the VM as root:   bash host6.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "13-multihoming-ad-routes/lacp/host6" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host6 (lab 13, variant lacp)
lab-reset          # remove everything a previous lab created
set -x

# --- host interface ---
ip link set eth1 address 00:ff:ff:ff:ff:ff
ip link set eth1 mtu 1450 up
ip addr add 10.10.10.60/24 dev eth1
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host6
