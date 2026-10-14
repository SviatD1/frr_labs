#!/bin/bash
# =====================================================================
# EVPN lab 16 - Service Insertion in EVPN using PBR
# node: fw   role: fw   variant: symmetric
# Generated file. Apply on the VM as root:   bash fw.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "16-service-insertion-pbr/symmetric/fw" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for fw (lab 16, variant symmetric)
lab-reset          # remove everything a previous lab created
set -x
# eth1: service VLAN 999
ip link set eth1 up
ip addr add 10.100.100.100/24 dev eth1
# eth2: back into VRF A on leaf3
ip link set eth2 up
ip addr add 172.16.32.1/24 dev eth2
ip link set eth1 mtu 1450
nft add table inet fw
nft add chain inet fw forward '{ type filter hook forward priority 0; policy accept; }'
nft add rule inet fw forward ct state established,related counter accept
nft add rule inet fw forward counter log prefix '"FW-NEW "' level info accept

# --- keep the leaf's ARP/ND entry for this host fresh (see lab 05 README) ---
pkill -f "lab-gw-keepalive-fw -c" 2>/dev/null || true
setsid -f bash -c 'exec -a lab-gw-keepalive-fw bash -c "while true; do ping -c1 -W1 10.100.100.1 >/dev/null 2>&1; sleep 20; done"' </dev/null >/dev/null 2>&1
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname fw
log syslog informational
service integrated-vtysh-config
!
ip route 10.10.10.0/24 172.16.32.3
ip route 10.20.20.0/24 172.16.32.3
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply fw
