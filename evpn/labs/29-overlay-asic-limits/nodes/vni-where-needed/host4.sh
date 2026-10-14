#!/bin/bash
# =====================================================================
# EVPN lab 29 - Designing EVPN Overlay for Data Center. ASICs and their limits
# node: host4   role: host   variant: vni-where-needed
# Generated file. Apply on the VM as root:   bash host4.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "29-overlay-asic-limits/vni-where-needed/host4" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host4 (lab 29, variant vni-where-needed)
lab-reset          # remove everything a previous lab created
set -x

# --- host interface ---
ip link set eth1 address 00:dd:dd:dd:dd:dd
ip link set eth1 mtu 1450 up
ip addr add 10.20.0.40/16 dev eth1
ip route add default via 10.20.0.1 dev eth1

# --- keep the leaf's ARP/ND entry for this host fresh (see lab 05 README) ---
pkill -f "lab-gw-keepalive-host4 -c" 2>/dev/null || true
setsid -f bash -c 'exec -a lab-gw-keepalive-host4 bash -c "while true; do ping -c1 -W1 10.20.0.1 >/dev/null 2>&1; sleep 20; done"' </dev/null >/dev/null 2>&1
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# helper files used in this lab
# ---------------------------------------------------------------------
install -d $(dirname /usr/local/bin/mac-flood)
cat > /usr/local/bin/mac-flood <<'__LAB_FILE__'
#!/bin/bash
# Create N fake endpoints (macvlan interfaces) behind this host and make the leaf learn them.
# usage: mac-flood N [iface] [first-octets]    e.g. mac-flood 200 eth1 10.10      (IPs 10.10.<x>.<y>/16)
#        mac-flood clean
if [ "$1" = clean ]; then for d in $(ip -o link show type macvlan | awk -F'[ :@]+' '{print $2}'); do ip link del $d; done; exit; fi
n=${1:-100}; dev=${2:-eth1}; pfx=${3:-10.10}
gw=$(ip route show default | awk '{print $3; exit}')
id=$(hostname | tr -dc 0-9); id=${id:-9}
for k in $(seq 1 $n); do
  ip=$pfx.$((100 + id)).$k
  mac=$(printf '02:%02x:00:00:%02x:%02x' $id $((k / 256)) $((k % 256)))
  ip link add mv$k link $dev type macvlan mode bridge 2>/dev/null || continue
  ip link set mv$k address $mac up
  ip addr add $ip/32 dev mv$k
  arping -q -c 1 -I mv$k -s $ip $gw &
done
wait
echo "created $n endpoints on $dev ($pfx.$((100 + id)).1-$n)"
__LAB_FILE__
chmod 755 /usr/local/bin/mac-flood

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host4
