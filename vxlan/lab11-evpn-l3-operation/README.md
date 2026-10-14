# Lab 11 · Understanding MP-BGP EVPN Layer 3 operation

**Video:** *VXLAN - Understanding MP-BGP EVPN Layer 3 Operation* (#11)
**Status:** ⚠️ FRR configs syntax-checked (`vtysh --dryrun`) and built from FRR's standard symmetric-IRB pattern; not run end-to-end (test kernel had no VRF support). Lab 10's fabric, which this extends, is fully tested.

## The L3 picture

Lab 10 only bridged. Now hosts in **different subnets** talk, and every leaf routes locally (distributed routing):

- **Tenant VRF** `TENANT1` (Linux `vrf` device, table 1001) on every leaf.
- **L3VNI 4001** — a VNI that belongs to the VRF, not to a subnet. Routed traffic between leaves travels in VNI 4001: *symmetric IRB* (route at ingress leaf → VNI 4001 → route at egress leaf).
- **Router MAC (RMAC)** — each leaf's MAC on the L3VNI bridge, advertised in BGP; used as inner destination MAC for routed packets.
- **Type-2 MAC+IP** routes now carry **two labels** (L2VNI + L3VNI) and the RMAC → each leaf installs a /32 host route in the VRF.
- **Type-5** IP prefix routes carry subnets and external prefixes (from the border leaf).

## Topology

```
     [spine1] RR        [spine2] RR                       (fabric = lab 10)
   [leaf1]          [leaf2]          [leaf3]──eth4── [ext] AS 65100
    eth3             eth3             eth3     10.99.0.0/31   lo 172.16.1.1, 172.16.2.1
     h1               h2               h3
 VNI 100              VNI 200          VNI 200          all in VRF TENANT1, L3VNI 4001
 192.168.100.101      192.168.200.102  192.168.200.103
 gw .100.1            gw .200.1        gw .200.1   (gateway IP + MAC 02:00:5e:00:01:01 identical on every leaf)
```

leaf3 is also the **border leaf**: its eth4 is in VRF TENANT1 and peers eBGP with `ext`.

## Linux pieces per leaf (read `nodes/leaf1.sh`)

```
TENANT1 (vrf, table 1001)
 ├── br4001 ── vxlan4001      L3VNI: transit for routed traffic, br4001's MAC = this leaf's RMAC
 └── br100  ── vxlan100, eth3  L2VNI + SVI 192.168.100.1 (anycast gateway)
```

FRR: `vrf TENANT1 / vni 4001`, plus `router bgp 65000 vrf TENANT1` with `redistribute connected` and `address-family l2vpn evpn / advertise ipv4 unicast` (this is what creates type-5s).

## Build

Run `nodes/<node>.sh` on spine1-2, leaf1-3, ext, h1-3.

## Verify

```bash
leaf1# vtysh -c 'show evpn vni'                          # 100 L2 + 4001 L3
leaf1# vtysh -c 'show vrf vni'                           # TENANT1 -> 4001, state Up, Router MAC
leaf1# vtysh -c 'show evpn rmac vni 4001'                # RMACs of leaf2 and leaf3
leaf1# vtysh -c 'show evpn next-hops vni 4001'
h1$ ping 192.168.200.102 ; ping 192.168.200.103        # routed between subnets
leaf1# ip route show vrf TENANT1
#  192.168.200.102 via 10.0.0.12 dev br4001 proto bgp onlink    <- /32 from a type-2 (MAC+IP)
#  192.168.200.0/24 nhid ... via 10.0.0.12 / 10.0.0.13            <- type-5 subnet (ECMP)
leaf1# ip neigh show dev br4001                          # 10.0.0.12 lladdr <leaf2 RMAC> extern_learn
leaf1# vtysh -c 'show bgp l2vpn evpn route type macip'   # [2]...[32]:[192.168.200.102]  RT:65000:200 RT:65000:4001  Rmac:...
leaf1# vtysh -c 'show bgp l2vpn evpn route type prefix'  # [5] 192.168.200.0/24, 172.16.1.1/32 ...
```

## External connectivity (border leaf)

```bash
leaf3# vtysh -c 'show bgp vrf TENANT1 summary'           # ext Established
ext#   vtysh -c 'show ip bgp'                            # tenant subnets + /32 hosts learned from leaf3
h1$    ping 172.16.1.1                                    # h1 -> leaf1 -> L3VNI -> leaf3 -> ext
leaf1# ip route get 172.16.1.1 vrf TENANT1                # via 10.0.0.13 dev br4001
```

## Experiments

1. **Packet walk**: capture spine↔leaf while h1 pings h2. Outer: 10.0.0.11 → 10.0.0.12. **VNI 4001**, not 200! Inner dst MAC = leaf2's RMAC, inner src MAC = leaf1's RMAC, inner TTL decremented. Compare to an h2↔h3 ping (same subnet): VNI 200, inner MACs = real host MACs.
2. **Silent host**: start a new host h4 = 192.168.200.104 on leaf2:eth4 (cable it, then on leaf2 `ip link set eth4 master br200; ip link set eth4 up`; on h4 use `nodes/h3.sh` with the IP changed) but don't let it send anything. Ping it from h1: leaf1 uses the **type-5 /24** to reach *some* leaf with VNI 200, which ARPs for it. Then a type-2 for .104 appears.
3. **Summarize at the border**: on leaf3, `aggregate-address 192.168.0.0/16 summary-only` under the VRF's ipv4 unicast → ext sees one prefix.

## Break / fix

| Break it | Symptom |
|---|---|
| leaf2: remove `vni 4001` under `vrf TENANT1` | routing to/from h2 breaks; `show vrf vni` shows nothing; type-2s from leaf2 lose the L3 RT/RMAC |
| leaf3: change L3VNI to 4002 | leaf3's VRF isolated (RT 65000:4002) |
| leaf1: remove `advertise ipv4 unicast` | no type-5 from leaf1; external networks can't reach 192.168.100.0/24 subnet route (hosts still via /32) |

## Questions

- Why does a routed packet between leaves never use the destination host's L2VNI?
- What exactly does the RMAC buy you that the VTEP IP alone doesn't?
