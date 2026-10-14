#!/usr/bin/env bash
# Install a lab FRR config on this node and (re)start FRR.
# Usage: apply-frr.sh <path/to/node.frr.conf>
# The first line of every *.frr.conf is "! daemons: ospfd bgpd ..." - those
# daemons are switched on in /etc/frr/daemons, all others off.
set -euo pipefail
conf="$1"
[ -f "$conf" ] || { echo "no such file: $conf"; exit 1; }

want=$(sed -n '1s/^! *daemons: *//p' "$conf")
for d in bgpd ospfd ospf6d ripd ripngd isisd pimd ldpd nhrpd eigrpd babeld sharpd pbrd bfdd fabricd vrrpd pathd; do
  if echo " $want " | grep -q " $d "; then v=yes; else v=no; fi
  sed -i "s/^${d}=.*/${d}=${v}/" /etc/frr/daemons
done

install -m 640 -o frr -g frr "$conf" /etc/frr/frr.conf
: > /etc/frr/vtysh.conf
chown frr:frr /etc/frr/vtysh.conf
systemctl restart frr
echo "FRR restarted with daemons: zebra staticd ${want}"
