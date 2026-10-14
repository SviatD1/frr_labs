#!/bin/bash
# =====================================================================
# EVPN lab 01 - EVPN Fundamentals
# node: sw1   role: switch   variant: default
# Generated file. Apply on the VM as root:   bash sw1.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "01-evpn-fundamentals/default/sw1" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for sw1 (lab 01, variant default)
lab-reset          # remove everything a previous lab created
set -x

# --- classic 802.1D bridge with the kernel STP implementation ---
ip link add br0 type bridge stp_state 1 priority 4096
ip link set br0 up
ip link set eth1 master br0
ip link set eth1 up
ip link set eth2 master br0
ip link set eth2 up
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname sw1
log syslog informational
service integrated-vtysh-config
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply sw1
