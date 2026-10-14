from gen import *

HOSTMAC = ["", "00:aa:aa:aa:aa:aa", "00:bb:bb:bb:bb:bb", "00:cc:cc:cc:cc:cc",
           "00:dd:dd:dd:dd:dd", "00:ee:ee:ee:ee:ee", "00:ff:ff:ff:ff:ff"]

BGP_UP = r"BGP state = Established"
PING_OK = r" 0% packet loss"


# ==========================================================================
# 01 EVPN fundamentals
# ==========================================================================
def lab01():
    lab = Lab(1, "evpn-fundamentals", "EVPN Fundamentals", "Dk-qNDrZDX4", "37 min",
              """
The video explains *why* EVPN exists: classic STP bridging wastes links and converges slowly, MLAG/vPC
patches the problem only for pairs of switches, and a pure L3 fabric cannot stretch a subnet.
This lab lets you **see both problems on real Linux boxes** before you build your first EVPN fabric
in lab 02:

* **Part A - STP triangle**: three Linux bridges (`sw1..sw3`) running kernel 802.1D STP. One link is
  blocked, traffic between host1 and host2 takes the long way round, and a link failure takes ~30 s to heal.
* **Part B - L3-only leaf/spine fabric**: two spines, two leaves, IS-IS underlay, every link is used
  (ECMP) - but host3 and host4 are forced into different subnets. EVPN/VXLAN (next lab) gives you both:
  an L3 ECMP underlay *and* L2 stretched over it.
""")
    nodes = lab.variant("default", "STP triangle + routed leaf/spine")
    lab.diagram = """
        Part A (STP)                            Part B (L3 only, IS-IS)
            sw1 (root, prio 4096)               spine1        spine2
           /eth1   \\eth2                          |  \\      /  |
      eth1/          \\eth1                         |    \\  /    |
        sw2 -------- sw3                         leaf1        leaf2
       eth3 eth2  eth2 eth3                        |eth1         |eth1
        |              |                         host3         host4
      host1          host2                     10.1.1.10/24  10.2.2.10/24
    192.168.1.1   192.168.1.2
    """
    prio = {1: 4096, 2: 8192, 3: 32768}
    for k in (1, 2, 3):
        s = Node(f"sw{k}", "router", "switch")
        s.comment("classic 802.1D bridge with the kernel STP implementation")
        s.sh(f"ip link add br0 type bridge stp_state 1 priority {prio[k]}",
             "ip link set br0 up")
        for p in (("eth1", "eth2") if k == 1 else ("eth1", "eth2", "eth3")):
            s.sh(f"ip link set {p} master br0", f"ip link set {p} up")
        s.notes.append(f"bridge priority {prio[k]}")
        nodes[s.name] = s
    lab.link("sw1", "eth1", "sw2", "eth1")
    lab.link("sw1", "eth2", "sw3", "eth1")
    lab.link("sw2", "eth2", "sw3", "eth2")
    host(lab, nodes, "host1", "192.168.1.1/24", mac=HOSTMAC[1])
    host(lab, nodes, "host2", "192.168.1.2/24", mac=HOSTMAC[2])
    lab.link("sw2", "eth3", "host1", "eth1")
    lab.link("sw3", "eth3", "host2", "eth1")

    spines, leaves = std_fabric(lab, nodes, 2, [1, 2])
    for i, l in leaves.items():
        l.comment("routed host port (no bridging at all in an L3-only fabric)")
        addr(l, "eth1", f"10.{i}.{i}.1/24")
        l.frr.iface("eth1", "ip router isis 1", "isis passive")
    host(lab, nodes, "host3", "10.1.1.10/24", "10.1.1.1", HOSTMAC[3])
    host(lab, nodes, "host4", "10.2.2.10/24", "10.2.2.1", HOSTMAC[4])
    lab.link("leaf1", "eth1", "host3", "eth1")
    lab.link("leaf2", "eth1", "host4", "eth1")
    lab.positions = {"sw1": {"x": -450, "y": -200}, "sw2": {"x": -550, "y": -30}, "sw3": {"x": -350, "y": -30},
                     "host1": {"x": -550, "y": 140}, "host2": {"x": -350, "y": 140},
                     "spine1": {"x": 150, "y": -200}, "spine2": {"x": 350, "y": -200},
                     "leaf1": {"x": 150, "y": -30}, "leaf2": {"x": 350, "y": -30},
                     "host3": {"x": 150, "y": 140}, "host4": {"x": 350, "y": 140}}
    lab.check("default", "sw3", "bridge link show dev eth2", r"state blocking", "sw3<->sw2 is blocked by STP")
    lab.check("default", "sw1", "bridge link show dev eth1", r"state forwarding")
    lab.check("default", "host1", "ping -c 3 -W 1 192.168.1.2", PING_OK)
    lab.check("default", "leaf1", "ip route show 10.2.2.0/24", r"nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12",
              "two equal-cost paths")
    lab.check("default", "host3", "ping -c 3 -W 1 10.2.2.10", PING_OK)
    lab.readme = r"""
## What you will learn

* How a Linux bridge does STP (`stp_state 1`) and how to read port roles/states with `bridge link`.
* Why STP blocks links and converges slowly.
* How an L3 leaf/spine fabric with an IGP uses **all** links (ECMP) and converges in about a second.
* Why neither design alone gives you "any subnet anywhere" - the motivation for EVPN.

## Part A - STP

Wait ~30 s after the push (listening + learning = 2 x forward_delay 15 s), then:

```bash
# on sw1, sw2, sw3
bridge link show                 # state forwarding / blocking per port
cat /sys/class/net/br0/bridge/root_id /sys/class/net/br0/bridge/bridge_id
cat /sys/class/net/br0/brif/eth2/state   # 0 disabled 1 listening 2 learning 3 forwarding 4 blocking
```

* `sw1` has the lowest priority -> root bridge. On the sw2-sw3 link, sw2 has the better bridge-id so
  **sw3 eth2 is blocking**.
* From host1 ping host2 and run `tcpdump -ni eth1 -e icmp` on sw1: the traffic hair-pins through the
  root even though sw2 and sw3 are directly connected.

**Break it:** `ip link set eth2 down` on sw1 (the sw1-sw3 link) while pinging host1 -> host2 with
`ping -D -O 192.168.1.2`. Count the lost pings (~30 s) until sw3 eth2 moves listening -> learning -> forwarding.
Bring it back up and watch STP re-block.

## Part B - L3 only fabric

```bash
# on leaf1
vtysh -c 'show isis neighbor'
vtysh -c 'show ip route 10.2.2.0/24'     # two next hops: spine1 and spine2
ip route show 10.2.2.0/24                # same, as installed in the kernel (ECMP)
```

* Ping host4 from host3 - routed through either spine. Shut one uplink (`ip link set eth11 down` on leaf1)
  and see that IS-IS reconverges in ~1 s (look at `ping -D -O`).
* Now try to move host4 into 10.1.1.0/24 (`ip addr flush dev eth1; ip addr add 10.1.1.20/24 dev eth1` on host4):
  it cannot talk to host3 - leaf2 has no idea about that subnet. **This** is the problem EVPN-VXLAN solves:
  keep this L3 underlay, and carry Ethernet frames on top of it (lab 02).

## Linux notes

* Kernel STP is plain 802.1D (no RSTP). Real switches would run RSTP/MSTP - faster, but the blocking problem stays.
* `ip -d link show br0` shows every bridge attribute (`stp_state`, `forward_delay`, `priority`, ...).
"""
    return lab


# ==========================================================================
# 02 Basic bridging
# ==========================================================================
def lab02():
    lab = Lab(2, "basic-bridging", "Basic Bridging/Switching in EVPN", "a4Lfu9x3eyY", "39 min", """
Your first EVPN-VXLAN fabric: one spine (BGP route reflector), two leaves (VTEPs), IS-IS underlay,
iBGP EVPN overlay and a single stretched VLAN 10 <-> VNI 10010. host1 and host2 sit in the same
subnet on different leaves and talk over VXLAN.
""", ref="basic_bridging")
    nodes = lab.variant("default", "IS-IS underlay, iBGP EVPN, VLAN10/VNI10010")
    lab.diagram = """
                     spine1  lo 11.11.11.11  (IS-IS + BGP RR, not a VTEP)
                  eth1/      \\eth2
        10.1.11.0/24/          \\10.2.11.0/24
             eth11 /              \\ eth11
          leaf1 1.1.1.1         leaf2 2.2.2.2      <- VTEPs, AS 65000
             eth1|                  |eth1   (access VLAN 10 -> VNI 10010)
            host1                 host2
        10.10.10.10/24         10.10.10.20/24
    """
    spines, leaves = std_fabric(lab, nodes, 1, [1, 2])
    std_overlay(spines, leaves)
    for i, l in leaves.items():
        l2_services(l, i, [(10, 10010, ["eth1"])], suppress=False)
        leaf_overlay(l, i, spines)
    host(lab, nodes, "host1", "10.10.10.10/24", mac=HOSTMAC[1])
    host(lab, nodes, "host2", "10.10.10.20/24", mac=HOSTMAC[2])
    lab.link("leaf1", "eth1", "host1", "eth1")
    lab.link("leaf2", "eth1", "host2", "eth1")
    c = lambda *a: lab.check("default", *a)
    c("leaf1", "vtysh -c 'show ip route isis'", r"2\.2\.2\.2/32")
    c("leaf1", "vtysh -c 'show bgp neighbor 11.11.11.11'", BGP_UP)
    c("host1", "ping -c 3 -W 1 10.10.10.20", PING_OK)
    c("leaf1", "vtysh -c 'show evpn mac vni 10010'", r"00:bb:bb:bb:bb:bb\s+remote\s+2\.2\.2\.2")
    c("leaf1", "bridge fdb show dev vxlan10010", r"00:bb:bb:bb:bb:bb.*extern_learn|00:bb:bb:bb:bb:bb dst 2\.2\.2\.2")
    c("leaf1", "vtysh -c 'show bgp l2vpn evpn route type multicast'", r"\[3\]:\[0\]:\[32\]:\[2\.2\.2\.2\]")
    lab.readme = r"""
## What you will learn

* The Linux objects that make a VTEP: a VLAN-aware **bridge** (`br0`), a **vxlan** device per VNI,
  access ports with a PVID.
* Who does what: **the kernel forwards** (bridge FDB + vxlan), **FRR/zebra** watches the kernel
  (local MACs) and **bgpd** exchanges MACs as EVPN type-2 routes; remote MACs are written back into
  the kernel FDB.
* The underlay: IS-IS point-to-point between loopbacks; iBGP sessions loopback-to-loopback with the spine as RR.

## How the Linux side maps to the Arista config in the video

| Arista (video) | Linux / FRR (this lab) |
|---|---|
| `vlan 10` + `switchport access vlan 10` | `bridge vlan add dev eth1 vid 10 pvid untagged` |
| `interface Vxlan1` / `vxlan vlan 10 vni 10010` | `ip link add vxlan10010 type vxlan id 10010 local 1.1.1.1 dstport 4789 nolearning` + `bridge vlan add dev vxlan10010 vid 10 pvid untagged` |
| `vxlan source-interface Loopback0` | `local 1.1.1.1` on the vxlan device |
| `router bgp` / `vlan 10` / `redistribute learned` | `address-family l2vpn evpn` / `advertise-all-vni` |
| `rd auto`, `route-target both auto` | FRR default: RD = router-id:auto-index, RT = AS:VNI |
| `router isis` / `isis enable` | `router isis 1` + `ip router isis 1` on interfaces |

## Step by step

1. **Underlay first.** On leaf1: `vtysh -c 'show isis neighbor'`, `ip route` -> you must reach `2.2.2.2`
   and `11.11.11.11` via eth11 *before* anything else works: `ping -I 1.1.1.1 2.2.2.2`.
2. **BGP**: `vtysh -c 'show bgp l2vpn evpn summary'` on spine1 shows both leaves.
3. **Local learning**: ping from host1 to host2, then on leaf1:
   ```bash
   bridge fdb show br br0 | grep -i aa:aa         # learnt on eth1 by the kernel
   vtysh -c 'show evpn mac vni 10010'              # local + remote MACs
   vtysh -c 'show evpn vni detail'
   ```
4. **Routes**: `vtysh -c 'show bgp l2vpn evpn route'` - one type-3 (IMET) per VTEP and one type-2
   per MAC. Look at a route in detail: `vtysh -c 'show bgp l2vpn evpn route type macip detail'`
   -> RD, RT `65000:10010`, label = VNI 10010, next hop = remote loopback.
5. **Kernel result**: `bridge fdb show dev vxlan10010` -> `00:bb:.. dst 2.2.2.2 ... extern_learn`
   (FRR-installed) and `00:00:00:00:00:00 dst 2.2.2.2` (the BUM flood list - lab 03).
6. **Data plane**: on leaf1 `tcpdump -ni eth11 -e udp port 4789` while pinging. Copy the capture to
   your PC (or run `tshark -V`) to see outer IP 1.1.1.1 -> 2.2.2.2, UDP 4789, VXLAN header VNI 10010,
   inner Ethernet aa:aa -> bb:bb.

## Things to break

* `ip link set eth11 down` on leaf2: the IS-IS route to 2.2.2.2 disappears, the BGP session drops
  after the hold timer (datacenter defaults: 9 s) and all of leaf2's MACs are withdrawn.
* `bridge link set dev vxlan10010 learning on` and stop FRR on leaf1 (`systemctl stop frr`) - the
  data plane keeps working for a while from the FDB, but no new MACs are signalled.
* MTU: hosts use MTU 1450 because VXLAN adds 50 bytes. Set host1 eth1 to 1500 and run
  `ping -M do -s 1472 10.10.10.20` - it fails. Lab 37 revisits MTU in depth.
"""
    return lab


# ==========================================================================
# 03 BUM traffic
# ==========================================================================
def lab03():
    lab = Lab(3, "bum-traffic", "Handling BUM traffic in EVPN", "r9W8o7jCNzE", "33 min", """
Broadcast, Unknown-unicast and Multicast (BUM) frames have to reach every VTEP in the VNI. EVPN
signals the flood list with **type-3 IMET** routes and the Linux vxlan device does **head-end
(ingress) replication** using all-zero FDB entries. Then **ARP/ND suppression** lets the local VTEP
answer ARP requests from the EVPN-learnt MAC+IP table so most broadcasts never leave the leaf.
""", ref="bum_with_her")
    lab.diagram = """
                         spine1 (RR)
             /eth1     /eth2     \\eth3    \\eth4
          leaf1      leaf2      leaf3      leaf4        all VLAN 10 / VNI 10010
            |          |          |          |
          host1      host2      host3      host4
         .10 aa     .20 bb     .30 cc     .40 dd        10.10.10.0/24
    """
    for vname, supp, desc in (("her", False, "head-end replication, no ARP suppression"),
                              ("arp-suppression", True, "head-end replication + ARP/ND suppression (+ SVI so the leaves learn host IPs)")):
        nodes = lab.variant(vname, desc)
        spines, leaves = std_fabric(lab, nodes, 1, [1, 2, 3, 4])
        std_overlay(spines, leaves)
        for i, l in leaves.items():
            l2_services(l, i, [(10, 10010, ["eth1"])], suppress=supp)
            if supp:
                svi(l, 10, "10.10.10.1/24", comment="SVI so the kernel (and zebra) learn host IP<->MAC from ARP")
            leaf_overlay(l, i, spines)
        for i in range(1, 5):
            if supp:
                h = host(lab, nodes, f"host{i}", f"10.10.10.{i}0/24", "10.10.10.1", mac=HOSTMAC[i],
                         extra=["ping -c 1 -W 1 10.10.10.1 >/dev/null || true"])
            else:
                host(lab, nodes, f"host{i}", f"10.10.10.{i}0/24", mac=HOSTMAC[i])
            if ("leaf%d" % i, "eth1", f"host{i}", "eth1") not in lab.links:
                lab.link(f"leaf{i}", "eth1", f"host{i}", "eth1")
    for v in ("her", "arp-suppression"):
        lab.check(v, "host1", "ping -c 3 -W 1 10.10.10.40", PING_OK)
        lab.check(v, "leaf1", "bridge fdb show dev vxlan10010 | grep 00:00:00:00:00:00",
                  r"dst 2\.2\.2\.2[\s\S]*dst 3\.3\.3\.3[\s\S]*dst 4\.4\.4\.4|dst 4\.4\.4\.4[\s\S]*dst 3\.3\.3\.3")
        lab.check(v, "leaf1", "vtysh -c 'show evpn vni 10010'", r"Number of Remote VTEPs: 3|Remote VTEPs for this VNI:")
    lab.check("her", "leaf1", "bridge -d link show dev vxlan10010", r"neigh_suppress off")
    lab.check("arp-suppression", "leaf1", "bridge -d link show dev vxlan10010", r"neigh_suppress on")
    lab.check("arp-suppression", "host4", "ping -c 2 -W 1 10.10.10.1", PING_OK, "host4 ARPs its leaf -> leaf4 learns its IP")
    lab.check("arp-suppression", "leaf1", "vtysh -c 'show evpn arp-cache vni 10010'", r"10\.10\.10\.40\s+remote")
    lab.check("arp-suppression", "leaf1", "ip neigh show dev vlan10", r"10\.10\.10\.40 lladdr 00:dd:dd:dd:dd:dd.*extern_learn")
    lab.readme = r"""
## What you will learn

* EVPN **type-3 Inclusive Multicast Ethernet Tag (IMET)** routes = "I am a VTEP for VNI X, send me BUM".
* How Linux implements **head-end replication**: one `00:00:00:00:00:00 dst <vtep>` FDB entry per
  remote VTEP on the vxlan device; a broadcast is copied once per entry.
* How **ARP suppression** works on Linux: `neigh_suppress on` on the vxlan bridge port + FRR installing
  remote MAC+IP (type-2) as neighbor entries -> the bridge answers ARP locally.

## Step by step (variant `her`)

```bash
# leaf1
vtysh -c 'show bgp l2vpn evpn route type multicast'   # one IMET per VTEP: [3]:[0]:[32]:[x.x.x.x]
bridge fdb show dev vxlan10010 | grep 00:00:00:00:00:00
vtysh -c 'show evpn vni 10010'                         # remote VTEP list
```

Capture on leaf2/leaf3/leaf4 uplinks (`tcpdump -ni eth11 -e udp port 4789`) and from host1 run
`arping -c1 -I eth1 10.10.10.40`: **every** leaf receives a copy of the ARP broadcast, from source 1.1.1.1.
Count the copies leaving leaf1 on eth11: 3 - one per remote VTEP (that's the "head-end" cost).

Unknown unicast: on host1 `ip neigh replace 10.10.10.99 lladdr 00:12:34:56:78:9a dev eth1` and ping it - the frame is
flooded to all VTEPs because no VTEP advertised that MAC.

## Step by step (variant `arp-suppression`)

```bash
python tools\gns3_lab.py push labs\03-bum-traffic --variant arp-suppression
```

```bash
# leaf1
bridge -d link show dev vxlan10010 | grep -o 'neigh_suppress [a-z]*'
vtysh -c 'show evpn arp-cache vni 10010'      # IP->MAC from type-2 routes
ip neigh show                                  # (nothing on br0 - the bridge itself answers)
```

From host1 `ip neigh flush all; arping -c1 -I eth1 10.10.10.40` while capturing on leaf2..4 eth11:
the ARP request is **not** flooded anymore; leaf1's bridge replies with dd:dd:.. on behalf of host4.
(If a host was quiet for a long time its neighbor entry on its leaf may have been garbage-collected and the
type-2 route lost its IP - ping the gateway from it again.)

Important Linux detail: a VTEP can only suppress ARP for hosts it has a MAC+IP for, and a type-2 route carries
an IP only if the originating leaf knows it. On Linux, zebra learns a local host's IP from the **SVI's neighbor
table** - so the leaf needs an SVI in that VLAN (`vlan10`, here anycast 10.10.10.1 without any VRF) and the host
must ARP for it (hosts use it as their gateway and ping it once at boot). Without an SVI (variant `her`) the
type-2 routes are MAC-only and there is nothing to suppress with. Remote entries show up in
`ip neigh show dev vlan10` as `extern_learn` - that's what the bridge answers ARP requests from.

## Multicast underlay (theory / extra credit)

The video also covers **PIM-SM/BiDir/SSM underlay** for BUM. Linux can do it: create the vxlan device with
`group 239.1.1.10 dev <underlay-if>` instead of relying on the zero-MAC flood list, and run `pimd` in the
underlay (`ip pim` on fabric links and `lo`, RP on the spine). FRR supports this
("PIM-SM over VXLAN for BUM") but expect some fiddling; head-end replication is what nearly every
production EVPN data center uses.

## Things to break

* Remove the flood list on leaf1: `bridge fdb del 00:00:00:00:00:00 dev vxlan10010 dst 4.4.4.4` -> host1
  can't ARP host4 (in `her`), but can still ping it if the ARP entry already exists. FRR re-adds the entry
  when you `vtysh -c 'clear bgp l2vpn evpn *'`.
* `ip link set eth1 down` on leaf4 - leaf4 keeps advertising IMET (the VNI is still up) but host4's MAC is withdrawn.
"""
    return lab


# ==========================================================================
# 04 Bridging deep dive
# ==========================================================================
def lab04():
    lab = Lab(4, "bridging-deep-dive", "EVPN Bridging Deep Dive: RD, RT, VNI, EVI, MAC-VRF, VLAN-Aware Bundle",
              "YRMEEhEaXgw", "1 h 15 min", """
Route Distinguishers, Route Targets, VNIs and VLANs - which ones must match and which are only locally
significant. Variants let you break RT and VNI consistency and use different local VLANs for the same
broadcast domain; a second tenant reuses the *same MAC and IP addresses* in its own VNI to show that
EVPN keeps MAC-VRFs apart.
""", ref="bridging_deep_dive")
    lab.diagram = """
                                   spine1 (RR)
                  /eth1        /eth2         \\eth3        \\eth4
             leaf1           leaf2            leaf3          leaf4
          eth1  eth2      eth1  eth2          eth1           eth1
          host1 host2     host3 host4         host5          host6
   VLAN    10    20        10    20            30             30
   VNI   10010 10020     10010 10020         10030          10030
          .10.10 .20.20   .10.30 .20.40     10.10.10.10 aa  10.10.10.20 bb   <- tenant B reuses
                                            (same MAC/IP as host1/host2!)       tenant A addresses
    """
    variants = [
        ("baseline", "manual RTs 10:10 / 20:20 / 30:30 on all leaves"),
        ("rt-mismatch", "leaf2 uses RT 99:99 for VNI 10010"),
        ("vni-mismatch", "leaf2 maps VLAN 10 to VNI 10011 (RT still 10:10)"),
        ("local-vlans", "leaf2 uses VLAN 110/120 locally for VNIs 10010/10020"),
    ]
    for vname, desc in variants:
        nodes = lab.variant(vname, desc, default=(vname == "baseline"))
        spines, leaves = std_fabric(lab, nodes, 1, [1, 2, 3, 4])
        std_overlay(spines, leaves)
        for i, l in leaves.items():
            if i in (1, 2):
                v10, v20, n10 = 10, 20, 10010
                if i == 2 and vname == "local-vlans":
                    v10, v20 = 110, 120
                if i == 2 and vname == "vni-mismatch":
                    n10 = 10011
                svc = [(v10, n10, ["eth1"]), (v20, 10020, ["eth2"])]
                rts = {n10: "10:10", 10020: "20:20"}
                if i == 2 and vname == "rt-mismatch":
                    rts[10010] = "99:99"
            else:
                svc = [(30, 10030, ["eth1"])]
                rts = {10030: "30:30"}
            l2_services(l, i, svc, suppress=False)
            vl = {}
            for vni, rt in rts.items():
                vl[vni] = [f"rd {leaf_lo(i)}:{vni % 1000}", f"route-target import {rt}", f"route-target export {rt}"]
            leaf_overlay(l, i, spines, vni_lines=vl)
        host(lab, nodes, "host1", "10.10.10.10/24", mac=HOSTMAC[1])
        host(lab, nodes, "host2", "10.20.20.20/24", mac=HOSTMAC[2])
        host(lab, nodes, "host3", "10.10.10.30/24", mac=HOSTMAC[3])
        host(lab, nodes, "host4", "10.20.20.40/24", mac=HOSTMAC[4])
        host(lab, nodes, "host5", "10.10.10.10/24", mac=HOSTMAC[1])
        host(lab, nodes, "host6", "10.10.10.20/24", mac=HOSTMAC[2])
    for a, b in (("leaf1", "eth1"), ("leaf1", "eth2"), ("leaf2", "eth1"), ("leaf2", "eth2"), ("leaf3", "eth1"), ("leaf4", "eth1")):
        pass
    lab.link("leaf1", "eth1", "host1", "eth1")
    lab.link("leaf1", "eth2", "host2", "eth1")
    lab.link("leaf2", "eth1", "host3", "eth1")
    lab.link("leaf2", "eth2", "host4", "eth1")
    lab.link("leaf3", "eth1", "host5", "eth1")
    lab.link("leaf4", "eth1", "host6", "eth1")
    lab.check("baseline", "host1", "ping -c 3 -W 1 10.10.10.30", PING_OK)
    lab.check("baseline", "host2", "ping -c 3 -W 1 10.20.20.40", PING_OK)
    lab.check("baseline", "host5", "ping -c 3 -W 1 10.10.10.20", PING_OK, "tenant B with overlapping MAC/IP")
    lab.check("baseline", "leaf1", "vtysh -c 'show bgp l2vpn evpn route rd 2.2.2.2:10 type macip'", r"00:cc:cc:cc:cc:cc")
    lab.check("baseline", "leaf3", "vtysh -c 'show evpn mac vni 10030'", r"00:bb:bb:bb:bb:bb\s+remote\s+4\.4\.4\.4")
    lab.check("rt-mismatch", "host1", "ping -c 2 -W 1 10.10.10.30", r"100% packet loss")
    lab.check("rt-mismatch", "host2", "ping -c 2 -W 1 10.20.20.40", PING_OK)
    lab.check("local-vlans", "host1", "ping -c 3 -W 1 10.10.10.30", PING_OK)
    lab.check("local-vlans", "leaf2", "bridge vlan show dev vxlan10010", r"110 PVID")
    lab.check("vni-mismatch", "leaf1", "vtysh -c 'show evpn mac vni 10010'", r"00:cc:cc:cc:cc:cc\s+remote")
    lab.readme = r"""
## What you will learn

* **VNI** = data-plane identifier of a broadcast domain (in the VXLAN header). Must be agreed between VTEPs.
* **VLAN** = *locally significant* on each leaf (only the access port and the VNI mapping care).
* **RD** = makes routes unique in BGP (FRR default `router-id:index`). Never needs to match.
* **RT** = import/export policy - decides which MAC-VRF (EVI) a route is imported into. Must be consistent.
* **EVI / MAC-VRF** = the EVPN instance; on FRR every VNI is its own EVI (*VLAN-based service*).

Here the RTs are configured manually (`route-target import/export 10:10`) instead of FRR's auto
`65000:10010`, to make them visible and easy to break. The RD is set to `<loopback>:<vni % 1000>`.

## Step by step (baseline)

```bash
vtysh -c 'show evpn vni 10010 detail'                       # RD, import/export RTs, VTEPs
vtysh -c 'show bgp l2vpn evpn vni 10010'                    # BGP view of that EVI
vtysh -c 'show bgp l2vpn evpn route rd 2.2.2.2:10'          # everything leaf2 originated for VNI 10010
vtysh -c 'show bgp l2vpn evpn route type macip detail'      # Extended Community: RT:10:10 ET:8
```

Notice: route-type 2 NLRI = `[2]:[EthTag]:[MAClen]:[MAC]:[IPlen]:[IP]`. The **Ethernet Tag is 0** - that is
VLAN-based service. The VNI travels as the MPLS-label field of the NLRI.

**Multitenancy:** host5/host6 (VNI 10030) reuse host1/host2's MAC *and* IP. Both pairs ping fine. Look at
`vtysh -c 'show bgp l2vpn evpn route'` on spine1: the same MAC appears under different RDs, so BGP
keeps both, and RTs 10:10 vs 30:30 import them into different MAC-VRFs.

## Variants (push them one by one)

| variant | what to observe |
|---|---|
| `rt-mismatch` | leaf2 exports VNI 10010 with RT 99:99. leaf1 *receives* the routes (`show bgp l2vpn evpn route rd 2.2.2.2:10`) but does not import them: `show evpn mac vni 10010` has no host3, and leaf2 is not in leaf1's VTEP list. host1 <-> host3 breaks; VLAN 20 keeps working. |
| `vni-mismatch` | leaf2 uses VNI 10011, RT still 10:10. Control plane imports the routes (RT matches), but the data plane label differs. Capture on leaf2 eth11: frames arrive with VNI 10010 and leaf2 has no such VNI -> dropped. Lesson: RT-based import does not fix inconsistent VNIs. |
| `local-vlans` | leaf2 uses VLAN 110/120. Everything works: `bridge vlan show` on leaf2 vs leaf1 - VLAN numbers are local, VNIs are global. |

## VLAN-aware bundle (video 1:02:53)

The video shows Arista's *VLAN-aware bundle* service: one EVI (one RD/RT) carrying many VLANs,
distinguished by a non-zero **Ethernet Tag** in the routes. **FRR implements only VLAN-based service**
(one VNI = one EVI, Ethernet Tag 0), so there is no FRR equivalent to configure. What you *can* do on
FRR is give several VNIs the **same RT** - routes will then be imported into all of them, and FRR
uses the VNI label to sort them out. Try setting `route-target import/export 10:10` on VNI 10020 too
and look at what `show evpn mac vni 10020` contains. Interoperating with a VLAN-aware-bundle
peer is possible only if that peer uses the same VNI-per-VLAN mapping.
"""
    return lab


# ==========================================================================
# 05 Basic routing - asymmetric / symmetric IRB
# ==========================================================================
def lab05():
    lab = Lab(5, "basic-routing-irb", "Basic routing in EVPN: VRFs, Anycast Gateway, Asymmetric and Symmetric IRB",
              "AJc1dd6_gBg", "32 min", """
Add routing to the fabric: a tenant VRF, **anycast gateway** SVIs (same IP and MAC on every leaf) and the
two IRB models. *Asymmetric* IRB routes on the ingress leaf and bridges in the destination VNI (every
leaf needs every VLAN). *Symmetric* IRB routes on both leaves through an **L3VNI** using the remote
leaf's router MAC (RMAC).
""", ref="basic_routing")
    lab.diagram = """
                         spine1 (RR)
                     eth1/       \\eth2
                   leaf1           leaf2         VRF CUSTOMER_A, anycast GW 10.10.10.1 / 10.20.20.1
                eth1  eth2      eth1  eth2       MAC 00:00:5e:00:01:01 on every leaf
               host1  host2    host3  host4
          VLAN  10     20       10     20
         10.10.10.10 10.20.20.20 10.10.10.30 10.20.20.40
                                   symmetric only: L3VNI 1000 (VLAN 4001)
    """
    for vname, desc in (("asymmetric", "SVIs on every leaf, no L3VNI"),
                        ("symmetric", "SVIs + L3VNI 1000 (router MAC, type-2 with two labels)")):
        nodes = lab.variant(vname, desc, default=(vname == "symmetric"))
        spines, leaves = std_fabric(lab, nodes, 1, [1, 2])
        std_overlay(spines, leaves)
        for i, l in leaves.items():
            l2_services(l, i, [(10, 10010, ["eth1"]), (20, 10020, ["eth2"])])
            vrf_dev(l, "CUSTOMER_A", 1001)
            svi(l, 10, "10.10.10.1/24", vrf="CUSTOMER_A")
            svi(l, 20, "10.20.20.1/24", vrf="CUSTOMER_A")
            leaf_overlay(l, i, spines)
            if vname == "symmetric":
                l3vni(l, "CUSTOMER_A", 1000, 4001, leaf_lo(i))
                vrf_evpn(l, 65000, leaf_lo(i), "CUSTOMER_A")
        host(lab, nodes, "host1", "10.10.10.10/24", "10.10.10.1", HOSTMAC[1])
        host(lab, nodes, "host2", "10.20.20.20/24", "10.20.20.1", HOSTMAC[2])
        host(lab, nodes, "host3", "10.10.10.30/24", "10.10.10.1", HOSTMAC[3])
        host(lab, nodes, "host4", "10.20.20.40/24", "10.20.20.1", HOSTMAC[4])
    lab.link("leaf1", "eth1", "host1", "eth1")
    lab.link("leaf1", "eth2", "host2", "eth1")
    lab.link("leaf2", "eth1", "host3", "eth1")
    lab.link("leaf2", "eth2", "host4", "eth1")
    for v in ("asymmetric", "symmetric"):
        lab.check(v, "host1", "ping -c 3 -W 1 10.20.20.40", PING_OK, "routed between VLANs across leaves")
        lab.check(v, "host1", "ping -c 3 -W 1 10.10.10.30", PING_OK)
        lab.check(v, "host1", "ping -c 2 -W 1 10.10.10.1", PING_OK, "anycast gateway")
    lab.check("asymmetric", "leaf1", "ip neigh show vrf CUSTOMER_A 10.20.20.40", r"lladdr 00:dd:dd:dd:dd:dd")
    lab.check("symmetric", "leaf1", "vtysh -c 'show evpn vni 1000'", r"Type: L3|L3")
    lab.check("symmetric", "leaf1", "ip route show vrf CUSTOMER_A 10.20.20.40", r"via 2\.2\.2\.2 dev vlan4001")
    lab.check("symmetric", "leaf1", "vtysh -c 'show evpn rmac vni all'", r"2\.2\.2\.2")
    lab.readme = r"""
## What you will learn

* Linux **VRF** devices (`ip link add CUSTOMER_A type vrf table 1001`) and enslaving SVIs to them.
* **Anycast gateway**: every leaf has `vlan10` = 10.10.10.1 with MAC `00:00:5e:00:01:01`. Linux needs one
  extra trick for a VLAN device whose MAC differs from the bridge: a local FDB entry
  `bridge fdb replace 00:00:5e:00:01:01 dev br0 vlan 10 self local` so frames to that MAC are delivered up
  to the SVI.
* **Asymmetric IRB**: leaf1 routes 10.10.10.10 -> 10.20.20.40 into vlan20 *locally*, resolves host4's
  MAC from an ARP entry that FRR installed from host4's type-2 MAC+IP route, then bridges over VNI 10020.
  Return traffic is routed on leaf2 and bridged over VNI 10010 - different VNIs each way, hence "asymmetric".
* **Symmetric IRB**: both directions use the **L3VNI 1000**. leaf1 installs `10.20.20.40/32 via 2.2.2.2 dev vlan4001 onlink`,
  the inner destination MAC is leaf2's **router MAC** (its `br0`/`vlan4001` MAC, carried in the
  *Router's MAC* extended community).

## Why the hosts ping their gateway every 20 s

Every host in these labs runs a tiny keepalive (`lab-gw-keepalive-<host>`, started by its net.sh) that pings
its default gateway. Real servers talk constantly; lab hosts are silent - and a silent host is invisible to
EVPN routing on Linux:

* zebra learns a local host's **IP** only from the neighbor (ARP/ND) table of the SVI;
* if leaf1 itself has to ARP for host4 (10.20.20.40), the request leaves with the **anycast** source
  10.20.20.1 / `00:00:5e:00:01:01`. host4 replies to that MAC - and leaf2, which owns the same anycast MAC,
  swallows the reply. leaf1's entry stays `FAILED`.

Once host4 has ARPed *its* gateway (leaf2), leaf2 advertises a type-2 MAC+IP route and leaf1 installs the
neighbor entry (`extern_learn`) - no ARP needed. Kill the keepalive on host4
(`pkill -f lab-gw-keepalive`), flush leaf2's entry (`ip neigh flush dev vlan20`) and watch the asymmetric
variant break. (Production fabrics use the same trick: Cumulus/SONiC refresh neighbor entries periodically,
and Arista sends ARP from a unique per-leaf address.)

## Linux objects for symmetric IRB

```text
CUSTOMER_A (vrf, table 1001)
 ├─ vlan10   10.10.10.1/24  (anycast)      br0 vid 10   <-> vxlan10010
 ├─ vlan20   10.20.20.1/24  (anycast)      br0 vid 20   <-> vxlan10020
 └─ vlan4001 (no IP, MAC = RMAC)           br0 vid 4001 <-> vxlan1000  (L3VNI)
```

FRR side: `vrf CUSTOMER_A / vni 1000` and `router bgp 65000 vrf CUSTOMER_A / address-family l2vpn evpn / advertise ipv4 unicast`.

## Step by step

Push `asymmetric` first:

```bash
python tools\gns3_lab.py push labs\05-basic-routing-irb --variant asymmetric
```

```bash
# leaf1
ip -br link show master CUSTOMER_A
ip route show vrf CUSTOMER_A                        # only connected subnets!
ip neigh show vrf CUSTOMER_A                        # remote hosts appear as neighbors (from EVPN)
vtysh -c 'show evpn arp-cache vni 10020'
```

Ping host1 -> host4 and capture on leaf1 eth11: the VXLAN packet carries **VNI 10020** (destination VLAN).
Capture leaf2 eth11 on the return path: **VNI 10010**.

Then push `symmetric`:

```bash
# leaf1
vtysh -c 'show evpn vni'                 # L2 and L3 VNIs
vtysh -c 'show evpn rmac vni all'        # remote router MACs
vtysh -c 'show evpn next-hops vni all'
vtysh -c 'show bgp l2vpn evpn route type macip detail'   # two labels: 10020 and 1000, RT 65000:1000 + Rmac
ip route show vrf CUSTOMER_A             # 10.20.20.40 via 2.2.2.2 dev vlan4001 proto bgp onlink
ip neigh show dev vlan4001               # 2.2.2.2 lladdr <leaf2 RMAC> extern_learn
```

Capture: now both directions use **VNI 1000** and the inner destination MAC is the remote RMAC
(`44:38:39:ff:00:02` for leaf2).

## Things to try

* In `symmetric`, remove VLAN 20 from leaf1 entirely (`ip link del vlan20; ip link del vxlan10020`).
  host1 still reaches host4 - with symmetric IRB a leaf only needs the VLANs it has hosts in.
  Do the same in `asymmetric` and it breaks.
* Look at the type-5 routes too: `redistribute connected` in the VRF advertises 10.10.10.0/24 and
  10.20.20.0/24 as **type-5 IP prefix** routes (`show bgp l2vpn evpn route type prefix`). Lab 06 uses them.
"""
    return lab


# ==========================================================================
# 06 Routing deep dive
# ==========================================================================
def lab06():
    lab = Lab(6, "routing-deep-dive", "EVPN Routing Deep Dive: Route Types, Isolated VNIs, Inter-VRF Route Leaking",
              "Ntm772VEEdE", "49 min", """
Routing between a *stretched* subnet and an *isolated* one (a VNI that exists on a single leaf),
type-2 MAC/IP host routes vs type-5 IP-prefix routes, a second customer VRF and **inter-VRF route
leaking** with FRR's `import vrf`.
""", ref="routing_deep_dive")
    lab.diagram = """
                               spine1 (RR)
                    /eth1          |eth2          \\eth3
                leaf1            leaf2             leaf3
                 eth1             eth1          eth1      eth2
                host1            host2          host3     host4
   VRF           A                 A              A         B
   VLAN/VNI   10/10010         10/10010       30/10030  40/10040  (30 and 40 only on leaf3 = isolated)
            10.10.10.10      10.10.10.20    10.30.30.30 10.40.40.40
   L3VNI: CUSTOMER_A 1000 (VLAN 4001), CUSTOMER_B 2000 (VLAN 4002)
    """
    for vname, desc in (("no-leak", "two VRFs fully isolated"),
                        ("leak", "leaf3 leaks 10.40.40.0/24 into A and A's subnets into B (import vrf + route-maps)")):
        nodes = lab.variant(vname, desc, default=(vname == "leak"))
        spines, leaves = std_fabric(lab, nodes, 1, [1, 2, 3])
        std_overlay(spines, leaves)
        for i, l in leaves.items():
            if i in (1, 2):
                svc = [(10, 10010, ["eth1"])]
            else:
                svc = [(30, 10030, ["eth1"]), (40, 10040, ["eth2"])]
            l2_services(l, i, svc)
            vrf_dev(l, "CUSTOMER_A", 1001)
            vrf_dev(l, "CUSTOMER_B", 1002)
            if i in (1, 2):
                svi(l, 10, "10.10.10.1/24", vrf="CUSTOMER_A")
            else:
                svi(l, 30, "10.30.30.1/24", vrf="CUSTOMER_A")
                svi(l, 40, "10.40.40.1/24", vrf="CUSTOMER_B")
            leaf_overlay(l, i, spines)
            l3vni(l, "CUSTOMER_A", 1000, 4001, leaf_lo(i))
            l3vni(l, "CUSTOMER_B", 2000, 4002, leaf_lo(i))
            a = vrf_evpn(l, 65000, leaf_lo(i), "CUSTOMER_A")
            b = vrf_evpn(l, 65000, leaf_lo(i), "CUSTOMER_B")
            if vname == "leak" and i == 3:
                l.frr.line("ip prefix-list B-SUBNETS seq 5 permit 10.40.40.0/24",
                           "ip prefix-list A-SUBNETS seq 5 permit 10.10.10.0/24",
                           "ip prefix-list A-SUBNETS seq 10 permit 10.30.30.0/24")
                l.frr.block("""
                    route-map FROM-B permit 10
                     match ip address prefix-list B-SUBNETS
                    exit
                    !
                    route-map FROM-A permit 10
                     match ip address prefix-list A-SUBNETS
                    exit""")
                a.af("ipv4 unicast", "import vrf route-map FROM-B", "import vrf CUSTOMER_B")
                b.af("ipv4 unicast", "import vrf route-map FROM-A", "import vrf CUSTOMER_A")
        host(lab, nodes, "host1", "10.10.10.10/24", "10.10.10.1", HOSTMAC[1])
        host(lab, nodes, "host2", "10.10.10.20/24", "10.10.10.1", HOSTMAC[2])
        host(lab, nodes, "host3", "10.30.30.30/24", "10.30.30.1", HOSTMAC[3])
        host(lab, nodes, "host4", "10.40.40.40/24", "10.40.40.1", HOSTMAC[4])
    lab.link("leaf1", "eth1", "host1", "eth1")
    lab.link("leaf2", "eth1", "host2", "eth1")
    lab.link("leaf3", "eth1", "host3", "eth1")
    lab.link("leaf3", "eth2", "host4", "eth1")
    for v in ("no-leak", "leak"):
        lab.check(v, "host1", "ping -c 3 -W 1 10.30.30.30", PING_OK, "stretched -> isolated subnet")
        lab.check(v, "leaf1", "vtysh -c 'show bgp l2vpn evpn route type prefix'", r"\[5\]:\[0\]:\[24\]:\[10\.30\.30\.0\]")
    lab.check("no-leak", "host1", "ping -c 2 -W 1 10.40.40.40", r"100% packet loss|Unreachable")
    lab.check("leak", "leaf1", "ip route show vrf CUSTOMER_A 10.40.40.0/24", r"10\.40\.40\.0/24")
    lab.check("leak", "host1", "ping -c 3 -W 1 10.40.40.40", PING_OK, "A -> B via route leaking")
    lab.check("leak", "host4", "ping -c 3 -W 1 10.10.10.20", PING_OK)
    lab.readme = r"""
## What you will learn

* **Stretched BD** (VNI 10010 on leaf1+leaf2) vs **isolated BD** (VNI 10030/10040 only on leaf3).
  Leaves without VNI 10030 cannot do asymmetric IRB to it - only symmetric IRB (L3VNI) works.
* How a route to a host in an isolated VNI is found: the type-2 MAC/IP route carries the L3VNI RT + RMAC,
  so leaf1 gets a /32. For hosts that never sent traffic (*silent hosts*) only the **type-5** subnet
  route (`redistribute connected` in the VRF) helps.
* Inter-VRF **route leaking** on FRR: `import vrf OTHER` (+ `import vrf route-map NAME`) in
  `address-family ipv4 unicast` of the VRF's BGP instance. Leaked routes keep their original next hop
  (an interface or L3VNI in the other VRF) and the kernel happily routes across VRFs. Leaked routes are
  re-advertised into EVPN as type-5 routes of the importing VRF - which is how leaf1/leaf2 learn about
  10.40.40.0/24 in VRF A without any leaking config of their own.

## Step by step

```bash
# leaf1
vtysh -c 'show bgp l2vpn evpn route type macip'     # host routes, with 2 labels when L3VNI exists
vtysh -c 'show bgp l2vpn evpn route type prefix'    # [5]:[0]:[24]:[10.30.30.0] etc.
vtysh -c 'show bgp vrf CUSTOMER_A ipv4 unicast'     # what got imported into the VRF
ip route show vrf CUSTOMER_A
```

* Ping host1 -> host3. Which route is used on leaf1, the /32 or the /24? (`ip route get vrf CUSTOMER_A 10.30.30.30`).
* **Silent host**: on leaf1 `ip route show vrf CUSTOMER_A 10.30.30.0/24` is the type-5 route. Add an
  extra IP on host3 (`ip addr add 10.30.30.31/24 dev eth1`) and ping it from host1 without sending
  anything from host3 first - the /24 carries the packet to leaf3, leaf3 ARPs, learns, advertises a /32.
  Then remove `redistribute connected` in CUSTOMER_A on leaf3 and repeat with `10.30.30.32`: it fails.

## Route leaking (variant `leak`)

```bash
vtysh -c 'show bgp vrf CUSTOMER_A ipv4 unicast 10.40.40.0/24'   # "Imported from ... vrf CUSTOMER_B"
ip route show vrf CUSTOMER_A 10.40.40.0/24                       # nexthop in another VRF
vtysh -c 'show bgp l2vpn evpn route type prefix'                 # is the leaked route re-advertised as type-5?
```

Questions to answer in the lab:

1. Leaking is configured on **leaf3 only**, and only for subnets. What would happen with unfiltered mutual
   `import vrf` on *every* leaf? Try it (add `import vrf CUSTOMER_B` to A and `import vrf CUSTOMER_A` to B on all
   three leaves, no route-maps) and look at `ip route show vrf CUSTOMER_A 10.10.10.10` on leaf1: host1's own /32
   comes back *through VRF B from a remote VTEP* (leaked -> advertised as type-5 -> imported -> leaked again).
   It is preferred over the local /24 (longest match) and traffic for a local host leaves the leaf. That is the
   route-leaking loop the video warns about; filters and a single leaking point avoid it.
2. Why is 10.30.30.0/24 in `A-SUBNETS`? (host4 in B must reach host3 too - remove it and test.)
3. The video's EVPN-native alternative is importing the other VRF's **RT** into the L3VNI
   (`route-target import 65000:2000` under `address-family l2vpn evpn` of CUSTOMER_A). Try it in `no-leak`:
   leaf1 installs the route, but Linux encapsulates with *A's* L3VNI (1000) and leaf3 delivers it into VRF A,
   where 10.40.40.0/24 does not exist. On Linux, leak locally instead.
"""
    return lab


LABS = [lab01, lab02, lab03, lab04, lab05, lab06]
