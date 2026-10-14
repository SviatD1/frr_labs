#!/bin/bash
# 29-bgp-in-one-minute :: R3 setup script.
# Used automatically as cloud-init user-data by tools/lab.py, or paste it into
# the node's console as root (login root / lab) to (re)apply the START config.
hostnamectl set-hostname R3 2>/dev/null || hostname R3
sed -i '/127.0.1.1/d' /etc/hosts; echo '127.0.1.1 R3' >> /etc/hosts
mkdir -p /etc/lab
cat > /etc/lab/net.sh <<'LABEOF'
#!/bin/sh
# Linux network config for R3 (29-bgp-in-one-minute) - generated
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
ip addr replace 3.3.3.3/32 dev lo
ip link set eth0 up   # to R2
sysctl -qw net.ipv4.conf.eth0.rp_filter=0
ip addr replace 10.0.23.3/24 dev eth0
ip link set eth1 up   # LAN to H3
sysctl -qw net.ipv4.conf.eth1.rp_filter=0
ip addr replace 192.168.3.1/24 dev eth1
LABEOF
chmod +x /etc/lab/net.sh
systemctl enable lab-net.service >/dev/null 2>&1
/bin/sh /etc/lab/net.sh
cat > /etc/frr/frr.conf <<'LABEOF'
frr defaults traditional
hostname R3
log syslog informational
service integrated-vtysh-config
!
! empty: speed-run time
!
line vty
!
end
LABEOF
chown frr:frr /etc/frr/frr.conf
systemctl enable frr >/dev/null 2>&1
systemctl restart frr
echo 'R3 configured. Run: vtysh'
