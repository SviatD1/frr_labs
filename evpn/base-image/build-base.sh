#!/bin/bash
# =============================================================================
# build-base.sh - turn a fresh Debian 13 "nocloud" VM into the EVPN lab image.
# Run it ONCE on a VM that has Internet access (GNS3 NAT node on its first NIC):
#   python tools/gns3_lab.py run-script --project evpn-base --node <node> base-image/build-base.sh
# or paste it into the VM console. The VM powers off at the end.
# =============================================================================
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
log() { echo -e "\n### $*"; }

# ----------------------------------------------------------------------------
log "1/9 network for the build (DHCP on the first NIC)"
IF=$(ls /sys/class/net | grep -vE '^(lo|docker|br|vir)' | head -1)
ip link set "$IF" up
if ! ip route | grep -q '^default'; then
  (command -v dhclient >/dev/null && timeout 30 dhclient -1 "$IF") ||
  (command -v dhcpcd >/dev/null && timeout 30 dhcpcd -w -4 "$IF") ||
  (command -v networkctl >/dev/null && systemctl restart systemd-networkd && sleep 10) || true
fi
if ! ip route | grep -q '^default'; then
  echo "No DHCP lease - falling back to the GNS3 NAT defaults (192.168.122.0/24)"
  ip addr add 192.168.122.250/24 dev "$IF"; ip route add default via 192.168.122.1
fi
getent hosts deb.debian.org >/dev/null || echo "nameserver 1.1.1.1" > /etc/resolv.conf
ping -c1 -W3 deb.debian.org >/dev/null || { echo "!!! no Internet - connect the first NIC to a GNS3 NAT node"; exit 1; }

# ----------------------------------------------------------------------------
log "2/9 packages"
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release
CODENAME=$(lsb_release -sc)
curl -fsSL https://deb.frr.org/frr/keys.gpg -o /usr/share/keyrings/frrouting.gpg || true
echo "deb [signed-by=/usr/share/keyrings/frrouting.gpg] https://deb.frr.org/debian $CODENAME frr-stable" > /etc/apt/sources.list.d/frr.list
if ! apt-get update 2>&1 | tee /tmp/apt.log | grep -qE "deb.frr.org.*(404|NO_PUBKEY|not signed|Release)"; then
  echo "using the FRR project repository (frr-stable)"
else
  echo "FRR repository not usable for $CODENAME - using Debian's own frr package"
  rm -f /etc/apt/sources.list.d/frr.list; apt-get update
fi
apt-get install -y --no-install-recommends \
  frr frr-pythontools iproute2 ethtool bridge-utils tcpdump iperf3 iputils-ping iputils-arping \
  iputils-tracepath traceroute mtr-tiny ndisc6 nftables lldpd netcat-openbsd socat \
  python3 python3-scapy jq less vim-tiny bash-completion kmod procps psmisc

# ----------------------------------------------------------------------------
log "3/9 FRR daemons"
sed -i -E 's/^(bgpd|ospfd|ospf6d|isisd|pimd|pim6d|bfdd|pbrd|vrrpd|staticd)=no/\1=yes/' /etc/frr/daemons
grep -q '^frr_profile=' /etc/frr/daemons && sed -i 's/^frr_profile=.*/frr_profile="datacenter"/' /etc/frr/daemons || echo 'frr_profile="datacenter"' >> /etc/frr/daemons
grep -q 'service integrated-vtysh-config' /etc/frr/vtysh.conf 2>/dev/null || echo 'service integrated-vtysh-config' >> /etc/frr/vtysh.conf
printf 'frr defaults datacenter\nhostname lab\n' > /etc/frr/frr.conf
chown frr:frr /etc/frr/frr.conf
systemctl enable frr

# ----------------------------------------------------------------------------
log "4/9 kernel modules + sysctl"
printf 'vrf\nvxlan\nbonding\n8021q\nbridge\n' > /etc/modules-load.d/lab.conf
echo 'options bonding max_bonds=0' > /etc/modprobe.d/lab-bonding.conf

# ----------------------------------------------------------------------------
log "5/9 lab tools"
mkdir -p /etc/lab
cat > /usr/local/sbin/lab-reset <<'__LAB_EOF__'
#!/bin/bash
# lab-reset: bring the VM's networking back to a clean slate before a lab applies its config.
# Keeps lo and the physical ethN interfaces, deletes everything else a lab may have created.
nft flush ruleset 2>/dev/null
pkill -f lab-gw-keepalive 2>/dev/null
for d in $(ls /sys/class/net); do
  case "$d" in lo|eth[0-9]|eth[0-9][0-9]) ;; *) ip link del "$d" 2>/dev/null ;; esac
done
for d in $(ls /sys/class/net); do
  case "$d" in
    eth[0-9]|eth[0-9][0-9])
      ip link set "$d" nomaster 2>/dev/null
      ip link set "$d" down
      ip addr flush dev "$d"
      ip link set "$d" mtu 1500
      tc qdisc del dev "$d" root 2>/dev/null
      perm=$(ethtool -P "$d" 2>/dev/null | awk '{print $3}')
      [ -n "$perm" ] && [ "$perm" != "00:00:00:00:00:00" ] && ip link set "$d" address "$perm"
      ;;
  esac
done
ip addr flush dev lo scope global
ip -6 addr flush dev lo scope global
ip route flush table main proto static 2>/dev/null
ip route flush table main proto boot 2>/dev/null
ip -6 route flush table main proto boot 2>/dev/null
ip nexthop flush 2>/dev/null
sysctl -q --system >/dev/null 2>&1
true
__LAB_EOF__
chmod 755 /usr/local/sbin/lab-reset

cat > /usr/local/sbin/lab-apply <<'__LAB_EOF__'
#!/bin/bash
# lab-apply NODE: called at the end of every node script (labs/*/nodes/<variant>/<node>.sh)
node="$1"
kind=$(cat /etc/lab/kind 2>/dev/null || echo router)
echo "$node" > /etc/hostname
hostname "$node"
sed -i "/^127.0.1.1/d" /etc/hosts; echo "127.0.1.1 $node" >> /etc/hosts
if [ "$kind" = router ]; then fwd=1; else fwd=0; fi
cat > /etc/sysctl.d/95-lab-kind.conf <<EOT
net.ipv4.ip_forward=$fwd
net.ipv6.conf.all.forwarding=$fwd
net.ipv6.conf.default.forwarding=$fwd
EOT
systemctl stop frr 2>/dev/null
if bash /etc/lab/net.sh > /var/log/lab-net.log 2>&1; then
  echo "net.sh OK"
else
  echo "WARNING: net.sh reported errors - see /var/log/lab-net.log"; grep -iE "error|cannot|invalid|no such" /var/log/lab-net.log | head -5
fi
systemctl enable lab-net.service >/dev/null 2>&1
if [ "$kind" = router ]; then
  systemctl enable frr >/dev/null 2>&1
  systemctl restart frr
  sleep 2
  vtysh -c 'show running-config' >/dev/null 2>&1 || echo "WARNING: FRR not answering"
else
  systemctl disable --now frr >/dev/null 2>&1
fi
echo "LAB-APPLIED $(cat /etc/lab/id 2>/dev/null)"
__LAB_EOF__
chmod 755 /usr/local/sbin/lab-apply

cat > /usr/local/bin/lab-info <<'__LAB_EOF__'
#!/bin/bash
# lab-info: one-screen summary of this node
echo "== $(hostname): $(cat /etc/lab/id 2>/dev/null || echo 'no lab applied')"
ip -br link | grep -v '^lo' ; echo; ip -br addr | grep -v '^lo ' ; echo
ip route | head -20
if systemctl is-active -q frr; then
  echo; vtysh -c 'show bgp summary' 2>/dev/null | grep -vE '^$' | head -30
  vtysh -c 'show evpn vni' 2>/dev/null | head -20
fi
__LAB_EOF__
chmod 755 /usr/local/bin/lab-info

cat > /usr/local/bin/mcast-send <<'__LAB_EOF__'
#!/usr/bin/env python3
"""Send numbered UDP datagrams to a multicast group.
usage: mcast-send GROUP [-i IFACE] [-p PORT] [-t TTL] [-c COUNT] [-n INTERVAL]"""
import argparse, socket, struct, time, fcntl

def if_ip(name):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', name[:15].encode()))[20:24])

ap = argparse.ArgumentParser()
ap.add_argument("group"); ap.add_argument("-i", "--iface", default="eth1")
ap.add_argument("-p", "--port", type=int, default=5000); ap.add_argument("-t", "--ttl", type=int, default=16)
ap.add_argument("-c", "--count", type=int, default=0); ap.add_argument("-n", "--interval", type=float, default=1.0)
a = ap.parse_args()
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, a.ttl)
s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(if_ip(a.iface)))
i = 0
while not a.count or i < a.count:
    i += 1
    s.sendto(f"{socket.gethostname()} seq {i}".encode(), (a.group, a.port))
    print(f"sent seq {i} to {a.group}:{a.port} ttl {a.ttl}", flush=True)
    time.sleep(a.interval)
__LAB_EOF__
chmod 755 /usr/local/bin/mcast-send

cat > /usr/local/bin/mcast-recv <<'__LAB_EOF__'
#!/usr/bin/env python3
"""Join an (S,G) with IGMPv3 (or a *,G with IGMPv2) and print what arrives.
usage: mcast-recv GROUP [SOURCE] [-i IFACE] [-p PORT] [-c COUNT]"""
import argparse, socket, struct, fcntl, time

def if_ip(name):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', name[:15].encode()))[20:24])

ap = argparse.ArgumentParser()
ap.add_argument("group"); ap.add_argument("source", nargs="?")
ap.add_argument("-i", "--iface", default="eth1"); ap.add_argument("-p", "--port", type=int, default=5000)
ap.add_argument("-c", "--count", type=int, default=0)
a = ap.parse_args()
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setsockopt(socket.SOL_SOCKET, 25, a.iface.encode())   # SO_BINDTODEVICE
s.bind(("", a.port))
local = socket.inet_aton(if_ip(a.iface))
if a.source:
    IP_ADD_SOURCE_MEMBERSHIP = 39
    s.setsockopt(socket.IPPROTO_IP, IP_ADD_SOURCE_MEMBERSHIP,
                 socket.inet_aton(a.group) + local + socket.inet_aton(a.source))
    print(f"joined ({a.source},{a.group}) on {a.iface} (IGMPv3 SSM)", flush=True)
else:
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(a.group) + local)
    print(f"joined (*,{a.group}) on {a.iface}", flush=True)
n = 0
while True:
    data, src = s.recvfrom(2048)
    n += 1
    print(f"{time.strftime('%H:%M:%S')} from {src[0]}: {data.decode(errors='replace')}  (received {n})", flush=True)
    if a.count and n >= a.count:
        break
__LAB_EOF__
chmod 755 /usr/local/bin/mcast-recv

cat > /etc/systemd/system/lab-net.service <<'__LAB_EOF__'
[Unit]
Description=EVPN lab: Linux network configuration (/etc/lab/net.sh)
DefaultDependencies=no
After=systemd-udevd.service systemd-sysctl.service network-pre.target
Before=network.target frr.service
ConditionPathExists=/etc/lab/net.sh

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash /etc/lab/net.sh
StandardOutput=append:/var/log/lab-net.log
StandardError=append:/var/log/lab-net.log

[Install]
WantedBy=multi-user.target
__LAB_EOF__
chmod 644 /etc/systemd/system/lab-net.service

cat > /etc/sysctl.d/90-lab.conf <<'__LAB_EOF__'
# EVPN lab defaults (forwarding is set per node by lab-apply in 95-lab-kind.conf)
net.ipv4.conf.all.rp_filter=0
net.ipv4.conf.default.rp_filter=0
net.ipv4.tcp_l3mdev_accept=1
net.ipv4.udp_l3mdev_accept=1
net.ipv4.raw_l3mdev_accept=1
net.ipv4.fib_multipath_hash_policy=1
net.ipv6.fib_multipath_hash_policy=1
net.ipv6.conf.all.keep_addr_on_down=1
net.ipv6.conf.default.addr_gen_mode=0
net.ipv4.igmp_max_memberships=512
net.ipv4.conf.all.ignore_routes_with_linkdown=1
net.ipv6.conf.all.ignore_routes_with_linkdown=1
kernel.printk=3 4 1 3
__LAB_EOF__
chmod 644 /etc/sysctl.d/90-lab.conf

systemctl daemon-reload
systemctl enable lab-net.service

# ----------------------------------------------------------------------------
log "6/9 classic interface names (eth0, eth1, ...) + serial console"
mkdir -p /etc/default/grub.d
cat > /etc/default/grub.d/99-lab.cfg <<'EOT'
GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT net.ifnames=0 biosdevname=0 console=tty0 console=ttyS0,115200"
GRUB_TIMEOUT=1
GRUB_TERMINAL="console serial"
GRUB_SERIAL_COMMAND="serial --speed=115200"
EOT
update-grub
mkdir -p /etc/systemd/system/serial-getty@ttyS0.service.d
cat > /etc/systemd/system/serial-getty@ttyS0.service.d/autologin.conf <<'EOT'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --keep-baud 115200,57600,38400,9600 - $TERM
EOT
systemctl enable serial-getty@ttyS0.service

# ----------------------------------------------------------------------------
log "7/9 no automatic network management on the lab VMs (labs configure everything)"
rm -f /etc/systemd/network/*.network /etc/netplan/*.yaml 2>/dev/null
systemctl disable systemd-networkd.service systemd-networkd.socket systemd-networkd-wait-online.service 2>/dev/null
systemctl mask systemd-networkd-wait-online.service 2>/dev/null
[ -f /etc/network/interfaces ] && printf 'auto lo\niface lo inet loopback\n' > /etc/network/interfaces
rm -rf /etc/network/interfaces.d/* 2>/dev/null
systemctl disable --now apt-daily.timer apt-daily-upgrade.timer unattended-upgrades 2>/dev/null
systemctl disable lldpd 2>/dev/null   # enable per lab with: systemctl start lldpd
echo "export VTYSH_PAGER=cat" > /etc/profile.d/lab.sh
cat >> /root/.bashrc <<'EOT'
alias v='vtysh'
alias bgp='vtysh -c "show bgp summary"'
alias evpn='vtysh -c "show evpn vni"'
PS1='\h:\w# '
EOT
echo lab > /etc/hostname

# ----------------------------------------------------------------------------
log "8/9 clean up"
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
journalctl --vacuum-size=10M >/dev/null 2>&1
truncate -s0 /etc/machine-id
rm -f /var/lib/dbus/machine-id
fstrim -av 2>/dev/null || true

# ----------------------------------------------------------------------------
log "9/9 done - FRR $(dpkg-query -W -f='${Version}' frr). Powering off in 5 s."
log "Next: create the 'debian-frr' GNS3 template from this disk (see base-image/README.md)"
sync
(sleep 5; systemctl poweroff) &
exit 0
