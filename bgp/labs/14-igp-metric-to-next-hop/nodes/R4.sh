#!/bin/bash
# 14-igp-metric-to-next-hop :: R4 setup script.
# Used automatically as cloud-init user-data by tools/lab.py, or paste it into
# the node's console as root (login root / lab) to (re)apply the START config.
hostnamectl set-hostname R4 2>/dev/null || hostname R4
sed -i '/127.0.1.1/d' /etc/hosts; echo '127.0.1.1 R4' >> /etc/hosts
mkdir -p /etc/lab
cat > /etc/lab/net.sh <<'LABEOF'
#!/bin/sh
# Linux network config for R4 (14-igp-metric-to-next-hop) - generated
# Rename NICs to eth0..ethN in PCI order if the image did not (net.ifnames=0 fallback)
if ! ip link show eth0 >/dev/null 2>&1; then
  i=0
  for d in $(for x in /sys/class/net/*; do [ -e $x/device ] && echo "$(readlink -f $x/device) ${x##*/}"; done | sort | awk '{print $2}'); do
    ip link set "$d" down; ip link set "$d" name eth$i; i=$((i+1))
  done
fi
sysctl -qw net.ipv4.ip_forward=1
sysctl -qw net.ipv6.conf.all.forwarding=1 2>/dev/null
sysctl -qw net.ipv4.conf.all.rp_filter=0
sysctl -qw net.ipv4.conf.default.rp_filter=0
ip link set lo up
ip addr replace 4.4.4.4/32 dev lo
ip link set eth0 up   # to R2
sysctl -qw net.ipv4.conf.eth0.rp_filter=0
ip addr replace 10.0.24.4/24 dev eth0
ip link set eth1 up   # to R3
sysctl -qw net.ipv4.conf.eth1.rp_filter=0
ip addr replace 10.0.34.4/24 dev eth1
ip link set eth2 up   # LAN to H4
sysctl -qw net.ipv4.conf.eth2.rp_filter=0
ip addr replace 192.168.4.1/24 dev eth2
LABEOF
chmod +x /etc/lab/net.sh
systemctl enable lab-net.service >/dev/null 2>&1
/bin/sh /etc/lab/net.sh
cat > /etc/frr/frr.conf <<'LABEOF'
frr defaults traditional
hostname R4
log syslog informational
service integrated-vtysh-config
!
router bgp 200
 bgp router-id 4.4.4.4
 no bgp ebgp-requires-policy
 neighbor 10.0.24.2 remote-as 100
 neighbor 10.0.34.3 remote-as 100
 !
 address-family ipv4 unicast
  network 192.168.4.0/24
 exit-address-family
exit
!
line vty
!
end
LABEOF
chown frr:frr /etc/frr/frr.conf
systemctl enable frr >/dev/null 2>&1
systemctl restart frr
echo 'R4 configured. Run: vtysh'
