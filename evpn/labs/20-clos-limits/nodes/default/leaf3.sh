#!/bin/bash
# =====================================================================
# EVPN lab 20 - Calculating Clos Fabric Limits for Data Center Networks
# node: leaf3   role: leaf   variant: default
# Generated file. Apply on the VM as root:   bash leaf3.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "20-clos-limits/default/leaf3" > /etc/lab/id
echo "router" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for leaf3 (lab 20, variant default)
lab-reset          # remove everything a previous lab created
set -x

# --- loopback (router-id / VTEP source) ---
ip addr add 3.3.3.3/32 dev lo

# --- uplinks to spines ---
ip link set eth11 up
ip addr add 10.3.11.3/24 dev eth11
ip link set eth12 up
ip addr add 10.3.12.3/24 dev eth12

# --- rack subnet: hosts bridged locally, leaf routes (no VXLAN) ---
ip link add br0 type bridge
ip link set br0 up
ip addr add 10.30.30.1/24 dev br0
ip link set eth1 master br0
ip link set eth1 up
tc qdisc replace dev eth11 root tbf rate 100mbit burst 32kb latency 20ms
tc qdisc replace dev eth12 root tbf rate 100mbit burst 32kb latency 20ms
tc qdisc replace dev eth1 root tbf rate 100mbit burst 32kb latency 20ms
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
interface eth11
 ip router isis 1
 isis network point-to-point
exit
!
interface eth12
 ip router isis 1
 isis network point-to-point
exit
!
interface lo
 ip router isis 1
 isis passive
exit
!
interface br0
 ip router isis 1
 isis passive
exit
!
router isis 1
 net 49.0001.0000.0000.0003.00
 is-type level-2-only
 lsp-gen-interval 1
 spf-interval 1
exit
!
end
__LAB_FRR__

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
lab-apply leaf3
