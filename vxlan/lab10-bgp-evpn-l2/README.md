# Lab 10 · Understanding the MP-BGP EVPN control plane

**Video:** *VXLAN - Understanding the MP-BGP EVPN Underlay* (#10) — despite the title, EVPN is the *overlay control plane*; the underlay stays OSPF.
**Status:** ✅ tested

## From flood & learn to a real control plane

Instead of discovering MACs by flooding, each leaf **advertises** what it knows in BGP (AFI l2vpn / SAFI evpn):

| Route type | Name | What it says | Replaces |
|---|---|---|---|
| **3** | Inclusive Multicast Ethernet Tag (IMET) | "I am a VTEP for VNI 100 at 10.0.0.11 — send me BUM" | the static flood list / multicast group |
| **2** | MAC/IP advertisement | "MAC aa:bb… (and optionally IP) lives behind 10.0.0.11 in VNI 100" | data-plane MAC learning |
| 5 | IP prefix | routed prefixes (lab 11) | — |

Every route carries a **Route Distinguisher** (makes it unique, `10.0.0.11:2`) and a **Route Target** (which VNI imports it; FRR auto-derives `65000:<VNI>`), plus the encapsulation community (`ET:8` = VXLAN).

## Topology

```
     [spine1] RR 10.0.0.1      [spine2] RR 10.0.0.2      underlay: OSPF ; overlay: iBGP AS 65000
        full mesh to all leaves (as lab 06)                 spines = route reflectors, no VNIs
     [leaf1]          [leaf2]          [leaf3]
    eth3   eth4        eth3           eth3   eth4
     h1     h4          h2             h3     h5
 VNI 100: h1 h2 h3  (192.168.100.0/24)       VNI 200: h4 h5  (192.168.200.0/24)
```

Leaf kernel config: just `brVNI` + `vxlanVNI` with **`nolearning`** and **no flood list**. FRR's `advertise-all-vni` makes zebra discover every local VNI and BGP do the rest.

## Build

Run `nodes/<node>.sh` on spine1-2, leaf1-3, h1-5.

## Verify — control plane

```bash
leaf1# vtysh -c 'show bgp l2vpn evpn summary'       # 2 RR sessions Established
leaf1# vtysh -c 'show evpn vni'                      # VNI 100: 2 remote VTEPs ; VNI 200: 1
leaf1# vtysh -c 'show bgp l2vpn evpn route type multicast'   # type-3 from 10.0.0.12 / .13
leaf1# vtysh -c 'show evpn vni 100'                  # remote VTEPs list
```

Before any host traffic you already have the **flood list** — and you never configured it:

```bash
leaf1# bridge fdb show dev vxlan100 | grep 00:00:00:00:00:00
00:00:00:00:00:00 dst 10.0.0.12 self permanent
00:00:00:00:00:00 dst 10.0.0.13 self permanent
```

## Verify — after traffic

```bash
h1$ ping -c2 192.168.100.103
leaf1# vtysh -c 'show bgp l2vpn evpn route type macip'  # [2]:[0]:[48]:[<h3-mac>]  nh 10.0.0.13  RT:65000:100
leaf1# vtysh -c 'show evpn mac vni 100'                  # local h1 on eth3, remote h2/h3 with VTEP IPs
leaf1# bridge fdb show dev vxlan100                      # remote MACs flagged "extern_learn" = installed by zebra
spine1# vtysh -c 'show bgp l2vpn evpn'                   # the RR holds everything but installs nothing
```

Note: type-2 routes here are **MAC-only** — the leaves have no IP in these bridges, so they never learn hosts' IPs. Labs 11-15 give the bridges a gateway IP and you'll see MAC+IP routes and ARP suppression.

## Experiments

1. **Withdraw**: shut h3's port (`ip link set eth3 down` on leaf3). Watch leaf1: `show bgp l2vpn evpn route type macip` — h3's route is withdrawn once leaf3's bridge entry ages/flushes (`bridge fdb flush dev eth3` on leaf3 makes it immediate).
2. **VNI without local ports**: VNI 200 isn't on leaf2. `show bgp l2vpn evpn route type multicast` on leaf2 still shows VNI 200's type-3s (the RR reflects everything), but leaf2 doesn't import them — `show evpn vni` lists only 100. That's Route-Target filtering at work.
3. **RD vs RT**: `show bgp l2vpn evpn vni 100` on leaf1 — RD `10.0.0.11:2` (router-id : internal VNI index), RT `65000:100`. Change the RT for VNI 100 on leaf3 only:
   ```
   router bgp 65000
    address-family l2vpn evpn
     vni 100
      route-target import 65000:999
      route-target export 65000:999
   ```
   leaf3 falls out of VNI 100 (`show evpn vni 100` on leaf1: 1 remote VTEP).
4. **Capture BGP**: GNS3 capture leaf1↔spine1, filter `bgp.type == 2`, decode an UPDATE with EVPN NLRI.

## Break / fix

| Break it | Symptom | Look at |
|---|---|---|
| leaf2: remove `advertise-all-vni` | leaf2 sends/receives no EVPN routes; h2 isolated | `show evpn vni` (empty), `show bgp l2vpn evpn` |
| spine1+spine2: remove `route-reflector-client` | leaves don't see each other's routes (iBGP split horizon) | `show bgp l2vpn evpn summary` PfxRcd = 0 |
| leaf3: `update-source` missing | BGP stays Active/Connect | `show bgp neighbors` |
| leaf1: `ip link set vxlan100 type vxlan learning` (recreate with learning) | works, but MACs show as learned, not `extern_learn` | always `nolearning` with EVPN |

## Questions

- Why don't the spines need `advertise-all-vni`?
- Type-3 replaces what, exactly — the multicast group or the head-end list? (FRR does ingress replication by default.)
