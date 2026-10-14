#!/bin/bash
# =====================================================================
# EVPN lab 12 - EVPN Multihoming Deep Dive. Ethernet Segment Route. Designated Forwarder. Split Horizon.
# node: host4   role: host   variant: default
# Generated file. Apply on the VM as root:   bash host4.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "12-multihoming-deep-dive/default/host4" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host4 (lab 12, variant default)
lab-reset          # remove everything a previous lab created
set -x

# --- host interface ---
ip link set eth1 address 00:dd:dd:dd:dd:dd
ip link set eth1 mtu 1450 up
ip addr add 10.10.10.40/24 dev eth1
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host4
