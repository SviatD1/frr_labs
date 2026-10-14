from gen import *
from labs_basics import HOSTMAC, BGP_UP, PING_OK

EXT_DIAGRAM = """
                 spine1 (RR)                spine2 (RR)
          ________/ |  \\ \\__________   ______/ / |  \\
        leaf1     leaf2     leaf3 (border)   leaf4 (border)        VRF A, L3VNI 10100
      eth1 eth2  eth1 eth2   eth1   eth2      eth1   eth2
      host1 host3 host2 host4  |  \\    ________/      /
                               |   \\  /    __________/
                               |    \\/    /
                               r1 ----X---- r2          AS 65001 (external)
                                \\eth3      /eth3
                                  host5  (FRR, lo 10.100.100.100 = "the internet")
   leaf3 eth1 - r1 eth1 172.16.31.0/24     leaf3 eth2 - r2 eth2 172.16.32.0/24
   leaf4 eth1 - r2 eth1 172.16.42.0/24     leaf4 eth2 - r1 eth2 172.16.41.0/24
   r1 eth3 - host5 eth1 172.16.15.0/24     r2 eth3 - host5 eth2 172.16.25.0/24
"""

BORDER_LINKS = {  # leaf: [(ifname, peer, peer_if, subnet_third_octet_pair)]
    3: [("eth1", "r1", "eth1", "31", 1), ("eth2", "r2", "eth2", "32", 2)],
    4: [("eth1", "r2", "eth1", "42", 2), ("eth2", "r1", "eth2", "41", 1)],
}


def ext_fabric(lab, nodes, vrf="A", l3=10100):
    """Fabric used by labs 07/08: 2 spines, leaf1/2 with hosts, leaf3/4 border, VRF A."""
    spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3, 4])
    std_overlay(spines, leaves)
    for i, l in leaves.items():
        if i in (1, 2):
            l2_services(l, i, [(10, 10010, ["eth1"]), (20, 10020, ["eth2"])])
        else:
            bridge(l, leaf_mac(i))
        vrf_dev(l, vrf, 1001)
        if i in (1, 2):
            svi(l, 10, "10.10.10.1/24", vrf=vrf)
            svi(l, 20, "10.20.20.1/24", vrf=vrf)
        l3vni(l, vrf, l3, 4001, leaf_lo(i))
    host(lab, nodes, "host1", "10.10.10.10/24", "10.10.10.1", HOSTMAC[1])
    host(lab, nodes, "host2", "10.10.10.20/24", "10.10.10.1", HOSTMAC[2])
    host(lab, nodes, "host3", "10.20.20.30/24", "10.20.20.1", HOSTMAC[3])
    host(lab, nodes, "host4", "10.20.20.40/24", "10.20.20.1", HOSTMAC[4])
    for t in (("leaf1", "eth1", "host1", "eth1"), ("leaf2", "eth1", "host2", "eth1"),
              ("leaf1", "eth2", "host3", "eth1"), ("leaf2", "eth2", "host4", "eth1")):
        if t not in lab.links:
            lab.link(*t)
    # external routers
    r = {}
    for k in (1, 2):
        rr = Node(f"r{k}", "router", "ext")
        loopback(rr, f"172.16.{k}.{k}")
        nodes[rr.name] = rr
        r[k] = rr
    h5 = Node("host5", "router", "exthost")
    loopback(h5, "10.100.100.100")
    h5.notes.append("external 'internet' router, runs FRR")
    nodes["host5"] = h5
    for i in (3, 4):
        l = leaves[i]
        l.comment("border links to the external routers (inside VRF A)")
        for ifn, peer, pif, sub, k in BORDER_LINKS[i]:
            addr(l, ifn, f"172.16.{sub}.{i}/24", vrf=vrf)
            addr(r[k], pif, f"172.16.{sub}.{k}/24")
            t = (l.name, ifn, peer, pif)
            if t not in lab.links:
                lab.link(*t)
    for k in (1, 2):
        addr(r[k], "eth3", f"172.16.{k}5.{k}/24")
        addr(h5, f"eth{k}", f"172.16.{k}5.5/24")
        t = (f"r{k}", "eth3", "host5", f"eth{k}")
        if t not in lab.links:
            lab.link(*t)
    return spines, leaves, r, h5


def ext_ospf_core(r, h5):
    for k, rr in r.items():
        ifs = ["eth3"]
        for ifn in ifs:
            rr.frr.iface(ifn, "ip ospf area 0", "ip ospf network point-to-point")
        rr.frr.iface("lo", "ip ospf area 0", "ip ospf passive")
        rr.frr.block(f"router ospf\n ospf router-id {rr.lo4}\nexit")
    for ifn in ("eth1", "eth2"):
        h5.frr.iface(ifn, "ip ospf area 0", "ip ospf network point-to-point")
    h5.frr.iface("lo", "ip ospf area 0", "ip ospf passive")
    h5.frr.block("router ospf\n ospf router-id 10.100.100.100\nexit")


# ==========================================================================
# 07 External routing with OSPF
# ==========================================================================
def lab07():
    lab = Lab(7, "external-routing-ospf", "External Routing in EVPN using OSPF. Mutual redistribution and loop avoidance",
              "EEXWnOcnE1g", "1 h 14 min", """
North-south traffic: two **border leaves** connect tenant VRF A to an external OSPF domain. OSPF routes
are redistributed into BGP (and become EVPN type-5 routes), fabric routes are redistributed into OSPF.
With two border leaves, *mutual redistribution* leaks routes back and forth - you will see sub-optimal
routing and loops, then fix them with **tags, communities and route-maps** exactly like the video.
""", ref="external_routing_ospf")
    lab.diagram = EXT_DIAGRAM
    for vname, desc in (("naive", "plain mutual redistribution OSPF <-> BGP (broken on purpose)"),
                        ("loop-prevention", "tags + communities + route-maps (the fix from the video)")):
        nodes = lab.variant(vname, desc, default=(vname == "loop-prevention"))
        spines, leaves, r, h5 = ext_fabric(lab, nodes)
        ext_ospf_core(r, h5)
        for k, rr in r.items():
            for ifn in ("eth1", "eth2"):
                rr.frr.iface(ifn, "ip ospf area 0", "ip ospf network point-to-point")
        for i, l in leaves.items():
            fp = (vname == "loop-prevention")
            leaf_overlay(l, i, spines, extra_evpn=(["neighbor RR route-map DENY_OSPF_FROM_EVPN in"] if fp and i in (3, 4) else []))
            v4 = ["maximum-paths ibgp 4"]
            if i in (3, 4):
                v4.append("redistribute ospf" + (" route-map OSPF_INTO_BGP" if fp else ""))
                for ifn in ("eth1", "eth2"):
                    l.frr.iface(ifn, "ip ospf area 0", "ip ospf network point-to-point")
                l.frr.block(f"""
                    router ospf vrf A
                     ospf router-id {leaf_lo(i)}
                     redistribute bgp{' route-map BGP_INTO_OSPF' if fp else ''}
                    exit""")
                if fp:
                    l.frr.line("bgp community-list standard OSPF seq 5 permit 65000:65000")
                    l.frr.block("""
                        route-map BGP_INTO_OSPF permit 10
                         set tag 1111
                        exit
                        !
                        route-map OSPF_INTO_BGP deny 5
                         match tag 1111
                        exit
                        !
                        route-map OSPF_INTO_BGP permit 10
                         set community 65000:65000 additive
                        exit
                        !
                        route-map DENY_OSPF_FROM_EVPN deny 10
                         match community OSPF
                        exit
                        !
                        route-map DENY_OSPF_FROM_EVPN permit 20
                        exit""")
            vrf_evpn(l, 65000, leaf_lo(i), "A", extra_v4=v4, connected=(i in (1, 2)))
    for v in ("naive", "loop-prevention"):
        lab.check(v, "r1", "vtysh -c 'show ip ospf neighbor'", r"3\.3\.3\.3.*Full[\s\S]*4\.4\.4\.4.*Full|4\.4\.4\.4.*Full[\s\S]*3\.3\.3\.3.*Full")
    c = lambda *a: lab.check("loop-prevention", *a)
    c("leaf1", "ip route show vrf A 10.100.100.100", r"nexthop via 3\.3\.3\.3[\s\S]*nexthop via 4\.4\.4\.4|nexthop via 4\.4\.4\.4[\s\S]*nexthop via 3\.3\.3\.3")
    c("host1", "ping -c 3 -W 1 10.100.100.100", PING_OK)
    c("host5", "vtysh -c 'show ip route 10.10.10.0/24'", r"ospf")
    c("leaf3", "vtysh -c 'show ip route vrf A 10.100.100.100'", r"Known via \"ospf\"")
    c("host5", "ping -c 3 -W 1 -I 10.100.100.100 10.20.20.40", PING_OK)
    lab.readme = r"""
## What you will learn

* Putting physical interfaces into a VRF on a border leaf (`ip link set eth1 master A`) and running
  **OSPF inside a VRF** in FRR (`router ospf vrf A`).
* Redistribution OSPF -> BGP (becomes EVPN type-5 with the L3VNI) and BGP -> OSPF (type-5 LSAs).
* Why two redistribution points create **feedback loops**, and the classic fix:
  * BGP -> OSPF: `set tag 1111`
  * OSPF -> BGP: deny tag 1111 (never bring our own routes back), `set community 65000:65000`
  * EVPN in (border leaves only): deny routes with that community, so a border never prefers the *other*
    border's copy of an OSPF route over its own OSPF view.

## Step by step

Start with the `naive` variant:

```powershell
python tools\gns3_lab.py push labs\07-external-routing-ospf --variant naive
```

```bash
# leaf3
vtysh -c 'show ip route vrf A'                         # O  vs B  routes
vtysh -c 'show ip ospf vrf A database external'        # what leaf3/leaf4 inject
vtysh -c 'show bgp l2vpn evpn route type prefix'       # who originates 10.100.100.100?
# r1
vtysh -c 'show ip route 10.10.10.0/24'                 # learnt from both borders (E2)
```

Things to look for in `naive`:

1. leaf4 learns 10.100.100.100 both via OSPF (AD 110) **and** via EVPN from leaf3 (iBGP, AD 200).
   Fine as long as OSPF is up. Now shut leaf4's OSPF links (`ip link set eth1 down; ip link set eth2 down`):
   leaf4 now redistributes the EVPN copy *back into OSPF*... once its links come back, which copy wins?
2. Change the BGP distance (`distance bgp 20 100 200` under `router bgp 65000 vrf A` / ipv4 unicast) like in
   the video and watch the border leaves prefer the **other border's** route over OSPF -> sub-optimal
   routing and, with redistribution into OSPF, a data-plane loop. Use `traceroute -n 10.100.100.100`
   from host1 and `ping -t 64` + `tcpdump` on the border uplinks to see TTL-expiring loops.

Then push `loop-prevention` and repeat. Check:

```bash
# leaf3
vtysh -c 'show route-map'                                 # hit counters
vtysh -c 'show bgp vrf A ipv4 unicast 10.100.100.100/32'  # community 65000:65000 on local OSPF route
vtysh -c 'show ip ospf vrf A database external self-originate'   # tag 1111 on our LSAs
```

## Notes on FRR vs the video's Arista config

* Arista: `router ospf 1 vrf A` + `network ... area 0`. FRR: `router ospf vrf A` + `ip ospf area 0` per interface.
* FRR community-list syntax: `bgp community-list standard OSPF seq 5 permit 65000:65000`.
* The route-map on the EVPN neighbor applies to *all* EVPN routes (type-2/3/5); the explicit `permit 20` keeps everything else.
* The video ends by explaining why IGPs are a poor fit for inter-domain routing (no policy, TE is hard). Lab 08 does the same thing with eBGP.
"""
    return lab


# ==========================================================================
# 08 External routing with BGP
# ==========================================================================
def lab08():
    lab = Lab(8, "external-routing-bgp", "External Routing in EVPN using BGP", "uuUZyg-tZ20", "40 min", """
The same fabric, but the border leaves peer **eBGP** (inside VRF A) with the external AS 65001.
No redistribution, no loops - BGP's AS-path does it for you. You will block host routes from leaking
outside, then do **traffic engineering** with local-preference so that each subnet enters the fabric
through a specific border leaf.
""", ref="external_routing_bgp")
    lab.diagram = EXT_DIAGRAM
    for vname, desc in (("basic", "eBGP border leaves <-> r1/r2, host routes filtered"),
                        ("te", "basic + r1 prefers leaf3 for 10.10.10.0/24, r2 prefers leaf4 for 10.20.20.0/24")):
        nodes = lab.variant(vname, desc, default=(vname == "basic"))
        spines, leaves, r, h5 = ext_fabric(lab, nodes)
        ext_ospf_core(r, h5)
        for i, l in leaves.items():
            leaf_overlay(l, i, spines)
            b = vrf_evpn(l, 65000, leaf_lo(i), "A", extra_v4=["maximum-paths ibgp 4"], connected=(i in (1, 2)))
            if i in (3, 4):
                l.frr.line("ip prefix-list HOSTS seq 10 permit 0.0.0.0/0 ge 32")
                l.frr.block("""
                    route-map OUT deny 10
                     match ip address prefix-list HOSTS
                    exit
                    !
                    route-map OUT permit 20
                    exit""")
                b.g("no bgp ebgp-requires-policy", "neighbor EXT peer-group", "neighbor EXT remote-as 65001")
                for ifn, peer, pif, sub, k in BORDER_LINKS[i]:
                    b.g(f"neighbor 172.16.{sub}.{k} peer-group EXT")
                b.af("ipv4 unicast", "maximum-paths 4", "neighbor EXT route-map OUT out")
        # external AS
        peers = {1: [("172.16.31.3", 3), ("172.16.41.4", 4)], 2: [("172.16.32.3", 3), ("172.16.42.4", 4)]}
        for k, rr in r.items():
            b = rr.frr.bgp(65001, rr.lo4)
            b.g("no bgp ebgp-requires-policy", "neighbor FABRIC peer-group", "neighbor FABRIC remote-as 65000",
                "neighbor IBGP peer-group", "neighbor IBGP remote-as 65001", "neighbor IBGP update-source lo")
            for ip, _ in peers[k]:
                b.g(f"neighbor {ip} peer-group FABRIC")
            b.g(f"neighbor {'172.16.2.2' if k == 1 else '172.16.1.1'} peer-group IBGP",
                f"neighbor 172.16.{k}5.5 remote-as 65001")
            v4_host5 = f"neighbor 172.16.{k}5.5 next-hop-self"
            v4 = ["neighbor IBGP next-hop-self", v4_host5, "maximum-paths 4", "maximum-paths ibgp 4"]
            if vname == "te":
                pfx = "10.10.10.0/24" if k == 1 else "10.20.20.0/24"
                pref_leaf = 3 if k == 1 else 4
                rr.frr.line(f"ip prefix-list PREFER seq 5 permit {pfx}")
                rr.frr.block(f"""
                    route-map FROM-LEAF{pref_leaf} permit 10
                     match ip address prefix-list PREFER
                     set local-preference 200
                    exit
                    !
                    route-map FROM-LEAF{pref_leaf} permit 20
                    exit""")
                nip = [ip for ip, li in peers[k] if li == pref_leaf][0]
                v4.append(f"neighbor {nip} route-map FROM-LEAF{pref_leaf} in")
            b.af("ipv4 unicast", *v4)
        b = h5.frr.bgp(65001, "10.100.100.100")
        b.g("neighbor 172.16.15.1 remote-as 65001", "neighbor 172.16.25.2 remote-as 65001")
        b.af("ipv4 unicast", "network 10.100.100.100/32", "maximum-paths ibgp 4")
    for v in ("basic", "te"):
        lab.check(v, "leaf3", "vtysh -c 'show bgp vrf A summary'", r"172\.16\.31\.1\)?\s+4\s+65001\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\S+\s+\d+")
        lab.check(v, "host1", "ping -c 3 -W 1 10.100.100.100", PING_OK)
        lab.check(v, "r1", "vtysh -c 'show ip bgp'", r"10\.10\.10\.0/24")
        lab.check(v, "r1", "vtysh -c 'show ip bgp 10.10.10.10/32'", r"Network not in table|not in table")
    lab.check("te", "host5", "vtysh -c 'show ip bgp 10.10.10.0/24'", r"Local Pref(erence)?:? ?200|localpref 200")
    lab.check("te", "host5", "ip route get 10.10.10.10", r"via 172\.16\.15\.1")
    lab.check("te", "host5", "ip route get 10.20.20.40", r"via 172\.16\.25\.2")
    lab.readme = r"""
## What you will learn

* eBGP inside a VRF on FRR (`router bgp 65000 vrf A` + neighbors) - the border leaf exchanges routes between
  the VRF's BGP table, EVPN type-5 routes, and the external AS.
* Why you **summarise / filter host routes** (/32 from type-2 MAC-IP) before handing them to the outside world.
* **Traffic engineering**: inbound with local-preference on the external routers; ECMP outbound
  inside the fabric (`maximum-paths`).

## Step by step

```bash
# leaf3
vtysh -c 'show bgp vrf A summary'
vtysh -c 'show bgp vrf A ipv4 unicast'            # external + EVPN-imported routes
vtysh -c 'show bgp vrf A neighbors 172.16.31.1 advertised-routes'   # no /32s thanks to route-map OUT
# leaf1
vtysh -c 'show bgp l2vpn evpn route type prefix'  # 10.100.100.100/32 from both borders
ip route show vrf A 10.100.100.100               # ECMP via 3.3.3.3 and 4.4.4.4 (L3VNI)
# r1 / host5
vtysh -c 'show ip bgp'
```

**Host routes**: on leaf3 remove the outbound route-map
(`no neighbor EXT route-map OUT out` under `address-family ipv4 unicast`) and look at `show ip bgp` on r1:
every host that ever ARPed appears as a /32. Put it back.

**TE (variant `te`)**: host5 now reaches 10.10.10.0/24 via r1 -> leaf3 and 10.20.20.0/24 via r2 -> leaf4
(`ip route get` on host5, or `traceroute -n -s 10.100.100.100 10.10.10.10`).

Ideas from the video to try yourself:

* AS-path prepend on leaf4 for 10.10.10.0/24 (`set as-path prepend 65000 65000` in a route-map OUT entry) instead of LP on the external side.
* *TE with next-hop*: with multiple links between the same routers, set the next hop with `set ip next-hop` in an inbound route-map on r1 (the author's NH route-map).
* Shut a border leaf (`systemctl stop frr` on leaf3) and watch how quickly host5 fails over.
"""
    return lab


# ==========================================================================
# 09 Multi-tenant external routing
# ==========================================================================
def lab09():
    lab = Lab(9, "external-routing-multitenant", "Multi-Tenant External Routing in EVPN", "Zcf54mN1awc", "35 min", """
Two tenants (VRF A and VRF B) need to reach the outside. Option 1: **VRF-lite hand-off** - one
802.1Q sub-interface and one eBGP session per VRF. Option 2: a **shared external connection** - one
`INTERNET` VRF on the border leaves, with routes leaked between the tenants and INTERNET. You will
also see how the shared design can quietly break tenant isolation.
""", ref="external_routing_multi_tenancy")
    lab.diagram = """
                 spine1          spine2
        leaf1    leaf2     leaf3 (border)   leaf4 (border)
       e1   e2  e1   e2       | eth1            | eth1
     host1 host3 host2 host4  r1 ---- eth4 ---- r2       AS 65001
       A     B    A    B      | eth3            | eth3
                            host5            host6
                       192.168.5.5/24    192.168.6.6/24
    VRF A: VLAN10 10.10.10.0/24, L3VNI 1000      VRF B: VLAN30 10.30.30.0/24, L3VNI 2000
    vrf-lite:   leafX eth1.100 (A) 172.16.3X.0/24   leafX eth1.200 (B) 172.17.3X.0/24
    shared:     leafX eth1 (INTERNET) 172.16.3X.0/24, r1/r2 send a default route
    """
    for vname, desc in (("vrf-lite", "one sub-interface + eBGP session per tenant VRF"),
                        ("shared", "INTERNET VRF on the border leaves, route leaking with import vrf")):
        nodes = lab.variant(vname, desc, default=(vname == "vrf-lite"))
        spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3, 4])
        std_overlay(spines, leaves)
        r = {}
        for k in (1, 2):
            rr = Node(f"r{k}", "router", "ext")
            loopback(rr, f"172.16.{k}.{k}")
            nodes[rr.name] = rr
            r[k] = rr
        for i, l in leaves.items():
            if i in (1, 2):
                l2_services(l, i, [(10, 10010, ["eth1"]), (30, 10030, ["eth2"])])
            else:
                bridge(l, leaf_mac(i))
            vrf_dev(l, "A", 1001)
            vrf_dev(l, "B", 1002)
            if i in (1, 2):
                svi(l, 10, "10.10.10.1/24", vrf="A")
                svi(l, 30, "10.30.30.1/24", vrf="B")
            l3vni(l, "A", 1000, 4001, leaf_lo(i))
            l3vni(l, "B", 2000, 4002, leaf_lo(i))
            leaf_overlay(l, i, spines)
            a = vrf_evpn(l, 65000, leaf_lo(i), "A", extra_v4=["maximum-paths ibgp 4"], connected=(i in (1, 2)))
            bb = vrf_evpn(l, 65000, leaf_lo(i), "B", extra_v4=["maximum-paths ibgp 4"], connected=(i in (1, 2)))
            if i in (3, 4):
                k = i - 2
                rr = r[k]
                t = (l.name, "eth1", rr.name, "eth1")
                if t not in lab.links:
                    lab.link(*t)
                l.frr.line("ip prefix-list HOSTS seq 10 permit 0.0.0.0/0 ge 32")
                l.frr.block("route-map NO-HOSTS deny 10\n match ip address prefix-list HOSTS\nexit\n!\nroute-map NO-HOSTS permit 20\nexit")
                rb = rr.frr.bgp(65001, rr.lo4)
                rb.g("no bgp ebgp-requires-policy")
                if vname == "vrf-lite":
                    l.comment("VRF-lite: one 802.1Q sub-interface per tenant towards the external router")
                    l.sh("ip link set eth1 up")
                    rr.sh("ip link set eth1 up")
                    for vid, vrf, sec, bgpi in ((100, "A", 16, a), (200, "B", 17, bb)):
                        l.sh(f"ip link add link eth1 name eth1.{vid} type vlan id {vid}")
                        addr(l, f"eth1.{vid}", f"172.{sec}.3{i}.{i}/24", vrf=vrf)
                        rr.sh(f"ip link add link eth1 name eth1.{vid} type vlan id {vid}")
                        addr(rr, f"eth1.{vid}", f"172.{sec}.3{i}.{k}/24")
                        bgpi.g("no bgp ebgp-requires-policy", f"neighbor 172.{sec}.3{i}.{k} remote-as 65001")
                        bgpi.af("ipv4 unicast", f"neighbor 172.{sec}.3{i}.{k} route-map NO-HOSTS out")
                        rb.g(f"neighbor 172.{sec}.3{i}.{i} remote-as 65000")
                else:
                    vrf_dev(l, "INTERNET", 1100)
                    addr(l, "eth1", f"172.16.3{i}.{i}/24", vrf="INTERNET")
                    addr(rr, "eth1", f"172.16.3{i}.{k}/24")
                    ib = l.frr.bgp(65000, leaf_lo(i), "INTERNET")
                    ib.g("no bgp ebgp-requires-policy", f"neighbor 172.16.3{i}.{k} remote-as 65001")
                    ib.af("ipv4 unicast", "import vrf A", "import vrf B", "maximum-paths 4",
                          f"neighbor 172.16.3{i}.{k} route-map NO-HOSTS out")
                    l.frr.line("ip prefix-list DEFAULT seq 5 permit 0.0.0.0/0")
                    l.frr.block("route-map ONLY-DEFAULT permit 10\n match ip address prefix-list DEFAULT\nexit")
                    a.af("ipv4 unicast", "import vrf route-map ONLY-DEFAULT", "import vrf INTERNET")
                    bb.af("ipv4 unicast", "import vrf route-map ONLY-DEFAULT", "import vrf INTERNET")
                    rb.g(f"neighbor 172.16.3{i}.{i} remote-as 65000")
                    rb.af("ipv4 unicast", f"neighbor 172.16.3{i}.{i} default-originate")
                addr(rr, "eth3", f"192.168.{4 + k}.1/24")
                addr(rr, "eth4", f"172.16.12.{k}/24")
                rb.g(f"neighbor 172.16.12.{3 - k} remote-as 65001")
                rb.af("ipv4 unicast", "redistribute connected", f"neighbor 172.16.12.{3 - k} next-hop-self")
        for t in (("r1", "eth4", "r2", "eth4"), ("leaf1", "eth1", "host1", "eth1"), ("leaf1", "eth2", "host3", "eth1"),
                  ("leaf2", "eth1", "host2", "eth1"), ("leaf2", "eth2", "host4", "eth1"),
                  ("r1", "eth3", "host5", "eth1"), ("r2", "eth3", "host6", "eth1")):
            if t not in lab.links:
                lab.link(*t)
        host(lab, nodes, "host1", "10.10.10.10/24", "10.10.10.1", HOSTMAC[1])
        host(lab, nodes, "host2", "10.10.10.20/24", "10.10.10.1", HOSTMAC[2])
        host(lab, nodes, "host3", "10.30.30.30/24", "10.30.30.1", HOSTMAC[3])
        host(lab, nodes, "host4", "10.30.30.40/24", "10.30.30.1", HOSTMAC[4])
        host(lab, nodes, "host5", "192.168.5.5/24", "192.168.5.1", HOSTMAC[5], role="exthost")
        host(lab, nodes, "host6", "192.168.6.6/24", "192.168.6.1", HOSTMAC[6], role="exthost")
    for v in ("vrf-lite", "shared"):
        lab.check(v, "host1", "ping -c 3 -W 1 192.168.5.5", PING_OK)
        lab.check(v, "host4", "ping -c 3 -W 1 192.168.6.6", PING_OK)
    lab.check("vrf-lite", "r1", "vtysh -c 'show ip bgp summary'", r"172\.16\.33\.3\)?\s+4\s+65000[\s\S]*172\.17\.33\.3\)?\s+4\s+65000")
    lab.check("shared", "leaf1", "ip route show vrf A default", r"default")
    lab.readme = r"""
## What you will learn

* 802.1Q sub-interfaces on Linux (`ip link add link eth1 name eth1.100 type vlan id 100`) placed in VRFs.
* **VRF-lite hand-off**: per-tenant eBGP sessions. Simple and isolated, but N tenants = N sessions/sub-interfaces per link.
* **Shared external connection**: one `INTERNET` VRF, routes **leaked** with FRR's `import vrf`:
  * INTERNET imports A and B (so the outside world can reach the tenants),
  * A and B import only the default route from INTERNET (route-map `ONLY-DEFAULT`).

## Step by step (vrf-lite)

```bash
# leaf3
ip -d link show eth1.100 ; ip -br addr show vrf A
vtysh -c 'show bgp vrf all summary'
# r1
vtysh -c 'show ip bgp'          # 10.10.10.0/24 from session .100 and 10.30.30.0/24 from session .200
```

Notice: r1 keeps both tenants in its **global** table. Can host1 (A) reach host3 (B)? Try
`ping 10.30.30.30` from host1 and `traceroute -n` it. Isolation is only as good as the external
router - in real life r1 would be a PE with its own VRFs.

## Step by step (shared)

```powershell
python tools\gns3_lab.py push labs\09-external-routing-multitenant --variant shared
```

```bash
# leaf3
vtysh -c 'show bgp vrf INTERNET ipv4 unicast'     # 0.0.0.0/0 from r1 + leaked tenant routes
vtysh -c 'show bgp vrf A ipv4 unicast 0.0.0.0/0'  # "Imported from ...:INTERNET"
ip route show vrf A default ; ip route show vrf INTERNET
# leaf1
vtysh -c 'show bgp l2vpn evpn route type prefix'  # default route advertised by leaf3/leaf4 in VRF A and B
```

**Breaking isolation:** from host1 (A) ping host3 (B) in the `shared` variant. VRF A only knows a default route...
which points into INTERNET... which knows 10.30.30.0/24 (leaked from B). The border leaf hair-pins
A -> INTERNET -> B. That's the trap the video warns about. Ways out:

* don't leak tenant prefixes into INTERNET at all (NAT/firewall instead),
* or add an nftables rule on the border leaves: `nft add rule inet filter forward iifname "A" oifname "B" drop`
  (and vice-versa) - Linux forwards between VRFs, so the kernel firewall can stop it,
* or use a firewall per tenant (labs 14-16).

## How this maps to the video

The video uses Arista's RT import/export between VRFs (INTERNET imports RT 100:100 and 200:200,
tenants import 10000:10000). On Linux, a route imported this way would be installed in the tenant VRF
pointing at the *INTERNET* L3VNI, but the remote leaf has no INTERNET VRF - so this lab uses FRR's
local `import vrf` leaking on the border leaves instead and re-advertises the leaked default route
inside each tenant's own L3VNI.
"""
    return lab


# ==========================================================================
# 10 Tenant multicast (OISM-style)
# ==========================================================================
def lab10():
    lab = Lab(10, "tenant-multicast", "Tenant Multicast in EVPN. OISM with Source Specific Multicast (SSM)",
              "vi3Q1ibzB7w", "1 h 12 min", """
Multicast *inside* a tenant VRF, between subnets, with SSM (IGMPv3). FRR does not implement OISM's
EVPN route types 6/7/8 (SMET / IGMP join/leave sync), but you can build OISM's **data-plane model**
on Linux: every leaf has every tenant VLAN, the ingress leaf floods the source's traffic in the
*source* VNI, and each egress leaf **routes it locally** (PIM SSM in the VRF) to its own receivers -
routed copies never go back into the fabric.
""", ref="multicast_routing")
    lab.diagram = """
                               spine1 (RR)
                  /eth1           |eth2           \\eth3
              leaf1             leaf2              leaf3
               eth1              eth1           eth1   eth2
              host1             host2          host3   host4
            SOURCE            receiver        receiver receiver
          VLAN10 .10.10      VLAN20 .20.20   VLAN10 .10.30 VLAN20 .20.40
     VLAN 10 and 20 + VRF A (L3VNI 1000) on every leaf, pimd (SSM 232/8) + IGMPv3 on the SVIs
     group (10.10.10.10, 232.1.1.1)
    """
    nodes = lab.variant("default", "OISM-like egress routing with pimd SSM in VRF A")
    spines, leaves = std_fabric(lab, nodes, 1, [1, 2, 3])
    std_overlay(spines, leaves)
    ports = {1: ([("eth1", 10)]), 2: ([("eth1", 20)]), 3: ([("eth1", 10), ("eth2", 20)])}
    for i, l in leaves.items():
        svc = [(10, 10010, [p for p, v in ports[i] if v == 10]), (20, 10020, [p for p, v in ports[i] if v == 20])]
        l2_services(l, i, svc)
        vrf_dev(l, "A", 1001)
        svi(l, 10, "10.10.10.1/24", vrf="A")
        svi(l, 20, "10.20.20.1/24", vrf="A")
        l3vni(l, "A", 1000, 4001, leaf_lo(i))
        l.comment("OISM rule: multicast routed by this leaf is delivered locally only, never back into VXLAN")
        l.sh("nft add table bridge oism",
             "nft add chain bridge oism out '{ type filter hook output priority 0; }'",
             "nft add rule bridge oism out oifname 'vxlan100*' ip daddr 224.0.0.0/4 counter drop")
        for v in (10, 20):
            l.frr.iface(f"vlan{v}", "ip pim", "ip pim passive", "ip igmp", "ip igmp version 3")
        leaf_overlay(l, i, spines)
        vrf_evpn(l, 65000, leaf_lo(i), "A")
    host(lab, nodes, "host1", "10.10.10.10/24", "10.10.10.1", HOSTMAC[1])
    host(lab, nodes, "host2", "10.20.20.20/24", "10.20.20.1", HOSTMAC[2])
    host(lab, nodes, "host3", "10.10.10.30/24", "10.10.10.1", HOSTMAC[3])
    host(lab, nodes, "host4", "10.20.20.40/24", "10.20.20.1", HOSTMAC[4])
    lab.link("leaf1", "eth1", "host1", "eth1")
    lab.link("leaf2", "eth1", "host2", "eth1")
    lab.link("leaf3", "eth1", "host3", "eth1")
    lab.link("leaf3", "eth2", "host4", "eth1")
    c = lambda *a: lab.check("default", *a)
    c("host1", "ping -c 2 -W 1 10.20.20.40", PING_OK)
    c("host1", "kill -0 $(cat /tmp/ms.pid 2>/dev/null) 2>/dev/null || { setsid mcast-send 232.1.1.1 -n 0.5 >/dev/null 2>&1 & echo $! > /tmp/ms.pid; }; echo started", r"started")
    c("host2", "timeout 20 mcast-recv 232.1.1.1 10.10.10.10 -c 3", r"received 3", "routed on leaf2 (VLAN10 -> VLAN20)")
    c("host4", "timeout 20 mcast-recv 232.1.1.1 10.10.10.10 -c 3", r"received 3", "routed on leaf3")
    c("host3", "timeout 20 mcast-recv 232.1.1.1 10.10.10.10 -c 3", r"received 3", "bridged in VLAN10")
    c("leaf2", "vtysh -c 'show ip mroute vrf A'", r"10\.10\.10\.10\s+232\.1\.1\.1")
    lab.readme = r"""
## What you will learn

* SSM basics: receivers join **(S,G)** with IGMPv3; no RP, no shared tree.
* FRR `pimd` inside a VRF: `ip pim` + `ip igmp` + `ip igmp version 3` on the SVIs, kernel multicast
  routing tables per VRF (`ip mroute show table <vrf-table>` / `vtysh -c 'show ip mroute vrf A'`).
* The **OISM** idea (RFC 9625) in data-plane terms:
  1. every leaf is attached to every tenant BD (or a Supplementary BD), so the source subnet is "local" everywhere;
  2. the ingress VTEP sends traffic only in the **source** BD (bridged, here by head-end replication);
  3. egress VTEPs **route locally** from the source BD to their receivers' BDs;
  4. routed traffic is never sent back into the fabric - here that rule is one nftables line in the
     bridge `output` hook (`oifname vxlan100* ip daddr 224.0.0.0/4 drop`).
* What FRR **does not** do here: OISM signalling (SMET type-6 routes to send traffic only to VTEPs with
  receivers, IGMP sync types 7/8 for multihoming). In this lab the source BD is flooded to *all*
  VTEPs - fine for a lab, but that's the inefficiency SMET removes.

`ip pim passive` stops PIM hellos on the SVIs: all leaves share the same anycast IP on the SVI and must
not become PIM neighbors of each other over the stretched VLAN.

## Step by step

Helper tools are in the base image: `mcast-send GROUP` and `mcast-recv GROUP SOURCE` (IGMPv3 SSM join).

```bash
# host1 (source)
mcast-send 232.1.1.1 -n 0.5
# host2 / host4 (receivers in VLAN 20 on other leaves)
mcast-recv 232.1.1.1 10.10.10.10
# host3 (receiver in the source VLAN on leaf3) - pure bridging
mcast-recv 232.1.1.1 10.10.10.10
```

On the leaves:

```bash
vtysh -c 'show ip igmp vrf A groups'
vtysh -c 'show ip igmp vrf A sources'
vtysh -c 'show ip mroute vrf A'             # iif vlan10 -> oif vlan20
vtysh -c 'show ip pim vrf A upstream'
nft list table bridge oism                  # counter = routed copies we refused to flood
tcpdump -ni eth11 -e udp port 4789          # only VNI 10010 carries the stream across the fabric
```

## Experiments (match the video's chapters)

* **Sender only**: stop all receivers. Traffic still floods VNI 10010 to every leaf (no SMET pruning).
* **Receiver only**: start a receiver without a sender; check `show ip igmp vrf A sources` - state exists, no traffic.
* **Remove the OISM rule** on leaf2 (`nft delete table bridge oism`): leaf2's routed copy is flooded into
  VNI 10020 and host4 on leaf3 receives **duplicates** (`mcast-recv` shows each seq twice).
* **Mapping groups to VNIs** (video 1:06): with an underlay-multicast design each tenant BD maps to a
  provider group; here we use ingress replication, so think about how many copies leaf1 sends per packet.
"""
    return lab


LABS = [lab07, lab08, lab09, lab10]
