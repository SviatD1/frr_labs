#!/bin/bash
# =====================================================================
# EVPN lab 26 - BGP Path Hunting / Path Exploration in Data Center. BGP MRAI
# node: leaf3   role: leaf   variant: unique-asn-mrai5
# Generated file. Apply on the VM as root:   bash leaf3.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "26-bgp-path-hunting/unique-asn-mrai5/leaf3" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf3 (lab 26, variant unique-asn-mrai5)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 3.3.3.3/32 dev lo

# --- uplinks ---
ip link set eth11 up
ip addr add 10.3.11.3/24 dev eth11
ip link set eth12 up
ip addr add 10.3.12.3/24 dev eth12
__LAB_NET__
chmod +x /etc/lab/net.sh

# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
frr defaults datacenter
hostname leaf3
log syslog informational
service integrated-vtysh-config
!
log syslog debugging
!
router bgp 65003
 bgp router-id 3.3.3.3
 no bgp ebgp-requires-policy
 bgp bestpath as-path multipath-relax
 neighbor SPINES peer-group
 neighbor SPINES remote-as external
 neighbor SPINES advertisement-interval 5
 neighbor 10.3.11.11 peer-group SPINES
 neighbor 10.3.12.12 peer-group SPINES
 !
 address-family ipv4 unicast
  network 3.3.3.3/32
 exit-address-family
exit
!
end
__LAB_FRR__

# ---------------------------------------------------------------------
# helper files used in this lab
# ---------------------------------------------------------------------
install -d $(dirname /usr/local/bin/bgp-updates)
cat > /usr/local/bin/bgp-updates <<'__LAB_FILE__'
#!/bin/bash
# Print BGP UPDATE messages received per neighbor.  usage: bgp-updates [reset]
[ "$1" = reset ] && vtysh -c 'clear bgp * soft' >/dev/null
vtysh -c 'show bgp neighbors' | awk '/^BGP neighbor is/{n=$4} /Updates:/{print n, "sent", $2, "rcvd", $3}'
__LAB_FILE__
chmod 755 /usr/local/bin/bgp-updates

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply leaf3
