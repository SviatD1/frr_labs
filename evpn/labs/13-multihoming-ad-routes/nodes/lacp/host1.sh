#!/bin/bash
# =====================================================================
# EVPN lab 13 - EVPN Multihoming. Auto Discovery Routes. Fast Convergence. Aliasing.
# node: host1   role: host   variant: lacp
# Generated file. Apply on the VM as root:   bash host1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "13-multihoming-ad-routes/lacp/host1" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host1 (lab 13, variant lacp)
lab-reset          # remove everything a previous lab created
set -x

# --- 802.3ad bond towards two leaves ---
ip link add bond0 type bond mode 802.3ad miimon 100 lacp_rate fast xmit_hash_policy layer3+4
ip link set eth1 down
ip link set eth1 master bond0
ip link set eth2 down
ip link set eth2 master bond0
ip link set bond0 address 00:aa:aa:aa:aa:aa
ip link set bond0 mtu 1450 up
ip link set eth1 up
ip link set eth2 up
ip addr add 10.10.10.10/24 dev bond0
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
lab-apply host1
