from gen import *
from labs_basics import HOSTMAC, BGP_UP, PING_OK

ES_SYSMAC = "44:38:39:ff:ff:01"


def es_bond(l, bond, members, es, sysmac=ES_SYSMAC, vlans=(10,), trunk=False, df_pref=None, lacp=True):
    """Multihomed bond on a leaf. es = int (type-3 ESI from sys-mac) or 10-byte string (type-0 ESI)."""
    l.comment(f"{bond}: EVPN multihomed {'LACP ' if lacp else ''}bond (ES {es})")
    mode = "802.3ad miimon 100 lacp_rate fast min_links 1 ad_actor_system " + sysmac if lacp else "balance-xor miimon 100"
    l.sh(f"ip link add {bond} type bond mode {mode}")
    for m in members:
        l.sh(f"ip link set {m} down", f"ip link set {m} master {bond}")
    l.sh(f"ip link set {bond} master br0")
    if trunk:
        for v in vlans:
            l.sh(f"bridge vlan add dev {bond} vid {v}")
    else:
        l.sh(f"bridge vlan add dev {bond} vid {vlans[0]} pvid untagged")
    l.sh(f"ip link set {bond} up")
    for m in members:
        l.sh(f"ip link set {m} up")
    lines = [f"evpn mh es-id {es}"]
    if isinstance(es, int):
        lines.append(f"evpn mh es-sys-mac {sysmac}")
    if df_pref:
        lines.append(f"evpn mh es-df-pref {df_pref}")
    l.frr.iface(bond, *lines)


def mh_uplinks(l, ifs=("eth11", "eth12")):
    for i in ifs:
        l.frr.iface(i, "evpn mh uplink")
    l.frr.line("evpn mh startup-delay 10")


def bond_host(lab, nodes, name, mac, members=("eth1", "eth2"), ips=(), gw=None, vlans=None,
              mode="802.3ad", role="host"):
    h = Node(name, "host", role)
    h.comment(f"{mode} bond towards two leaves")
    opts = {"802.3ad": "802.3ad miimon 100 lacp_rate fast xmit_hash_policy layer3+4",
            "active-backup": "active-backup miimon 100 primary eth1",
            "balance-xor": "balance-xor miimon 100 xmit_hash_policy layer3+4"}[mode]
    h.sh(f"ip link add bond0 type bond mode {opts}")
    for m in members:
        h.sh(f"ip link set {m} down", f"ip link set {m} master bond0")
    h.sh(f"ip link set bond0 address {mac}", "ip link set bond0 mtu 1450 up")
    for m in members:
        h.sh(f"ip link set {m} up")
    if vlans:
        for v, ip in zip(vlans, ips):
            h.sh(f"ip link add link bond0 name bond0.{v} type vlan id {v}", f"ip link set bond0.{v} up",
                 f"ip addr add {ip} dev bond0.{v}")
    else:
        for ip in ips:
            h.sh(f"ip addr add {ip} dev bond0")
    if gw:
        h.sh(f"ip route add default via {gw}")
        src = ips[0].split("/")[0]
        # also ARP the gateway through *each* bond member, so both ES leaves learn our IP
        gw_keepalive(h, [gw], [f"arping -q -c1 -I {m} -s {src} {gw} >/dev/null 2>&1" for m in members])
    h.notes.append(", ".join(list(ips) + [mac, f"bond {mode}"]))
    nodes[name] = h
    return h


PING_SH = """
#!/bin/bash
# continuous ping with timestamps; Ctrl-C prints the loss summary
# usage: lab-ping <dst> [interval]
exec ping -D -O -i ${2:-0.2} "$1"
"""


# ==========================================================================
# 11 Multihoming fundamentals
# ==========================================================================
def lab11():
    lab = Lab(11, "multihoming-fundamentals", "EVPN Multihoming Fundamentals", "PvIDqq3bwRw", "41 min", """
Active/active dual-homing of a server to two leaves **without MLAG**: the server runs an ordinary
LACP bond, both leaves present the same LACP system-id and the same **Ethernet Segment (ES)** in EVPN.
FRR's EVPN-MH (zebra `evpn mh ...`) signals the ES and load-balances towards it from remote leaves.
""", ref="multihoming_fundamentals")
    lab.diagram = """
                   spine1                    spine2
            /    /      \\    \\         /    /     \\
         leaf1        leaf2          leaf3          leaf4
        e1   e2      e1   e2           e1
         \\    |     /     |            |
          \\ host2  /    host3         host5
           \\  ___ /
            host1  bond0 (LACP) = ES 03:44:38:39:ff:ff:01:00:00:01
     everything in VLAN 10 / VNI 10010, 10.10.10.0/24
     host1 .10 (aa)  host2 .20 orphan on leaf1   host3 .30 orphan on leaf2   host5 .50 on leaf3
    """
    for vname, desc in (("evpn-mh", "LACP bond on host1, ES on leaf1+leaf2"),
                        ("no-mh", "host1 still runs LACP, but the leaves have plain access ports (what goes wrong?)")):
        nodes = lab.variant(vname, desc, default=(vname == "evpn-mh"))
        spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3, 4])
        std_overlay(spines, leaves)
        for i, l in leaves.items():
            if i in (1, 2):
                l2_services(l, i, [(10, 10010, ["eth2"])])
                if vname == "evpn-mh":
                    es_bond(l, "bond1", ["eth1"], 1)
                    mh_uplinks(l)
                else:
                    access_port(l, "eth1", 10)
            elif i == 3:
                l2_services(l, i, [(10, 10010, ["eth1"])])
            else:
                l2_services(l, i, [(10, 10010, [])])
            leaf_overlay(l, i, spines)
        h1 = bond_host(lab, nodes, "host1", HOSTMAC[1], ips=["10.10.10.10/24"])
        h1.files["/usr/local/bin/lab-ping"] = (PING_SH, "755")
        host(lab, nodes, "host2", "10.10.10.20/24", mac=HOSTMAC[2])
        host(lab, nodes, "host3", "10.10.10.30/24", mac=HOSTMAC[3])
        host(lab, nodes, "host5", "10.10.10.50/24", mac=HOSTMAC[5])
    for t in (("leaf1", "eth1", "host1", "eth1"), ("leaf2", "eth1", "host1", "eth2"), ("leaf1", "eth2", "host2", "eth1"),
              ("leaf2", "eth2", "host3", "eth1"), ("leaf3", "eth1", "host5", "eth1")):
        lab.link(*t)
    c = lambda *a: lab.check("evpn-mh", *a)
    c("host1", "cat /proc/net/bonding/bond0", r"Number of ports: 2")
    c("leaf1", "vtysh -c 'show evpn es'", r"03:44:38:39:ff:ff:01:00:00:01\s+LR")
    c("leaf3", "vtysh -c 'show evpn es'", r"03:44:38:39:ff:ff:01:00:00:01\s+R\s")
    c("host5", "ping -c 3 -W 1 10.10.10.10", PING_OK)
    c("host2", "ping -c 3 -W 1 10.10.10.10", PING_OK)
    c("host3", "ping -c 3 -W 1 10.10.10.10", PING_OK)
    c("leaf3", "vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa'", r"03:44:38:39:ff:ff:01:00:00:01")
    lab.check("no-mh", "host1", "cat /proc/net/bonding/bond0", r"Partner Mac Address: 00:00:00:00:00:00")
    lab.readme = r"""
## What you will learn

* Linux **bonding** in 802.3ad (LACP) mode on both sides: on the host (`bond0`) and on each leaf (`bond1`).
* The trick that makes two independent leaves look like one LACP partner: the same
  `ad_actor_system 44:38:39:ff:ff:01` on both leaves' bonds (Arista: `lacp system-id`).
* FRR EVPN multihoming:
  ```text
  interface bond1
   evpn mh es-id 1                     <- local discriminator
   evpn mh es-sys-mac 44:38:39:ff:ff:01 -> ESI type 3 = 03:44:38:39:ff:ff:01:00:00:01
  interface eth11 / eth12
   evpn mh uplink                      <- if all uplinks fail, the ES is protodown'ed
  evpn mh startup-delay 10             <- default is 180 s of protodown after boot!
  ```

## Step by step

```bash
# host1
cat /proc/net/bonding/bond0      # both slaves in the same aggregator, partner = 44:38:39:ff:ff:01
# leaf1 / leaf2
cat /proc/net/bonding/bond1
vtysh -c 'show evpn es'           # ESI, Type L (local) R (remote) -> LR on leaf1/leaf2, R on leaf3
vtysh -c 'show evpn es detail'    # VTEPs in the ES, DF status (lab 12)
vtysh -c 'show evpn mac vni 10010'
# leaf3
vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa'    # remote ES, not a single VTEP
bridge fdb show dev vxlan10010 | grep aa:aa                 # ... nhid N  -> a nexthop group
ip nexthop show                                             # group N = 1.1.1.1 + 2.2.2.2
```

**Load balancing from leaf3**: `ip nexthop show` shows the group used for host1's MAC. Send many
flows from host5 to host1 (e.g. `for p in $(seq 5000 5100); do echo x | nc -u -w0 10.10.10.10 $p; done`)
while running `tcpdump -ni eth11 udp port 4789` on leaf1 and leaf2: both receive some of the flows.
The video uses Scapy for the same test; Scapy is installed in the base image (`python3 -m scapy`).

**Orphan ports**: host2 hangs off leaf1 only. Shut leaf1's link to host1 (`ip link set eth1 down` on leaf1)
and ping host1 from host2 - traffic now goes leaf1 -> VXLAN -> leaf2 -> host1.

## Variant `no-mh` - "LAG only on the endpoint"

The leaves don't speak LACP. On host1 `cat /proc/net/bonding/bond0` shows partner MAC 00:00:00:00:00:00
and only one slave in the active aggregator - the bond falls back to a single link. Now replace the host
bond with a static `balance-xor` bond (`ip link del bond0` and recreate with `mode balance-xor`):
both links are used, leaf1 and leaf2 both learn 00:aa:.. and advertise it -> **MAC flapping** between the
two VTEPs (`vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa detail'` - watch the sequence number grow).
That's exactly why you need either MLAG or EVPN-MH.
"""
    return lab


# ==========================================================================
# 12 Multihoming deep dive: ES route, DF, split horizon
# ==========================================================================
def lab12():
    lab = Lab(12, "multihoming-deep-dive", "EVPN Multihoming Deep Dive. Ethernet Segment Route. Designated Forwarder. Split Horizon.",
              "EMA8-csnilA", "1 h 05 min", """
Two multihomed servers with **trunk bonds** (VLAN 10 and 20 sub-interfaces on the host), manually
configured **type-0 ESIs**, the **type-4 Ethernet Segment route** and its ES-Import RT, **Designated
Forwarder** election (who sends BUM to the ES) and **split horizon** (don't send BUM back into the ES it came from).
""", ref="multihoming_deep_dive")
    lab.diagram = """
                  spine1                  spine2
           leaf1         leaf2        leaf3       leaf4
         e1 e2 e3      e1 e2 e3        e1
         |  |  |       |  |  |          |
         |  |  host3   |  |  host4     host5
         |  +----------|--+-- host2  (bond0, ES 00:22:22:22:22:22:22:22:22:22)
         +------------ +----- host1  (bond0, ES 00:11:11:11:11:11:11:11:11:11)
   host1/host2: bond0.10 and bond0.20 (trunk)   10.10.10.x / 10.20.20.x
   host3 VLAN10 on leaf1 (orphan)  host4 VLAN10 on leaf2 (orphan)  host5 VLAN10 on leaf3
    """
    nodes = lab.variant("default", "two type-0 ESs, trunk bonds, DF preference on leaf1")
    spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3, 4])
    std_overlay(spines, leaves)
    for i, l in leaves.items():
        if i in (1, 2):
            l2_services(l, i, [(10, 10010, ["eth3"]), (20, 10020, [])])
            es_bond(l, "bond1", ["eth1"], "00:11:11:11:11:11:11:11:11:11", sysmac="44:38:39:ff:ff:11",
                    vlans=(10, 20), trunk=True, df_pref=50000 if i == 1 else None)
            es_bond(l, "bond2", ["eth2"], "00:22:22:22:22:22:22:22:22:22", sysmac="44:38:39:ff:ff:22",
                    vlans=(10, 20), trunk=True)
            mh_uplinks(l)
        elif i == 3:
            l2_services(l, i, [(10, 10010, ["eth1"]), (20, 10020, [])])
        else:
            l2_services(l, i, [(10, 10010, []), (20, 10020, [])])
        leaf_overlay(l, i, spines)
    bond_host(lab, nodes, "host1", HOSTMAC[1], ips=["10.10.10.10/24", "10.20.20.10/24"], vlans=[10, 20])
    bond_host(lab, nodes, "host2", HOSTMAC[2], ips=["10.10.10.20/24", "10.20.20.20/24"], vlans=[10, 20])
    host(lab, nodes, "host3", "10.10.10.30/24", mac=HOSTMAC[3])
    host(lab, nodes, "host4", "10.10.10.40/24", mac=HOSTMAC[4])
    host(lab, nodes, "host5", "10.10.10.50/24", mac=HOSTMAC[5])
    for t in (("leaf1", "eth1", "host1", "eth1"), ("leaf2", "eth1", "host1", "eth2"),
              ("leaf1", "eth2", "host2", "eth1"), ("leaf2", "eth2", "host2", "eth2"),
              ("leaf1", "eth3", "host3", "eth1"), ("leaf2", "eth3", "host4", "eth1"), ("leaf3", "eth1", "host5", "eth1")):
        lab.link(*t)
    c = lambda *a: lab.check("default", *a)
    c("leaf1", "vtysh -c 'show evpn es'", r"00:11:11:11:11:11:11:11:11:11\s+LR[\s\S]*00:22:22:22:22:22:22:22:22:22\s+LR")
    c("leaf1", "vtysh -c 'show bgp l2vpn evpn route type es'", r"\[4\]:\[00:11:11:11:11:11:11:11:11:11\]:\[32\]:\[2\.2\.2\.2\]")
    c("leaf1", "vtysh -c 'show evpn es 00:11:11:11:11:11:11:11:11:11'", r"DF status: df")
    c("leaf2", "vtysh -c 'show evpn es 00:11:11:11:11:11:11:11:11:11'", r"DF status: non-df")
    c("host5", "ping -c 3 -W 1 10.10.10.10", PING_OK)
    c("host1", "ping -c 3 -W 1 10.20.20.20", PING_OK)
    c("host3", "ping -c 3 -W 1 10.10.10.20", PING_OK)
    lab.readme = r"""
## What you will learn

* **ESI formats**: type 0 (operator-configured 9 bytes: `00:11:11:...`) vs type 3 (MAC + discriminator, lab 11).
  FRR: `evpn mh es-id 00:11:11:11:11:11:11:11:11:11` on the bond (plus `es-sys-mac` only for LACP).
* **Type-4 ES route** `[4]:[ESI]:[32]:[VTEP-IP]` with the **ES-Import RT** (derived from the ESI's MAC bytes) -
  only VTEPs attached to the same ES import it. Used for DF election.
* **DF election**: per ES (and per VLAN in the standard modulo algorithm). FRR implements the
  **preference-based** DF election (RFC draft "df-pref"): highest `evpn mh es-df-pref` wins, tie -> lowest IP.
  leaf1 is configured with 50000 for ES 00:11:..; ES 00:22:.. uses the defaults.
* **Split horizon**: a BUM frame that arrives at leaf2 *from leaf1* and belongs to an ES both share must not be
  sent back to that ES. With VXLAN this is done by **local bias** (RFC 8365): the ingress VTEP delivers BUM to its
  own local ES ports; the other ES peers never forward VXLAN-received BUM from that VTEP to the shared ES.
  zebra programs the kernel for DF and local-bias filtering - you only see the effect (and `show evpn es detail`).
* VLAN sub-interfaces on a bond (host side trunk) and `bridge vlan add dev bond1 vid 10` (tagged) on the leaf.

## Step by step

```bash
# leaf1
vtysh -c 'show evpn es detail'                          # VTEPs, DF pref, "DF status: df"
vtysh -c 'show evpn es-evi'                             # ES per VNI
vtysh -c 'show bgp l2vpn evpn route type es'            # type-4
vtysh -c 'show bgp l2vpn evpn route type es detail'     # ES-Import RT (ES-Import Rt:11:11:11:11:11:11)
bridge -d link show dev bond1                           # protodown state, etc.
```

**DF in action**: from host5 send a broadcast (`arping -c 3 -I eth1 10.10.10.99`) and capture on **host1**
eth1 and eth2 (`tcpdump -ni eth1 arp` / `-ni eth2 arp`): host1 receives it only on the link to the DF (leaf1).
Change preference (`evpn mh es-df-pref 1000` on leaf1, `60000` on leaf2), re-check, re-capture.

**Without EVPN-MH** (video 27:43): on leaf2, `ip link set eth1 nomaster`... easier: remove the `evpn mh es-id`
lines on leaf2 only (`vtysh` -> `conf t` -> `interface bond1` -> `no evpn mh es-id`) and watch duplicates
and MAC moves on leaf3 (`show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa detail`).

**Split horizon**: from host1 send a broadcast in VLAN 10 (`arping -I bond0.10 10.10.10.99`). It hashes to
one link, say leaf1. leaf1 floods to host3 and to leaf2/3/4 via VXLAN. Capture on host1: the frame must
**not** come back to host1 via leaf2 (`tcpdump -ni eth2 arp` on host1 stays quiet).
"""
    return lab


# ==========================================================================
# 13 Multihoming: AD routes, fast convergence, aliasing
# ==========================================================================
def lab13():
    lab = Lab(13, "multihoming-ad-routes", "EVPN Multihoming. Auto Discovery Routes. Fast Convergence. Aliasing.",
              "Q-oBiCV_EO0", "46 min", """
**Type-1 Ethernet Auto-Discovery** routes: *per-ES* (used for **mass withdraw** - one route
withdrawal invalidates every MAC behind the ES) and *per-EVI* (used for **aliasing** - remote VTEPs
can load-balance to a MAC even if only one of the ES members learnt it). You will measure failover
time and compare an LACP bond with an active-backup bond on the host.
""", ref="multihoming_auto_discovery")
    lab.diagram = """
                  spine1                spine2
          leaf1        leaf2       leaf3        leaf4
            e1          e1          e1           e1
             \\         /            |            |
              host1 (bond0)        host5        host6
         ES 03:44:38:39:ff:ff:01:00:00:01, VLAN 10, 10.10.10.0/24
    """
    for vname, mode, desc in (("lacp", "802.3ad", "all-active ES, LACP bond on host1"),
                              ("host-active-backup", "active-backup", "same ES config, but host1 uses an active-backup bond (no LACP)")):
        nodes = lab.variant(vname, desc, default=(vname == "lacp"))
        spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3, 4])
        std_overlay(spines, leaves)
        for i, l in leaves.items():
            if i in (1, 2):
                l2_services(l, i, [(10, 10010, [])])
                es_bond(l, "bond1", ["eth1"], 1, lacp=(mode == "802.3ad"))
                mh_uplinks(l)
            else:
                l2_services(l, i, [(10, 10010, ["eth1"])])
            leaf_overlay(l, i, spines)
        h = bond_host(lab, nodes, "host1", HOSTMAC[1], ips=["10.10.10.10/24"], mode=mode)
        h.files["/usr/local/bin/lab-ping"] = (PING_SH, "755")
        h5 = host(lab, nodes, "host5", "10.10.10.50/24", mac=HOSTMAC[5])
        h5.files["/usr/local/bin/lab-ping"] = (PING_SH, "755")
        host(lab, nodes, "host6", "10.10.10.60/24", mac=HOSTMAC[6])
    for t in (("leaf1", "eth1", "host1", "eth1"), ("leaf2", "eth1", "host1", "eth2"),
              ("leaf3", "eth1", "host5", "eth1"), ("leaf4", "eth1", "host6", "eth1")):
        lab.link(*t)
    for v in ("lacp", "host-active-backup"):
        lab.check(v, "host5", "ping -c 3 -W 1 10.10.10.10", PING_OK)
    c = lambda *a: lab.check("lacp", *a)
    c("leaf3", "vtysh -c 'show bgp l2vpn evpn route type ead'", r"\[1\]:\[0\]:\[03:44:38:39:ff:ff:01:00:00:01\]:\[128\]:\[0\.0\.0\.0\]|\[1\]:\[4294967295\]")
    c("leaf3", "bridge fdb show dev vxlan10010", r"00:aa:aa:aa:aa:aa .*nhid \d+")
    c("leaf3", "ip nexthop show", r"group \d+/\d+")
    lab.readme = r"""
## What you will learn

* EAD **per-ES** route `[1]:[4294967295]:[ESI]...` (Ethernet Tag MAX-ET) - one per ES per VTEP. Withdrawn when the
  ES goes down -> remote VTEPs immediately remove that VTEP from **all** MACs on the ES (*fast convergence /
  mass withdraw*), without waiting for hundreds of type-2 withdrawals.
* EAD **per-EVI** route `[1]:[0]:[ESI]...` (Ethernet Tag 0) - one per ES per VNI. Lets a remote VTEP send to
  *any* VTEP that has the ES in this VNI -> **aliasing**, plus a backup path.
* On Linux, FRR programs remote ES MACs as `bridge fdb ... nhid N` pointing at an `ip nexthop` **group**,
  so a single nexthop-group update moves all MACs.

## Step by step

```bash
# leaf3
vtysh -c 'show bgp l2vpn evpn route type ead'
vtysh -c 'show evpn es detail'                # VTEP list per ES
bridge fdb show dev vxlan10010 | grep aa:aa  # ... nhid 2xx
ip nexthop show                               # id 2xx group <leaf1-nh>/<leaf2-nh> fdb
```

**Aliasing**: make host1 talk through one link only (`ip link set eth2 down` on host1, then
`ip neigh flush all; ping 10.10.10.50`). Only leaf1 learns 00:aa..., but leaf3 still has the
ES nexthop group with *both* leaf1 and leaf2 - thanks to leaf2's per-EVI EAD route.

**Fast convergence**: run `lab-ping 10.10.10.10` on host5, then on leaf1 `ip link set eth1 down`.
Count lost packets. Capture BGP on leaf1's uplinks during the failure (`tcpdump -ni eth11 -w /tmp/bgp.pcap tcp port 179`)
and look for a single EAD-per-ES withdrawal. Compare with `evpn mh` features disabled on leaf3:
`conf t` -> `router bgp 65000` -> `address-family l2vpn evpn` -> `disable-ead-evi-rx` (aliasing off).

## Variant `host-active-backup` - the single-active problem

FRR implements **all-active** multihoming only (no single-active / port-active redundancy mode).
In this variant host1 uses an active-backup bond and the leaves don't run LACP, so **both** leaves
consider the ES up. leaf3 aliases traffic to leaf2 as well - and host1's *backup* slave silently
drops frames arriving on it. Watch `lab-ping` from host5 and capture on host1 eth2: some flows vanish.
Lessons:

* single-active (DF-only forwarding) exists in the RFC precisely for hosts that can't do LACP;
* with FRR, make sure the non-active link is really down (LACP, or `ip link set down` on the standby).

The video also shows DF election in **VLAN-aware bundle** mode; FRR only does VLAN-based (see lab 04).
"""
    return lab


# ==========================================================================
# 17 All EVPN route types
# ==========================================================================
def lab17():
    lab = Lab(17, "all-route-types", "Explaining all BGP EVPN Route Types for Data Center", "9JJrcvuVYfU", "46 min", """
One fabric that produces **every unicast EVPN route type** so you can study them side by side:
type-1 (EAD) and type-4 (ES) from a multihomed host, type-2 (MAC and MAC/IP), type-3 (IMET), and
type-5 (IP prefix) for an isolated subnet, a silent host and an external network behind a border leaf.
""", ref="evpn_routes")
    lab.diagram = """
                       spine1 (RR)            spine2 (RR)
        leaf1      leaf2         leaf3            leaf4 (border)
         e1         e1        e1     e2             e1
          \\        /          |       |              |
           host1 (bond)     host3   host4            r1  AS 65001, lo 10.100.100.100
      VLAN10 10.10.10.10   VLAN10  VLAN30 (only leaf3, isolated)
                          .10.30   10.30.30.40
      VRF A, L3VNI 1000 on all leaves.  leaf4 eth1 <-> r1 eth1  172.16.41.0/24 (eBGP in VRF A)
    """
    nodes = lab.variant("default", "MH + L2 + L3 + external")
    spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3, 4])
    std_overlay(spines, leaves)
    for i, l in leaves.items():
        if i in (1, 2):
            l2_services(l, i, [(10, 10010, [])])
            es_bond(l, "bond1", ["eth1"], 1)
            mh_uplinks(l)
        elif i == 3:
            l2_services(l, i, [(10, 10010, ["eth1"]), (30, 10030, ["eth2"])])
        else:
            bridge(l, leaf_mac(i))
        vrf_dev(l, "A", 1001)
        if i != 4:
            svi(l, 10, "10.10.10.1/24", vrf="A")
        if i == 3:
            svi(l, 30, "10.30.30.1/24", vrf="A")
        l3vni(l, "A", 1000, 4001, leaf_lo(i))
        leaf_overlay(l, i, spines)
        b = vrf_evpn(l, 65000, leaf_lo(i), "A", connected=(i != 4))
        if i == 4:
            addr(l, "eth1", "172.16.41.4/24", vrf="A")
            b.g("neighbor 172.16.41.1 remote-as 65001")
    r1 = Node("r1", "router", "ext")
    loopback(r1, "10.100.100.100")
    addr(r1, "eth1", "172.16.41.1/24")
    rb = r1.frr.bgp(65001, "10.100.100.100")
    rb.g("no bgp ebgp-requires-policy", "neighbor 172.16.41.4 remote-as 65000")
    rb.af("ipv4 unicast", "network 10.100.100.100/32")
    nodes["r1"] = r1
    bond_host(lab, nodes, "host1", HOSTMAC[1], ips=["10.10.10.10/24"], gw="10.10.10.1")
    host(lab, nodes, "host3", "10.10.10.30/24", "10.10.10.1", HOSTMAC[3])
    host(lab, nodes, "host4", "10.30.30.40/24", "10.30.30.1", HOSTMAC[4])
    for t in (("leaf1", "eth1", "host1", "eth1"), ("leaf2", "eth1", "host1", "eth2"),
              ("leaf3", "eth1", "host3", "eth1"), ("leaf3", "eth2", "host4", "eth1"), ("leaf4", "eth1", "r1", "eth1")):
        lab.link(*t)
    c = lambda *a: lab.check("default", *a)
    c("host1", "ping -c 3 -W 1 10.30.30.40", PING_OK)
    c("host1", "ping -c 3 -W 1 10.100.100.100", PING_OK)
    c("spine1", "vtysh -c 'show bgp l2vpn evpn route type ead'", r"\[1\]:")
    c("spine1", "vtysh -c 'show bgp l2vpn evpn route type es'", r"\[4\]:")
    c("spine1", "vtysh -c 'show bgp l2vpn evpn route type macip'", r"\[2\]:\[0\]:\[48\]:\[00:aa:aa:aa:aa:aa\]:\[32\]")
    c("spine1", "vtysh -c 'show bgp l2vpn evpn route type multicast'", r"\[3\]:")
    c("spine1", "vtysh -c 'show bgp l2vpn evpn route type prefix'", r"\[5\]:\[0\]:\[32\]:\[10\.100\.100\.100\]")
    lab.readme = r"""
## What you will learn

| Type | Name | Who sends it here | Purpose |
|---|---|---|---|
| 1 | Ethernet Auto-Discovery (per-ES / per-EVI) | leaf1, leaf2 | mass withdraw, aliasing |
| 2 | MAC/IP Advertisement | every leaf with hosts | MAC learning (L2), host routes (L3, 2 labels) |
| 3 | Inclusive Multicast Ethernet Tag | every VTEP per L2VNI | BUM flood list |
| 4 | Ethernet Segment | leaf1, leaf2 | ES discovery, DF election |
| 5 | IP Prefix | all leaves (connected subnets), leaf4 (external) | subnets, silent hosts, external routes |
| 6-8 | SMET / IGMP join & leave sync | - | multicast (OISM), not implemented in FRR - see lab 10 |

## Step by step

On spine1 (the RR sees everything):

```bash
vtysh -c 'show bgp l2vpn evpn route type ead'
vtysh -c 'show bgp l2vpn evpn route type es'
vtysh -c 'show bgp l2vpn evpn route type macip'
vtysh -c 'show bgp l2vpn evpn route type multicast'
vtysh -c 'show bgp l2vpn evpn route type prefix'
vtysh -c 'show bgp l2vpn evpn route detail' | less     # attributes: RTs, Rmac, ESI, MM seq, label(s)
```

Questions to answer:

1. Which type-2 routes have **one** label and which have **two**? (MAC-only vs MAC+IP with L3VNI.)
2. Which type-5 routes have a gateway IP / ESI? (all 0 here - "interface-less" model of RFC 9136.)
3. **Silent hosts** (video 19:20): add `10.30.30.41/24` to host4 but never send traffic from it.
   From host1 ping 10.30.30.41: works only because of the type-5 10.30.30.0/24 route. Remove
   `redistribute connected` from VRF A on leaf3 -> 10.30.30.41 unreachable, 10.30.30.40 still OK (it has a type-2).
4. **Second route reflector** (video 43:05): with two RRs every leaf receives each route twice
   (`show bgp l2vpn evpn route rd 3.3.3.3:2` shows 2 paths). Why don't they loop? (CLUSTER_LIST / ORIGINATOR_ID.)
   Each spine here has a different `bgp cluster-id` - try giving both the same and compare path counts.
"""
    return lab


LABS = [lab11, lab12, lab13]
LABS_LATE = [lab17]
