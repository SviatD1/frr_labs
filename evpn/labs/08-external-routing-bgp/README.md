# Lab 08 - External Routing in EVPN using BGP

**Video:** [External Routing in EVPN using BGP](https://www.youtube.com/watch?v=uuUZyg-tZ20) (40 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/external_routing_bgp  

The same fabric, but the border leaves peer **eBGP** (inside VRF A) with the external AS 65001.
No redistribution, no loops - BGP's AS-path does it for you. You will block host routes from leaking
outside, then do **traffic engineering** with local-preference so that each subnet enters the fabric
through a specific border leaf.

## Topology

```
              spine1 (RR)                spine2 (RR)
       ________/ |  \ \__________   ______/ / |  \
     leaf1     leaf2     leaf3 (border)   leaf4 (border)        VRF A, L3VNI 10100
   eth1 eth2  eth1 eth2   eth1   eth2      eth1   eth2
   host1 host3 host2 host4  |  \    ________/      /
                            |   \  /    __________/
                            |    \/    /
                            r1 ----X---- r2          AS 65001 (external)
                             \eth3      /eth3
                               host5  (FRR, lo 10.100.100.100 = "the internet")
leaf3 eth1 - r1 eth1 172.16.31.0/24     leaf3 eth2 - r2 eth2 172.16.32.0/24
leaf4 eth1 - r2 eth1 172.16.42.0/24     leaf4 eth2 - r1 eth2 172.16.41.0/24
r1 eth3 - host5 eth1 172.16.15.0/24     r2 eth3 - host5 eth2 172.16.25.0/24
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
| host1 | host | 10.10.10.10/24, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.10.10.20/24, gw 10.10.10.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.20.20.30/24, gw 10.20.20.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.20.20.40/24, gw 10.20.20.1, 00:dd:dd:dd:dd:dd |
| r1 | ext | 172.16.1.1 |
| r2 | ext | 172.16.2.2 |
| host5 | exthost | 10.100.100.100 external 'internet' router, runs FRR |

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
| leaf1 | eth2 | host3 | eth1 |
| leaf2 | eth2 | host4 | eth1 |
| leaf3 | eth1 | r1 | eth1 |
| leaf3 | eth2 | r2 | eth2 |
| leaf4 | eth1 | r2 | eth1 |
| leaf4 | eth2 | r1 | eth2 |
| r1 | eth3 | host5 | eth1 |
| r2 | eth3 | host5 | eth2 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **basic** *(default)* - eBGP border leaves <-> r1/r2, host routes filtered
- **te** - basic + r1 prefers leaf3 for 10.10.10.0/24, r2 prefers leaf4 for 10.20.20.0/24

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\08-external-routing-bgp   # default variant: basic
python tools\gns3_lab.py push labs\08-external-routing-bgp --variant te   # switch variant in place
python tools\gns3_lab.py check labs\08-external-routing-bgp
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/basic/` (see the top-level README).

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

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant basic*

| node | command | expect |
|---|---|---|
| leaf3 | `vtysh -c 'show bgp vrf A summary'` | `172\.16\.31\.1\)?\s+4\s+65001\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\S+\s+\d+` |
| host1 | `ping -c 3 -W 1 10.100.100.100` | ` 0% packet loss` |
| r1 | `vtysh -c 'show ip bgp'` | `10\.10\.10\.0/24` |
| r1 | `vtysh -c 'show ip bgp 10.10.10.10/32'` | `Network not in table\|not in table` |

*variant te*

| node | command | expect |
|---|---|---|
| leaf3 | `vtysh -c 'show bgp vrf A summary'` | `172\.16\.31\.1\)?\s+4\s+65001\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\S+\s+\d+` |
| host1 | `ping -c 3 -W 1 10.100.100.100` | ` 0% packet loss` |
| r1 | `vtysh -c 'show ip bgp'` | `10\.10\.10\.0/24` |
| r1 | `vtysh -c 'show ip bgp 10.10.10.10/32'` | `Network not in table\|not in table` |
| host5 | `vtysh -c 'show ip bgp 10.10.10.0/24'` | `Local Pref(erence)?:? ?200\|localpref 200` |
| host5 | `ip route get 10.10.10.10` | `via 172\.16\.15\.1` |
| host5 | `ip route get 10.20.20.40` | `via 172\.16\.25\.2` |

