from gen import *
from labs_basics import HOSTMAC, BGP_UP, PING_OK

FW_NFT = """
nft add table inet fw
nft add chain inet fw forward '{ type filter hook forward priority 0; policy accept; }'
nft add rule inet fw forward ct state established,related counter accept
nft add rule inet fw forward counter log prefix '"FW-NEW "' level info accept
"""


def fw_node(nodes, name="fw"):
    fw = Node(name, "router", "fw")
    fw.notes.append("Linux 'firewall': FRR + nftables counters")
    nodes[name] = fw
    return fw


# ==========================================================================
# 14 Service insertion - VRF sandwich
# ==========================================================================
def lab14():
    lab = Lab(14, "service-insertion-vrf-sandwich", "Service Insertion in EVPN. VRF Sandwich", "roktYzoyW5U", "43 min", """
Force traffic between two tenant VRFs through a firewall: the **VRF sandwich**. A service leaf
connects VRF A to the firewall's inside and VRF B to its outside; the firewall (a Linux box running
FRR, AS 100) peers eBGP with both VRFs and re-advertises one side's routes to the other. Because both
VRFs live in AS 65000, BGP loop prevention drops the routes - fixed with **as-override**.
""", ref="service_insertion")
    lab.diagram = """
                  spine1                  spine2
         leaf1                leaf2                leaf3 (service leaf)
       e1     e2            e1     e2           eth1 (VRF A)  eth2 (VRF B)
     host1   host3        host2   host4           |               |
   VRF A VLAN10 10.10.10.0/24   VRF B VLAN20 10.20.20.0/24     eth1  fw  eth2     AS 100
                                                  172.16.31.0/24   172.16.32.0/24
   L3VNI: A 10100, B 10200
    """
    for vname, desc in (("no-as-override", "routes are dropped by AS-path loop prevention"),
                        ("as-override", "fw uses as-override -> traffic A <-> B flows through fw")):
        nodes = lab.variant(vname, desc, default=(vname == "as-override"))
        spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3])
        std_overlay(spines, leaves)
        fw = fw_node(nodes)
        for i, l in leaves.items():
            if i == 1:
                l2_services(l, i, [(10, 10010, ["eth1", "eth2"])])
            elif i == 2:
                l2_services(l, i, [(20, 10020, ["eth1", "eth2"])])
            else:
                bridge(l, leaf_mac(i))
            vrfs = {1: ["A"], 2: ["B"], 3: ["A", "B"]}[i]
            for v in vrfs:
                vrf_dev(l, v, 1001 if v == "A" else 1002)
            if i == 1:
                svi(l, 10, "10.10.10.1/24", vrf="A")
            if i == 2:
                svi(l, 20, "10.20.20.1/24", vrf="B")
            for v in vrfs:
                l3vni(l, v, 10100 if v == "A" else 10200, 4001 if v == "A" else 4002, leaf_lo(i))
            leaf_overlay(l, i, spines)
            for v in vrfs:
                b = vrf_evpn(l, 65000, leaf_lo(i), v, connected=(i != 3))
                if i == 3:
                    ifn, sub = ("eth1", 31) if v == "A" else ("eth2", 32)
                    addr(l, ifn, f"172.16.{sub}.3/24", vrf=v)
                    b.g(f"neighbor 172.16.{sub}.1 remote-as 100")
                    b.af("ipv4 unicast", f"neighbor 172.16.{sub}.1 route-map NO-HOSTS out")
            if i == 3:
                l.frr.line("ip prefix-list HOSTS seq 10 permit 0.0.0.0/0 ge 32")
                l.frr.block("route-map NO-HOSTS deny 10\n match ip address prefix-list HOSTS\nexit\n!\nroute-map NO-HOSTS permit 20\nexit")
        addr(fw, "eth1", "172.16.31.1/24", desc="inside  (VRF A)")
        addr(fw, "eth2", "172.16.32.1/24", desc="outside (VRF B)")
        fw.comment("stateful 'firewall' - counters show the steered traffic")
        fw.sh(FW_NFT)
        fb = fw.frr.bgp(100, "172.16.31.1")
        fb.g("no bgp ebgp-requires-policy")
        for ip in ("172.16.31.3", "172.16.32.3"):
            fb.g(f"neighbor {ip} remote-as 65000", f"neighbor {ip} solo")
            if vname == "as-override":
                fb.af("ipv4 unicast", f"neighbor {ip} as-override")
        host(lab, nodes, "host1", "10.10.10.10/24", "10.10.10.1", HOSTMAC[1])
        host(lab, nodes, "host3", "10.10.10.30/24", "10.10.10.1", HOSTMAC[3])
        host(lab, nodes, "host2", "10.20.20.20/24", "10.20.20.1", HOSTMAC[2])
        host(lab, nodes, "host4", "10.20.20.40/24", "10.20.20.1", HOSTMAC[4])
    for t in (("leaf1", "eth1", "host1", "eth1"), ("leaf1", "eth2", "host3", "eth1"), ("leaf2", "eth1", "host2", "eth1"),
              ("leaf2", "eth2", "host4", "eth1"), ("leaf3", "eth1", "fw", "eth1"), ("leaf3", "eth2", "fw", "eth2")):
        lab.link(*t)
    lab.check("no-as-override", "host1", "ping -c 2 -W 1 10.20.20.20", r"100% packet loss|Unreachable")
    lab.check("no-as-override", "fw", "vtysh -c 'show ip bgp'", r"10\.10\.10\.0/24")
    c = lambda *a: lab.check("as-override", *a)
    c("leaf1", "ip route show vrf A 10.20.20.0/24", r"10\.20\.20\.0/24")
    c("host1", "ping -c 3 -W 1 10.20.20.20", PING_OK)
    c("host1", "traceroute -n -w 1 -q 1 10.20.20.20", r"172\.16\.3[12]\.1")
    c("fw", "nft list table inet fw", r"counter packets [1-9]")
    lab.readme = r"""
## What you will learn

* The VRF sandwich: tenant VRFs never import each other's routes in EVPN; the only path between them is
  `VRF A -> service leaf -> fw -> service leaf -> VRF B`.
* **eBGP loop prevention**: fw receives `10.10.10.0/24` with AS path `65000` from VRF A and sends it to VRF B
  as `100 65000`; leaf3 (AS 65000) sees its own AS and drops it. Fixes: `as-override` on the fw
  (replace 65000 with 100) or `allowas-in` on the leaves.
* FRR detail from the video: FRR eBGP *does* advertise a route back to the peer it came from (the receiver
  drops it). `neighbor X solo` stops that - it puts the neighbor in its own update-group.
* A Linux box as a stateful firewall: nftables `forward` chain with conntrack and counters.

## Step by step

Push `no-as-override` first:

```bash
# fw
vtysh -c 'show ip bgp'                                     # has both tenants' subnets
vtysh -c 'show ip bgp neighbors 172.16.32.3 advertised-routes'   # 10.10.10.0/24 is sent to VRF B...
# leaf3
vtysh -c 'show bgp vrf B ipv4 unicast'                     # ...but not accepted (AS loop)
vtysh -c 'show bgp vrf B neighbors 172.16.32.1' | grep -i 'loop\|denied'
```

Then `as-override`:

```bash
# leaf3
vtysh -c 'show bgp vrf B ipv4 unicast 10.10.10.0/24'       # AS path "100 100"
# leaf1
vtysh -c 'show bgp l2vpn evpn route type prefix'           # 10.20.20.0/24 advertised by leaf3 in VRF A
ip route show vrf A
# host1
traceroute -n 10.20.20.20                                  # ... 172.16.31.1 (fw) ...
# fw
nft list table inet fw                                     # counters climb
journalctl -k | grep FW-NEW                                # new flows logged
```

**Block something on the "firewall"**: `nft insert rule inet fw forward ip daddr 10.20.20.40 icmp type echo-request drop`
and ping host4 from host1.

## Disadvantages (video 37:00) to think about

* Every inter-VRF flow hair-pins through the service leaf and the fw - bandwidth and latency.
* One sandwich per pair of VRFs doesn't scale -> lab 15 (dedicated service VRFs) and lab 16 (PBR).
* Firewall HA: with an active/standby pair, BGP sessions to the standby must not attract traffic
  (AS-path prepend / MED from the standby, or the fw cluster's single virtual IP).
"""
    return lab


# ==========================================================================
# 15 Multitenant service insertion
# ==========================================================================
def lab15():
    lab = Lab(15, "service-insertion-multitenant", "Multitenant Service Insertion in EVPN. Advanced VRF Sandwich",
              "JMo-iI2npy4", "57 min", """
Four tenants (A, B, C, D) share one firewall through two **service VRFs** on the service leaf:
`OUT` (towards the fw, collects every tenant's routes) and `IN` (from the fw, gives tenants the routes
they are allowed to reach). Which tenant can talk to which is pure **route policy** - full mesh or
partial mesh - and a sloppy policy creates loops.
""", ref="service_insertion_multitenant")
    lab.diagram = """
                  spine1                      spine2
          leaf1                 leaf2                    leaf3 (service leaf)
        e1     e2             e1     e2            VRFs A B C D + OUT + IN
      host1   host3         host2   host4          eth1 (OUT)        eth2 (IN)
     A VLAN10 C VLAN30     B VLAN20 D VLAN40         |                  |
     10.10.10.10 10.30.30.30 10.20.20.20 10.40.40.40  eth1 ---- fw ---- eth2     AS 100
                                                  172.16.31.0/24     172.16.32.0/24
    """
    tenants = {"A": (10, 1, 1001, 10100), "B": (20, 2, 1002, 10200), "C": (30, 1, 1003, 10300), "D": (40, 2, 1004, 10400)}
    allowed = {
        "full-mesh": {"A": "BCD", "B": "ACD", "C": "ABD", "D": "ABC"},
        "partial-mesh": {"A": "BC", "B": "A", "C": "A", "D": ""},
    }
    for vname, desc in (("full-mesh", "every tenant can reach every other tenant through the fw"),
                        ("partial-mesh", "A<->B, A<->C only; D is isolated")):
        nodes = lab.variant(vname, desc, default=(vname == "partial-mesh"))
        spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3])
        std_overlay(spines, leaves)
        fw = fw_node(nodes)
        for i, l in leaves.items():
            mine = [t for t, (vl, li, tb, vni) in tenants.items() if li == i] if i != 3 else list(tenants)
            if i != 3:
                l2_services(l, i, [(tenants[t][0], 10000 + tenants[t][0], [f"eth{k + 1}"]) for k, t in enumerate(mine)])
            else:
                bridge(l, leaf_mac(i))
            for t in mine:
                vrf_dev(l, t, tenants[t][2])
            for t in mine:
                vl = tenants[t][0]
                if i != 3:
                    svi(l, vl, f"10.{vl}.{vl}.1/24", vrf=t)
                l3vni(l, t, tenants[t][3], 4000 + vl, leaf_lo(i))
            leaf_overlay(l, i, spines)
            for t in mine:
                b = vrf_evpn(l, 65000, leaf_lo(i), t, connected=(i != 3))
                if i == 3:
                    ok = allowed[vname][t]
                    pl = [f"ip prefix-list TO-{t} seq {5 * (k + 1)} permit 10.{tenants[o][0]}.{tenants[o][0]}.0/24"
                          for k, o in enumerate(ok)] or [f"ip prefix-list TO-{t} seq 5 deny any"]
                    l.frr.line(*pl)
                    l.frr.block(f"route-map FROM-IN-TO-{t} permit 10\n match ip address prefix-list TO-{t}\nexit")
                    b.af("ipv4 unicast", f"import vrf route-map FROM-IN-TO-{t}", "import vrf IN")
            if i == 3:
                l.comment("service VRFs: OUT faces the fw inside, IN faces the fw outside")
                vrf_dev(l, "OUT", 1100)
                vrf_dev(l, "IN", 1101)
                addr(l, "eth1", "172.16.31.3/24", vrf="OUT")
                addr(l, "eth2", "172.16.32.3/24", vrf="IN")
                l.frr.line("ip prefix-list SUBNETS seq 5 permit 10.0.0.0/8 le 24")
                l.frr.block("route-map SUBNETS-ONLY permit 10\n match ip address prefix-list SUBNETS\nexit")
                ob = l.frr.bgp(65000, leaf_lo(i), "OUT")
                ob.g("neighbor 172.16.31.1 remote-as 100")
                ob.af("ipv4 unicast", "import vrf route-map SUBNETS-ONLY", *[f"import vrf {t}" for t in tenants],
                      "neighbor 172.16.31.1 route-map SUBNETS-ONLY out")
                ib = l.frr.bgp(65000, leaf_lo(i), "IN")
                ib.g("neighbor 172.16.32.1 remote-as 100")
                ib.af("ipv4 unicast", "neighbor 172.16.32.1 route-map SUBNETS-ONLY in")
        addr(fw, "eth1", "172.16.31.1/24", desc="towards VRF OUT")
        addr(fw, "eth2", "172.16.32.1/24", desc="towards VRF IN")
        fw.sh(FW_NFT)
        fb = fw.frr.bgp(100, "172.16.31.1")
        fb.g("no bgp ebgp-requires-policy")
        for ip in ("172.16.31.3", "172.16.32.3"):
            fb.g(f"neighbor {ip} remote-as 65000", f"neighbor {ip} solo")
            fb.af("ipv4 unicast", f"neighbor {ip} as-override")
        for k, (t, (vl, li, tb, vni)) in enumerate(tenants.items()):
            host(lab, nodes, f"host{k + 1}", f"10.{vl}.{vl}.{vl}/24", f"10.{vl}.{vl}.1", HOSTMAC[k + 1])
    for t in (("leaf1", "eth1", "host1", "eth1"), ("leaf1", "eth2", "host3", "eth1"), ("leaf2", "eth1", "host2", "eth1"),
              ("leaf2", "eth2", "host4", "eth1"), ("leaf3", "eth1", "fw", "eth1"), ("leaf3", "eth2", "fw", "eth2")):
        lab.link(*t)
    lab.check("full-mesh", "host1", "ping -c 3 -W 1 10.40.40.40", PING_OK)
    lab.check("full-mesh", "host3", "ping -c 3 -W 1 10.20.20.20", PING_OK)
    c = lambda *a: lab.check("partial-mesh", *a)
    c("host1", "ping -c 3 -W 1 10.20.20.20", PING_OK, "A -> B allowed")
    c("host1", "ping -c 3 -W 1 10.30.30.30", PING_OK, "A -> C allowed")
    c("host3", "ping -c 2 -W 1 10.20.20.20", r"100% packet loss|Unreachable", "C -> B not allowed")
    c("host4", "ping -c 2 -W 1 10.10.10.10", r"100% packet loss|Unreachable", "D isolated")
    c("fw", "nft list table inet fw", r"counter packets [1-9]")
    lab.readme = r"""
## What you will learn

* **Dedicated service VRFs** so that adding tenant N doesn't need another pair of fw interfaces:
  * `OUT` imports every tenant's subnets and advertises them to the fw;
  * the fw sends them back (as-override) into `IN`;
  * each tenant VRF imports from `IN` only the prefixes it is allowed to reach -> **policy = route-maps**.
* **Loops**: if tenant A imported its *own* prefix back from `IN`, the service leaf would prefer the eBGP
  copy (via fw) over the EVPN one and hair-pin A's own traffic forever. Each `TO-<tenant>` prefix-list
  only permits *other* tenants.
* Route leaking chains on FRR: `import vrf` from tenant VRFs into OUT, from IN into tenant VRFs, each
  filtered by `import vrf route-map ...`.

## Linux vs the video

The video keeps the tenant VRFs **off** the service leaf and uses EVPN RT tricks (export with rewritten
RTs `101:101`, `202:202` ...). On Linux every VRF has exactly one L3VNI, and a route imported into VRF A
always egresses with **A's** L3VNI - so a type-5 route originated in `IN` (different L3VNI) can't be used
directly by VRF A on leaf1. The Linux-friendly equivalent is to instantiate the tenant VRFs on the service
leaf and do the leaking there, which is what this lab does. The policy logic (who imports what) is the same.

## Step by step

```bash
# leaf3
vtysh -c 'show bgp vrf OUT ipv4 unicast'     # all 4 tenant subnets (leaked)
vtysh -c 'show bgp vrf IN ipv4 unicast'      # same subnets learnt back from the fw (AS path 100 100)
vtysh -c 'show bgp vrf A ipv4 unicast'       # only the subnets A may reach, via IN
ip route show vrf A
# leaf1
ip route show vrf A ; ip route show vrf C    # what each tenant can reach fabric-wide
```

Partial mesh test matrix (`partial-mesh`): A<->B ok, A<->C ok, B<->C blocked, D isolated.
Edit `ip prefix-list TO-D` on leaf3 to allow D -> A (and TO-A to allow A -> D) and re-test.

**Build a loop on purpose** (video 31:43): on leaf3 add A's own subnet to `TO-A`
(`ip prefix-list TO-A seq 100 permit 10.10.10.0/24`), then `clear bgp vrf A *`. Compare
`vtysh -c 'show bgp vrf A ipv4 unicast 10.10.10.0/24'` before/after and ping host1 -> host3. Remove it again.
"""
    return lab


# ==========================================================================
# 16 Service insertion with PBR
# ==========================================================================
def lab16():
    lab = Lab(16, "service-insertion-pbr", "Service Insertion in EVPN using PBR", "VsSOVx5P3UM", "50 min", """
Instead of a VRF sandwich, steer only *selected* flows to the firewall with **policy-based routing**
on the ingress leaf's SVI. The firewall sits in a stretched **service VLAN 999**; FRR's `pbrd`
installs Linux `ip rule`s that send 10.10.10.0/24 -> 10.20.20.0/24 to the fw instead of the normal route.
""", ref="service_insertion_pbr")
    lab.diagram = """
                  spine1                     spine2
          leaf1                 leaf2                 leaf3 (service leaf)
           e1                    e1                 e1 (VLAN 999)   e2 (VRF A, routed)
         host1                 host2                  |               |
     VLAN10 10.10.10.10    VLAN20 10.20.20.20        eth1     fw     eth2
                                                10.100.100.100/24   172.16.32.1/24
     all in VRF A (L3VNI 10100); VLAN 999 (VNI 10999, 10.100.100.0/24) on every leaf
     VLAN 999 SVIs live in VRF SVC (no L3VNI), the tenant (hosts, L3VNI) in VRF A
     pbr on leaf1 vlan10: src 10.10.10.0/24 dst 10.20.20.0/24 -> nexthop 10.100.100.100 in VRF SVC
    """
    for vname, desc in (("one-way", "PBR on leaf1 only (asymmetric through the fw)"),
                        ("symmetric", "PBR on leaf1 and on leaf2 for the return direction")):
        nodes = lab.variant(vname, desc, default=(vname == "symmetric"))
        spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3])
        std_overlay(spines, leaves)
        fw = fw_node(nodes)
        for i, l in leaves.items():
            svc = {1: [(10, 10010, ["eth1"]), (999, 10999, [])], 2: [(20, 10020, ["eth1"]), (999, 10999, [])],
                   3: [(999, 10999, ["eth1"])]}[i]
            l2_services(l, i, svc)
            vrf_dev(l, "A", 1001)
            if i == 1:
                svi(l, 10, "10.10.10.1/24", vrf="A")
            if i == 2:
                svi(l, 20, "10.20.20.1/24", vrf="A")
            vrf_dev(l, "SVC", 1999)
            svi(l, 999, "10.100.100.1/24", vrf="SVC",
                comment="service VLAN SVI in its own VRF without L3VNI -> no host routes for the fw")
            l3vni(l, "A", 10100, 4001, leaf_lo(i))
            if i == 3:
                addr(l, "eth2", "172.16.32.3/24", vrf="A")
            leaf_overlay(l, i, spines)
            vrf_evpn(l, 65000, leaf_lo(i), "A")
            pbr = None
            if i == 1:
                pbr = ("vlan10", "10.10.10.0/24", "10.20.20.0/24")
            if i == 2 and vname == "symmetric":
                pbr = ("vlan20", "10.20.20.0/24", "10.10.10.0/24")
            if pbr:
                ifn, src, dst = pbr
                l.frr.block(f"""
                    pbr-map TO-FW seq 10
                     match src-ip {src}
                     match dst-ip {dst}
                     set nexthop 10.100.100.100 nexthop-vrf SVC
                    exit""")
                l.frr.iface(ifn, "pbr-policy TO-FW")
        addr(fw, "eth1", "10.100.100.100/24", desc="service VLAN 999")
        addr(fw, "eth2", "172.16.32.1/24", desc="back into VRF A on leaf3")
        fw.sh("ip link set eth1 mtu 1450")
        fw.sh(FW_NFT)
        gw_keepalive(fw, ["10.100.100.1"])
        fw.frr.line("ip route 10.10.10.0/24 172.16.32.3", "ip route 10.20.20.0/24 172.16.32.3")
        host(lab, nodes, "host1", "10.10.10.10/24", "10.10.10.1", HOSTMAC[1])
        host(lab, nodes, "host2", "10.20.20.20/24", "10.20.20.1", HOSTMAC[2])
    for t in (("leaf1", "eth1", "host1", "eth1"), ("leaf2", "eth1", "host2", "eth1"),
              ("leaf3", "eth1", "fw", "eth1"), ("leaf3", "eth2", "fw", "eth2")):
        lab.link(*t)
    for v in ("one-way", "symmetric"):
        lab.check(v, "host1", "ping -c 3 -W 1 10.20.20.20", PING_OK)
        lab.check(v, "leaf1", "ip rule show", r"from 10\.10\.10\.0/24 to 10\.20\.20\.0/24 iif vlan10")
        lab.check(v, "host1", "traceroute -n -w 1 -q 1 10.20.20.20", r"172\.16\.32\.1 ", "hop via the fw")
    lab.check("symmetric", "host2", "traceroute -n -w 1 -q 1 10.10.10.10", r"172\.16\.32\.1 ", "return via the fw")
    lab.readme = r"""
## What you will learn

* FRR **pbrd**: `pbr-map` (match src/dst, set nexthop) applied with `pbr-policy` on an interface.
  Under the hood it is plain Linux policy routing - look at `ip rule` and the extra routing table.
* Why the service VLAN's SVI sits in its **own VRF `SVC` without an L3VNI**: if vlan999 were in VRF A, the fw's
  MAC/IP type-2 route would carry A's L3VNI RT and every leaf would install a **/32 host route** for 10.100.100.100
  via the L3VNI to leaf3. The PBR next hop would resolve through it, the packet would arrive at leaf3 in VRF A and
  be routed straight to host2 - past the firewall. That's the video's "disable host-route advertisement in the
  service VNI" (38:43); on Linux/FRR the clean way is to keep the service SVI out of the tenant VRF. FRR then
  resolves the next hop via the connected 10.100.100.0/24 on vlan999 and bridges to the fw over VNI 10999.
* Asymmetric vs **symmetric PBR**: a stateful fw must see both directions.

## Step by step

```bash
# leaf1
vtysh -c 'show pbr map'                 # installed? which table?
vtysh -c 'show pbr interface'
ip rule show                            # 300: from 10.10.10.0/24 to 10.20.20.0/24 iif vlan10 lookup 10000
ip route show table 10000               # default via 10.100.100.100 dev vlan999
ip neigh show dev vlan999               # fw's MAC (from EVPN type-2)
# host1
traceroute -n 10.20.20.20               # 10.10.10.1 -> 172.16.32.1 (fw; it answers from its egress IP) -> 172.16.32.3 -> 10.20.20.1 -> host2
# fw
nft list table inet fw
```

In `one-way`, traceroute from host2 back to host1 does **not** traverse the fw - a stateful fw would see
only half of each TCP session (conntrack `INVALID`). Push `symmetric` and compare.

## Experiments

* Move `vlan999` into VRF A on all leaves (`ip link set vlan999 master A`) and point the pbr-map at
  `nexthop-vrf A`: `show pbr map detail` now resolves 10.100.100.100 via `vlan4001` (the /32), and a capture on leaf3
  shows the PBR'd packets arriving on the **L3VNI** (VNI 10100) and routed straight to host2 - fw bypassed.
* The video's bug (42:19): detach the policy (`no pbr-policy TO-FW` on vlan10) and check that `ip rule` is cleaned up.
* **Resilient hashing** (47:32): with two firewalls you would use a nexthop-group in the pbr-map
  (`nexthop-group FWS` + `set nexthop-group FWS`); lab 21 shows resilient nexthop groups on Linux.
"""
    return lab


LABS = [lab14, lab15, lab16]
