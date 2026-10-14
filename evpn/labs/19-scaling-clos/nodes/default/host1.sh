#!/bin/bash
# =====================================================================
# EVPN lab 19 - Scaling Clos fabrics in Data Center
# node: host1   role: host   variant: default
# Generated file. Apply on the VM as root:   bash host1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "19-scaling-clos/default/host1" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host1 (lab 19, variant default)
lab-reset          # remove everything a previous lab created
set -x

# --- host interface ---
ip link set eth1 address 00:aa:aa:aa:aa:aa
ip link set eth1 mtu 1450 up
ip addr add 10.10.10.10/24 dev eth1
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host1
