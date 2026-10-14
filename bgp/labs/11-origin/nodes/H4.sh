#!/bin/bash
# 11-origin :: H4 setup script.
# Used automatically as cloud-init user-data by tools/lab.py, or paste it into
# the node's console as root (login root / lab) to (re)apply the START config.
hostnamectl set-hostname H4 2>/dev/null || hostname H4
sed -i '/127.0.1.1/d' /etc/hosts; echo '127.0.1.1 H4' >> /etc/hosts
mkdir -p /etc/lab
cat > /etc/lab/net.sh <<'LABEOF'
#!/bin/sh
# Linux network config for H4 (11-origin) - generated
# Rename NICs to eth0..ethN in PCI order if the image did not (net.ifnames=0 fallback)
if ! ip link show eth0 >/dev/null 2>&1; then
  i=0
  for d in $(for x in /sys/class/net/*; do [ -e $x/device ] && echo "$(readlink -f $x/device) ${x##*/}"; done | sort | awk '{print $2}'); do
    ip link set "$d" down; ip link set "$d" name eth$i; i=$((i+1))
  done
fi
sysctl -qw net.ipv4.conf.all.rp_filter=0
sysctl -qw net.ipv4.conf.default.rp_filter=0
ip link set lo up
ip link set eth0 up   # to R4
sysctl -qw net.ipv4.conf.eth0.rp_filter=0
ip addr replace 192.168.4.10/24 dev eth0
ip route replace default via 192.168.4.1
LABEOF
chmod +x /etc/lab/net.sh
systemctl enable lab-net.service >/dev/null 2>&1
/bin/sh /etc/lab/net.sh
systemctl disable --now frr >/dev/null 2>&1
echo 'H4 configured.'
