# Lab 06 · Spine and leaf architecture

**Video:** *VXLAN - Spine and Leaf Architecture* (#6)
**Status:** ✅ tested (ECMP and BFD failover verified)

## Why spine-leaf

Every leaf connects to every spine; spines never connect to each other; hosts only connect to leaves. Any leaf→leaf path is exactly **leaf → spine → leaf**, and with N spines there are N equal-cost paths. VXLAN makes this possible because the whole fabric is **routed** (no spanning tree), while VXLAN still gives you L2 wherever you need it.

## Topology

```
          [spine1]10.0.0.1        [spine2]10.0.0.2
          eth1 eth2 eth3          eth1 eth2 eth3
            |  \  / \ /             /  /   /
            |   \/   X     ...full mesh...
          eth1 eth2  eth1 eth2  eth1 eth2
          [leaf1]    [leaf2]    [leaf3]
           eth3       eth3       eth3
            h1         h2         h3        VNI 100, 192.168.100.0/24
```

Underlay: OSPF point-to-point on every /31, `maximum-paths 8`, **BFD** on all fabric links, `fib_multipath_hash_policy=1` (L4 hashing). Overlay: VNI 100 with static head-end replication between the three leaf loopbacks.

## Build

Run `nodes/<node>.sh` on spine1-2, leaf1-3, h1-3.

## Verify

```bash
leaf1# vtysh -c 'show ip ospf neighbor'          # 2 neighbours (both spines)
leaf1# ip route show 10.0.0.12                    # TWO nexthops: via eth1 and via eth2 (ECMP)
leaf1# vtysh -c 'show bfd peers brief'            # 2 sessions up
spine1# vtysh -c 'show ip route'                  # spines see 3 leaf loopbacks; no host subnets
h1$ ping 192.168.100.102 ; ping 192.168.100.103
```

## Experiments

1. **ECMP with VXLAN entropy**: on h2 run `iperf3 -s`; on h1 run `iperf3 -c 192.168.100.102 -P 8` (8 TCP flows). On both spines `ip -s link show eth1` before/after, or `tcpdump -ni eth1 -c 50 udp port 4789` — both spines carry traffic. Different inner flows → different outer UDP source ports → different ECMP hash results.
   Check what the kernel would pick: `ip route get 10.0.0.12 ipproto udp sport 50000 dport 4789` vs `sport 50001`, `50002`…
2. **Failover with BFD**: start `ping -i 0.2 192.168.100.103` on h1, then in GNS3 *suspend* the spine1–leaf1 link (or `ip link set eth1 down` on spine1). BFD (300 ms × 3 in FRR's default) pulls the OSPF adjacency in ~1 s; count lost pings. Repeat with BFD removed (`no ip ospf bfd` on the interfaces) — with the default 40 s dead interval and a link that stays "up" (GNS3 suspend), the outage is much longer.
3. **Scale by adding a leaf**: add leaf4 (copy leaf3's script, change numbers, cable spine1:eth4 & spine2:eth4 — no spine-to-spine cable in this lab so eth4 is free). Add it to every leaf's flood list. Notice how *nothing* changes on the spines except two OSPF interfaces.
4. **Oversubscription thought exercise**: leaf with 48×25G down and 4×100G up = 3:1.

## Break / fix

| Break it | Symptom |
|---|---|
| leaf2: `ip addr del 10.0.0.12/32 dev lo` | overlay to leaf2 dies; underlay pings to spines still fine |
| spine2: shut all interfaces | everything still works on spine1 alone — that's the point |
| remove `maximum-paths 8` / set `maximum-paths 1` on leaf1 | only one nexthop in `ip route show 10.0.0.12` |

## Questions

- Why do spines never need to know about VNIs or MAC addresses?
- What would happen if you connected spine1 to spine2? (Lab 08 does it, for a reason.)
