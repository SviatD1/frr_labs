# Lab 07 · Understanding the multicast underlay

**Video:** *VXLAN - Understanding the Multicast Underlay* (#7)
**Status:** ✅ tested (IGMP joins, (*,G) and (S,G) state verified)

## The idea

Head-end replication (labs 02-06) sends N−1 unicast copies of every broadcast. The RFC's original answer: map each VNI to an **IP multicast group**. Every VTEP that has the VNI **joins** the group; BUM traffic is sent **once** to the group address and the underlay (PIM) replicates it only where needed.

- **IGMP** — VTEP tells its first-hop router "I want 239.1.1.100".
- **PIM-SM** — routers build the distribution tree. A **Rendezvous Point (RP)** is the meeting place: receivers join toward the RP — the shared tree, (*,G); sources register to the RP; then routers switch to the shortest-path tree, (S,G).
- Known unicast (after learning) is still plain unicast VTEP-to-VTEP.

## Topology

```
                [spine1]  lo 10.0.0.1 = RP for 239.0.0.0/8
                 PIM + IGMP on eth1-3
              eth1   eth2    eth3
            [leaf1] [leaf2] [leaf3]       VNI 100  ->  group 239.1.1.100
              h1      h2      h3          192.168.100.101-103
```

### Design note (important, read once)

On a Nexus every leaf runs PIM itself. In this lab the leaves are kept simple: they are **IGMP members** (the Linux kernel joins the group because the vxlan device was created with `group 239.1.1.100 dev eth1`), and the VTEP source address is the leaf's **uplink** IP (`10.1.1L.1`), so spine1 sees a *directly connected* multicast source and can act as first-hop router. Lab 08 adds a second PIM router so you see real PIM joins between routers. (FRR can also make the leaf itself the PIM first-hop router using a dummy `ipmr-lo` device — see "FRR PIM EVPN BUM" in the FRR docs, as an advanced challenge.)

Also note `ttl 16` on the vxlan devices: Linux sends VXLAN multicast with TTL 1 by default, which would die at the first router.

## Build

Run `nodes/<node>.sh` on spine1, leaf1-3, h1-3.

## Verify — step by step

```bash
leaf1# ip -d link show vxlan100              # ... group 239.1.1.100 dev eth1 ... ttl 16
leaf1# ip maddr show dev eth1                # inet 239.1.1.100  <- the kernel joined the group
spine1# vtysh -c 'show ip igmp groups'       # 239.1.1.100 on eth1, eth2, eth3
spine1# vtysh -c 'show ip pim rp-info'       # 10.0.0.1, I am RP: yes
h1$ ping -c3 192.168.100.103
spine1# vtysh -c 'show ip mroute'
#   *          239.1.1.100   IGMP  -> eth1 eth2 eth3      (shared tree, built from IGMP joins)
#   10.1.11.1  239.1.1.100   in eth1 -> eth2 eth3         (source tree for leaf1's BUM traffic)
spine1# vtysh -c 'show ip pim upstream'
leaf2# bridge fdb show dev vxlan100          # 00:00:00:00:00:00 dst 239.1.1.100 ; learned MACs dst <VTEP IP>
```

## Experiments

1. **One copy instead of N−1**: `tcpdump -ni eth1 udp port 4789` on leaf1 while h1 runs `arping -c1 192.168.100.99`. You see **one** packet to 239.1.1.100 (lab 02 sent one per remote VTEP). On spine1 `tcpdump -ni any udp port 4789` shows it replicated out eth2 and eth3.
2. **Receiver leaves**: on leaf3 `ip link del vxlan100` (VNI gone → IGMP leave). Within a few seconds spine1 removes eth3 from the OIL in `show ip mroute`. Re-run `nodes/leaf3.sh` to restore.
3. **Unicast after learning**: after the first ping, capture again — h1↔h3 echo traffic goes 10.1.11.1 → 10.1.13.1 unicast, not to the group.
4. **IGMP versions**: `vtysh -c 'show ip igmp interface'` on spine1 (querier, version 3). Change with `ip igmp version 2` under an interface.

## Break / fix

| Break it | Symptom | Look at |
|---|---|---|
| leaf2: recreate vxlan100 **without** `ttl 16` | leaf2's broadcasts never reach others (TTL 1) — others' do reach leaf2 | `ip -d link`, tcpdump TTL on spine |
| spine1: `no ip igmp` on eth3 | leaf3 stops receiving BUM; h1→h3 first ping fails | `show ip igmp groups` |
| spine1: change RP to an address that doesn't exist (`ip pim rp 10.9.9.9 239.0.0.0/8`) | BUM breaks | `show ip pim rp-info`, `show ip mroute` |
| leaf3: map VNI 100 to group 239.1.1.101 | leaf3 is in its own flood domain | VNI→group mapping must agree everywhere |

## Questions

- Why can many VNIs share one multicast group, and what's the cost?
- Why is the RP a single point of failure here? (→ lab 09)
