#!/bin/bash
# =====================================================================
# EVPN lab 04 - EVPN Bridging Deep Dive: RD, RT, VNI, EVI, MAC-VRF, VLAN-Aware Bundle
# node: host6   role: host   variant: vni-mismatch
# Generated file. Apply on the VM as root:   bash host6.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "04-bridging-deep-dive/vni-mismatch/host6" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host6 (lab 04, variant vni-mismatch)
lab-reset          # remove everything a previous lab created
set -x

# --- host interface ---
ip link set eth1 address 00:bb:bb:bb:bb:bb
ip link set eth1 mtu 1450 up
ip addr add 10.10.10.20/24 dev eth1
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host6
