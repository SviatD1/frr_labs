# Lab 15 · Integrated Routing and Bridging — asymmetric vs symmetric

**Video:** *VXLAN - Integrated Routing and Bridging* (#15)
**Status:** ⚠️ FRR configs syntax-checked; not run on the VRF-less test kernel.

## Two ways to route in an EVPN fabric

| | **Asymmetric IRB** | **Symmetric IRB** |
|---|---|---|
| Where routing happens | ingress leaf only: route, then **bridge** in the destination VNI | ingress leaf routes into the **L3VNI**, egress leaf routes again |
| VNIs on each leaf | **every** VNI of the tenant, everywhere | only VNIs with local hosts + one L3VNI per VRF |
| VNI on the wire (h1→h2) | 200 (destination subnet's VNI) | 4001 (L3VNI) |
| Inner dst MAC | h2's real MAC | egress leaf's router MAC (RMAC) |
| Inner TTL | −1 | −2 |
| Return path | uses VNI 100 — different from forward (hence "asymmetric") | uses 4001 — same both ways |
| Scale | ARP/MAC for all hosts on every leaf | host /32s, no remote ARP state needed |

## Topology

```
     [spine1] RR        [spine2] RR
   [leaf1]            [leaf2]            [leaf3]
    eth3               eth3               eth3
     h1                 h2                 h3
 VNI100 .100.101    VNI200 .200.102    VNI100 .100.103     VRF TENANT1, anycast gw .1
```

Two sets of leaf files:

| Variant | Leaf script | Leaf VNIs | L3VNI |
|---|---|---|---|
| **Symmetric** (default) | `nodes/leafN.sh` | leaf1: 100, leaf2: 200, leaf3: 100 | 4001 |
| **Asymmetric** | `nodes/leafN-asym.sh` | 100 **and** 200 on every leaf | none |

Spines and hosts are the same for both.

## Part A — asymmetric

```bash
leafN# ./nodes/leafN-asym.sh          # on all three leaves; spines/hosts: their normal scripts
leaf1# vtysh -c 'show evpn vni'       # 100 and 200 (L2 only), no L3 VNI
leaf1# vtysh -c 'show vrf vni'        # nothing
h1$ ping -c3 192.168.200.102
leaf1# ip neigh show dev br200        # h2's IP->MAC, installed by zebra from the type-2 (extern_learn)
leaf1# ip route show vrf TENANT1      # only connected subnets — no /32s needed
```

Capture spine↔leaf1 and spine↔leaf2 during the ping:

- h1 → h2 request: VNI **200**, inner dst MAC = h2.
- h2 → h1 reply: VNI **100**, inner dst MAC = h1.
- `h1$ ping -c1 192.168.200.102` → reply **ttl=63**: h2 starts at 64 and only leaf2 (the ingress leaf for the reply) routes it.

## Part B — symmetric

```bash
leafN# ./nodes/leafN.sh               # all three leaves (the script wipes the asym config)
leaf1# vtysh -c 'show evpn vni'       # 100 (L2) + 4001 (L3) — no 200 on leaf1!
leaf1# ip route show vrf TENANT1      # 192.168.200.102 via 10.0.0.12 dev br4001 onlink
leaf1# ip neigh show dev br4001       # 10.0.0.12 -> leaf2 RMAC
h1$ ping -c3 192.168.200.102
```

Capture again: both directions in VNI **4001**, inner MACs are the two leaves' RMACs. `h1$ ping -c1 192.168.200.102` now replies with **ttl=62**: routed on leaf2 *and* leaf1.

## Fill this in

| | asymmetric | symmetric |
|---|---|---|
| VNIs configured on leaf1 | | |
| `ip neigh` entries for remote hosts on leaf1 | | |
| VNI seen on wire h1→h2 / h2→h1 | | |
| reply TTL seen by h1 | | |
| EVPN routes for h2 on leaf1 (`show bgp l2vpn evpn route type macip`) — RTs and labels | | |

## Experiments

1. **Scale thought experiment**: 50 leaves, 500 subnets, 20 000 hosts. In asymmetric mode each leaf holds 500 SVIs and ~20 000 ARP entries; in symmetric, only local subnets plus /32 routes. Which one fits in a leaf's hardware tables?
2. **Mix them** (don't do this in production): run leaf1 asymmetric and leaf2 symmetric. Does h1↔h2 work? Explain from the route types and VNIs each leaf can decode.
3. **Silent host in symmetric mode**: add a host on leaf3 in VNI 200 (leaf3 needs VNI 200 for that) that never talks. h1 reaches it via the type-5 /24 for 192.168.200.0/24 — check `ip route show vrf TENANT1` on leaf1.

## Questions

- Why is asymmetric IRB simpler to explain but harder to scale?
- In symmetric IRB, why does the egress leaf still need the destination host's ARP entry?
