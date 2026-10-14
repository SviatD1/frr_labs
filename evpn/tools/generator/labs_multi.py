from gen import *
from labs_basics import HOSTMAC, BGP_UP, PING_OK
from labs_underlay import underlay_fabric, ebgp_fabric, leaf_lo6, spine_lo6, V6NOTE

# ==========================================================================
# 35 Multi-vendor
# ==========================================================================
EOS_SNIPPETS = {
    "unnumbered-isis-ibgp": """
! Arista EOS equivalent of leaf2 for variant unnumbered-isis-ibgp (swap leaf2 for a vEOS/cEOS node)
hostname leaf2
service routing protocols model multi-agent
ip routing
ip routing vrf A
vlan 10,20
vrf instance A
interface Ethernet1
   switchport access vlan 10
interface Ethernet2
   switchport access vlan 20
interface Ethernet11
   no switchport
   mtu 1500
   ip address unnumbered Loopback0
   isis enable 1
   isis network point-to-point
interface Ethernet12
   no switchport
   mtu 1500
   ip address unnumbered Loopback0
   isis enable 1
   isis network point-to-point
interface Loopback0
   ip address 2.2.2.2/32
   isis enable 1
interface Vlan10
   vrf A
   ip address virtual 10.10.10.1/24
interface Vlan20
   vrf A
   ip address virtual 10.20.20.1/24
ip virtual-router mac-address 00:00:5e:00:01:01
interface Vxlan1
   vxlan source-interface Loopback0
   vxlan vlan 10 vni 10010
   vxlan vlan 20 vni 10020
   vxlan vrf A vni 10100
router isis 1
   net 49.0001.0000.0000.0002.00
   is-type level-2
   address-family ipv4 unicast
router bgp 65000
   router-id 2.2.2.2
   neighbor 11.11.11.11 remote-as 65000
   neighbor 11.11.11.11 update-source Loopback0
   neighbor 11.11.11.11 send-community extended
   neighbor 12.12.12.12 remote-as 65000
   neighbor 12.12.12.12 update-source Loopback0
   neighbor 12.12.12.12 send-community extended
   vlan 10
      rd auto
      route-target both 65000:10010
      redistribute learned
   vlan 20
      rd auto
      route-target both 65000:10020
      redistribute learned
   address-family evpn
      neighbor 11.11.11.11 activate
      neighbor 12.12.12.12 activate
   address-family ipv4
      no neighbor 11.11.11.11 activate
      no neighbor 12.12.12.12 activate
   vrf A
      rd 2.2.2.2:10100
      route-target import evpn 65000:10100
      route-target export evpn 65000:10100
      redistribute connected
""",
}


def lab35():
    lab = Lab(35, "multivendor-frr", "Multi-vendor EVPN design using Arista and FRR", "576MaUMsmig", "46 min", """
A vendor-agnostic EVPN design means picking options every box supports the same way. The video runs
Arista leaves with **FRR spines**; here everything is FRR (so it runs on plain Linux VMs), but the
leaf configs stick to the "common denominator" choices, and `arista/` holds an EOS config you can drop
onto a vEOS leaf2 to make it truly multi-vendor. Four underlay/overlay combinations from the video,
plus the **IS-IS MTU / hello-padding** trap.
""", ref="multivendor_spines_frr")
    lab.diagram = """
             spine1 (FRR, RR)            spine2 (FRR, RR)
              |      \\                 /      |
            leaf1      \\______________/     leaf2   (FRR here; Arista in the video - see arista/)
          e1    e2                         e1    e2
        host1  host2                     host3  host4
        V10    V20                        V10    V20     VRF A, L3VNI 10100, anycast GWs
    """
    variants = (
        ("unnumbered-isis-ibgp", "IPv4 unnumbered links, IS-IS, iBGP EVPN with RR on spines"),
        ("ipv6-lla-isis-ibgp", "IPv6 link-local links, IS-IS IPv6, iBGP over IPv6 loopbacks, IPv6 VTEPs (FRR >= 10.6)"),
        ("rfc5549-ibgp", "no IGP: iBGP unnumbered (interface) sessions, spines RR + next-hop-self for IPv4"),
        ("rfc5549-ebgp", "no IGP: eBGP unnumbered, spines AS 65100, leaves AS 65001/65002"),
        ("mtu-mismatch", "unnumbered-isis-ibgp with leaf2 eth11 MTU 9000 and spine1 eth2 MTU 1500"),
    )
    for vname, desc in variants:
        nodes = lab.variant(vname, desc, default=(vname == "unnumbered-isis-ibgp"))
        v6 = vname == "ipv6-lla-isis-ibgp"
        if vname in ("unnumbered-isis-ibgp", "mtu-mismatch", "ipv6-lla-isis-ibgp"):
            spines, leaves = underlay_fabric(lab, nodes, 2, [1, 2], "ipv6-lla" if v6 else "ipv4-unnumbered")
            if v6:
                for n in list(spines.values()) + list(leaves.values()):
                    k = int(n.name[-1])
                    n.sh(f"ip addr add {(spine_lo if n.role == 'spine' else leaf_lo)(k)}/32 dev lo")
            for m, s in spines.items():
                evpn_rr_ibgp(s, 65000, spine_lo(m), [leaf_lo6(i) if v6 else leaf_lo(i) for i in leaves])
            for i, l in leaves.items():
                evpn_leaf_ibgp(l, 65000, leaf_lo(i), [spine_lo6(m) if v6 else spine_lo(m) for m in spines])
            if vname == "mtu-mismatch":
                leaves[2].sh("ip link set eth11 mtu 9000")
        elif vname == "rfc5549-ebgp":
            spines, leaves = ebgp_fabric(lab, nodes, 2, [1, 2], lambda m: 65100, lambda i: 65000 + i, unnumbered=True)
        else:  # rfc5549-ibgp
            spines, leaves = ebgp_fabric(lab, nodes, 2, [1, 2], lambda m: 65000, lambda i: 65000, unnumbered=True)
            for m, s in spines.items():
                b = s.frr.bgps[0]
                b.glob = [g.replace("remote-as external", "remote-as internal") for g in b.glob]
                b.g(f"bgp cluster-id {spine_lo(m)}")
                b.af("ipv4 unicast", "neighbor LEAVES route-reflector-client", "neighbor LEAVES next-hop-self force")
                b.af("l2vpn evpn", "neighbor LEAVES route-reflector-client")
            for i, l in leaves.items():
                b = l.frr.bgps[0]
                b.glob = [g.replace("remote-as external", "remote-as internal") for g in b.glob]
                b.af("ipv4 unicast", "maximum-paths ibgp 4")
        for i, l in leaves.items():
            local = leaf_lo6(i) if v6 else leaf_lo(i)
            l2_services(l, i, [(10, 10010, ["eth1"]), (20, 10020, ["eth2"])], local=local)
            vrf_dev(l, "A", 1001)
            svi(l, 10, "10.10.10.1/24", vrf="A")
            svi(l, 20, "10.20.20.1/24", vrf="A")
            l3vni(l, "A", 10100, 4001, local)
            vrf_evpn(l, l.frr.bgps[0].asn, leaf_lo(i), "A")
        for k, (li, v) in enumerate(((1, 10), (1, 20), (2, 10), (2, 20))):
            hk = k + 1
            host(lab, nodes, f"host{hk}", f"10.{v}.{v}.{10 * hk}/24", f"10.{v}.{v}.1", HOSTMAC[hk])
            t = (f"leaf{li}", f"eth{1 if v == 10 else 2}", f"host{hk}", "eth1")
            if t not in lab.links:
                lab.link(*t)
    for v, _ in variants:
        if v == "mtu-mismatch":
            continue
        lab.check(v, "host1", "ping -c 3 -W 1 10.20.20.40", PING_OK)
        lab.check(v, "host1", "ping -c 3 -W 1 10.10.10.30", PING_OK)
    lab.check("mtu-mismatch", "spine1", "vtysh -c 'show isis neighbor'", r"\seth1\s+2\s+Up", "adjacency to leaf1 is fine")
    lab.check("mtu-mismatch", "spine1", "vtysh -c 'show isis neighbor' | grep -c 'eth2 .*Up'", r"^0", "no adjacency to leaf2")
    lab.extra_files["arista/leaf2-unnumbered-isis-ibgp.eos"] = EOS_SNIPPETS["unnumbered-isis-ibgp"]
    lab.readme = r"""
## What you will learn

* The vendor-neutral checklist from the video: **same RTs** (set explicitly or rely on the common AS:VNI auto
  scheme), **same RD style** doesn't matter, **same MTU**, same anycast-gateway MAC, VLAN-based service (FRR has
  no VLAN-aware bundle, lab 04), standard route types only.
* Four ways to build the underlay/overlay - all interoperable with Arista:

| variant | links | underlay | overlay |
|---|---|---|---|
| unnumbered-isis-ibgp | IPv4 unnumbered | IS-IS | iBGP EVPN to spine RRs |
| ipv6-lla-isis-ibgp | IPv6 LLA | IS-IS (IPv6) | iBGP over IPv6 loopbacks, IPv6 VTEPs |
| rfc5549-ibgp | IPv6 LLA | iBGP unnumbered (RR + next-hop-self force) | same sessions |
| rfc5549-ebgp | IPv6 LLA | eBGP unnumbered | same sessions |

* **IS-IS hello padding**: IS-IS pads hellos up to the interface MTU, so an MTU mismatch (Arista defaults to
  9214, Linux to 1500) prevents the adjacency - a classic multi-vendor gotcha. Variant `mtu-mismatch`
  reproduces it: spine1 never forms an adjacency with leaf2. Fix: same MTU on both ends
  (`ip link set eth11 mtu 1500` on leaf2), or `no isis hello padding` (FRR) / `isis hello padding disabled`... on
  one side (hides the problem rather than fixing it).
* **IPv6 forwarding in Linux** (video 25:55): FRR routes nothing unless `net.ipv6.conf.all.forwarding=1` -
  the base image sets it for every router.

""" + V6NOTE + r"""

## Step by step

```bash
vtysh -c 'show isis neighbor'  ; vtysh -c 'show bgp summary'
vtysh -c 'show bgp l2vpn evpn route type macip detail' | grep -i 'extended community'
# mtu-mismatch:
vtysh -c 'show isis neighbor'                  # leaf2 missing on spine1
tcpdump -ni eth2 -c 3 isis                     # leaf2's hellos are ~9000 bytes -> dropped by spine1's 1500-byte NIC
ip -d link show eth11                          # mtu on leaf2
```

## Going truly multi-vendor

In GNS3, add an Arista vEOS (or cEOS via Docker) appliance, replace leaf2 with it on the same links (Ethernet11/12
to the spines, Ethernet1/2 to host3/host4) and paste `arista/leaf2-unnumbered-isis-ibgp.eos`. The FRR side is the
`unnumbered-isis-ibgp` variant unchanged. Things that differ and must be aligned by hand: the virtual-router MAC,
RTs (EOS `route-target both auto` uses the same AS:VNI scheme as FRR, but setting them explicitly is safer),
IS-IS area/NET format, MTU.

The video's last point: FRR on a VM uses a fraction of the RAM/CPU of a vendor NOS image - which is why this whole
course runs on FRR.
"""
    return lab


# ==========================================================================
# 36/37 multi-fabric
# ==========================================================================
def mf_lo(n):
    return f"{n}.{n}.{n}.{n}"


def multi_fabric(lab, nodes, spines_per_fabric, variant):
    """Two fabrics (AS 65001 / 65002). Leaves 101,102 / 201,202. Spines 111(,112) / 211(,212)."""
    fab = {1: {"asn": 65001, "spines": [111, 112][:spines_per_fabric], "leaves": [101, 102]},
           2: {"asn": 65002, "spines": [211, 212][:spines_per_fabric], "leaves": [201, 202]}}
    N = {}
    for f, d in fab.items():
        for s in d["spines"]:
            n = Node(f"spine{s}", "router", "spine")
            loopback(n, mf_lo(s))
            n.notes.append(f"fabric {f}, AS {d['asn']}")
            nodes[n.name] = n
            N[s] = n
        for l in d["leaves"]:
            n = Node(f"leaf{l}", "router", "leaf")
            loopback(n, mf_lo(l))
            n.notes.append(f"fabric {f}, AS {d['asn']}")
            nodes[n.name] = n
            N[l] = n
    # intra-fabric links + IS-IS (one IS-IS domain per fabric = fault isolation)
    for f, d in fab.items():
        ifs = {x: [] for x in d["spines"] + d["leaves"]}
        for k, s in enumerate(d["spines"]):
            for j, l in enumerate(d["leaves"]):
                sif, lif = f"eth{j + 1}", f"eth{11 + k}"
                if (f"spine{s}", sif, f"leaf{l}", lif) not in lab.links:
                    lab.link(f"spine{s}", sif, f"leaf{l}", lif)
                addr(N[s], sif, f"10.{l}.{s}.2/24")
                addr(N[l], lif, f"10.{l}.{s}.1/24")
                ifs[s].append(sif)
                ifs[l].append(lif)
        for x in ifs:
            isis(N[x], ifs[x], x, area=f"49.000{f}")
    # DCI links (full mesh between the fabrics' spines)
    dci = []
    for a, sa in enumerate(fab[1]["spines"]):
        for b, sb in enumerate(fab[2]["spines"]):
            ia, ib = f"eth{10 + b}", f"eth{10 + a}"
            if (f"spine{sa}", ia, f"spine{sb}", ib) not in lab.links:
                lab.link(f"spine{sa}", ia, f"spine{sb}", ib)
            N[sa].comment(f"DCI link to spine{sb}")
            addr(N[sa], ia, f"10.{sa}.{sb}.1/24")
            N[sb].comment(f"DCI link to spine{sa}")
            addr(N[sb], ib, f"10.{sa}.{sb}.2/24")
            dci.append((sa, ia, f"10.{sa}.{sb}.2", sb, ib, f"10.{sa}.{sb}.1"))
    # BGP
    for f, d in fab.items():
        asn = d["asn"]
        other = fab[3 - f]
        for s in d["spines"]:
            n = N[s]
            b = evpn_rr_ibgp(n, asn, mf_lo(s), [mf_lo(l) for l in d["leaves"]])
            b.g("neighbor DCI peer-group", f"neighbor DCI remote-as {other['asn']}")
            for (sa, ia, peer_a, sb, ib, peer_b) in dci:
                if sa == s:
                    b.g(f"neighbor {peer_a} peer-group DCI")
                if sb == s:
                    b.g(f"neighbor {peer_b} peer-group DCI")
            v4 = ["neighbor DCI activate", "maximum-paths 4"]
            pl = [f"ip prefix-list LOCAL-LOOPBACKS seq {5 * (k + 1)} permit {mf_lo(x)}/32"
                  for k, x in enumerate(d["leaves"] + d["spines"])]
            if variant == "naive":
                v4.append("redistribute isis")
                n.frr.block("router isis 1\n redistribute ipv4 bgp level-2\nexit")
            else:
                n.frr.line(*pl)
                n.frr.block("route-map LOCAL-LOOPBACKS permit 10\n match ip address prefix-list LOCAL-LOOPBACKS\nexit")
                v4 += ["redistribute isis route-map LOCAL-LOOPBACKS", "neighbor DCI route-map LOCAL-LOOPBACKS out"]
                n.frr.block("route-map BGP-TO-ISIS permit 10\n set tag 999\nexit")
                n.frr.block("router isis 1\n redistribute ipv4 bgp level-2 route-map BGP-TO-ISIS\nexit")
                if variant == "oscillation":
                    v4.append("distance bgp 200 200 200")
                if variant == "fixed":
                    v4.append("distance bgp 20 200 200")
            b.af("ipv4 unicast", *v4)
            b.af("l2vpn evpn", "neighbor DCI activate", "neighbor DCI attribute-unchanged next-hop")
    return fab, N


def mf_leaves_and_hosts(lab, nodes, fab, N):
    rts = {10010: "10:10", 10120: "120:120", 10220: "220:220"}
    for f, d in fab.items():
        for j, l in enumerate(d["leaves"]):
            n = N[l]
            local_vlan = 120 if l == 102 else (220 if l == 202 else None)
            svc = [(10, 10010, ["eth1"])]
            if local_vlan:
                svc.append((local_vlan, 10000 + local_vlan, ["eth2"]))
            l2_services(n, l, svc, mac=f"44:38:39:ff:{f:02x}:{j + 1:02x}")
            vrf_dev(n, "A", 1001)
            svi(n, 10, "10.10.10.1/24", vrf="A")
            if local_vlan:
                svi(n, local_vlan, f"10.{local_vlan}.{local_vlan}.1/24", vrf="A")
            l3vni(n, "A", 10100, 4001, mf_lo(l))
            vl = {vni: [f"route-target import {rt}", f"route-target export {rt}"] for vni, rt in rts.items()
                  if vni == 10010 or vni == 10000 + (local_vlan or 0)}
            evpn_leaf_ibgp(n, d["asn"], mf_lo(l), [mf_lo(s) for s in d["spines"]], vni_lines=vl)
            vrf_evpn(n, d["asn"], mf_lo(l), "A", extra_evpn=["route-target import 100:100", "route-target export 100:100"])
    hosts = [("host11", 101, "eth1", "10.10.10.10/24", "10.10.10.1"), ("host12", 102, "eth1", "10.10.10.20/24", "10.10.10.1"),
             ("host13", 102, "eth2", "10.120.120.30/24", "10.120.120.1"), ("host24", 201, "eth1", "10.10.10.40/24", "10.10.10.1"),
             ("host25", 202, "eth1", "10.10.10.50/24", "10.10.10.1"), ("host26", 202, "eth2", "10.220.220.60/24", "10.220.220.1")]
    for k, (hn, l, lif, ip, gw) in enumerate(hosts):
        host(lab, nodes, hn, ip, gw, HOSTMAC[k + 1])
        if (f"leaf{l}", lif, hn, "eth1") not in lab.links:
            lab.link(f"leaf{l}", lif, hn, "eth1")


def lab36():
    lab = Lab(36, "multi-fabric-basics", "Interconnecting multiple EVPN fabrics. Multi Domain, Inter Domain, Multi Pod, Multi Site.",
              "JMBQiF4DbNA", "29 min", """
Two independent EVPN fabrics (own AS, own IS-IS, own route reflector) joined spine-to-spine. Only the
**bare minimum** crosses the boundary: leaf loopbacks (IPv4 unicast) and EVPN routes with their
**original next hops**, so VXLAN tunnels run end-to-end leaf-to-leaf. VLAN 10 is stretched across both
fabrics, each fabric also has a local subnet routed through VRF A.
""", ref="design_multi_fabric_basics")
    lab.diagram = """
         fabric 1 (AS 65001)                       fabric 2 (AS 65002)
            spine111  eth10 ----------------- eth10  spine211           10.111.211.0/24, eBGP ipv4 + evpn
            /      \\                                 /      \\
        leaf101   leaf102                       leaf201    leaf202
          |       |    \\                          |        |     \\
       host11  host12  host13                  host24   host25   host26
       V10      V10    V120 10.120.120.30       V10      V10     V220 10.220.220.60
       10.10.10.10 .20                          .40      .50
    """
    for vname, desc in (("connected", "loopbacks via network/redistribute + EVPN next-hop unchanged"),):
        nodes = lab.variant(vname, desc)
        fab, N = multi_fabric(lab, nodes, 1, "basic")
        mf_leaves_and_hosts(lab, nodes, fab, N)
    c = lambda *a: lab.check("connected", *a)
    c("spine111", "vtysh -c 'show ip bgp'", r"201\.201\.201\.201/32")
    c("leaf101", "ip route show 201.201.201.201", r"201\.201\.201\.201")
    c("host11", "ping -c 3 -W 1 10.10.10.40", PING_OK)
    c("host13", "ping -c 3 -W 1 10.220.220.60", PING_OK)
    c("leaf101", "bridge fdb show dev vxlan10010", r"dst 201\.201\.201\.201")
    lab.readme = r"""
## What you will learn

* Fabric boundaries: separate IS-IS domains (`49.0001` / `49.0002`), separate ASNs, separate RRs - a failure or
  flap in one fabric stays there.
* The minimum to interconnect:
  1. **underlay**: each side's VTEP loopbacks reach the other side (eBGP IPv4 between spines, redistributed into the
     local IS-IS);
  2. **overlay**: EVPN routes exchanged over eBGP **without changing the next hop**
     (`neighbor DCI attribute-unchanged next-hop` under `address-family l2vpn evpn`), so leaf101 tunnels directly to leaf201;
  3. **matching RTs** - auto-RT is `AS:VNI`, which differs between AS 65001 and 65002, so the RTs are set by hand
     (`route-target import/export 10:10` for VNI 10010, `100:100` for VRF A).
* "Fixing the next hop" (video 19:50 / 21:16): see what happens without step 2, and without step 1.

## Step by step

```bash
# spine111
vtysh -c 'show bgp summary'                        # ipv4 unicast + l2vpn evpn with 10.111.211.2
vtysh -c 'show ip bgp'                             # 201.201.201.201/32, 202.202.202.202/32 from AS 65002
vtysh -c 'show isis database detail' | grep -A3 201  # redistributed into IS-IS for the leaves
# leaf101
vtysh -c 'show bgp l2vpn evpn route rd 201.201.201.201:2'   # next hop 201.201.201.201 (unchanged)
bridge fdb show dev vxlan10010 | grep dst
tcpdump -ni eth11 -e udp port 4789                 # outer IP 101.101.101.101 -> 201.201.201.201
```

## Break it

* Remove `neighbor DCI attribute-unchanged next-hop` on both spines (`clear bgp *`): leaves now see next hop
  10.111.211.x / spine loopback, try to build tunnels to the spine (which is not a VTEP) -> traffic dies.
* Remove `redistribute ipv4 bgp level-2` from spine111's IS-IS: EVPN routes arrive but leaf101 can't resolve
  201.201.201.201 -> routes stay invalid (`show bgp l2vpn evpn route` without `*`).
* Use the auto RTs (delete the `route-target` lines on fabric-2 leaves): control plane up, nothing imported.

## Design discussion (video)

Multi-pod vs multi-site vs multi-domain: this lab is the simplest "flat end-to-end VXLAN" interconnect. Real
multi-site designs often terminate and re-originate VXLAN at border gateways (EVPN *Interconnect*, RFC 9014) to
hide one fabric's VTEPs from the other - FRR doesn't implement re-origination, so it's left as theory here.
"""
    return lab


def lab37():
    lab = Lab(37, "multi-fabric-dci-ha", "DCI network for EVPN Multi-Fabric. MTU, BUM traffic, HA and Fault Isolation",
              "ulLjeL_tUts", "30 min", """
Make the interconnect redundant: two spines per fabric, full-mesh DCI links, and loopbacks exchanged
by redistribution on all four spines. Done naively it **oscillates** (each fabric re-learns its own
loopbacks from the other side, and eBGP's distance 20 beats IS-IS's 115). Fix it with filters, tags and
administrative distance, then look at MTU and BUM across the DCI.
""", ref="design_multi_fabric_ha")
    lab.diagram = """
          fabric 1 (AS 65001)                      fabric 2 (AS 65002)
      spine111 eth10 ============== eth10 spine211
               eth11 ==\\        /== eth10
                         \\    /                    full mesh DCI, 4 x eBGP (ipv4 + evpn)
               eth10 ==/        \\== eth11
      spine112 eth11 ============== eth11 spine212
        |    \\   /   |                |    \\   /   |
      leaf101  leaf102                leaf201   leaf202     same hosts/VLANs as lab 36
    """
    for vname, desc in (("naive", "unfiltered mutual redistribution IS-IS <-> BGP on all spines"),
                        ("oscillation", "filtered + tagged, but eBGP distance 200 (Arista's default) -> oscillation"),
                        ("fixed", "filtered + tagged, eBGP distance 20 (FRR default, set explicitly)")):
        nodes = lab.variant(vname, desc, default=(vname == "fixed"))
        fab, N = multi_fabric(lab, nodes, 2, vname)
        mf_leaves_and_hosts(lab, nodes, fab, N)
    lab.check("fixed", "host11", "ping -c 3 -W 1 10.10.10.50", PING_OK)
    lab.check("fixed", "host13", "ping -c 3 -W 1 10.220.220.60", PING_OK)
    lab.check("fixed", "spine111", "ip route show 201.201.201.201", r"nexthop via 10\.111\.211\.2[\s\S]*nexthop via 10\.111\.212\.2")
    lab.check("fixed", "spine112", "vtysh -c 'show ip route 101.101.101.101'", r"Known via \"isis\"")
    lab.check("oscillation", "spine111", "vtysh -c 'show bgp summary'", r"10\.111\.211\.2\)?\s+4\s+65002")
    lab.check("naive", "spine111", "vtysh -c 'show ip bgp'", r"10\.101\.111\.0/24")
    lab.readme = r"""
## What you will learn

* Redundant DCI = several redistribution points, so you must control *what* is redistributed and *which
  source wins*:
  * BGP -> IS-IS: tag the routes (`set tag 999`) so you can recognise them;
  * IS-IS -> BGP: only the fabric's own loopbacks (prefix-list `LOCAL-LOOPBACKS`), also as an outbound filter on
    the DCI sessions - otherwise a fabric can re-advertise the *other* fabric's loopbacks back to it (`naive`);
  * **administrative distance** - the root cause of the oscillation in the video. Arista's default distance for
    eBGP is **200**, worse than IS-IS (115). spine111 learns 201.201.201.201 via eBGP *and* via IS-IS (spine112
    redistributed its own eBGP copy). With eBGP at 200, spine111 picks IS-IS and stops redistributing; spine112 does
    the same with spine111's copy; both copies vanish, both fall back to eBGP, redistribute again... forever.
    Variant `oscillation` sets `distance bgp 200 200 200` to reproduce it on FRR. FRR's default is already
    `20 200 200` (eBGP 20 beats IS-IS), which is the fix (`fixed` sets it explicitly).
* **Disabling IPv4 unicast inside the DC**: leaves only run `l2vpn evpn` (`no bgp default ipv4-unicast`) - the
  underlay is IS-IS, so the DC never sees external IPv4 churn.
* **Fault isolation**: separate IS-IS domains; the DCI only carries a handful of /32s and EVPN.
* **MTU and BUM over DCI**: VXLAN +50 bytes end-to-end, ingress replication means one copy *per remote VTEP*
  crosses the DCI for every broadcast.

## Step by step

Start with `oscillation`:

```bash
# spine111
watch -n1 "vtysh -c 'show ip route 201.201.201.201' | head -4"    # flips between "bgp" and "isis"
vtysh -c 'show isis database detail' | grep -B2 -A6 201.201       # the redistributed copies come and go
# host11
ping -D -O 10.10.10.50                       # drops / jitter whenever the underlay flips
```

Then `fixed`: the route is stable, via eBGP with 2-way ECMP on each spine. Finally look at `naive`:
`vtysh -c 'show ip bgp'` on spine111 is full of fabric-1 *link* subnets and anything IS-IS knows - and with
unlucky timing a fabric can learn its own loopbacks back through the other fabric. Compare
`show ip route 101.101.101.101` on spine112 and spine211 across the variants.
Shut a DCI link (`ip link set eth10 down` on spine111) - ECMP shrinks, nothing else moves.

## MTU

```bash
# host11 (MTU 1450): fits
ping -M do -s 1422 10.10.10.50
# make the DCI path smaller than the VXLAN packet: on all four spines' DCI interfaces
ip link set eth10 mtu 1400 ; ip link set eth11 mtu 1400
ping -M do -s 1422 10.10.10.50              # silently dropped: the leaf sends 1450+50 byte VXLAN packets
                                            # with DF set, nobody tells the host -> black hole
```

Rule from the video: the DCI must carry at least host MTU + 50 (+ 4 per extra 802.1Q tag) everywhere.

## BUM

```bash
# leaf101
bridge fdb show dev vxlan10010 | grep 00:00:00:00:00:00     # 3 remote VTEPs, 2 of them across the DCI
# capture on spine111 eth10/eth11 while host11 runs: arping -c 5 -I eth1 10.10.10.99
```
"""
    return lab


LABS = [lab35, lab36, lab37]
