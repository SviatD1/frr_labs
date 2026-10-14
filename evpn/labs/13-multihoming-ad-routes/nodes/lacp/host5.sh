#!/bin/bash
# =====================================================================
# EVPN lab 13 - EVPN Multihoming. Auto Discovery Routes. Fast Convergence. Aliasing.
# node: host5   role: host   variant: lacp
# Generated file. Apply on the VM as root:   bash host5.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "13-multihoming-ad-routes/lacp/host5" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host5 (lab 13, variant lacp)
lab-reset          # remove everything a previous lab created
set -x

# --- host interface ---
ip link set eth1 address 00:ee:ee:ee:ee:ee
ip link set eth1 mtu 1450 up
ip addr add 10.10.10.50/24 dev eth1
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# helper files used in this lab
# ---------------------------------------------------------------------
install -d $(dirname /usr/local/bin/lab-ping)
cat > /usr/local/bin/lab-ping <<'__LAB_FILE__'
#!/bin/bash
# continuous ping with timestamps; Ctrl-C prints the loss summary
# usage: lab-ping <dst> [interval]
exec ping -D -O -i ${2:-0.2} "$1"
__LAB_FILE__
chmod 755 /usr/local/bin/lab-ping

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host5
