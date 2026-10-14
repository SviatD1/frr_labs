# Lab 04 - EVPN Bridging Deep Dive: RD, RT, VNI, EVI, MAC-VRF, VLAN-Aware Bundle

**Video:** [EVPN Bridging Deep Dive: RD, RT, VNI, EVI, MAC-VRF, VLAN-Aware Bundle](https://www.youtube.com/watch?v=YRMEEhEaXgw) (1 h 15 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/bridging_deep_dive  

Route Distinguishers, Route Targets, VNIs and VLANs - which ones must match and which are only locally
significant. Variants let you break RT and VNI consistency and use different local VLANs for the same
broadcast domain; a second tenant reuses the *same MAC and IP addresses* in its own VNI to show that
EVPN keeps MAC-VRFs apart.

## Topology

```
                                spine1 (RR)
               /eth1        /eth2         \eth3        \eth4
          leaf1           leaf2            leaf3          leaf4
       eth1  eth2      eth1  eth2          eth1           eth1
       host1 host2     host3 host4         host5          host6
VLAN    10    20        10    20            30             30
VNI   10010 10020     10010 10020         10030          10030
       .10.10 .20.20   .10.30 .20.40     10.10.10.10 aa  10.10.10.20 bb   <- tenant B reuses
                                         (same MAC/IP as host1/host2!)       tenant A addresses
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| leaf4 | leaf | 4.4.4.4 |
| host1 | host | 10.10.10.10/24, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.20.20.20/24, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.10.10.30/24, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.20.20.40/24, 00:dd:dd:dd:dd:dd |
| host5 | host | 10.10.10.10/24, 00:aa:aa:aa:aa:aa |
| host6 | host | 10.10.10.20/24, 00:bb:bb:bb:bb:bb |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine1 | eth3 | leaf3 | eth11 |
| spine1 | eth4 | leaf4 | eth11 |
| leaf1 | eth1 | host1 | eth1 |
| leaf1 | eth2 | host2 | eth1 |
| leaf2 | eth1 | host3 | eth1 |
| leaf2 | eth2 | host4 | eth1 |
| leaf3 | eth1 | host5 | eth1 |
| leaf4 | eth1 | host6 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **baseline** *(default)* - manual RTs 10:10 / 20:20 / 30:30 on all leaves
- **rt-mismatch** - leaf2 uses RT 99:99 for VNI 10010
- **vni-mismatch** - leaf2 maps VLAN 10 to VNI 10011 (RT still 10:10)
- **local-vlans** - leaf2 uses VLAN 110/120 locally for VNIs 10010/10020

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\04-bridging-deep-dive   # default variant: baseline
python tools\gns3_lab.py push labs\04-bridging-deep-dive --variant rt-mismatch   # switch variant in place
python tools\gns3_lab.py check labs\04-bridging-deep-dive
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/baseline/` (see the top-level README).

## What you will learn

* **VNI** = data-plane identifier of a broadcast domain (in the VXLAN header). Must be agreed between VTEPs.
* **VLAN** = *locally significant* on each leaf (only the access port and the VNI mapping care).
* **RD** = makes routes unique in BGP (FRR default `router-id:index`). Never needs to match.
* **RT** = import/export policy - decides which MAC-VRF (EVI) a route is imported into. Must be consistent.
* **EVI / MAC-VRF** = the EVPN instance; on FRR every VNI is its own EVI (*VLAN-based service*).

Here the RTs are configured manually (`route-target import/export 10:10`) instead of FRR's auto
`65000:10010`, to make them visible and easy to break. The RD is set to `<loopback>:<vni % 1000>`.

## Step by step (baseline)

```bash
vtysh -c 'show evpn vni 10010 detail'                       # RD, import/export RTs, VTEPs
vtysh -c 'show bgp l2vpn evpn vni 10010'                    # BGP view of that EVI
vtysh -c 'show bgp l2vpn evpn route rd 2.2.2.2:10'          # everything leaf2 originated for VNI 10010
vtysh -c 'show bgp l2vpn evpn route type macip detail'      # Extended Community: RT:10:10 ET:8
```

Notice: route-type 2 NLRI = `[2]:[EthTag]:[MAClen]:[MAC]:[IPlen]:[IP]`. The **Ethernet Tag is 0** - that is
VLAN-based service. The VNI travels as the MPLS-label field of the NLRI.

**Multitenancy:** host5/host6 (VNI 10030) reuse host1/host2's MAC *and* IP. Both pairs ping fine. Look at
`vtysh -c 'show bgp l2vpn evpn route'` on spine1: the same MAC appears under different RDs, so BGP
keeps both, and RTs 10:10 vs 30:30 import them into different MAC-VRFs.

## Variants (push them one by one)

| variant | what to observe |
|---|---|
| `rt-mismatch` | leaf2 exports VNI 10010 with RT 99:99. leaf1 *receives* the routes (`show bgp l2vpn evpn route rd 2.2.2.2:10`) but does not import them: `show evpn mac vni 10010` has no host3, and leaf2 is not in leaf1's VTEP list. host1 <-> host3 breaks; VLAN 20 keeps working. |
| `vni-mismatch` | leaf2 uses VNI 10011, RT still 10:10. Control plane imports the routes (RT matches), but the data plane label differs. Capture on leaf2 eth11: frames arrive with VNI 10010 and leaf2 has no such VNI -> dropped. Lesson: RT-based import does not fix inconsistent VNIs. |
| `local-vlans` | leaf2 uses VLAN 110/120. Everything works: `bridge vlan show` on leaf2 vs leaf1 - VLAN numbers are local, VNIs are global. |

## VLAN-aware bundle (video 1:02:53)

The video shows Arista's *VLAN-aware bundle* service: one EVI (one RD/RT) carrying many VLANs,
distinguished by a non-zero **Ethernet Tag** in the routes. **FRR implements only VLAN-based service**
(one VNI = one EVI, Ethernet Tag 0), so there is no FRR equivalent to configure. What you *can* do on
FRR is give several VNIs the **same RT** - routes will then be imported into all of them, and FRR
uses the VNI label to sort them out. Try setting `route-target import/export 10:10` on VNI 10020 too
and look at what `show evpn mac vni 10020` contains. Interoperating with a VLAN-aware-bundle
peer is possible only if that peer uses the same VNI-per-VLAN mapping.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant baseline*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.30` | ` 0% packet loss` |
| host2 | `ping -c 3 -W 1 10.20.20.40` | ` 0% packet loss` |
| host5 | `ping -c 3 -W 1 10.10.10.20` | ` 0% packet loss` |
| leaf1 | `vtysh -c 'show bgp l2vpn evpn route rd 2.2.2.2:10 type macip'` | `00:cc:cc:cc:cc:cc` |
| leaf3 | `vtysh -c 'show evpn mac vni 10030'` | `00:bb:bb:bb:bb:bb\s+remote\s+4\.4\.4\.4` |

*variant rt-mismatch*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 2 -W 1 10.10.10.30` | `100% packet loss` |
| host2 | `ping -c 2 -W 1 10.20.20.40` | ` 0% packet loss` |

*variant local-vlans*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.30` | ` 0% packet loss` |
| leaf2 | `bridge vlan show dev vxlan10010` | `110 PVID` |

*variant vni-mismatch*

| node | command | expect |
|---|---|---|
| leaf1 | `vtysh -c 'show evpn mac vni 10010'` | `00:cc:cc:cc:cc:cc\s+remote` |

