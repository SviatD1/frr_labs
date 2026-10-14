from gen import *
from labs_basics import HOSTMAC, BGP_UP, PING_OK

V6NOTE = ("IPv6 VTEPs (VXLAN over an IPv6 underlay) need **FRR 10.6 or newer** - the base image installs the current "
          "FRR stable release, check with `vtysh -c 'show version'`.")


def leaf_lo6(i):
    return f"fc00::{i}"


def spine_lo6(m):
    return f"fc00::{10 + m}"


def underlay_fabric(lab, nodes, n_spines, leaves, mode):
    """mode: ipv4-numbered | ipv4-unnumbered | ipv6-numbered | ipv6-lla. IS-IS underlay. Returns spines, leaves, vtep(i)"""
    spines, lv = OrderedDict(), OrderedDict()
    v6 = mode.startswith("ipv6")
    for m in range(1, n_spines + 1):
        s = Node(f"spine{m}", "router", "spine")
        loopback(s, None if v6 else spine_lo(m), spine_lo6(m) if v6 else None)
        nodes[s.name] = s
        spines[m] = s
    for i in leaves:
        l = Node(f"leaf{i}", "router", "leaf")
        loopback(l, None if v6 else leaf_lo(i), leaf_lo6(i) if v6 else None)
        nodes[l.name] = l
        lv[i] = l
    for m, s in spines.items():
        s.comment(f"fabric links ({mode})")
        for i, l in lv.items():
            sif, lif = f"eth{i}", f"eth{10 + m}"
            if (s.name, sif, l.name, lif) not in lab.links:
                lab.link(s.name, sif, l.name, lif)
            if mode == "ipv4-numbered":
                addr(s, sif, f"10.{i}.{10 + m}.{10 + m}/24")
                addr(l, lif, f"10.{i}.{10 + m}.{i}/24")
            elif mode == "ipv4-unnumbered":
                s.sh(f"ip link set {sif} up", f"ip addr add {spine_lo(m)}/32 peer {leaf_lo(i)}/32 dev {sif}")
                l.sh(f"ip link set {lif} up", f"ip addr add {leaf_lo(i)}/32 peer {spine_lo(m)}/32 dev {lif}")
            elif mode == "ipv6-numbered":
                addr(s, sif, ip6=f"fc00:10:{i}:{10 + m}::{10 + m}/64")
                addr(l, lif, ip6=f"fc00:10:{i}:{10 + m}::{i}/64")
            else:  # ipv6-lla
                s.sh(f"ip link set {sif} up")
                l.sh(f"ip link set {lif} up")
    for m, s in spines.items():
        isis(s, [f"eth{i}" for i in lv], 10 + m, ipv4=not v6, ipv6=v6)
    for i, l in lv.items():
        isis(l, [f"eth{10 + m}" for m in spines], i, ipv4=not v6, ipv6=v6)
    return spines, lv


def overlay_any(spines, leaves, v6):
    for m, s in spines.items():
        b = evpn_rr_ibgp(s, 65000, spine_lo(m), [leaf_lo6(i) if v6 else leaf_lo(i) for i in leaves])
    for i, l in leaves.items():
        evpn_leaf_ibgp(l, 65000, leaf_lo(i), [spine_lo6(m) if v6 else spine_lo(m) for m in spines])


# ==========================================================================
# 23 Underlay IP addressing
# ==========================================================================
def lab23():
    lab = Lab(23, "underlay-ip-addressing", "Designing Underlay IP Connectivity for Data Center Networks", "wvRWIa6GK4s", "38 min", """
Four ways to address the fabric links, same IS-IS underlay and EVPN overlay on top: **numbered IPv4**,
**unnumbered IPv4** (links borrow the loopback address), **numbered IPv6** and **IPv6 link-local only**.
Compare how much addressing you have to plan, what the routing table looks like, and what still works.
""", ref="design_underlay_ip")
    lab.diagram = """
             spine1                spine2
              |    \\            /    |
              |      \\        /      |       ipv4-numbered:   10.<leaf>.<10+spine>.0/24 per link
              |        \\    /        |       ipv4-unnumbered: 1.1.1.1/32 peer 11.11.11.11/32 on the link
              |          \\/          |       ipv6-numbered:   fc00:10:<leaf>:<10+spine>::/64
            leaf1                 leaf2      ipv6-lla:        fe80:: only; loopbacks fc00::N/128
              |eth1                 |eth1
            host1                 host2      VLAN 10 / VNI 10010 (10.10.10.0/24) in every variant
    """
    for mode, desc in (("ipv4-numbered", "classic /24 (or /31) per link"),
                       ("ipv4-unnumbered", "links carry the loopback /32 with a peer address"),
                       ("ipv6-numbered", "/64 per link, IPv6 loopbacks, IPv6 VTEPs (FRR >= 10.6)"),
                       ("ipv6-lla", "link-local only, IPv6 loopbacks, IPv6 VTEPs (FRR >= 10.6)")):
        nodes = lab.variant(mode, desc, default=(mode == "ipv4-numbered"))
        v6 = mode.startswith("ipv6")
        spines, leaves = underlay_fabric(lab, nodes, 2, [1, 2], mode)
        overlay_any(spines, leaves, v6)
        for i, l in leaves.items():
            l2_services(l, i, [(10, 10010, ["eth1"])], local=leaf_lo6(i) if v6 else leaf_lo(i))
        host(lab, nodes, "host1", "10.10.10.10/24", mac=HOSTMAC[1])
        host(lab, nodes, "host2", "10.10.10.20/24", mac=HOSTMAC[2])
    lab.link("leaf1", "eth1", "host1", "eth1")
    lab.link("leaf2", "eth1", "host2", "eth1")
    for v in ("ipv4-numbered", "ipv4-unnumbered", "ipv6-numbered", "ipv6-lla"):
        lab.check(v, "host1", "ping -c 3 -W 1 10.10.10.20", PING_OK)
    lab.check("ipv4-numbered", "leaf1", "ip route show 2.2.2.2", r"nexthop via 10\.1\.11\.11")
    lab.check("ipv4-unnumbered", "leaf1", "ip route show 2.2.2.2", r"nexthop via 11\.11\.11\.11 dev eth11")
    lab.check("ipv6-numbered", "leaf1", "ip -6 route show fc00::2", r"via fc00:10:1:11::11")
    lab.check("ipv6-lla", "leaf1", "ip -6 route show fc00::2", r"via fe80::")
    lab.readme = r"""
## What you will learn

| | IPv4 numbered | IPv4 unnumbered | IPv6 numbered | IPv6 LLA |
|---|---|---|---|---|
| addresses to plan per link | 2 (a /31 or /30) | 0 | 2 (a /64 or /127) | 0 |
| Linux config | `ip addr add 10.1.11.1/24 dev eth11` | `ip addr add 1.1.1.1/32 peer 11.11.11.11/32 dev eth11` | `ip -6 addr add fc00:10:1:11::1/64` | nothing - LLA is automatic |
| traceroute shows | link IPs | loopbacks | link IPs | loopbacks (ICMPv6 from global addr) |
| VTEP / BGP | IPv4 | IPv4 | IPv6 | IPv6 |

""" + V6NOTE + r"""

## Step by step

For each variant (`python tools\gns3_lab.py push labs\23-underlay-ip-addressing --variant <name>`):

```bash
# leaf1
ip -br addr ; ip route ; ip -6 route
vtysh -c 'show isis neighbor'  ; vtysh -c 'show isis route'
vtysh -c 'show bgp l2vpn evpn summary'
bridge fdb show dev vxlan10010 | grep dst       # VTEP addresses: IPv4 or IPv6
traceroute -n 2.2.2.2   (IPv4 variants)  /  traceroute -6 -n fc00::2   (IPv6 variants)
```

Things to notice:

* **Unnumbered IPv4**: the `peer` form puts a /32 host route to the neighbor's loopback on the link, so the
  IS-IS next hop (the neighbor's loopback) is directly reachable. That's exactly what the author's FRR spines do
  (`ip address 11.11.11.11 peer 1.1.1.1/32`). Arista does `ip address unnumbered Loopback0` and resolves the
  next hop with ARP on the link.
* **IPv6 LLA**: every route's next hop is `fe80::...%ethX`. Nothing to plan, nothing to conflict, and
  the loopbacks are still the only global addresses. `ping -6 fe80::<x>%eth11` works only with the interface scope.
* VXLAN over IPv6 adds 70 bytes instead of 50 - hosts here still use MTU 1450; try 1500-70 = 1430 vs 1450 with `ping -M do -s ...`.
"""
    return lab


# ==========================================================================
# 24 Underlay routing protocol options
# ==========================================================================
def lab24():
    lab = Lab(24, "underlay-igp-options", "Routing Protocol Options for EVPN Underlay", "JsiWm88AKLA", "29 min", """
Same fabric, three link-state underlays: **OSPFv2**, **OSPFv3** (IPv6 underlay) and **IS-IS** (the
default of the rest of this course). Look at the LSDBs, SPF and why fabric links should always be
**point-to-point**.
""", ref="design_underlay_igp")
    lab.diagram = """
                spine1                    spine2
           /   /    \\   \\           /   /    \\   \\
        leaf1  leaf2  leaf3  leaf4   (every leaf to both spines)
          |      |      |      |
        host1  host2  host3  host4    VLAN 10 / VNI 10010, 10.10.10.0/24
    """
    for proto, desc in (("ospfv2", "OSPFv2 point-to-point, area 0"),
                        ("ospfv3", "OSPFv3 over an IPv6 underlay, IPv6 VTEPs (FRR >= 10.6)"),
                        ("isis", "IS-IS level-2, point-to-point")):
        nodes = lab.variant(proto, desc, default=(proto == "ospfv2"))
        v6 = proto == "ospfv3"
        if proto == "ospfv3":
            spines, leaves = underlay_fabric(lab, nodes, 2, [1, 2, 3, 4], "ipv6-numbered")
            for n in list(spines.values()) + list(leaves.values()):
                n.frr.ifaces.clear()
                n.frr.blocks = [b for b in n.frr.blocks if not b.startswith("router isis")]
            for m, s in spines.items():
                for i in leaves:
                    s.frr.iface(f"eth{i}", "ipv6 ospf6 area 0", "ipv6 ospf6 network point-to-point")
                s.frr.iface("lo", "ipv6 ospf6 area 0", "ipv6 ospf6 passive")
                s.frr.block(f"router ospf6\n ospf6 router-id {spine_lo(m)}\nexit")
            for i, l in leaves.items():
                for m in spines:
                    l.frr.iface(f"eth{10 + m}", "ipv6 ospf6 area 0", "ipv6 ospf6 network point-to-point")
                l.frr.iface("lo", "ipv6 ospf6 area 0", "ipv6 ospf6 passive")
                l.frr.block(f"router ospf6\n ospf6 router-id {leaf_lo(i)}\nexit")
        else:
            spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3, 4], underlay="ospf" if proto == "ospfv2" else "isis")
        overlay_any(spines, leaves, v6)
        for i, l in leaves.items():
            l2_services(l, i, [(10, 10010, ["eth1"])], local=leaf_lo6(i) if v6 else leaf_lo(i))
            host(lab, nodes, f"host{i}", f"10.10.10.{10 * i}/24", mac=HOSTMAC[i])
            if (l.name, "eth1", f"host{i}", "eth1") not in lab.links:
                lab.link(l.name, "eth1", f"host{i}", "eth1")
    for v in ("ospfv2", "ospfv3", "isis"):
        lab.check(v, "host1", "ping -c 3 -W 1 10.10.10.40", PING_OK)
    lab.check("ospfv2", "leaf1", "vtysh -c 'show ip ospf neighbor'", r"11\.11\.11\.11\s+\d+\s+Full")
    lab.check("ospfv2", "leaf1", "ip route show 4.4.4.4", r"nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12")
    lab.check("isis", "leaf1", "ip route show 4.4.4.4", r"nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12")
    lab.check("ospfv3", "leaf1", "vtysh -c 'show ipv6 ospf6 neighbor'", r"11\.11\.11\.11.*Full")
    lab.readme = r"""
## What you will learn

* Configuring each IGP in FRR, the interface-centric way:
  * OSPFv2: `ip ospf area 0` + `ip ospf network point-to-point` on the interface, `router ospf` / `ospf router-id`.
  * OSPFv3: `ipv6 ospf6 area 0` + `ipv6 ospf6 network point-to-point`, `router ospf6`.
  * IS-IS: `ip router isis 1` + `isis network point-to-point`, `router isis 1` / `net` / `is-type level-2-only`.
* Link-state vs BGP for the underlay (video 5:55): flooding domain size, SPF cost, and why a folded Clos
  with N leaves means every leaf receives every other leaf's LSA via every spine.
* **Why point-to-point**: on a broadcast network type OSPF elects DR/BDR, waits (`wait timer` = dead interval
  40 s on Ethernet) and adds a type-2 network LSA per link. On a 2-node link that's pure overhead.

## Step by step

```bash
# OSPFv2
vtysh -c 'show ip ospf neighbor'            # state Full, no DR/BDR ("Full/-")
vtysh -c 'show ip ospf database'            # one router LSA per switch, no network LSAs
vtysh -c 'show ip ospf route'
# OSPFv3
vtysh -c 'show ipv6 ospf6 neighbor' ; vtysh -c 'show ipv6 ospf6 database'
# IS-IS
vtysh -c 'show isis database detail' ; vtysh -c 'show isis spf-delay-ietf'
```

**Break p2p**: on leaf1 and spine1 change eth11/eth1 to broadcast (OSPFv2: `no ip ospf network point-to-point`).
Watch `show ip ospf neighbor` go through `2-Way/DROther`, `ExStart` ... and a DR election; look for the new
**type-2 network LSA** in `show ip ospf database`. Time how long the adjacency takes compared with p2p.

**Convergence**: run `ping -D -O 10.10.10.40` on host1 and shut leaf1 eth11. All three IGPs converge in
about a second with FRR's default timers (BFD would make link-down detection independent of the IGP).
"""
    return lab


def ebgp_fabric(lab, nodes, n_spines, leaves, spine_asn, leaf_asn, unnumbered=False, mrai=None, evpn=True):
    spines, lv = OrderedDict(), OrderedDict()
    for m in range(1, n_spines + 1):
        s = Node(f"spine{m}", "router", "spine")
        loopback(s, spine_lo(m))
        s.notes.append(f"AS {spine_asn(m)}")
        nodes[s.name] = s
        spines[m] = s
    for i in leaves:
        l = Node(f"leaf{i}", "router", "leaf")
        loopback(l, leaf_lo(i))
        l.notes.append(f"AS {leaf_asn(i)}")
        nodes[l.name] = l
        lv[i] = l
    for m, s in spines.items():
        s.comment("fabric links" + (" (no IPv4: BGP unnumbered over IPv6 link-local)" if unnumbered else ""))
        for i, l in lv.items():
            sif, lif = f"eth{i}", f"eth{10 + m}"
            if (s.name, sif, l.name, lif) not in lab.links:
                lab.link(s.name, sif, l.name, lif)
            if unnumbered:
                s.sh(f"ip link set {sif} up")
            else:
                addr(s, sif, f"10.{i}.{10 + m}.{10 + m}/24")
    for i, l in lv.items():
        l.comment("uplinks")
        for m in spines:
            if unnumbered:
                l.sh(f"ip link set eth{10 + m} up")
            else:
                addr(l, f"eth{10 + m}", f"10.{i}.{10 + m}.{i}/24")

    def common(b, pg):
        b.g("no bgp ebgp-requires-policy", "bgp bestpath as-path multipath-relax",
            f"neighbor {pg} peer-group", f"neighbor {pg} remote-as external")
        if mrai is not None:
            b.g(f"neighbor {pg} advertisement-interval {mrai}")

    for m, s in spines.items():
        b = s.frr.bgp(spine_asn(m), spine_lo(m))
        common(b, "LEAVES")
        for i in lv:
            b.g(f"neighbor eth{i} interface peer-group LEAVES" if unnumbered else f"neighbor 10.{i}.{10 + m}.{i} peer-group LEAVES")
        b.af("ipv4 unicast", f"network {spine_lo(m)}/32")
        if evpn:
            b.af("l2vpn evpn", "neighbor LEAVES activate")
    for i, l in lv.items():
        b = l.frr.bgp(leaf_asn(i), leaf_lo(i))
        common(b, "SPINES")
        for m in spines:
            b.g(f"neighbor eth{10 + m} interface peer-group SPINES" if unnumbered else f"neighbor 10.{i}.{10 + m}.{10 + m} peer-group SPINES")
        b.af("ipv4 unicast", f"network {leaf_lo(i)}/32")
        if evpn:
            b.af("l2vpn evpn", "neighbor SPINES activate", "advertise-all-vni")
    return spines, lv


# ==========================================================================
# 25 eBGP underlay
# ==========================================================================
def lab25():
    lab = Lab(25, "ebgp-underlay", "eBGP as Underlay for EVPN in Data Center", "ty5JxLFjtJQ", "47 min", """
RFC 7938 style: no IGP at all, **eBGP on every link**, and the EVPN address family on the same sessions.
Compare ASN schemes (same ASN on all spines vs unique ASN everywhere), see the **transit leaf** problem
appear with unique spine ASNs, and replace all link addressing with **BGP unnumbered** over IPv6 link-local.
""", ref="design_underlay_ebgp")
    lab.diagram = """
          spine1 AS 65100 (or 65101)       spine2 AS 65100 (or 65102)
             |   \\     \\                /    /   |
           leaf1      leaf2         leaf3          leaf1..3 = AS 65001..65003
             |          |             |
           host1      host2         host3        VLAN 10 / VNI 10010, 10.10.10.0/24
       EVPN rides the same eBGP sessions; spines keep the leaves' next hops (VTEP IPs)
    """
    for vname, sasn, unn, desc in (
            ("same-asn-spines", lambda m: 65100, False, "spines AS 65100, leaves 65001-65003, numbered links"),
            ("unique-asn", lambda m: 65100 + m, False, "every switch its own AS (transit leaf possible)"),
            ("unnumbered", lambda m: 65100, True, "same as same-asn-spines but BGP unnumbered (IPv6 LLA, RFC 5549)")):
        nodes = lab.variant(vname, desc, default=(vname == "same-asn-spines"))
        spines, leaves = ebgp_fabric(lab, nodes, 2, [1, 2, 3], sasn, lambda i: 65000 + i, unnumbered=unn)
        for i, l in leaves.items():
            l2_services(l, i, [(10, 10010, ["eth1"])])
            host(lab, nodes, f"host{i}", f"10.10.10.{10 * i}/24", mac=HOSTMAC[i])
            if (l.name, "eth1", f"host{i}", "eth1") not in lab.links:
                lab.link(l.name, "eth1", f"host{i}", "eth1")
    for v in ("same-asn-spines", "unique-asn", "unnumbered"):
        lab.check(v, "host1", "ping -c 3 -W 1 10.10.10.30", PING_OK)
        lab.check(v, "leaf1", "ip route show 3.3.3.3", r"nexthop via[\s\S]*nexthop via")
        lab.check(v, "leaf1", "vtysh -c 'show bgp l2vpn evpn route type macip'", r"00:cc:cc:cc:cc:cc")
        lab.check(v, "leaf1", "bridge fdb show dev vxlan10010", r"dst 3\.3\.3\.3")
    lab.check("unnumbered", "leaf1", "ip route show 3.3.3.3", r"via inet6 fe80::")
    lab.check("same-asn-spines", "leaf1", "vtysh -c 'show ip bgp 3.3.3.3/32'", r"65100 65003")
    lab.readme = r"""
## What you will learn

* eBGP-only underlay in FRR: `remote-as external`, peer-groups, `bgp bestpath as-path multipath-relax`
  (ECMP across paths with different AS numbers), `network <loopback>/32`.
* **EVPN over the same eBGP sessions**: spines activate `l2vpn evpn` but are not VTEPs; FRR keeps the
  original next hop (the VTEP loopback) on EVPN routes, so leaves build tunnels to each other, not to spines.
* ASN schemes:
  * **same ASN on all spines** (65100): a path leaf -> spine1 -> leaf2 -> spine2 is impossible (spine2 would
    see its own AS) - no transit leaf, automatically.
  * **unique ASN everywhere**: simpler to reason about, but leaves *can* become transit when a link fails.
* **BGP unnumbered**: `neighbor eth11 interface peer-group SPINES` - the session runs over IPv6 link-local
  (found via Router Advertisements), and IPv4 routes get **IPv6 next hops** (RFC 5549/8950).

## Step by step

```bash
# leaf1
vtysh -c 'show bgp summary'                  # ipv4 unicast + l2vpn evpn on the same peers
vtysh -c 'show ip bgp'                       # AS paths: 65100 65002, 65100 65003 ...
ip route show 3.3.3.3                        # ECMP
vtysh -c 'show bgp l2vpn evpn route type multicast'   # next hop = 2.2.2.2 / 3.3.3.3, not the spine
```

**Transit leaf** (video 32:34), variant `unique-asn`: on spine1 shut the link to leaf1 (`ip link set eth1 down`).
Then on spine1: `vtysh -c 'show ip bgp 1.1.1.1/32'` - spine1 still has a path ... via leaf2 -> spine2 -> leaf1
(AS path `65002 65102 65001`). Traffic for leaf1 that reaches spine1 is now carried by **leaf2's** uplinks.
Do the same in `same-asn-spines`: no path (spine1 rejects `65100` in the AS path) - good, the leaves simply stop
using spine1 for leaf1.

**Unnumbered**:

```bash
vtysh -c 'show bgp neighbors eth11' | grep -i 'hostname\|state\|extended nexthop'
ip -br addr show eth11                       # only fe80::
ip route show 3.3.3.3                        # nexthop via inet6 fe80::... dev eth11
ip neigh show dev eth11                      # FRR installs a fake IPv4 neighbor 169.254.0.1 on older kernels
```
"""
    return lab


# ==========================================================================
# 26 BGP path hunting / MRAI
# ==========================================================================
FLAP = r'''
#!/bin/bash
# Flap the test prefix 10.255.255.1/32 on this leaf.  usage: flap-prefix [down|up|cycle]
case "${1:-cycle}" in
  down)  ip addr del 10.255.255.1/32 dev lo ;;
  up)    ip addr add 10.255.255.1/32 dev lo ;;
  cycle) ip addr del 10.255.255.1/32 dev lo; sleep 5; ip addr add 10.255.255.1/32 dev lo ;;
esac
'''

COUNT = r'''
#!/bin/bash
# Print BGP UPDATE messages received per neighbor.  usage: bgp-updates [reset]
[ "$1" = reset ] && vtysh -c 'clear bgp * soft' >/dev/null
vtysh -c 'show bgp neighbors' | awk '/^BGP neighbor is/{n=$4} /Updates:/{print n, "sent", $2, "rcvd", $3}'
'''


def lab26():
    lab = Lab(26, "bgp-path-hunting", "BGP Path Hunting / Path Exploration in Data Center. BGP MRAI", "CA4kklcCeHk", "52 min", """
When a prefix disappears, BGP speakers don't learn "it's gone" in one step - they first try every
alternative path they still have (**path hunting / path exploration**), sending a burst of UPDATEs.
MRAI (Minimum Route Advertisement Interval) batches updates and changes the picture. You will flap
a prefix and count UPDATE messages across ASN designs and MRAI settings.
""", ref="design_underlay_bgp_hunt")
    lab.diagram = """
         spine1          spine2          (AS 65100 each, or unique 65101/65102)
        / | | \\         / | | \\
     leaf1 leaf2 leaf3 leaf4             AS 65001..65004
       10.255.255.1/32 originated on leaf1 (lo), flapped with `flap-prefix`
    """
    for vname, sasn, mrai, desc in (
            ("unique-asn-mrai0", lambda m: 65100 + m, 0, "unique ASN on every switch, MRAI 0 (FRR datacenter default)"),
            ("unique-asn-mrai5", lambda m: 65100 + m, 5, "unique ASN, MRAI 5 s"),
            ("same-asn-spines", lambda m: 65100, 0, "spines share AS 65100, MRAI 0")):
        nodes = lab.variant(vname, desc, default=(vname == "unique-asn-mrai0"))
        spines, leaves = ebgp_fabric(lab, nodes, 2, [1, 2, 3, 4], sasn, lambda i: 65000 + i, mrai=mrai, evpn=False)
        for n in list(spines.values()) + list(leaves.values()):
            n.files["/usr/local/bin/bgp-updates"] = (COUNT, "755")
            n.frr.line("log syslog debugging")
        l1 = leaves[1]
        l1.comment("test prefix to flap")
        l1.sh("ip addr add 10.255.255.1/32 dev lo")
        l1.frr.bgps[0].af("ipv4 unicast", "network 10.255.255.1/32")
        l1.files["/usr/local/bin/flap-prefix"] = (FLAP, "755")
    for v in ("unique-asn-mrai0", "unique-asn-mrai5", "same-asn-spines"):
        lab.check(v, "leaf4", "vtysh -c 'show ip bgp 10.255.255.1/32'", r"65001")
    lab.check("unique-asn-mrai0", "spine2", "vtysh -c 'show ip bgp 10.255.255.1/32'", r"6500[234] 65101 65001|6500[234] 65102 65001")
    lab.readme = r"""
## What you will learn

* BGP message types and the UPDATE/withdraw flow; why a withdrawal can produce *more* updates than an announcement.
* **Path hunting** in a Clos: with unique ASNs a spine knows 10.255.255.1/32 directly from leaf1 *and* via
  the other leaves (e.g. spine2 learns `65002 65101 65001` = leaf2 -> spine1 -> leaf1, because leaf2's best path goes
  through spine1). When leaf1 withdraws, spine2 switches to one of those stale alternatives, advertises it, then
  withdraws it when its source withdraws too... until nothing is left.
* **MRAI**: `neighbor X advertisement-interval N`. FRR `datacenter` defaults use 0 s (send immediately);
  RFC 4271 suggests 30 s for eBGP. Higher MRAI = fewer, batched updates but slower convergence.
* The structural fix from RFC 7938 / the video: **same ASN on all spines** (and, in 5-stage, per tier) so the
  alternative paths are never accepted in the first place.

## Step by step

```bash
# spine1 / spine2: how many paths for the test prefix?
vtysh -c 'show ip bgp 10.255.255.1/32'
# leaf4: watch updates arrive
bgp-updates                     # per-neighbor UPDATE counters (sent / rcvd)
journalctl -f -t bgpd           # with 'debug bgp updates' enabled (see below)
# leaf1
flap-prefix down ; sleep 10 ; flap-prefix up
```

Turn on update logging where you watch: `vtysh -c 'debug bgp updates'` (logs go to syslog: `journalctl -t bgpd`).
Count the UPDATE messages leaf4 received for one `flap-prefix down` in each variant (run `bgp-updates`
before and after). Typical result: `unique-asn-mrai0` shows several withdraw/re-announce rounds, `same-asn-spines`
just one withdrawal per spine; `unique-asn-mrai5` fewer messages but takes ~5 s+ to converge.

The video's capture approach: `tcpdump -ni eth11 -w /tmp/l4.pcap tcp port 179` on leaf4, open in Wireshark,
filter `bgp.type == 2`.

**EVPN impact** (video 48:20): VTEP loopbacks are underlay prefixes - while they "hunt", EVPN next hops stay
resolvable through stale paths, and type-2 routes keep pointing at a VTEP that may be gone.
"""
    return lab


# ==========================================================================
# 27 iBGP underlay
# ==========================================================================
def lab27():
    lab = Lab(27, "ibgp-underlay", "iBGP as Underlay for EVPN in Data Center", "jfGXKxvVfMg", "24 min", """
The other BGP-only option: **iBGP** in one AS, spines as route reflectors, sessions on the link
addresses - no IGP. You must deal with next hops (`next-hop-self force` on the RRs for the underlay
AF, but *not* for EVPN) and with **router-ids**: a duplicated router-id silently breaks route reflection.
""", ref="design_underlay_ibgp")
    lab.diagram = """
             spine1 (RR)          spine2 (RR)        all AS 65000
            /    |    \\          /    |    \\
         leaf1  leaf2  leaf3   (every leaf to both spines, iBGP on link addresses)
           |      |      |
         host1  host2  host3      VLAN 10 / VNI 10010
    """
    for vname, desc in (("ibgp", "iBGP underlay + EVPN, RR on spines"),
                        ("duplicate-router-id", "leaf2 and leaf3 share router-id 9.9.9.9 - spot the problem")):
        nodes = lab.variant(vname, desc, default=(vname == "ibgp"))
        spines, leaves = OrderedDict(), OrderedDict()
        for m in (1, 2):
            s = Node(f"spine{m}", "router", "spine")
            loopback(s, spine_lo(m))
            nodes[s.name] = s
            spines[m] = s
        for i in (1, 2, 3):
            l = Node(f"leaf{i}", "router", "leaf")
            loopback(l, leaf_lo(i))
            nodes[l.name] = l
            leaves[i] = l
        for m, s in spines.items():
            for i in leaves:
                if (s.name, f"eth{i}", f"leaf{i}", f"eth{10 + m}") not in lab.links:
                    lab.link(s.name, f"eth{i}", f"leaf{i}", f"eth{10 + m}")
                addr(s, f"eth{i}", f"10.{i}.{10 + m}.{10 + m}/24")
            b = s.frr.bgp(65000, spine_lo(m))
            b.g("no bgp default ipv4-unicast", f"bgp cluster-id {spine_lo(m)}", "neighbor LEAVES peer-group",
                "neighbor LEAVES remote-as internal")
            for i in leaves:
                b.g(f"neighbor 10.{i}.{10 + m}.{i} peer-group LEAVES")
            b.af("ipv4 unicast", "neighbor LEAVES activate", "neighbor LEAVES route-reflector-client",
                 "neighbor LEAVES next-hop-self force", f"network {spine_lo(m)}/32", "maximum-paths ibgp 4")
            b.af("l2vpn evpn", "neighbor LEAVES activate", "neighbor LEAVES route-reflector-client")
        for i, l in leaves.items():
            for m in spines:
                addr(l, f"eth{10 + m}", f"10.{i}.{10 + m}.{i}/24")
            rid = "9.9.9.9" if (vname == "duplicate-router-id" and i in (2, 3)) else leaf_lo(i)
            b = l.frr.bgp(65000, rid)
            b.g("no bgp default ipv4-unicast", "neighbor SPINES peer-group", "neighbor SPINES remote-as internal")
            for m in spines:
                b.g(f"neighbor 10.{i}.{10 + m}.{10 + m} peer-group SPINES")
            b.af("ipv4 unicast", "neighbor SPINES activate", f"network {leaf_lo(i)}/32", "maximum-paths ibgp 4")
            b.af("l2vpn evpn", "neighbor SPINES activate", "advertise-all-vni")
            l2_services(l, i, [(10, 10010, ["eth1"])])
            host(lab, nodes, f"host{i}", f"10.10.10.{10 * i}/24", mac=HOSTMAC[i])
            if (l.name, "eth1", f"host{i}", "eth1") not in lab.links:
                lab.link(l.name, "eth1", f"host{i}", "eth1")
    c = lambda *a: lab.check("ibgp", *a)
    c("leaf1", "ip route show 3.3.3.3", r"nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12")
    c("host1", "ping -c 3 -W 1 10.10.10.30", PING_OK)
    c("leaf1", "vtysh -c 'show bgp l2vpn evpn route type multicast'", r"\[3\]:\[0\]:\[32\]:\[3\.3\.3\.3\]")
    lab.check("duplicate-router-id", "leaf2", "vtysh -c 'show ip bgp 3.3.3.3/32'", r"Network not in table|not in table")
    lab.readme = r"""
## What you will learn

* iBGP doesn't change next hops and doesn't re-advertise iBGP routes - hence **route reflectors**.
* For the underlay AF the RR must rewrite the next hop to itself (`next-hop-self force` - plain
  `next-hop-self` doesn't touch reflected routes); for EVPN it must **not** (the next hop *is* the VTEP).
  That's why the two address families have different neighbor settings on the spines.
* `bgp cluster-id` per RR, ORIGINATOR_ID and CLUSTER_LIST loop prevention.
* **Router-id matters**: in an IPv6-only fabric there is no IPv4 address to derive it from, and a duplicated
  router-id makes the RR-reflected route look like the receiver's own (ORIGINATOR_ID == my router-id) -> dropped.

## Step by step

```bash
# leaf1
vtysh -c 'show ip bgp'                         # next hop = spine link address (next-hop-self force)
vtysh -c 'show ip bgp 3.3.3.3/32'              # Originator: 3.3.3.3, Cluster list: 11.11.11.11
vtysh -c 'show bgp l2vpn evpn route type multicast'   # next hop 3.3.3.3 untouched
```

Variant `duplicate-router-id`: leaf2 and leaf3 both use router-id 9.9.9.9.

```bash
# leaf2
vtysh -c 'show ip bgp 3.3.3.3/32'              # missing!
vtysh -c 'show bgp l2vpn evpn route'           # leaf3's routes missing too
journalctl -t bgpd | grep -i originator        # or: debug bgp updates in
```

host2 <-> host3 breaks while everything *looks* up (`show bgp summary` is all Established). Fix the
router-id and `clear bgp *`.

## eBGP vs iBGP underlay (video 22:34)

* iBGP: one AS, no AS-path tricks, but needs RRs, next-hop handling, and has no AS-path loop protection inside the fabric.
* eBGP: per-hop next-hop-self for free, AS-path loop prevention, but ASN planning and path hunting (lab 26).
"""
    return lab


# ==========================================================================
# 28 Mixed IPv4/IPv6 underlay (RFC 5549 / 8950)
# ==========================================================================
def lab28():
    lab = Lab(28, "mixed-underlay-rfc5549", "Mixed IPv4+IPv6 Underlay for EVPN. RFCs 5549 and 8950", "M__PhG_GMx8", "23 min", """
IPv4 loopbacks and VTEPs, but **no IPv4 on any fabric link**: eBGP unnumbered sessions run over IPv6
link-local addresses and carry IPv4 prefixes with **IPv6 next hops** (RFC 5549, updated by RFC 8950).
The Linux kernel forwards IPv4 packets to an IPv6 next hop natively (`via inet6 fe80::...`). A second
variant goes all the way: pure IPv6 core with IPv6 VTEPs.
""", ref="design_underlay_mixed")
    lab.diagram = """
         spine1 AS 65100            spine2 AS 65100
           |  \\                   /   |
         leaf1  AS 65001        leaf2  AS 65002      links: IPv6 link-local only
           |                      |
         host1                  host2                VLAN 10 / VNI 10010
     v4-loopbacks: lo 1.1.1.1 / 2.2.2.2 (IPv4 VTEPs)  ipv6-core: lo fc00::1 / fc00::2 (IPv6 VTEPs)
    """
    for vname, desc in (("v4-over-v6", "IPv4 NLRI with IPv6 next hops (extended next hop), IPv4 VTEPs"),
                        ("ipv6-core", "IPv6 loopbacks + IPv6 VTEPs, EVPN over IPv6 sessions (FRR >= 10.6)")):
        nodes = lab.variant(vname, desc, default=(vname == "v4-over-v6"))
        spines, leaves = ebgp_fabric(lab, nodes, 2, [1, 2], lambda m: 65100, lambda i: 65000 + i, unnumbered=True)
        if vname == "ipv6-core":
            for m, s in spines.items():
                s.netlines = [ln.replace(f"ip addr add {spine_lo(m)}/32 dev lo", f"ip -6 addr add {spine_lo6(m)}/128 dev lo") for ln in s.netlines]
                s.lo4, s.lo6 = None, spine_lo6(m)
                b = s.frr.bgps[0]
                b.afs["ipv4 unicast"] = [x for x in b.afs["ipv4 unicast"] if not x.startswith("network")]
                b.af("ipv6 unicast", "neighbor LEAVES activate", f"network {spine_lo6(m)}/128")
            for i, l in leaves.items():
                l.netlines = [ln.replace(f"ip addr add {leaf_lo(i)}/32 dev lo", f"ip -6 addr add {leaf_lo6(i)}/128 dev lo") for ln in l.netlines]
                l.lo4, l.lo6 = None, leaf_lo6(i)
                b = l.frr.bgps[0]
                b.afs["ipv4 unicast"] = [x for x in b.afs["ipv4 unicast"] if not x.startswith("network")]
                b.af("ipv6 unicast", "neighbor SPINES activate", f"network {leaf_lo6(i)}/128")
        for i, l in leaves.items():
            l2_services(l, i, [(10, 10010, ["eth1"])], local=leaf_lo6(i) if vname == "ipv6-core" else leaf_lo(i))
            host(lab, nodes, f"host{i}", f"10.10.10.{10 * i}/24", mac=HOSTMAC[i])
            if (l.name, "eth1", f"host{i}", "eth1") not in lab.links:
                lab.link(l.name, "eth1", f"host{i}", "eth1")
    lab.check("v4-over-v6", "leaf1", "ip route show 2.2.2.2", r"via inet6 fe80::")
    lab.check("v4-over-v6", "leaf1", "vtysh -c 'show ip bgp 2.2.2.2/32'", r"fe80::")
    lab.check("v4-over-v6", "host1", "ping -c 3 -W 1 10.10.10.20", PING_OK)
    lab.check("ipv6-core", "leaf1", "ip -6 route show fc00::2", r"via fe80::")
    lab.check("ipv6-core", "host1", "ping -c 3 -W 1 10.10.10.20", PING_OK)
    lab.readme = r"""
## What you will learn

* **Extended next hop** capability (RFC 8950): IPv4 NLRI whose next hop is an IPv6 address. FRR enables it
  automatically for interface-based (`neighbor eth11 interface`) sessions.
* Kernel side: `ip route show 2.2.2.2` -> `nexthop via inet6 fe80::xxxx dev eth11` - IPv4 forwarding uses the
  neighbor's MAC learnt via IPv6 ND. (Older kernels needed the 169.254.0.1 trick.)
* Why this is the sweet spot for many fabrics: zero link addressing, IPv4 overlay/VTEPs everyone understands,
  no dependence on vendors' IPv6-VTEP support.
* `ipv6-core` variant: everything IPv6 (loopbacks, VTEPs, BGP next hops), tenants still IPv4. """ + V6NOTE + r"""

## Step by step

```bash
# leaf1
vtysh -c 'show bgp neighbors eth11' | grep -i -A2 'extended nexthop'
vtysh -c 'show ip bgp'                       # next hop column: fe80::... for IPv4 prefixes
ip route show 2.2.2.2
ip -6 neigh show dev eth11                   # the MAC used for IPv4 packets
tcpdump -ni eth11 -e udp port 4789           # outer IPv4 1.1.1.1 -> 2.2.2.2 over a link with no IPv4 address!
```

Compare with `ipv6-core`: `bridge fdb show dev vxlan10010` shows `dst fc00::2`, and the capture shows an
IPv6 outer header (70 bytes of overhead instead of 50).
"""
    return lab


LABS = [lab23, lab24, lab25, lab26, lab27, lab28]
