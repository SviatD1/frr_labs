# Lab 24 - Routing Protocol Options for EVPN Underlay

**Video:** [Routing Protocol Options for EVPN Underlay](https://www.youtube.com/watch?v=JsiWm88AKLA) (29 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_underlay_igp  

Same fabric, three link-state underlays: **OSPFv2**, **OSPFv3** (IPv6 underlay) and **IS-IS** (the
default of the rest of this course). Look at the LSDBs, SPF and why fabric links should always be
**point-to-point**.

## Topology

```
        spine1                    spine2
   /   /    \   \           /   /    \   \
leaf1  leaf2  leaf3  leaf4   (every leaf to both spines)
  |      |      |      |
host1  host2  host3  host4    VLAN 10 / VNI 10010, 10.10.10.0/24
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| leaf4 | leaf | 4.4.4.4 |
| host1 | host | 10.10.10.10/24, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.10.10.20/24, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.10.10.30/24, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.10.10.40/24, 00:dd:dd:dd:dd:dd |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine1 | eth3 | leaf3 | eth11 |
| spine1 | eth4 | leaf4 | eth11 |
| spine2 | eth1 | leaf1 | eth12 |
| spine2 | eth2 | leaf2 | eth12 |
| spine2 | eth3 | leaf3 | eth12 |
| spine2 | eth4 | leaf4 | eth12 |
| leaf1 | eth1 | host1 | eth1 |
| leaf2 | eth1 | host2 | eth1 |
| leaf3 | eth1 | host3 | eth1 |
| leaf4 | eth1 | host4 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **ospfv2** *(default)* - OSPFv2 point-to-point, area 0
- **ospfv3** - OSPFv3 over an IPv6 underlay, IPv6 VTEPs (FRR >= 10.6)
- **isis** - IS-IS level-2, point-to-point

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\24-underlay-igp-options   # default variant: ospfv2
python tools\gns3_lab.py push labs\24-underlay-igp-options --variant ospfv3   # switch variant in place
python tools\gns3_lab.py check labs\24-underlay-igp-options
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/ospfv2/` (see the top-level README).

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

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant ospfv2*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.40` | ` 0% packet loss` |
| leaf1 | `vtysh -c 'show ip ospf neighbor'` | `11\.11\.11\.11\s+\d+\s+Full` |
| leaf1 | `ip route show 4.4.4.4` | `nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12` |

*variant ospfv3*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.40` | ` 0% packet loss` |
| leaf1 | `vtysh -c 'show ipv6 ospf6 neighbor'` | `11\.11\.11\.11.*Full` |

*variant isis*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.40` | ` 0% packet loss` |
| leaf1 | `ip route show 4.4.4.4` | `nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12` |

