# Lab 07 - External Routing in EVPN using OSPF. Mutual redistribution and loop avoidance

**Video:** [External Routing in EVPN using OSPF. Mutual redistribution and loop avoidance](https://www.youtube.com/watch?v=EEXWnOcnE1g) (1 h 14 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/external_routing_ospf  

North-south traffic: two **border leaves** connect tenant VRF A to an external OSPF domain. OSPF routes
are redistributed into BGP (and become EVPN type-5 routes), fabric routes are redistributed into OSPF.
With two border leaves, *mutual redistribution* leaks routes back and forth - you will see sub-optimal
routing and loops, then fix them with **tags, communities and route-maps** exactly like the video.

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

- **naive** - plain mutual redistribution OSPF <-> BGP (broken on purpose)
- **loop-prevention** *(default)* - tags + communities + route-maps (the fix from the video)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\07-external-routing-ospf   # default variant: loop-prevention
python tools\gns3_lab.py push labs\07-external-routing-ospf --variant naive   # switch variant in place
python tools\gns3_lab.py check labs\07-external-routing-ospf
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/loop-prevention/` (see the top-level README).

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

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant naive*

| node | command | expect |
|---|---|---|
| r1 | `vtysh -c 'show ip ospf neighbor'` | `3\.3\.3\.3.*Full[\s\S]*4\.4\.4\.4.*Full\|4\.4\.4\.4.*Full[\s\S]*3\.3\.3\.3.*Full` |

*variant loop-prevention*

| node | command | expect |
|---|---|---|
| r1 | `vtysh -c 'show ip ospf neighbor'` | `3\.3\.3\.3.*Full[\s\S]*4\.4\.4\.4.*Full\|4\.4\.4\.4.*Full[\s\S]*3\.3\.3\.3.*Full` |
| leaf1 | `ip route show vrf A 10.100.100.100` | `nexthop via 3\.3\.3\.3[\s\S]*nexthop via 4\.4\.4\.4\|nexthop via 4\.4\.4\.4[\s\S]*nexthop via 3\.3\.3\.3` |
| host1 | `ping -c 3 -W 1 10.100.100.100` | ` 0% packet loss` |
| host5 | `vtysh -c 'show ip route 10.10.10.0/24'` | `ospf` |
| leaf3 | `vtysh -c 'show ip route vrf A 10.100.100.100'` | `Known via \"ospf\"` |
| host5 | `ping -c 3 -W 1 -I 10.100.100.100 10.20.20.40` | ` 0% packet loss` |

