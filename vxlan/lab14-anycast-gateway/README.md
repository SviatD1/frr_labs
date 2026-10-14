# Lab 14 · EVPN anycast distributed gateway

**Video:** *VXLAN - EVPN Anycast Distributed Gateway* (#14)
**Status:** ⚠️ FRR configs syntax-checked; L3 building blocks as lab 11 (not run on the VRF-less test kernel).

## The idea

Every leaf is the default gateway for every subnet it serves, using the **same IP and the same MAC** (192.168.100.1 / `02:00:5e:00:01:01`). Consequences:

- First-hop routing always happens on the **directly attached** leaf — no hair-pinning to a central router.
- A host can **move** to any leaf and its cached gateway ARP entry stays valid.
- Gateways are never advertised in EVPN (each leaf owns them locally), so there's no "duplicate MAC" fight.

## Topology

```
     [spine1] RR        [spine2] RR
   [leaf1]            [leaf2]                [leaf3]
    eth3          eth3      eth4(empty)       eth3
     h1            h2       ← h1 moves here    h3
 VNI100 .101    VNI200 .102                  VNI100 .103
```

VRF TENANT1 / L3VNI 4001 everywhere. VNI 100 = 192.168.100.0/24 on leaf1, leaf2 (port eth4, empty for now), leaf3. VNI 200 = 192.168.200.0/24 on leaf2 and leaf3. `neigh_suppress on` on every L2VNI (ARP suppression).

## Build

Run `nodes/<node>.sh` on spine1-2, leaf1-3, h1-3.

## Verify — the gateway is the same everywhere

```bash
leaf1# ip -br addr show br100 ; ip -br link show br100       # 192.168.100.1/24, 02:00:5e:00:01:01
leaf3# ip -br addr show br100 ; ip -br link show br100       # identical
h1$ ping -c1 192.168.100.1 ; ip neigh show 192.168.100.1     # 02:00:5e:00:01:01
h3$ ping -c1 192.168.100.1 ; ip neigh show 192.168.100.1     # same MAC, different physical leaf
h1$ ping 192.168.200.102                                     # routed on leaf1, not on some central box
h1$ traceroute -n 192.168.200.102                            # first hop 192.168.100.1 = answered by leaf1 itself
leaf1# vtysh -c 'show evpn mac vni 100'                      # gateway MAC is NOT in the EVPN MAC table
```

## ARP suppression

```bash
leaf1# vtysh -c 'show evpn arp-cache vni 100'      # h1 local, h3 remote (learned via type-2 MAC+IP)
leaf1# ip neigh show dev br100                     # remote entries "extern_learn"
h1$ ip neigh flush all ; ping -c1 192.168.100.103
# capture spine<->leaf1 at the same time: the ARP for .103 is answered locally by leaf1
# (bridge neigh_suppress) and never crosses the fabric
```

## Host mobility

1. On h1 keep `ping 192.168.200.102` running.
2. In GNS3 delete the h1–leaf1:eth3 link and connect h1:eth1 to **leaf2:eth4**.
3. h1 sends anything (the running ping does) → leaf2 learns h1 locally and advertises a type-2 with a higher **MAC Mobility sequence number**:
   ```bash
   leaf2# vtysh -c 'show bgp l2vpn evpn route type macip'      # h1's route now from 10.0.0.12, "MM:1"
   leaf1# vtysh -c 'show evpn mac vni 100 mac <h1-mac>'        # remote, VTEP 10.0.0.12, seq 1
   ```
4. h1 never re-ARPs the gateway: same IP, same MAC on leaf2. Count lost pings — typically a handful while the leaves converge.

Move it back to leaf1:eth3 and watch the sequence number go to 2.

## Experiments

1. **Without anycast**: give each leaf a *unique* gateway MAC (`ip link set br100 address 02:00:5e:00:01:0N`) and repeat the move. h1 keeps sending to leaf1's MAC until its ARP times out → traffic hairpins or blackholes. That is the problem anycast solves.
2. **Centralized gateway alternative**: remove the SVI IP from leaf1/leaf3 and keep it only on leaf2, with `advertise-default-gw` under `address-family l2vpn evpn` on leaf2. Now every routed packet from h1/h3 crosses the fabric to leaf2 and back (look at the VNIs on the wire).
3. **Duplicate address detection**: move h1 back and forth quickly 5+ times within 3 minutes — FRR's DAD (`show evpn mac vni 100 duplicate`) freezes the MAC. Clear with `clear evpn dup-addr vni 100 all`.

## Break / fix

| Break it | Symptom |
|---|---|
| leaf3: gateway IP 192.168.100.254 | h3 (gw .1) loses routing; ARP for .1 now crosses the fabric to another leaf |
| leaf2: `bridge link set dev vxlan100 neigh_suppress off` | still works; ARPs flood again (capture to see it) |
| leaf1: same gateway MAC but a different IP | h1 routes fine; after a move to leaf3 its gateway IP is gone |

## Questions

- Why must the anycast MAC never be advertised as a type-2 route?
- What does the MAC Mobility extended community prevent?
