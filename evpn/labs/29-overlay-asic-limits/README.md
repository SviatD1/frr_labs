# Lab 29 - Designing EVPN Overlay for Data Center. ASICs and their limits

**Video:** [Designing EVPN Overlay for Data Center. ASICs and their limits](https://www.youtube.com/watch?v=jzDw9H-bM_Q) (37 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_overlay_asic  

Hardware tables (MAC, host routes, LPM, next hops, tunnels) are finite, and an EVPN design decides what
every leaf has to hold. Generate hundreds of endpoints with `mac-flood`, then compare how many MAC
and host-route entries each leaf ends up with when **every VNI is everywhere** versus **VNIs only
where needed**.

## Topology

```
         spine1                spine2           (RR; hold BGP state, no forwarding state)
    leaf1      leaf2      leaf3      leaf4
      |          |          |          |
    host1      host2      host3      host4
   VLAN10     VLAN10     VLAN20     VLAN20
VLAN 10: 10.10.0.0/16   VLAN 20: 10.20.0.0/16   VRF A, L3VNI 1000
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
| host1 | host | 10.10.0.10/16, gw 10.10.0.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.10.0.20/16, gw 10.10.0.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.20.0.30/16, gw 10.20.0.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.20.0.40/16, gw 10.20.0.1, 00:dd:dd:dd:dd:dd |

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

- **vni-everywhere** *(default)* - VLAN 10 and 20 configured on all leaves
- **vni-where-needed** - leaf1/leaf2 only VLAN 10, leaf3/leaf4 only VLAN 20

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\29-overlay-asic-limits   # default variant: vni-everywhere
python tools\gns3_lab.py push labs\29-overlay-asic-limits --variant vni-where-needed   # switch variant in place
python tools\gns3_lab.py check labs\29-overlay-asic-limits
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/vni-everywhere/` (see the top-level README).

## What you will learn

* The tables an EVPN leaf fills and where to look at them on Linux:

| ASIC table | Linux equivalent | count it with |
|---|---|---|
| MAC (L2 FDB) | bridge FDB | `bridge fdb show br br0 \| wc -l` / `vtysh -c 'show evpn vni'` (#MACs) |
| host routes (/32, /128) | VRF routing table | `ip route show vrf A \| grep -vc /` (host routes are printed without /32) |
| ARP/ND (adjacencies) | neighbor table | `ip neigh show \| wc -l` / `vtysh -c 'show evpn arp-cache vni all'` |
| tunnel endpoints | VTEP list | `vtysh -c 'show evpn vni detail' \| grep -c 'Remote VTEP'` |
| BGP state (CPU, not ASIC) | spine RIB | `vtysh -c 'show bgp l2vpn evpn summary'` on spine1 |

* A leaf only needs MAC state for the VNIs it has. With symmetric IRB, it still gets **host routes for every
  endpoint in the VRF** (type-2 with the L3VNI RT) - which is why labs 31/32 talk about limiting host routes.

## Step by step

```bash
# host1: 200 fake endpoints in VLAN 10
mac-flood 200 eth1 10.10
# compare leaf2 (has VLAN 10) and leaf3 (VLAN 20 only in vni-where-needed)
vtysh -c 'show evpn vni'
bridge fdb show br br0 | wc -l
ip route show vrf A | wc -l
# spine1
vtysh -c 'show bgp l2vpn evpn summary'           # PfxRcd grows on the RR regardless
```

Push the other variant and repeat. Fill in a table: MACs / host routes per leaf for each design. Then
`mac-flood clean`.

## Discussion (video)

* Leaf ASICs (Trident/Tomahawk/Jericho class) differ by 10-100x in host table size. Spines in EVPN are
  usually *not* VTEPs, so they need only underlay routes - any ASIC works.
* Border/service leaves are where table pressure concentrates (all VRFs, external routes).
* Linux has no hard table limit, but each entry costs memory and, more importantly, control-plane churn - try
  `mac-flood 1000` and watch `top` on the leaves (zebra/bgpd CPU).

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant vni-everywhere*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.0.40` | ` 0% packet loss` |
| host1 | `ip -o link show type macvlan \| wc -l \| grep -q 50 \|\| mac-flood 50 eth1 10.10 >/dev/null; ip -o link show type macvlan \| wc -l` | `^50` |
| leaf2 | `vtysh -c 'show evpn vni 10010'` | `Number of MACs \(local and remote\) known for this VNI: (5[0-9]\|[6-9][0-9])` |
| leaf3 | `bridge fdb show dev vxlan10010 \| grep -c '^02:'` | `^(4[0-9]\|5[0-9])` |

*variant vni-where-needed*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.0.40` | ` 0% packet loss` |
| host1 | `ip -o link show type macvlan \| wc -l \| grep -q 50 \|\| mac-flood 50 eth1 10.10 >/dev/null; ip -o link show type macvlan \| wc -l` | `^50` |
| leaf2 | `vtysh -c 'show evpn vni 10010'` | `Number of MACs \(local and remote\) known for this VNI: (5[0-9]\|[6-9][0-9])` |
| leaf3 | `ip link show vxlan10010` | `does not exist` |
| leaf3 | `ip route show vrf A \| grep -cE '^10\.10\.1[0-9]{2}\.'` | `^(4[0-9]\|5[0-9])` |

