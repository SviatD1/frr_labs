#!/bin/bash
# =====================================================================
# EVPN lab 14 - Service Insertion in EVPN. VRF Sandwich
# node: fw   role: fw   variant: as-override
# Generated file. Apply on the VM as root:   bash fw.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "14-service-insertion-vrf-sandwich/as-override/fw" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for fw (lab 14, variant as-override)
lab-reset          # remove everything a previous lab created
set -x
# eth1: inside  (VRF A)
ip link set eth1 up
ip addr add 172.16.31.1/24 dev eth1
# eth2: outside (VRF B)
ip link set eth2 up
ip addr add 172.16.32.1/24 dev eth2

# --- stateful 'firewall' - counters show the steered traffic ---
nft add table inet fw
nft add chain inet fw forward '{ type filter hook forward priority 0; policy accept; }'
nft add rule inet fw forward ct state established,related counter accept
nft add rule inet fw forward counter log prefix '"FW-NEW "' level info accept
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
router bgp 100
 bgp router-id 172.16.31.1
 no bgp ebgp-requires-policy
 neighbor 172.16.31.3 remote-as 65000
 neighbor 172.16.31.3 solo
 neighbor 172.16.32.3 remote-as 65000
 neighbor 172.16.32.3 solo
 !
 address-family ipv4 unicast
  neighbor 172.16.31.3 as-override
  neighbor 172.16.32.3 as-override
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply fw
