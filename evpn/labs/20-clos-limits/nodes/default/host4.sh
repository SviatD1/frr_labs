#!/bin/bash
# =====================================================================
# EVPN lab 20 - Calculating Clos Fabric Limits for Data Center Networks
# node: host4   role: host   variant: default
# Generated file. Apply on the VM as root:   bash host4.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "20-clos-limits/default/host4" > /etc/lab/id
echo "host" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for host4 (lab 20, variant default)
lab-reset          # remove everything a previous lab created
set -x

# --- host interface ---
ip link set eth1 address 00:dd:dd:dd:dd:dd
ip link set eth1 mtu 1500 up
ip addr add 10.30.30.40/24 dev eth1
ip route add default via 10.30.30.1 dev eth1

# --- keep the leaf's ARP/ND entry for this host fresh (see lab 05 README) ---
pkill -f "lab-gw-keepalive-host4 -c" 2>/dev/null || true
setsid -f bash -c 'exec -a lab-gw-keepalive-host4 bash -c "while true; do ping -c1 -W1 10.30.30.1 >/dev/null 2>&1; sleep 20; done"' </dev/null >/dev/null 2>&1
iperf3 -s -D
__LAB_NET__
chmod +x /etc/lab/net.sh

# 2) this node does not run FRR (plain Linux host)

# ---------------------------------------------------------------------
# helper files used in this lab
# ---------------------------------------------------------------------
install -d $(dirname /usr/local/bin/clos-calc)
cat > /usr/local/bin/clos-calc <<'__LAB_FILE__'
#!/usr/bin/env python3
"""Clos fabric calculator (folded 3-stage and 5-stage), as in the Sneaky Subnet video.

Examples:
  clos-calc --radix 64 --port 100 --server-port 25 --servers-per-rack 32 --uplinks 8
  clos-calc --radix 32 --port 400 --server-port 100 --oversub 3 --five-stage --super-radix 64
"""
import argparse, math

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--radix", type=int, default=64, help="ports per leaf/spine switch (at uplink speed)")
ap.add_argument("--port", type=float, default=100, help="fabric port speed, Gbit/s")
ap.add_argument("--server-port", type=float, default=25, help="server NIC speed, Gbit/s")
ap.add_argument("--leaf-down-ports", type=int, default=48, help="leaf server-facing ports")
ap.add_argument("--uplinks", type=int, default=0, help="leaf uplinks (0 = derive from --oversub)")
ap.add_argument("--oversub", type=float, default=1.0, help="target oversubscription down:up (1 = non-blocking)")
ap.add_argument("--servers-per-rack", type=int, default=0, help="limit servers per leaf (space/power)")
ap.add_argument("--five-stage", action="store_true")
ap.add_argument("--super-radix", type=int, default=64)
a = ap.parse_args()

down = a.leaf_down_ports if not a.servers_per_rack else min(a.leaf_down_ports, a.servers_per_rack)
down_bw = down * a.server_port
uplinks = a.uplinks or math.ceil(down_bw / a.oversub / a.port)
up_bw = uplinks * a.port
ratio = down_bw / up_bw
print(f"Leaf: {down} x {a.server_port:g}G down = {down_bw:g}G, {uplinks} x {a.port:g}G up = {up_bw:g}G  -> oversubscription {ratio:.2f}:1")
spines = uplinks                       # one uplink per spine (most common)
leaves = a.radix                       # every spine port goes to a leaf
print(f"3-stage: spines = leaf uplinks = {spines}, max leaves = spine radix = {leaves}")
print(f"         max servers = {leaves * down}, fabric bisection = {leaves * up_bw / 2:g}G")
if a.five_stage:
    # each spine splits its radix: half down to leaves, half up to super-spines (1:1)
    leaves_per_pod = a.radix // 2
    planes = spines
    pods = a.super_radix
    print(f"5-stage: spines use {a.radix // 2} ports down / {a.radix // 2} up, {planes} spine planes")
    print(f"         leaves per pod = {leaves_per_pod}, max pods = super-spine radix = {pods}")
    print(f"         super-spines per plane = {a.radix // 2}, total super-spines = {planes * (a.radix // 2)}")
    print(f"         max leaves = {pods * leaves_per_pod}, max servers = {pods * leaves_per_pod * down}")
__LAB_FILE__
chmod 755 /usr/local/bin/clos-calc

# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply host4
