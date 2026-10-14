from gen import *
from labs_basics import HOSTMAC, BGP_UP, PING_OK
from labs_mh import es_bond, mh_uplinks, bond_host

MAC_FLOOD = r'''
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
'''

VM_SH = r'''
#!/bin/bash
# Pretend a VM (MAC 00:aa:aa:aa:aa:aa, IP 10.10.10.10) lives on this host.
# usage: vm up | vm down | vm status
SELF_IP=__SELF_IP__; SELF_MAC=__SELF_MAC__     # this server's own identity
case "$1" in
  up)   ip addr flush dev eth1; ip link set eth1 address 00:aa:aa:aa:aa:aa
        ip addr add 10.10.10.10/24 dev eth1; ip route replace default via 10.10.10.1
        arping -U -c 3 -I eth1 10.10.10.10 >/dev/null; ping -c 1 -W 1 10.10.10.1 >/dev/null
        echo "VM is now on $(hostname)";;
  down) ip addr flush dev eth1; ip link set eth1 address $SELF_MAC
        ip addr add $SELF_IP dev eth1; ip route replace default via 10.10.10.1
        echo "VM left $(hostname)";;
  *)    ip -br addr show eth1; ip -br link show eth1;;
esac
'''


# ==========================================================================
# 29 Overlay design - ASIC limits
# ==========================================================================
def lab29():
    lab = Lab(29, "overlay-asic-limits", "Designing EVPN Overlay for Data Center. ASICs and their limits", "jzDw9H-bM_Q", "37 min", """
Hardware tables (MAC, host routes, LPM, next hops, tunnels) are finite, and an EVPN design decides what
every leaf has to hold. Generate hundreds of endpoints with `mac-flood`, then compare how many MAC
and host-route entries each leaf ends up with when **every VNI is everywhere** versus **VNIs only
where needed**.
""", ref="design_overlay_asic")
    lab.diagram = """
               spine1                spine2           (RR; hold BGP state, no forwarding state)
          leaf1      leaf2      leaf3      leaf4
            |          |          |          |
          host1      host2      host3      host4
         VLAN10     VLAN10     VLAN20     VLAN20
      VLAN 10: 10.10.0.0/16   VLAN 20: 10.20.0.0/16   VRF A, L3VNI 1000
    """
    for vname, desc in (("vni-everywhere", "VLAN 10 and 20 configured on all leaves"),
                        ("vni-where-needed", "leaf1/leaf2 only VLAN 10, leaf3/leaf4 only VLAN 20")):
        nodes = lab.variant(vname, desc, default=(vname == "vni-everywhere"))
        spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3, 4])
        std_overlay(spines, leaves)
        for i, l in leaves.items():
            myv = 10 if i <= 2 else 20
            vl = [10, 20] if vname == "vni-everywhere" else [myv]
            l2_services(l, i, [(v, 10000 + v, ["eth1"] if v == myv else []) for v in vl])
            vrf_dev(l, "A", 1001)
            for v in vl:
                svi(l, v, f"10.{v}.0.1/16", vrf="A")
            l3vni(l, "A", 1000, 4001, leaf_lo(i))
            leaf_overlay(l, i, spines)
            vrf_evpn(l, 65000, leaf_lo(i), "A")
        for i in (1, 2, 3, 4):
            v = 10 if i <= 2 else 20
            h = host(lab, nodes, f"host{i}", f"10.{v}.0.{10 * i}/16", f"10.{v}.0.1", HOSTMAC[i])
            h.files["/usr/local/bin/mac-flood"] = (MAC_FLOOD, "755")
            if (f"leaf{i}", "eth1", f"host{i}", "eth1") not in lab.links:
                lab.link(f"leaf{i}", "eth1", f"host{i}", "eth1")
    for v in ("vni-everywhere", "vni-where-needed"):
        lab.check(v, "host1", "ping -c 3 -W 1 10.20.0.40", PING_OK)
        lab.check(v, "host1", "ip -o link show type macvlan | wc -l | grep -q 50 || mac-flood 50 eth1 10.10 >/dev/null; ip -o link show type macvlan | wc -l", r"^50")
        lab.check(v, "leaf2", "vtysh -c 'show evpn vni 10010'", r"Number of MACs \(local and remote\) known for this VNI: (5[0-9]|[6-9][0-9])")
    lab.check("vni-everywhere", "leaf3", "bridge fdb show dev vxlan10010 | grep -c '^02:'", r"^(4[0-9]|5[0-9])")
    lab.check("vni-where-needed", "leaf3", "ip link show vxlan10010", r"does not exist")
    lab.check("vni-where-needed", "leaf3", "ip route show vrf A | grep -cE '^10\\.10\\.1[0-9]{2}\\.'", r"^(4[0-9]|5[0-9])")
    lab.readme = r"""
## What you will learn

* The tables an EVPN leaf fills and where to look at them on Linux:

| ASIC table | Linux equivalent | count it with |
|---|---|---|
| MAC (L2 FDB) | bridge FDB | `bridge fdb show br br0 \| wc -l` / `vtysh -c 'show evpn vni'` (#MACs) |
| host routes (/32, /128) | VRF routing table | `ip route show vrf A \| grep -vc /` (host routes are printed without /32) |
| ARP/ND (adjacencies) | neighbor table | `ip neigh show \| wc -l` / `vtysh -c 'show evpn arp-cache vni all'` |
| tunnel endpoints | VTEP list | `vtysh -c 'show evpn vni detail' \| grep -c 'Remote VTEP'` |
| BGP state (CPU, not ASIC) | spine RIB | `vtysh -c 'show bgp l2vpn evpn summary'` on spine1 |

* A leaf only needs MAC state for the VNIs it has. With symmetric IRB, it still gets **host routes for every
  endpoint in the VRF** (type-2 with the L3VNI RT) - which is why labs 31/32 talk about limiting host routes.

## Step by step

```bash
# host1: 200 fake endpoints in VLAN 10
mac-flood 200 eth1 10.10
# compare leaf2 (has VLAN 10) and leaf3 (VLAN 20 only in vni-where-needed)
vtysh -c 'show evpn vni'
bridge fdb show br br0 | wc -l
ip route show vrf A | wc -l
# spine1
vtysh -c 'show bgp l2vpn evpn summary'           # PfxRcd grows on the RR regardless
```

Push the other variant and repeat. Fill in a table: MACs / host routes per leaf for each design. Then
`mac-flood clean`.

## Discussion (video)

* Leaf ASICs (Trident/Tomahawk/Jericho class) differ by 10-100x in host table size. Spines in EVPN are
  usually *not* VTEPs, so they need only underlay routes - any ASIC works.
* Border/service leaves are where table pressure concentrates (all VRFs, external routes).
* Linux has no hard table limit, but each entry costs memory and, more importantly, control-plane churn - try
  `mac-flood 1000` and watch `top` on the leaves (zebra/bgpd CPU).
"""
    return lab


# ==========================================================================
# 30 VM mobility
# ==========================================================================
def lab30():
    lab = Lab(30, "vm-mobility", "EVPN Overlay Design for Virtual Machine Mobility in Data Center", "vgu2ZfYUYYM", "34 min", """
A "VM" (MAC 00:aa:aa:aa:aa:aa, IP 10.10.10.10) moves from a server on leaf1 to a server on leaf3 -
the classic vMotion use case for stretched L2. Watch the **MAC Mobility** extended community and its
sequence number, the host route following the VM, and FRR's **duplicate address detection** freezing
a MAC that moves too often.
""", ref="design_overlay_mobility")
    lab.diagram = """
               spine1                spine2
          leaf1      leaf2      leaf3      leaf4
            |          |          |          |
          host1      host2      host3      host4        VLAN 10, VRF A, anycast 10.10.10.1
       (VM here)               (moves here)
     the "VM" = 00:aa:aa:aa:aa:aa / 10.10.10.10, helper: `vm up` / `vm down` on host1 and host3
    """
    nodes = lab.variant("default", "VLAN 10 stretched over 4 leaves, symmetric IRB, ARP suppression")
    spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3, 4])
    std_overlay(spines, leaves)
    for i, l in leaves.items():
        l2_services(l, i, [(10, 10010, [] if i == 2 else ["eth1"]), (20, 10020, ["eth2"] if i == 2 else [])])
        vrf_dev(l, "A", 1001)
        svi(l, 10, "10.10.10.1/24", vrf="A")
        svi(l, 20, "10.20.20.1/24", vrf="A")
        l.sh("sysctl -w net.ipv4.conf.vlan10.arp_accept=1")
        l3vni(l, "A", 1000, 4001, leaf_lo(i))
        leaf_overlay(l, i, spines)
        vrf_evpn(l, 65000, leaf_lo(i), "A")
    selfs = {1: ("10.10.10.11/24", "00:a1:a1:a1:a1:a1"), 3: ("10.10.10.30/24", HOSTMAC[3]),
             4: ("10.10.10.40/24", HOSTMAC[4])}
    for i in (1, 3, 4):
        ip, mac = selfs[i]
        if i == 1:
            h = host(lab, nodes, "host1", "10.10.10.10/24", "10.10.10.1", "00:aa:aa:aa:aa:aa")
        else:
            h = host(lab, nodes, f"host{i}", ip, "10.10.10.1", mac)
        h.files["/usr/local/bin/vm"] = (VM_SH.replace("__SELF_IP__", ip).replace("__SELF_MAC__", mac), "755")
        lab.link(f"leaf{i}", "eth1", f"host{i}", "eth1")
    h2 = host(lab, nodes, "host2", "10.20.20.20/24", "10.20.20.1", HOSTMAC[2])
    lab.link("leaf2", "eth2", "host2", "eth1")
    c = lambda *a: lab.check("default", *a)
    c("host2", "ping -c 3 -W 1 10.10.10.10", PING_OK)
    c("leaf2", "vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa'", r"remote\s+1\.1\.1\.1|Remote VTEP: 1\.1\.1\.1")
    c("host1", "vm down", r"VM left")
    c("host3", "vm up", r"VM is now on")
    c("leaf2", "vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa'", r"3\.3\.3\.3")
    c("leaf2", "vtysh -c 'show bgp l2vpn evpn route type macip detail' | grep -A12 'aa:aa:aa:aa:aa:aa' | grep -i 'MM:'", r"MM:1|MM:[2-9]")
    c("host2", "ping -c 3 -W 1 10.10.10.10", PING_OK)
    lab.readme = r"""
## What you will learn

* **MAC mobility** (RFC 7432 s15): the new VTEP advertises the MAC with sequence number N+1
  (extended community `MM:<seq>`); everyone prefers the highest sequence, the old VTEP withdraws.
* With symmetric IRB the /32 host route moves too, so routed traffic follows the VM immediately.
* GARP after a move is what tells the new leaf about the VM (`arp_accept=1` on vlan10 lets the SVI create a neighbor
  entry from a gratuitous ARP; real hypervisors send RARP/GARP).
* **Duplicate address detection**: FRR default `dup-addr-detection max-moves 5 time 180` - more moves than
  that and the MAC/IP is flagged duplicate (and optionally frozen).

## Step by step

```bash
# leaf2 - before
vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa detail'
vtysh -c 'show evpn arp-cache vni 10010 ip 10.10.10.10 detail'
ip route show vrf A 10.10.10.10
# move the VM
host1$ vm down
host3$ vm up
# leaf2 - after
vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa detail'    # Remote VTEP 3.3.3.3, seq 1
vtysh -c 'show bgp l2vpn evpn route type macip detail' | grep -B3 -A12 aa:aa:aa   # MM:1
```

Keep `ping -D -O 10.10.10.10` running on host2 during the move and count lost packets.

**Duplicate detection**: move the VM back and forth 6 times quickly (`vm down`/`vm up` alternately on host1 and host3),
then on any leaf:

```bash
vtysh -c 'show evpn mac vni 10010 duplicate'
vtysh -c 'show evpn arp-cache vni 10010 duplicate'
vtysh -c 'clear evpn dup-addr vni 10010 mac 00:aa:aa:aa:aa:aa'
```

Tune it under `router bgp 65000` / `address-family l2vpn evpn`: `dup-addr-detection max-moves 3 time 60 freeze 30`.

Note: `gns3_lab.py check` for this lab performs the move itself (`vm down` on host1, `vm up` on host3).
Push the lab again (`gns3_lab.py push labs\30-vm-mobility`) to put the VM back on host1.

## Design notes (video)

* The mobility domain = the set of leaves that have the VNI. Every leaf in it holds every MAC of that VNI -
  bigger mobility domains cost table space (lab 29) and widen the BUM flooding domain.
* Limit broadcast domain size: stretch only the VLANs that really need mobility, keep the rest rack-local (lab 33).
"""
    return lab


# ==========================================================================
# 31 Overlay routing design
# ==========================================================================
STRIP_RM = """
bgp extcommunity-list standard L3VNI-RT seq 5 permit rt 65000:1000
!
route-map NO-HOST-ROUTES permit 10
 match evpn route-type macip
 set extcomm-list L3VNI-RT delete
exit
!
route-map NO-HOST-ROUTES permit 20
exit"""


def lab31():
    lab = Lab(31, "overlay-routing-design", "EVPN Overlay Design for Routing in Data Center", "jRbyPlaTZyQ", "34 min", """
Symmetric IRB by default installs a **/32 for every endpoint** in the VRF on every leaf. That's simple
and optimal, but it's the table that runs out first. Compare it with a design where leaves only use
**subnet (type-5) routes** across the fabric and resolve hosts locally via ARP/bridging.
""", ref="design_overlay_l3")
    lab.diagram = """
               spine1                 spine2
          leaf1        leaf2         leaf3        leaf4
         e1   e2      e1   e2         e1           e1
       host1 host2  host3 host4      host5        host6
       V10   V20    V10   V20        V30          V40
    VLAN 10/20 stretched on leaf1+leaf2, VLAN 30 only on leaf3, VLAN 40 only on leaf4
    VRF A, L3VNI 1000, every leaf advertises its subnets as type-5
    """
    for vname, desc in (("host-routes", "default symmetric IRB: /32 per endpoint on every leaf"),
                        ("subnets-only", "leaves strip the L3VNI RT from incoming type-2 -> no remote /32, only type-5 subnets")):
        nodes = lab.variant(vname, desc, default=(vname == "host-routes"))
        spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3, 4])
        std_overlay(spines, leaves)
        vmap = {1: [10, 20], 2: [10, 20], 3: [30], 4: [40]}
        for i, l in leaves.items():
            l2_services(l, i, [(v, 10000 + v, [f"eth{k + 1}"]) for k, v in enumerate(vmap[i])])
            vrf_dev(l, "A", 1001)
            for v in vmap[i]:
                svi(l, v, f"10.{v}.{v}.1/24", vrf="A")
            l3vni(l, "A", 1000, 4001, leaf_lo(i))
            extra = []
            if vname == "subnets-only":
                l.frr.block(STRIP_RM)
                extra = ["neighbor RR route-map NO-HOST-ROUTES in"]
            leaf_overlay(l, i, spines, extra_evpn=extra)
            vrf_evpn(l, 65000, leaf_lo(i), "A")
        hk = 0
        for i in (1, 2, 3, 4):
            for k, v in enumerate(vmap[i]):
                hk += 1
                host(lab, nodes, f"host{hk}", f"10.{v}.{v}.{10 * hk}/24", f"10.{v}.{v}.1", HOSTMAC[hk])
                if (f"leaf{i}", f"eth{k + 1}", f"host{hk}", "eth1") not in lab.links:
                    lab.link(f"leaf{i}", f"eth{k + 1}", f"host{hk}", "eth1")
    for v in ("host-routes", "subnets-only"):
        lab.check(v, "host1", "ping -c 3 -W 1 10.30.30.50", PING_OK)
        lab.check(v, "host1", "ping -c 3 -W 1 10.20.20.40", PING_OK)
        lab.check(v, "host5", "ping -c 3 -W 1 10.40.40.60", PING_OK)
    lab.check("host-routes", "leaf4", "ip route show vrf A", r"10\.10\.10\.10 .*vlan4001")
    lab.check("subnets-only", "leaf4", "ip route show vrf A", r"10\.10\.10\.0/24 .*vlan4001")
    lab.check("subnets-only", "leaf4", "ip route show vrf A 10.10.10.10", r"^$")
    lab.readme = r"""
## What you will learn

* Where host routes come from: a type-2 MAC/IP route carries **two** RTs (L2VNI `65000:100xx` and L3VNI
  `65000:1000`). The L3 RT imports it into VRF A as a /32.
* FRR policy trick for "subnets only": an inbound route-map that deletes the L3VNI RT from type-2 routes:
  ```text
  bgp extcommunity-list standard L3VNI-RT seq 5 permit rt 65000:1000
  route-map NO-HOST-ROUTES permit 10
   match evpn route-type macip
   set extcomm-list L3VNI-RT delete
  ```
  MACs and ARP suppression still work (L2 RT untouched), but no /32 lands in the VRF.
* How traffic then flows:
  * to a **stretched** subnet you also have locally (10.20.20.0/24 on leaf1): routed into the local SVI, ARP is
    answered by suppression, then *bridged* over the L2VNI - asymmetric IRB for that hop;
  * to a **non-local** subnet (10.30.30.0/24 from leaf1): type-5 /24 via the L3VNI to the subnet's owner,
    which resolves the host locally.

## Step by step

```bash
# leaf4 (has only VLAN 40)
ip route show vrf A                 # host-routes: many /32 entries;  subnets-only: just /24s
vtysh -c 'show bgp vrf A ipv4 unicast'
vtysh -c 'show bgp l2vpn evpn route type macip detail' | grep -i 'extended community' | head
# leaf1
vtysh -c 'show evpn arp-cache vni 10020'     # still populated in both variants (suppression keeps working)
```

## Trade-offs to discuss (video)

* Subnets-only breaks **mobility of a single host out of its home subnet's leaves** - an isolated subnet
  advertised by two leaves is load-balanced, the wrong leaf has to bridge/flood to find the host.
* A **stretched subnet that is not local** needs the /32, otherwise traffic goes to *one of* the leaves
  announcing the /24 and may need an extra hop. "Dedicated leaves advertise subnets" (border/gateway leaves
  that have every VLAN) is the middle ground from the video - try advertising 10.10.10.0/24 only from leaf2
  (remove `redistribute connected` on leaf1, or filter it with a route-map).
"""
    return lab


# ==========================================================================
# 32 Limiting host routes / RT constraint
# ==========================================================================
def lab32():
    lab = Lab(32, "limit-host-routes-rtc", "Limiting host route advertisement in EVPN. BGP Route Target Constraint",
              "lhVBoaH4Kxo", "43 min", """
Three ways to keep EVPN state where it is needed: stop host routes at the **source**, **filter** them on
the route reflector, and **Route Target Constraint** (RFC 4684) so the RR only sends a leaf the routes
whose RTs it imports. FRR doesn't implement RTC, so you'll build its effect with per-leaf outbound
filters on the RR and see exactly what RTC would have automated.
""", ref="design_overlay_rtconstraint")
    lab.diagram = """
               spine1 (RR)              spine2 (RR)
          leaf1        leaf2        leaf3          leaf4
          e1  e2      e1  e2         e1             e1
        host1 host2 host3 host4     host5          host6
         V10  V20   V10   V20       V30            V30
     VNIs 10010/10020 only on leaf1+leaf2, 10030 only on leaf3+leaf4, VRF A (L3VNI 1000) everywhere
    """
    for vname, desc in (("default", "everything everywhere"),
                        ("no-host-routes-at-source", "leaves strip the L3VNI RT from their own type-2 routes (outbound)"),
                        ("rr-filter-rtc", "spines send each leaf only the L2VNIs it has (manual RT-Constraint)")):
        nodes = lab.variant(vname, desc, default=(vname == "default"))
        spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3, 4])
        vmap = {1: [10, 20], 2: [10, 20], 3: [30], 4: [30]}
        for m, s in spines.items():
            if vname == "rr-filter-rtc":
                s.frr.line("bgp extcommunity-list standard VNI-10-20 seq 5 permit rt 65000:10010",
                           "bgp extcommunity-list standard VNI-10-20 seq 10 permit rt 65000:10020",
                           "bgp extcommunity-list standard VNI-30 seq 5 permit rt 65000:10030")
                s.frr.block("""
                    route-map TO-RACK-10-20 deny 10
                     match extcommunity VNI-30
                    exit
                    !
                    route-map TO-RACK-10-20 permit 20
                    exit
                    !
                    route-map TO-RACK-30 deny 10
                     match extcommunity VNI-10-20
                    exit
                    !
                    route-map TO-RACK-30 permit 20
                    exit""")
                b = s.frr.bgp(65000, spine_lo(m))
                b.g("no bgp default ipv4-unicast", f"bgp cluster-id {spine_lo(m)}")
                for pg, members in (("RACK-10-20", (1, 2)), ("RACK-30", (3, 4))):
                    b.g(f"neighbor {pg} peer-group", f"neighbor {pg} remote-as 65000", f"neighbor {pg} update-source lo")
                    for i in members:
                        b.g(f"neighbor {leaf_lo(i)} peer-group {pg}")
                    b.af("l2vpn evpn", f"neighbor {pg} activate", f"neighbor {pg} route-reflector-client",
                         f"neighbor {pg} route-map TO-{pg} out")
            else:
                evpn_rr_ibgp(s, 65000, spine_lo(m), [leaf_lo(i) for i in leaves])
        for i, l in leaves.items():
            l2_services(l, i, [(v, 10000 + v, [f"eth{k + 1}"]) for k, v in enumerate(vmap[i])])
            vrf_dev(l, "A", 1001)
            for v in vmap[i]:
                svi(l, v, f"10.{v}.{v}.1/24", vrf="A")
            l3vni(l, "A", 1000, 4001, leaf_lo(i))
            extra = []
            if vname == "no-host-routes-at-source":
                l.frr.block(STRIP_RM)
                extra = ["neighbor RR route-map NO-HOST-ROUTES out"]
            leaf_overlay(l, i, spines, extra_evpn=extra)
            vrf_evpn(l, 65000, leaf_lo(i), "A")
        hk = 0
        for i in (1, 2, 3, 4):
            for k, v in enumerate(vmap[i]):
                hk += 1
                host(lab, nodes, f"host{hk}", f"10.{v}.{v}.{10 * hk}/24", f"10.{v}.{v}.1", HOSTMAC[hk])
                if (f"leaf{i}", f"eth{k + 1}", f"host{hk}", "eth1") not in lab.links:
                    lab.link(f"leaf{i}", f"eth{k + 1}", f"host{hk}", "eth1")
    for v in ("default", "no-host-routes-at-source", "rr-filter-rtc"):
        lab.check(v, "host1", "ping -c 3 -W 1 10.30.30.50", PING_OK)
        lab.check(v, "host5", "ping -c 3 -W 1 10.30.30.60", PING_OK)
        lab.check(v, "host1", "ping -c 3 -W 1 10.20.20.40", PING_OK)
    lab.check("default", "leaf3", "vtysh -c 'show bgp l2vpn evpn route type macip'", r"00:aa:aa:aa:aa:aa")
    lab.check("rr-filter-rtc", "leaf3", "vtysh -c 'show bgp l2vpn evpn route type macip'", r"00:ee:ee:ee:ee:ee|00:ff:ff:ff:ff:ff")
    lab.check("rr-filter-rtc", "leaf3", "vtysh -c 'show bgp l2vpn evpn route type macip' | grep -c 00:aa:aa:aa:aa:aa", r"^0")
    lab.check("no-host-routes-at-source", "leaf3", "ip route show vrf A 10.10.10.10", r"^$")
    lab.readme = r"""
## What you will learn

* **Stop at the source** (outbound route-map on the originating leaf, deletes the L3VNI RT from type-2): nobody
  gets /32s for this leaf's hosts.
* **Filter on the RR**: per-peer-group outbound policies that match on RT (`match extcommunity`).
* **RT Constraint (RFC 4684)**: leaves send `rtfilter` NLRIs ("I import RTs X, Y"); the RR sends each leaf only
  matching routes - dynamic, no per-rack config. *FRR does not support the RTC address family* (there is no
  `address-family ipv4 rtfilter`), Arista/Juniper/Nokia do. Variant `rr-filter-rtc` is the static equivalent.
* Note: a leaf **without** RTC/filters still receives everything; it just doesn't import routes whose RTs it
  doesn't have. The cost is BGP memory/CPU on the leaf and churn - not forwarding state.

## Step by step

```bash
# leaf3 (has only VNI 10030)
vtysh -c 'show bgp l2vpn evpn summary'                  # PfxRcd: compare across variants
vtysh -c 'show bgp l2vpn evpn route type macip' | grep -c '\[2\]'
ip route show vrf A | grep -vc /                         # number of host routes
# spine1
vtysh -c 'show bgp l2vpn evpn neighbors 3.3.3.3 advertised-routes' | tail -3
vtysh -c 'show route-map'                                # rr-filter-rtc hit counters
```

Fill a table: received EVPN routes / VRF host routes on leaf3 for each variant.

Questions:

1. In `rr-filter-rtc`, leaf3 still reaches 10.10.10.10 - how? (type-5 10.10.10.0/24 from leaf1/leaf2 carries only
   the L3VNI RT and is not filtered.)
2. Why must the RR filter on RTs and not on VNI numbers? (`match evpn vni` exists in FRR - try it - but RTs are
   what import is based on.)
3. What breaks if leaf3 gets VLAN 10 later and you forget to update the spines' route-maps? That's the operational
   argument for real RTC.
"""
    return lab


# ==========================================================================
# 33 L3-only fabric with EVPN
# ==========================================================================
def lab33():
    lab = Lab(33, "l3-only-fabric", "Layer 3 Only Fabric with EVPN", "8tKi73LWPRM", "40 min", """
No stretched L2 at all: **one subnet per rack**, and EVPN used purely as a multi-tenant L3VPN
(type-5 routes in per-tenant L3VNIs). Overlapping tenant subnets just work. A second variant puts a
subnet on a *pair* of ToRs (dual-homed servers with EVPN multihoming) - the only place where L2 is
still needed.
""", ref="design_overlay_ip_vpn")
    lab.diagram = """
               spine1                  spine2
        leaf1        leaf2               leaf3
       e1   e2      e1   e2            e1     e2
        |    \\____ |    |              |      |
        |      ___\\|____|            host3   host4
       host1  /     host2            VRF A    VRF B   (same subnet 10.3.10.0/24 in both!)
   one-subnet-one-rack: host1 10.1.10.10 (leaf1, A), host2 10.2.10.20 (leaf2 eth2, A)
   two-tors: host1/host2 bonded to leaf1+leaf2, subnet 10.12.10.0/24 on both ToRs (ES + L2VNI 10012 local to the pair)
    """
    for vname, desc in (("one-subnet-one-rack", "rack-local subnets, type-5 only, no L2VNI"),
                        ("two-tors", "rack = 2 ToRs: EVPN-MH bond, L2VNI only inside the pair, type-5 to the rest")):
        nodes = lab.variant(vname, desc, default=(vname == "one-subnet-one-rack"))
        spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3])
        std_overlay(spines, leaves)
        for i, l in leaves.items():
            if vname == "two-tors" and i in (1, 2):
                l2_services(l, i, [(12, 10012, [])])
                es_bond(l, "bond1", ["eth1"], 1, vlans=(12,))
                es_bond(l, "bond2", ["eth2"], 2, vlans=(12,))
                mh_uplinks(l)
            else:
                bridge(l, leaf_mac(i))
            vrf_dev(l, "A", 1001)
            vrf_dev(l, "B", 1002)
            if vname == "two-tors" and i in (1, 2):
                svi(l, 12, "10.12.10.1/24", vrf="A")
            elif i == 1:
                addr(l, "eth1", "10.1.10.1/24", vrf="A", desc="rack subnet, routed port")
            elif i == 2:
                addr(l, "eth2", "10.2.10.1/24", vrf="A", desc="rack subnet, routed port")
            if i == 3:
                addr(l, "eth1", "10.3.10.1/24", vrf="A", desc="tenant A rack subnet")
                addr(l, "eth2", "10.3.10.1/24", vrf="B", desc="tenant B - same subnet, other VRF")
            l3vni(l, "A", 1000, 4001, leaf_lo(i))
            l3vni(l, "B", 2000, 4002, leaf_lo(i))
            leaf_overlay(l, i, spines)
            vrf_evpn(l, 65000, leaf_lo(i), "A")
            vrf_evpn(l, 65000, leaf_lo(i), "B")
        if vname == "two-tors":
            bond_host(lab, nodes, "host1", HOSTMAC[1], ips=["10.12.10.10/24"], gw="10.12.10.1")
            bond_host(lab, nodes, "host2", HOSTMAC[2], ips=["10.12.10.20/24"], gw="10.12.10.1")
        else:
            host(lab, nodes, "host1", "10.1.10.10/24", "10.1.10.1", HOSTMAC[1])
            h2 = host(lab, nodes, "host2", "10.2.10.20/24", "10.2.10.1", HOSTMAC[2], ifname="eth2")
        host(lab, nodes, "host3", "10.3.10.30/24", "10.3.10.1", HOSTMAC[3])
        host(lab, nodes, "host4", "10.3.10.30/24", "10.3.10.1", HOSTMAC[4])
    for t in (("leaf1", "eth1", "host1", "eth1"), ("leaf2", "eth1", "host1", "eth2"), ("leaf1", "eth2", "host2", "eth1"),
              ("leaf2", "eth2", "host2", "eth2"), ("leaf3", "eth1", "host3", "eth1"), ("leaf3", "eth2", "host4", "eth1")):
        lab.link(*t)
    lab.check("one-subnet-one-rack", "host1", "ping -c 3 -W 1 10.2.10.20", PING_OK)
    lab.check("one-subnet-one-rack", "host1", "ping -c 3 -W 1 10.3.10.30", PING_OK)
    lab.check("one-subnet-one-rack", "leaf3", "vtysh -c 'show evpn vni'", r"^(?![\s\S]*\bL2\b)")
    lab.check("two-tors", "host1", "ping -c 3 -W 1 10.3.10.30", PING_OK)
    lab.check("two-tors", "host1", "ping -c 3 -W 1 10.12.10.20", PING_OK)
    lab.check("two-tors", "leaf3", "ip route show vrf A 10.12.10.0/24", r"nexthop via 1\.1\.1\.1[\s\S]*nexthop via 2\.2\.2\.2|nexthop via 2\.2\.2\.2[\s\S]*nexthop via 1\.1\.1\.1")
    for v in ("one-subnet-one-rack", "two-tors"):
        lab.check(v, "leaf1", "ip route show vrf B", r"10\.3\.10\.0/24")
    lab.readme = r"""
## What you will learn

* EVPN without any L2VNI: routed host ports inside VRFs (`ip link set eth1 master A` + an IP), and
  `redistribute connected` + `advertise ipv4 unicast` -> type-5 routes. Functionally an MPLS-L3VPN-like service over VXLAN.
* **Overlapping tenant subnets**: 10.3.10.0/24 exists in VRF A *and* VRF B on leaf3; RDs keep the two type-5
  routes apart, RTs import them into the right VRF.
* RFC 9136 type-5 details: the interface-less model (no gateway IP, RMAC + L3VNI label).
* Why go L3-only (video): no BUM, no MAC tables, failure domains = racks, no VM mobility across racks.
* Dual ToR per rack: the *only* L2 left is inside the rack pair - L2VNI 10012 exists on leaf1/leaf2 only,
  servers dual-home with EVPN-MH, and the rest of the fabric sees the rack subnet as an ECMP type-5 route.

## Step by step

```bash
# leaf1
vtysh -c 'show evpn vni'                         # only L3 VNIs in one-subnet-one-rack
vtysh -c 'show bgp l2vpn evpn route type prefix' # [5]:[0]:[24]:[10.3.10.0] twice (RD 3.3.3.3:x for A and B)
ip route show vrf A ; ip route show vrf B
# host1 -> host3 (A) works; host1 can never reach host4 (B) even though they have the same IP.
```

`two-tors`:

```bash
# leaf3
ip route show vrf A 10.12.10.0/24      # ECMP via leaf1 and leaf2
# leaf1
vtysh -c 'show evpn es' ; vtysh -c 'show evpn vni 10012'   # L2VNI shared only with leaf2
```

Shut host1's link to leaf1 (`ip link set eth1 down` on leaf1): traffic from leaf3 still lands on leaf1 half of
the time (the /24 is still advertised by both) and gets bridged over VNI 10012 to leaf2 - that's why the pair
needs the L2VNI between them.
"""
    return lab


# ==========================================================================
# 34 IPv6 endpoints
# ==========================================================================
def lab34():
    lab = Lab(34, "ipv6-endpoints", "IPv6 Endpoints in EVPN", "miq6tTILvlU", "38 min", """
Dual-stack tenants: IPv6 anycast gateways next to IPv4 ones, type-2 routes with IPv6 addresses, type-5
IPv6 prefixes, **ND suppression**, and the IPv6 side effects that matter at scale - **Router
Advertisements/SLAAC**, DAD, and the extra multicast that IPv6 endpoints generate. Underlay stays IPv4.
""", ref="design_overlay_ipv6_endpoints")
    lab.diagram = """
               spine1               spine2
          leaf1          leaf2           leaf3
            |              |               |
          host1          host2           host3
        VLAN 10         VLAN 10         VLAN 20
   10.10.10.10        10.10.10.20     10.20.20.30
   fd00:10::10        fd00:10::20     fd00:20::30        gw 10.x.x.1 / fd00:x::1 (anycast, same MAC everywhere)
    """
    for vname, desc in (("static", "static IPv6 addresses on hosts, RAs suppressed"),
                        ("slaac", "leaves send RAs (prefix + default router), hosts autoconfigure (EUI-64)")):
        nodes = lab.variant(vname, desc, default=(vname == "static"))
        spines, leaves = std_fabric(lab, nodes, 2, [1, 2, 3])
        std_overlay(spines, leaves)
        for i, l in leaves.items():
            v = 10 if i <= 2 else 20
            l2_services(l, i, [(10, 10010, ["eth1"] if v == 10 else []), (20, 10020, ["eth1"] if v == 20 else [])])
            vrf_dev(l, "A", 1001)
            for vv in (10, 20):
                svi(l, vv, f"10.{vv}.{vv}.1/24", ip6=f"fd00:{vv}::1/64", vrf="A")
                if vname == "slaac":
                    l.frr.iface(f"vlan{vv}", "no ipv6 nd suppress-ra", "ipv6 nd ra-interval 10",
                                f"ipv6 nd prefix fd00:{vv}::/64")
                else:
                    l.frr.iface(f"vlan{vv}", "ipv6 nd suppress-ra")
            l3vni(l, "A", 1000, 4001, leaf_lo(i))
            leaf_overlay(l, i, spines)
            b = vrf_evpn(l, 65000, leaf_lo(i), "A")
            b.af("ipv6 unicast", "redistribute connected")
            b.af("l2vpn evpn", "advertise ipv6 unicast")
        for k, (li, v) in enumerate(((1, 10), (2, 10), (3, 20))):
            hk = k + 1
            if vname == "static":
                host(lab, nodes, f"host{hk}", f"10.{v}.{v}.{10 * hk}/24", f"10.{v}.{v}.1", HOSTMAC[hk],
                     ip6=f"fd00:{v}::{10 * hk}/64", gw6=f"fd00:{v}::1",
                     extra=["sysctl -w net.ipv6.conf.eth1.accept_ra=0"])
            else:
                host(lab, nodes, f"host{hk}", f"10.{v}.{v}.{10 * hk}/24", f"10.{v}.{v}.1", HOSTMAC[hk],
                     keepalive_extra=[f"fd00:{v}::1"],
                     extra=["sysctl -w net.ipv6.conf.eth1.accept_ra=1 net.ipv6.conf.eth1.autoconf=1",
                            "ip link set eth1 down; ip link set eth1 up"])
            if (f"leaf{li}", "eth1", f"host{hk}", "eth1") not in lab.links:
                lab.link(f"leaf{li}", "eth1", f"host{hk}", "eth1")
    lab.check("static", "host1", "ping -6 -c 3 -W 1 fd00:10::20", PING_OK)
    lab.check("static", "host1", "ping -6 -c 3 -W 1 fd00:20::30", PING_OK)
    lab.check("static", "host1", "ping -c 3 -W 1 10.20.20.30", PING_OK)
    lab.check("static", "leaf1", "vtysh -c 'show evpn arp-cache vni 10010'", r"fd00:10::20\s+remote")
    lab.check("static", "leaf1", "ip -6 route show vrf A fd00:20::30", r"via ::ffff:3\.3\.3\.3|via 3\.3\.3\.3|vlan4001")
    lab.check("slaac", "host1", "ip -6 addr show dev eth1", r"fd00:10::2aa:aaff:feaa:aaaa")
    lab.check("slaac", "host1", "ping -6 -c 3 -W 1 fd00:20::2cc:ccff:fecc:cccc", PING_OK)
    lab.readme = r"""
## What you will learn

* Dual-stack SVIs (`ip -6 addr add fd00:10::1/64 dev vlan10`) - the anycast MAC also makes the **link-local**
  gateway address identical on every leaf (EUI-64 of 00:00:5e:00:01:01 = `fe80::200:5eff:fe00:101`).
* FRR: `address-family ipv6 unicast` / `redistribute connected` and `advertise ipv6 unicast` in the VRF's EVPN AF.
  Type-2 routes carry IPv6 addresses; IPv6 type-5 prefixes ride the same IPv4 VTEPs ("IPv6 overlay over IPv4
  underlay") - in the kernel they show up as IPv6 routes via an IPv4-mapped next hop on vlan4001.
* **ND suppression**: the same `neigh_suppress on` covers NS/NA.
* **RA control**: FRR (zebra) only sends Router Advertisements when you ask (`no ipv6 nd suppress-ra`).
  With RAs, hosts do **SLAAC** (EUI-64 or privacy addresses) - every host gets addresses you didn't plan,
  each one a type-2 route on every leaf (scale!). The video recommends suppressing RAs unless you need them,
  and disabling SLAAC on servers (`sysctl net.ipv6.conf.eth1.autoconf=0`, `accept_ra=0`).
* IPv6 BUM: DAD NS, RS, MLD reports - all multicast, all flooded by ingress replication.

## Step by step

```bash
# leaf1
vtysh -c 'show evpn arp-cache vni 10010'               # IPv4 and IPv6 entries
vtysh -c 'show bgp l2vpn evpn route type macip'        # [2]:...:[128]:[fd00:10::20]
vtysh -c 'show bgp l2vpn evpn route type prefix'       # [5]:[0]:[64]:[fd00:20::]
ip -6 route show vrf A
ip -6 neigh show vrf A
# host1
ping -6 fd00:20::30 ; ip -6 route ; ip -6 neigh
```

`slaac` variant:

```bash
# host1
ip -6 addr show dev eth1      # fd00:10::2aa:aaff:feaa:aaaa (EUI-64 from 00:aa:aa:aa:aa:aa)
ip -6 route                   # default via fe80::200:5eff:fe00:101 proto ra
# leaf1
vtysh -c 'show interface vlan10' | grep -A6 'ND advertised'
tcpdump -ni eth11 -e udp port 4789 and ip6     # RAs/NS/DAD crossing the fabric
```

Turn on privacy addresses on host1 (`sysctl -w net.ipv6.conf.eth1.use_tempaddr=2; ip link set eth1 down; ip link set eth1 up`) and count
how many IPv6 type-2 routes one host creates over time.
"""
    return lab


LABS = [lab29, lab30, lab31, lab32, lab33, lab34]
