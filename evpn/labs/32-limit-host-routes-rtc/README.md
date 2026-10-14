# Lab 32 - Limiting host route advertisement in EVPN. BGP Route Target Constraint

**Video:** [Limiting host route advertisement in EVPN. BGP Route Target Constraint](https://www.youtube.com/watch?v=lhVBoaH4Kxo) (43 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_overlay_rtconstraint  

Three ways to keep EVPN state where it is needed: stop host routes at the **source**, **filter** them on
the route reflector, and **Route Target Constraint** (RFC 4684) so the RR only sends a leaf the routes
whose RTs it imports. FRR doesn't implement RTC, so you'll build its effect with per-leaf outbound
filters on the RR and see exactly what RTC would have automated.

## Topology

```
          spine1 (RR)              spine2 (RR)
     leaf1        leaf2        leaf3          leaf4
     e1  e2      e1  e2         e1             e1
   host1 host2 host3 host4     host5          host6
    V10  V20   V10   V20       V30            V30
VNIs 10010/10020 only on leaf1+leaf2, 10030 only on leaf3+leaf4, VRF A (L3VNI 1000) everywhere
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
| host2 | host | 10.20.20.20/24, gw 10.20.20.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.10.10.30/24, gw 10.10.10.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.20.20.40/24, gw 10.20.20.1, 00:dd:dd:dd:dd:dd |
| host5 | host | 10.30.30.50/24, gw 10.30.30.1, 00:ee:ee:ee:ee:ee |
| host6 | host | 10.30.30.60/24, gw 10.30.30.1, 00:ff:ff:ff:ff:ff |

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
| leaf1 | eth2 | host2 | eth1 |
| leaf2 | eth1 | host3 | eth1 |
| leaf2 | eth2 | host4 | eth1 |
| leaf3 | eth1 | host5 | eth1 |
| leaf4 | eth1 | host6 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **default** *(default)* - everything everywhere
- **no-host-routes-at-source** - leaves strip the L3VNI RT from their own type-2 routes (outbound)
- **rr-filter-rtc** - spines send each leaf only the L2VNIs it has (manual RT-Constraint)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\32-limit-host-routes-rtc   # default variant: default
python tools\gns3_lab.py push labs\32-limit-host-routes-rtc --variant no-host-routes-at-source   # switch variant in place
python tools\gns3_lab.py check labs\32-limit-host-routes-rtc
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/default/` (see the top-level README).

## What you will learn

* **Stop at the source** (outbound route-map on the originating leaf, deletes the L3VNI RT from type-2): nobody
  gets /32s for this leaf's hosts.
* **Filter on the RR**: per-peer-group outbound policies that match on RT (`match extcommunity`).
* **RT Constraint (RFC 4684)**: leaves send `rtfilter` NLRIs ("I import RTs X, Y"); the RR sends each leaf only
  matching routes - dynamic, no per-rack config. *FRR does not support the RTC address family* (there is no
  `address-family ipv4 rtfilter`), Arista/Juniper/Nokia do. Variant `rr-filter-rtc` is the static equivalent.
* Note: a leaf **without** RTC/filters still receives everything; it just doesn't import routes whose RTs it
  doesn't have. The cost is BGP memory/CPU on the leaf and churn - not forwarding state.

## Step by step

```bash
# leaf3 (has only VNI 10030)
vtysh -c 'show bgp l2vpn evpn summary'                  # PfxRcd: compare across variants
vtysh -c 'show bgp l2vpn evpn route type macip' | grep -c '\[2\]'
ip route show vrf A | grep -vc /                         # number of host routes
# spine1
vtysh -c 'show bgp l2vpn evpn neighbors 3.3.3.3 advertised-routes' | tail -3
vtysh -c 'show route-map'                                # rr-filter-rtc hit counters
```

Fill a table: received EVPN routes / VRF host routes on leaf3 for each variant.

Questions:

1. In `rr-filter-rtc`, leaf3 still reaches 10.10.10.10 - how? (type-5 10.10.10.0/24 from leaf1/leaf2 carries only
   the L3VNI RT and is not filtered.)
2. Why must the RR filter on RTs and not on VNI numbers? (`match evpn vni` exists in FRR - try it - but RTs are
   what import is based on.)
3. What breaks if leaf3 gets VLAN 10 later and you forget to update the spines' route-maps? That's the operational
   argument for real RTC.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant default*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.30.30.50` | ` 0% packet loss` |
| host5 | `ping -c 3 -W 1 10.30.30.60` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.20.20.40` | ` 0% packet loss` |
| leaf3 | `vtysh -c 'show bgp l2vpn evpn route type macip'` | `00:aa:aa:aa:aa:aa` |

*variant no-host-routes-at-source*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.30.30.50` | ` 0% packet loss` |
| host5 | `ping -c 3 -W 1 10.30.30.60` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.20.20.40` | ` 0% packet loss` |
| leaf3 | `ip route show vrf A 10.10.10.10` | `^$` |

*variant rr-filter-rtc*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.30.30.50` | ` 0% packet loss` |
| host5 | `ping -c 3 -W 1 10.30.30.60` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.20.20.40` | ` 0% packet loss` |
| leaf3 | `vtysh -c 'show bgp l2vpn evpn route type macip'` | `00:ee:ee:ee:ee:ee\|00:ff:ff:ff:ff:ff` |
| leaf3 | `vtysh -c 'show bgp l2vpn evpn route type macip' \| grep -c 00:aa:aa:aa:aa:aa` | `^0` |

