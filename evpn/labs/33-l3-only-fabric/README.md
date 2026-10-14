# Lab 33 - Layer 3 Only Fabric with EVPN

**Video:** [Layer 3 Only Fabric with EVPN](https://www.youtube.com/watch?v=8tKi73LWPRM) (40 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_overlay_ip_vpn  

No stretched L2 at all: **one subnet per rack**, and EVPN used purely as a multi-tenant L3VPN
(type-5 routes in per-tenant L3VNIs). Overlapping tenant subnets just work. A second variant puts a
subnet on a *pair* of ToRs (dual-homed servers with EVPN multihoming) - the only place where L2 is
still needed.

## Topology

```
            spine1                  spine2
     leaf1        leaf2               leaf3
    e1   e2      e1   e2            e1     e2
     |    \____ |    |              |      |
     |      ___\|____|            host3   host4
    host1  /     host2            VRF A    VRF B   (same subnet 10.3.10.0/24 in both!)
one-subnet-one-rack: host1 10.1.10.10 (leaf1, A), host2 10.2.10.20 (leaf2 eth2, A)
two-tors: host1/host2 bonded to leaf1+leaf2, subnet 10.12.10.0/24 on both ToRs (ES + L2VNI 10012 local to the pair)
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| host1 | host | 10.1.10.10/24, gw 10.1.10.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.2.10.20/24, gw 10.2.10.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.3.10.30/24, gw 10.3.10.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.3.10.30/24, gw 10.3.10.1, 00:dd:dd:dd:dd:dd |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine1 | eth3 | leaf3 | eth11 |
| spine2 | eth1 | leaf1 | eth12 |
| spine2 | eth2 | leaf2 | eth12 |
| spine2 | eth3 | leaf3 | eth12 |
| leaf1 | eth1 | host1 | eth1 |
| leaf2 | eth1 | host1 | eth2 |
| leaf1 | eth2 | host2 | eth1 |
| leaf2 | eth2 | host2 | eth2 |
| leaf3 | eth1 | host3 | eth1 |
| leaf3 | eth2 | host4 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **one-subnet-one-rack** *(default)* - rack-local subnets, type-5 only, no L2VNI
- **two-tors** - rack = 2 ToRs: EVPN-MH bond, L2VNI only inside the pair, type-5 to the rest

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\33-l3-only-fabric   # default variant: one-subnet-one-rack
python tools\gns3_lab.py push labs\33-l3-only-fabric --variant two-tors   # switch variant in place
python tools\gns3_lab.py check labs\33-l3-only-fabric
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/one-subnet-one-rack/` (see the top-level README).

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

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant one-subnet-one-rack*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.2.10.20` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.3.10.30` | ` 0% packet loss` |
| leaf3 | `vtysh -c 'show evpn vni'` | `^(?![\s\S]*\bL2\b)` |
| leaf1 | `ip route show vrf B` | `10\.3\.10\.0/24` |

*variant two-tors*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.3.10.30` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.12.10.20` | ` 0% packet loss` |
| leaf3 | `ip route show vrf A 10.12.10.0/24` | `nexthop via 1\.1\.1\.1[\s\S]*nexthop via 2\.2\.2\.2\|nexthop via 2\.2\.2\.2[\s\S]*nexthop via 1\.1\.1\.1` |
| leaf1 | `ip route show vrf B` | `10\.3\.10\.0/24` |

