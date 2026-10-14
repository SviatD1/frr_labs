#!/bin/bash
# =====================================================================
# EVPN lab 12 - EVPN Multihoming Deep Dive. Ethernet Segment Route. Designated Forwarder. Split Horizon.
# node: host1   role: host   variant: default
# Generated file. Apply on the VM as root:   bash host1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "12-multihoming-deep-dive/default/host1" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host1 (lab 12, variant default)
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
ip link add link bond0 name bond0.10 type vlan id 10
ip link set bond0.10 up
ip addr add 10.10.10.10/24 dev bond0.10
ip link add link bond0 name bond0.20 type vlan id 20
ip link set bond0.20 up
ip addr add 10.20.20.10/24 dev bond0.20
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host1
