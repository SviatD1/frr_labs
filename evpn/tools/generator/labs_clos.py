from gen import *
from labs_basics import HOSTMAC, BGP_UP, PING_OK


def shape(n, ifn, rate):
    n.sh(f"tc qdisc replace dev {ifn} root tbf rate {rate} burst 32kb latency 20ms")


def routed_leaf_hosts(lab, nodes, l, i, ports, hosts_start=1):
    """L3-only leaf: one /24 per leaf on a bridge with routed SVI."""
    l.comment("rack subnet: hosts bridged locally, leaf routes (no VXLAN)")
    l.sh("ip link add br0 type bridge", "ip link set br0 up", f"ip addr add 10.{i}0.{i}0.1/24 dev br0")
    for p in ports:
        l.sh(f"ip link set {p} master br0", f"ip link set {p} up")
    l.frr.iface("br0", "ip router isis 1", "isis passive")


IPERF_NOTE = """
`iperf3` is in the base image. Server: `iperf3 -s -D`. Client: `iperf3 -c <ip> -t 20` (TCP) or
`iperf3 -c <ip> -u -b 100M -t 20` (UDP, shows loss). Several parallel flows: `-P 4`.
"""


# ==========================================================================
# 18 Clos topology
# ==========================================================================
def lab18():
    lab = Lab(18, "clos-topology", "Clos / Leaf-Spine-Leaf Topology for EVPN Data Center", "WHt-zH8idDo", "27 min", """
The video is about the theory: crossbar switches, Charles Clos' 3-stage network, blocking,
rearrangeably vs strict-sense non-blocking. This lab turns it into something you can measure:
a 3-stage *folded* Clos (2 spines, 2 leaves) whose links are **shaped to 100 Mbit/s** with `tc`, so you
can create congestion on purpose and see when the fabric "blocks".
""")
    lab.diagram = """
         spine1          spine2          <- middle stage (both directions folded)
          |    \\        /    |
          |      \\    /      |              every link shaped to 100 Mbit/s
          |        \\/        |              (variant oversubscribed: uplinks 50 Mbit/s)
        leaf1             leaf2           <- ingress / egress stages
       e1    e2          e1    e2
     host1  host2      host3  host4
       10.10.10.0/24      10.20.20.0/24     (L3 only, IS-IS, ECMP)
    """
    for vname, up, desc in (("non-blocking", "100mbit", "2 x 100M down, 2 x 100M up per leaf (1:1)"),
                            ("oversubscribed", "50mbit", "2 x 100M down, 2 x 50M up per leaf (2:1)")):
        nodes = lab.variant(vname, desc, default=(vname == "non-blocking"))
        spines, leaves = std_fabric(lab, nodes, 2, [1, 2])
        for m, s in spines.items():
            s.comment("shape fabric links")
            for i in leaves:
                shape(s, f"eth{i}", up)
        for i, l in leaves.items():
            routed_leaf_hosts(lab, nodes, l, i, ["eth1", "eth2"])
            l.comment("shape links")
            for ifn in ("eth11", "eth12"):
                shape(l, ifn, up)
            for ifn in ("eth1", "eth2"):
                shape(l, ifn, "100mbit")
        for k in range(1, 5):
            li = 1 if k <= 2 else 2
            h = host(lab, nodes, f"host{k}", f"10.{li}0.{li}0.{10 * k}/24", f"10.{li}0.{li}0.1", HOSTMAC[k], mtu=1500)
            h.sh("tc qdisc replace dev eth1 root tbf rate 100mbit burst 32kb latency 20ms", "iperf3 -s -D")
    for t in (("leaf1", "eth1", "host1", "eth1"), ("leaf1", "eth2", "host2", "eth1"),
              ("leaf2", "eth1", "host3", "eth1"), ("leaf2", "eth2", "host4", "eth1")):
        lab.link(*t)
    for v in ("non-blocking", "oversubscribed"):
        lab.check(v, "host1", "ping -c 3 -W 1 10.20.20.30", PING_OK)
        lab.check(v, "leaf1", "ip route show 10.20.20.0/24", r"nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12")
    lab.check("non-blocking", "leaf1", "tc qdisc show dev eth11", r"tbf .*rate 100Mbit")
    lab.check("oversubscribed", "leaf1", "tc qdisc show dev eth11", r"tbf .*rate 50Mbit")
    lab.readme = r"""
## Theory refresher (from the video)

* **Crossbar**: N inputs x N outputs, N^2 crosspoints, non-blocking, doesn't scale.
* **Clos (1953)**: 3 stages - ingress (r switches of n inputs), middle (m switches), egress.
  * strict-sense non-blocking if **m >= 2n - 1** (a new call never needs re-arranging),
  * rearrangeably non-blocking if **m >= n** (may need to move existing calls).
* A leaf-spine fabric is a **folded** Clos: leaves are both ingress and egress stage, spines are the middle stage.
* Packet networks don't set up "calls" - flows are placed by **ECMP hashing**, so blocking shows up as
  *collisions*: two big flows hashed onto the same spine while the other spine idles (labs 20/21).

## What you will do

1. Check the shaping: `tc -s qdisc show dev eth11` on a leaf (rate, sent bytes, drops).
2. `iperf3 -c 10.20.20.30 -t 20` from host1: ~95 Mbit/s.
3. **Two flows** host1 -> host3 and host2 -> host4 at the same time. In `non-blocking` both should get ~95
   Mbit/s *if* they hash to different spines. Look at `tc -s qdisc show dev eth11/eth12` on leaf1 to see which
   uplink carried which flow. Re-run with different source ports (`iperf3 --cport 40001`, `--cport 40002`, ...)
   until you get a collision - both flows on one spine, ~47 Mbit/s each: that's "blocking" in a
   packet-switched Clos. (Kernel default hashing is L3-only - see lab 21 to switch to L4 hashing.)
4. Push `oversubscribed` (uplinks 50 Mbit): now even a perfect spread gives 2 x 50 Mbit for 2 x 100 Mbit
   of host demand - a 2:1 oversubscribed leaf. Measure it.

""" + IPERF_NOTE + r"""

## Linux notes

* `tc qdisc replace dev X root tbf rate 100mbit burst 32kb latency 20ms` - token bucket shaper on egress.
  Each side shapes its own egress, so a link is shaped in both directions.
* ECMP in the kernel: `ip route show 10.20.20.0/24` shows multiple `nexthop via` lines;
  `ip route get 10.20.20.30 from 10.10.10.10 ipproto tcp sport 40001 dport 5201` tells you which one a flow uses.
"""
    return lab


# ==========================================================================
# 19 Scaling Clos fabrics - 5-stage
# ==========================================================================
def lab19():
    lab = Lab(19, "scaling-clos", "Scaling Clos fabrics in Data Center", "fmRJkXP-ZZ4", "26 min", """
When one spine layer runs out of ports you add a stage: a **5-stage Clos** of pods, each pod a 3-stage
leaf-spine, interconnected by **super-spines**. This lab builds two pods plus a super-spine layer, runs
one EVPN domain over it (VLAN 10 stretched across pods) and recreates the **transit leaf** problem of a
3-stage fabric with a failed link.
""")
    lab.diagram = """
                    super1 (21.21.21.21)        super2 (22.22.22.22)    <- EVPN route reflectors
                   /   |    |    \\             /   |    |    \\
              spine1 spine2      spine3 spine4                         (each spine eth10->super1, eth11->super2)
               |  \\  /  |        |  \\  /  |
               |   \\/   |        |   \\/   |
              leaf1   leaf2     leaf3   leaf4
                |       |         |       |
              host1   host2     host3   host4       VLAN 10 / VNI 10010, 10.10.10.0/24
              ------ pod 1 ------  ------ pod 2 ------
    """
    nodes = lab.variant("default", "2 pods x (2 spines + 2 leaves) + 2 super-spines, IS-IS + iBGP EVPN (RR on super-spines)")
    supers = OrderedDict()
    for s in (1, 2):
        n = Node(f"super{s}", "router", "super")
        loopback(n, f"2{s}.2{s}.2{s}.2{s}")
        nodes[n.name] = n
        supers[s] = n
    spines = OrderedDict()
    for m in (1, 2, 3, 4):
        n = Node(f"spine{m}", "router", "spine")
        loopback(n, spine_lo(m))
        nodes[n.name] = n
        spines[m] = n
    leaves = OrderedDict()
    for i in (1, 2, 3, 4):
        n = Node(f"leaf{i}", "router", "leaf")
        loopback(n, leaf_lo(i))
        nodes[n.name] = n
        leaves[i] = n
    pod_spines = {1: (1, 2), 2: (3, 4)}
    isis_ifs = {n: [] for n in nodes}
    for i, l in leaves.items():
        pod = 1 if i <= 2 else 2
        for k, m in enumerate(pod_spines[pod]):
            s = spines[m]
            lif, sif = f"eth{11 + k}", f"eth{1 if i in (1, 3) else 2}"
            lab.link(s.name, sif, l.name, lif)
            addr(s, sif, f"10.{i}.{10 + m}.{10 + m}/24")
            addr(l, lif, f"10.{i}.{10 + m}.{i}/24")
            isis_ifs[s.name].append(sif)
            isis_ifs[l.name].append(lif)
    for m, s in spines.items():
        for k, (sid, sp) in enumerate(supers.items()):
            sif, pif = f"eth{10 + k}", f"eth{m}"
            lab.link(sp.name, pif, s.name, sif)
            addr(sp, pif, f"10.2{sid}.{m}.2{sid}/24")
            addr(s, sif, f"10.2{sid}.{m}.{m}/24")
            isis_ifs[s.name].append(sif)
            isis_ifs[sp.name].append(pif)
    for name, n in nodes.items():
        sysid = {"super1": 21, "super2": 22}.get(name) or (10 + int(name[-1]) if name.startswith("spine") else int(name[-1]))
        isis(n, isis_ifs[name], sysid)
    for s, sp in supers.items():
        evpn_rr_ibgp(sp, 65000, sp.lo4, [leaf_lo(i) for i in leaves])
    for i, l in leaves.items():
        l2_services(l, i, [(10, 10010, ["eth1"])])
        evpn_leaf_ibgp(l, 65000, leaf_lo(i), ["21.21.21.21", "22.22.22.22"])
        host(lab, nodes, f"host{i}", f"10.10.10.{10 * i}/24", mac=HOSTMAC[i])
        lab.link(l.name, "eth1", f"host{i}", "eth1")
    lab.positions = {f"super{s}": {"row": 0} for s in (1, 2)}
    for m in spines:
        lab.positions[f"spine{m}"] = {"row": 1}
    c = lambda *a: lab.check("default", *a)
    c("leaf1", "ip route show 3.3.3.3", r"nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12")
    c("spine1", "ip route show 3.3.3.3", r"nexthop via 10\.21\.1\.21[\s\S]*nexthop via 10\.22\.1\.22")
    c("host1", "ping -c 3 -W 1 10.10.10.40", PING_OK)
    c("leaf1", "vtysh -c 'show bgp l2vpn evpn summary'", r"21\.21\.21\.21\)?\s+4\s+65000[\s\S]*22\.22\.22\.22\)?\s+4\s+65000")
    lab.readme = r"""
## What you will learn

* 5-stage Clos = leaf -> spine -> **super-spine** -> spine -> leaf. Paths between pods: 2 (spines) x 2
  (super-spines) = 4 equal-cost paths per destination; check them with `ip route show 3.3.3.3` on leaf1
  and on spine1.
* Where to put the EVPN route reflectors in a multi-stage fabric (here: super-spines, a single EVPN domain).
* The **transit leaf** problem of 3-stage fabrics, and why a fabric needs *at least* 2 spines + careful failure analysis.

## Step by step

```bash
# leaf1
vtysh -c 'show isis topology'           # hop counts across pods
ip route show 3.3.3.3                   # 2-way ECMP inside the pod
# spine1
ip route show 3.3.3.3                   # 2-way ECMP via super1 / super2
# host1
traceroute -n 10.10.10.40               # it's L2 for the host - trace the VXLAN path on the leaves instead:
# leaf1 (while host1 pings host4)
tcpdump -ni eth11 udp port 4789 -c 5 ; tcpdump -ni eth12 udp port 4789 -c 5
```

**Transit leaf**: in pod 1 shut the spine1<->leaf1 link (`ip link set eth11 down` on leaf1). How does
spine1 now reach leaf1's loopback? `vtysh -c 'show ip route 1.1.1.1'` on spine1 ->
via super-spine -> spine2 -> leaf1 (5-stage saves you here). In a plain 3-stage fabric the only way
back would be spine1 -> leaf2 -> spine2 -> leaf1 - a **leaf becomes transit**, carrying traffic its
uplinks were never sized for. To see that version, also shut spine1's super-spine links
(`ip link set eth10 down; ip link set eth11 down` on spine1) and look again.

## Scaling notes from the video

* Fixed-form (single ASIC) switches: radix R ports. 3-stage max leaves = R (spine ports),
  max spines = leaf uplinks. 5-stage multiplies by the super-spine radix. Lab 20 has a calculator.
* Modular chassis are internally a Clos themselves (line cards = leaves, fabric modules = spines).
* "Single SKU" designs use one switch model for every role - simpler sparing, predictable limits.
"""
    return lab


# ==========================================================================
# 20 Calculating Clos limits
# ==========================================================================
CLOS_CALC = r'''
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
'''


def lab20():
    lab = Lab(20, "clos-limits", "Calculating Clos Fabric Limits for Data Center Networks", "j7mGuIrsU1k", "36 min", """
Oversubscription, incast and the arithmetic of fabric size. You get a small **calculator**
(`clos-calc`, on every node of this lab) to reproduce the video's tables, and a fabric where three senders
blast one receiver at once so you can watch **incast congestion** - drops in the egress queue of the
receiver's leaf port - with `tc -s qdisc`.
""")
    lab.diagram = """
                spine1            spine2          (all links shaped to 100 Mbit/s)
            /     |     \\       /    |     \\
        leaf1   leaf2   leaf3  (all leaves to both spines)
          |       |   \\      \\
        host1   host2 host3  host4
      receiver  -------- senders --------
     10.10.10.10 10.20.20.20 .30 10.30.30.40
    """
    nodes = lab.variant("default", "3 leaves, 2 spines, incast towards host1")
    spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3])
    for m, s in spines.items():
        for i in leaves:
            shape(s, f"eth{i}", "100mbit")
    hp = {1: ["eth1"], 2: ["eth1", "eth2"], 3: ["eth1"]}
    for i, l in leaves.items():
        routed_leaf_hosts(lab, nodes, l, i, hp[i])
        for ifn in ["eth11", "eth12"] + hp[i]:
            shape(l, ifn, "100mbit")
        l.files["/usr/local/bin/clos-calc"] = (CLOS_CALC, "755")
    hosts = [("host1", 1, "eth1", 10), ("host2", 2, "eth1", 20), ("host3", 2, "eth2", 30), ("host4", 3, "eth1", 40)]
    for k, (hn, li, lif, last) in enumerate(hosts):
        h = host(lab, nodes, hn, f"10.{li}0.{li}0.{last}/24", f"10.{li}0.{li}0.1", HOSTMAC[k + 1], mtu=1500)
        h.sh("iperf3 -s -D")
        h.files["/usr/local/bin/clos-calc"] = (CLOS_CALC, "755")
        lab.link(f"leaf{li}", lif, hn, "eth1")
    c = lambda *a: lab.check("default", *a)
    c("host2", "ping -c 3 -W 1 10.10.10.10", PING_OK)
    c("host1", "clos-calc --radix 64 --port 100 --server-port 25 --oversub 3", r"oversubscription 3\.\d+:1|oversubscription 2\.\d+:1")
    lab.extra_files["clos-calc.py"] = CLOS_CALC
    lab.readme = r"""
## What you will learn

* **Oversubscription** = server-facing bandwidth / uplink bandwidth of a leaf.
* Why even a 1:1 fabric congests: **incast** (many senders -> one receiver port) and **hash collisions** (lab 21).
* How to size a fabric: radix, port speeds, servers per rack, number of spines = number of leaf uplinks,
  max leaves = spine radix, and what a 5-stage design buys you. `clos-calc.py` (also in this folder) reproduces the
  video's formulas; run it with different inputs and fill the summary table yourself.

```bash
clos-calc --radix 64 --port 100 --server-port 25 --leaf-down-ports 48 --oversub 3
clos-calc --radix 32 --port 400 --server-port 100 --leaf-down-ports 24 --oversub 1 --five-stage --super-radix 64
```

## Incast experiment

```bash
# host2, host3, host4 at the same time (three consoles, or use & on one):
iperf3 -c 10.10.10.10 -u -b 90M -t 20 -p 5201      # host2
iperf3 -c 10.10.10.10 -u -b 90M -t 20 -p 5202      # host3 (start 2 more servers on host1: iperf3 -s -D -p 5202; -p 5203)
iperf3 -c 10.10.10.10 -u -b 90M -t 20 -p 5203      # host4
# leaf1 - the egress port towards the receiver is the bottleneck:
watch -n1 tc -s qdisc show dev eth1                # "dropped" climbs
```

270 Mbit/s of offered load into one 100 Mbit/s port: ~63 % loss, no matter how non-blocking the fabric is.
Repeat with TCP (`iperf3 -c ... -t 20` without `-u`): TCP backs off, the three flows share ~100 Mbit/s and
the drops are bursty - the classic incast pattern behind storage/AI "tail latency" problems.

## Things to think about (video chapters)

* Packet spraying vs flow hashing: spraying avoids collisions but reorders packets.
* "Don't forget about space": rack units, power and optics often limit servers-per-leaf before ports do.
"""
    return lab


# ==========================================================================
# 21 ECMP
# ==========================================================================
ECMP_TEST = r'''
#!/bin/bash
# Which uplink does each flow take?  usage: ecmp-test <dst> <src> [count]
dst=${1:-10.20.20.20}; src=${2:-10.10.10.10}; n=${3:-100}
for p in $(seq 1 $n); do
  ip route get $dst from $src iif eth1 ipproto tcp sport $((10000+p)) dport 80 2>/dev/null | grep -o 'dev eth[0-9]*'
done | sort | uniq -c
'''


def lab21():
    lab = Lab(21, "ecmp", "Why ECMP Algorithm is Critical in Data Center Networks", "LKp1RzZRMDg", "40 min", """
ECMP decides which spine carries each flow. You will look at Linux's hash policies (L3 vs L4),
measure the flow spread over four spines, watch flows **remap** when a path disappears (modulo-style
hashing) and fix that with **resilient nexthop groups** (hash buckets) - exactly the demo in the video.
""", ref="ecmp")
    lab.diagram = """
          spine1     spine2     spine3     spine4
            |  \\       |  \\     /  |      /  |
            |   \\______|___\\___/___|_____/   |      every leaf connects to every spine
            |          |    \\ /    |         |      leaf eth11..eth14 -> spine1..4
          leaf1 ------------X------------- leaf2
            |eth1                           |eth1
          host1 10.10.10.10            host2 10.20.20.20
    """
    for vname, pol, desc in (("l3-hash", 0, "fib_multipath_hash_policy=0 (src/dst IP only)"),
                             ("l4-hash", 1, "fib_multipath_hash_policy=1 (5-tuple)")):
        nodes = lab.variant(vname, desc, default=(vname == "l4-hash"))
        spines, leaves = std_fabric(lab, nodes, 4, [1, 2])
        for i, l in leaves.items():
            l.adapters = 15
            routed_leaf_hosts(lab, nodes, l, i, ["eth1"])
            l.comment("ECMP hash policy")
            l.sh(f"sysctl -w net.ipv4.fib_multipath_hash_policy={pol}")
            l.files["/usr/local/bin/ecmp-test"] = (ECMP_TEST, "755")
        host(lab, nodes, "host1", "10.10.10.10/24", "10.10.10.1", HOSTMAC[1], mtu=1500)
        host(lab, nodes, "host2", "10.20.20.20/24", "10.20.20.1", HOSTMAC[2], mtu=1500)
    lab.link("leaf1", "eth1", "host1", "eth1")
    lab.link("leaf2", "eth1", "host2", "eth1")
    for v, pol in (("l3-hash", 0), ("l4-hash", 1)):
        lab.check(v, "leaf1", "ip route show 10.20.20.0/24", r"(nexthop via[\s\S]*){4}")
        lab.check(v, "leaf1", "sysctl net.ipv4.fib_multipath_hash_policy", rf"= {pol}")
        lab.check(v, "host1", "ping -c 3 -W 1 10.20.20.20", PING_OK)
    lab.check("l4-hash", "leaf1", "ecmp-test 10.20.20.20 10.10.10.10 64 | wc -l", r"^\s*4\s*$")
    lab.check("l3-hash", "leaf1", "ecmp-test 10.20.20.20 10.10.10.10 64 | wc -l", r"^\s*1\s*$")
    lab.readme = r"""
## What you will learn

* Linux ECMP knobs: `net.ipv4.fib_multipath_hash_policy` (0 = L3, 1 = L4, 2 = L3 inner for tunnels, 3 = custom
  fields via `fib_multipath_hash_fields`) - same for IPv6 under `net.ipv6.*`.
* How to ask the kernel which path a flow takes: `ip route get <dst> from <src> iif eth1 ipproto tcp sport X dport Y`.
* **Static hashing** = hash mod N. Remove one path and most flows move (*remapping*) - bad for stateful
  middleboxes and for TCP (reordering).
* **Resilient hashing**: a nexthop group with buckets (`type resilient buckets 128`) - when a member
  fails, only *its* buckets move.

## Step by step

```bash
# leaf1
ip route show 10.20.20.0/24                # 4 nexthops
ecmp-test 10.20.20.20 10.10.10.10 100      # how 100 TCP flows spread over eth11..eth14
sysctl net.ipv4.fib_multipath_hash_policy
```

In `l3-hash` all 100 flows (same src/dst IP) land on **one** uplink. Push `l4-hash`: ~25 per uplink.
Try `sysctl -w net.ipv4.fib_multipath_hash_policy=3` with
`sysctl -w net.ipv4.fib_multipath_hash_fields=0x0037` (custom field set) and compare.

## Remapping vs resilient hashing (manual, same as the author's `commands.txt`)

```bash
# leaf1: record where 20 flows go
ecmp-test 10.20.20.20 10.10.10.10 20 > /tmp/before   # (or run the loop without | uniq -c to keep per-flow lines)
ip link set eth14 down; sleep 2
ecmp-test 10.20.20.20 10.10.10.10 20 > /tmp/after    # compare per-flow: many flows changed uplink, not just eth14's
ip link set eth14 up

# resilient group, built by hand for a test prefix
ip nexthop add id 101 via 10.1.11.11 dev eth11
ip nexthop add id 102 via 10.1.12.12 dev eth12
ip nexthop add id 103 via 10.1.13.13 dev eth13
ip nexthop add id 104 via 10.1.14.14 dev eth14
ip nexthop add id 1000 group 101/102/103/104 type resilient buckets 128 idle_timer 60 unbalanced_timer 300
ip route add 10.99.99.0/24 nhid 1000
ip nexthop bucket show id 1000 | head          # bucket -> nexthop map
ip link set eth14 down; ip nexthop bucket show id 1000 | awk '{print $NF}' | sort | uniq -c
```

Only the buckets that pointed at eth14 are reassigned. (FRR itself installs normal nexthop groups;
resilient groups are a kernel feature you configure directly or via `nexthop-group` + `resilient buckets` in FRR's `sharpd`/`pbrd` configs on recent versions.)

Note the leaves here have **15 adapters** (eth0-eth14) because of the four uplinks eth11-eth14.
"""
    return lab


# ==========================================================================
# 22 High level design approach
# ==========================================================================
DESIGN_PY = r'''
#!/usr/bin/env python3
"""
Design -> config: edit DESIGN below, run `python design.py`, and a new lab folder
(labs/22-design-your-fabric-custom) is generated with GNS3 topology + node scripts.
Then:  python tools\gns3_lab.py up labs\22-design-your-fabric-custom
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "generator"))
from labs_clos import build_design
from gen import emit

DESIGN = {
    "name": "custom",
    "spines": 2,             # number of spines (= uplinks per leaf)
    "leaves": 4,             # number of leaves (<= 10 with the default 13 adapters on spines)
    "underlay": "isis",      # isis | ospf
    "asn": 65000,
    "vlans": {10: "10.10.10.1/24", 20: "10.20.20.1/24"},   # VLAN -> anycast gateway
    "vrf": "PROD",           # tenant VRF (symmetric IRB, L3VNI 1000)
    "hosts_per_leaf": 1,     # host i on leaf j gets VLAN (list order, round robin)
}

if __name__ == "__main__":
    lab = build_design(DESIGN)
    emit(lab, ROOT)
    print("generated", os.path.join(ROOT, "labs", lab.dirname))
'''


def build_design(D):
    lab = Lab(22, "design-your-fabric" + ("" if D["name"] == "default" else "-" + D["name"]),
              "High-Level Approach to Designing Data Center Networks", "JtKccP5JYHI", "12 min", """
Design starts from requirements, not from someone else's config. This lab is a **design worksheet plus a
config generator**: you write the decisions down (`design.py`), the generator renders a complete GNS3 lab
(underlay, overlay, VLANs, VRF, hosts) from them. Change a decision, regenerate, compare.
""")
    nodes = lab.variant("default", f"{D['spines']} spines, {D['leaves']} leaves, {D['underlay']} underlay, iBGP EVPN RR on spines")
    spines, leaves = std_fabric(lab, nodes, D["spines"], list(range(1, D["leaves"] + 1)), underlay=D["underlay"])
    std_overlay(spines, leaves, D["asn"])
    vl = list(D["vlans"].items())
    hk = 0
    for i, l in leaves.items():
        ports = {}
        for p in range(D["hosts_per_leaf"]):
            hk += 1
            v, gw = vl[(hk - 1) % len(vl)]
            ports.setdefault(v, []).append(f"eth{p + 1}")
            net = gw.split("/")[0].rsplit(".", 1)[0]
            host(lab, nodes, f"host{hk}", f"{net}.{100 + hk}/{gw.split('/')[1]}", gw.split("/")[0],
                 f"00:00:00:00:{i:02x}:{hk:02x}")
            lab.link(l.name, f"eth{p + 1}", f"host{hk}", "eth1")
        l2_services(l, i, [(v, 10000 + v, ports.get(v, [])) for v, _ in vl])
        vrf_dev(l, D["vrf"], 1001)
        for v, gw in vl:
            svi(l, v, gw, vrf=D["vrf"])
        l3vni(l, D["vrf"], 1000, 4001, leaf_lo(i))
        leaf_overlay(l, i, spines, D["asn"])
        vrf_evpn(l, D["asn"], leaf_lo(i), D["vrf"])
    lab.check("default", "host1", f"ping -c 3 -W 1 {vl[0][1].split('/')[0]}", PING_OK)
    if hk >= 2:
        lab.check("default", "host1", "ping -c 3 -W 1 " + f"{vl[1 % len(vl)][1].split('/')[0].rsplit('.', 1)[0]}.{102}", PING_OK)
    lab.extra_files["design.py"] = DESIGN_PY
    lab.readme = r"""
## The worksheet (from the video)

Answer these *before* touching a config. Write the answers next to the matching key in `design.py`.

| Question | Typical options | Drives |
|---|---|---|
| Business goal - what must the network enable? | VM mobility, bare-metal K8s, AI/storage, multi-tenant | everything below |
| How many servers / racks today, in 3 years? | | leaves, spines, 3- vs 5-stage (labs 18-20) |
| Server NIC speed, dual-homing? | 25/100G, LACP/EVPN-MH | leaf model, MH (labs 11-13) |
| Do workloads need L2 stretched? | yes/no/some | L2VNI vs L3-only (lab 33) |
| Tenants / VRFs, inter-VRF policy? | | VRFs, service insertion (labs 14-16) |
| External connectivity | BGP/OSPF, how many borders | labs 07-09 |
| Underlay protocol | IS-IS / OSPF / eBGP / iBGP | labs 23-28 |
| Addressing | numbered /31, unnumbered, IPv6 LLA | lab 23 |
| Overlay control plane | iBGP+RR / eBGP | labs 25-27, 29-32 |
| Automation, monitoring, vendor diversity | | lab 35 |

RFC 7938 ("Use of BGP for Routing in Large-Scale Data Centers") is a great example of a design document that
starts from requirements and explains each trade-off - read it once.

## Use the generator

```powershell
cd evpn\labs\22-design-your-fabric
notepad design.py          # change spines/leaves/underlay/VLANs/...
python design.py           # -> labs\22-design-your-fabric-custom\
python ..\..\tools\gns3_lab.py up ..\22-design-your-fabric-custom
```

The prebuilt default (this folder) is 2 spines, 4 leaves, IS-IS, VLAN 10/20, VRF PROD with symmetric IRB.
The generator code lives in `tools/generator/` - it's the same code that produced every lab in this course,
so it is also a reference for "how would I template this?".
"""
    return lab


def lab22():
    return build_design({"name": "default", "spines": 2, "leaves": 4, "underlay": "isis", "asn": 65000,
                         "vlans": {10: "10.10.10.1/24", 20: "10.20.20.1/24"}, "vrf": "PROD", "hosts_per_leaf": 1})


LABS = [lab18, lab19, lab20, lab21, lab22]
