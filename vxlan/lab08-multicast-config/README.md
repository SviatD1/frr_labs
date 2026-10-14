# Lab 08 · Multicast underlay configuration

**Video:** *VXLAN - Multicast Underlay Configuration on Cisco Nexus Switches* (#8)
**Status:** ✅ tested (RPT→SPT across two PIM routers, two VNIs/groups)

## What's new vs lab 07

- **Two PIM routers**: spine1 is the RP, spine2 is not. leaf3 hangs off spine2, so its traffic must cross a **router-to-router PIM** link (spine1 eth4 ↔ spine2 eth4) — you get to see PIM joins, register messages and the SPT switchover.
- **Two VNIs mapped to two groups**: VNI 100 → 239.1.1.100, VNI 200 → 239.1.1.200.

## NX-OS ↔ FRR

| NX-OS | FRR / Linux here |
|---|---|
| `feature pim` | `pimd` enabled (first line of `*.frr.conf`) |
| `ip pim rp-address 10.0.0.1 group-list 239.0.0.0/8` | `ip pim rp 10.0.0.1 239.0.0.0/8` |
| `interface eth1/1` / `ip pim sparse-mode` | `interface eth1` / `ip pim` |
| `interface nve1` / `member vni 100 mcast-group 239.1.1.100` | `ip link add vxlan100 type vxlan id 100 group 239.1.1.100 dev eth1 ...` |
| `show ip mroute` / `show ip pim neighbor` | `vtysh -c 'show ip mroute'` / `'show ip pim neighbor'` |

## Topology

```
     [spine1] RP 10.0.0.1 ──eth4────eth4── [spine2] 10.0.0.2
      eth1    eth2                            eth3
     [leaf1] [leaf2]                         [leaf3]   (leaf3 uplink = its eth2)
     eth3 eth4  eth3                         eth3 eth4
      h1   h4    h2                           h3   h5

 VNI 100 / 239.1.1.100 : h1 (leaf1), h2 (leaf2), h3 (leaf3)   192.168.100.0/24
 VNI 200 / 239.1.1.200 : h4 (leaf1), h5 (leaf3)               192.168.200.0/24
```

## Build

Run `nodes/<node>.sh` on spine1-2, leaf1-3, h1-5.

## Verify

```bash
spine2# vtysh -c 'show ip pim neighbor'          # spine1 via eth4
spine2# vtysh -c 'show ip pim rp-info'           # RP 10.0.0.1, I am RP: no
spine2# vtysh -c 'show ip igmp groups'           # leaf3 joined both groups on eth3
h3$ ping -c2 192.168.100.101 ; h5$ ping -c2 192.168.200.101
spine2# vtysh -c 'show ip mroute'
#  *         239.1.1.100  IGMP in eth4 (towards RP) -> eth3          shared tree
#  10.2.13.1 239.1.1.100  PIM  in eth3 -> eth4                       leaf3 as source, sent towards spine1
#  10.1.11.1 239.1.1.100  in eth4 -> eth3                            leaf1 as source, SPT through spine1
spine1# vtysh -c 'show ip pim upstream'          # Register state for 10.1.x sources
spine1# vtysh -c 'show ip pim join'
```

## Experiments

1. **Watch PIM on the wire**: GNS3 capture on spine1↔spine2; filter `pim`. Restart FRR on spine2 (`systemctl restart frr`) and see Hello, Join/Prune toward the RP. When leaf3 starts sending, look for **Register** / **Register-Stop** between spine2 (first-hop for leaf3) and spine1 (RP).
2. **Group isolation**: only leaf1 and leaf3 join 239.1.1.200. Check spine1's `show ip mroute` — leaf2's port (eth2) is never in the 239.1.1.200 OIL. That's the bandwidth win over "flood to every VTEP".
3. **SPT switchover**: `show ip mroute` flags — `T` = SPT bit set. FRR switches to SPT immediately by default (`ip pim spt-switchover infinity-and-beyond` keeps traffic on the shared tree; try it on spine2 and compare paths).
4. **Many VNIs, one group**: add VNI 300 on leaf1+leaf3 mapped to the *same* 239.1.1.200. It works; but leaf2 would receive VNI 300 floods if it had VNI 200… Trade-off: multicast state vs unwanted traffic.

## Break / fix

| Break it | Symptom |
|---|---|
| spine2: `interface eth4` / `no ip pim` | leaf3 is cut off from BUM in both directions; unicast OSPF still fine |
| spine2: wrong RP address | spine2 can't build (*,G) toward the RP — `show ip pim rp-info`, `show ip mroute` |
| spine1: `ip pim rp 10.0.0.1 224.0.0.0/4` vs spine2 still `239.0.0.0/8` | still works (overlapping) — RP mappings must cover the groups; mismatched RP *addresses* break |

## Questions

- Which router is the first-hop router (DR) for leaf3's VXLAN traffic?
- Why does PIM need the unicast routing table (RPF check)?
