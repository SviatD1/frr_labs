# Lab 12 · Configuring MP-BGP EVPN for L2VNIs

**Video:** *VXLAN - Configuring MP-BGP EVPN for L2 VNIs on Cisco Nexus* (#12)
**Status:** ⚠️ FRR configs syntax-checked; the EVPN control plane is the one tested in lab 10, the VLAN-aware bridge part (as in lab 05) couldn't be run on the test kernel.

## What's new vs lab 10

The video's Nexus style: VLANs on a switch, `vlan X / vn-segment Y`, `evpn / vni Y l2 / rd auto / route-target both auto`, `suppress-arp`. Here you configure the same pieces **explicitly**:

- **VLAN-aware bridge** `br0`: VLAN 10 ↔ VNI 10010, VLAN 20 ↔ VNI 10020 (lab 05 model) — but no flood list, no learning.
- **Explicit RD and RT per VNI** instead of FRR's automatic ones.
- Trunk vs access ports toward hosts.

## NX-OS ↔ FRR

| NX-OS | FRR here |
|---|---|
| `nv overlay evpn` | `address-family l2vpn evpn` / `advertise-all-vni` |
| `router bgp 65000` / `neighbor 10.0.0.1` / `address-family l2vpn evpn` / `send-community extended` | `neighbor SPINES activate` (FRR always sends extended communities) |
| `interface nve1` / `host-reachability protocol bgp` | the `nolearning` vxlan devices + `advertise-all-vni` |
| `member vni 10010` / `ingress-replication protocol bgp` | default in FRR: type-3 driven HER |
| `evpn` / `vni 10010 l2` / `rd auto` / `route-target import/export auto` | `vni 10010` / `rd 10.0.0.11:10` / `route-target import|export 65000:10010` |
| `show bgp l2vpn evpn` / `show nve peers` / `show l2route evpn mac all` | `show bgp l2vpn evpn` / `show evpn vni detail` / `show evpn mac vni all` |

## Topology

Fabric as lab 10 (2 RR spines, 3 leaves).

| Host | Port | Mode | Addresses |
|---|---|---|---|
| h1 | leaf1:eth3 | trunk 10,20 | eth1.10 192.168.10.101, eth1.20 192.168.20.101 |
| h2 | leaf2:eth3 | access VLAN 10 | 192.168.10.102 |
| h3 | leaf3:eth3 | trunk 10,20 | eth1.10 192.168.10.103, eth1.20 192.168.20.103 |

## Build

Run `nodes/<node>.sh` on spine1-2, leaf1-3, h1-3.

## Verify

```bash
leaf1# bridge vlan show                                  # eth3: 10 20 ; vxlan10010: 10 PVID untagged ; vxlan10020: 20
leaf1# vtysh -c 'show evpn vni'                          # 10010, 10020 (VLAN-aware: zebra maps VNI<->VLAN via the bridge)
leaf1# vtysh -c 'show bgp l2vpn evpn vni 10010'          # RD 10.0.0.11:10, RT 65000:10010 (not auto)
leaf2# vtysh -c 'show evpn vni 10020'                    # configured on leaf2 too, with no VLAN 20 port: it still sends a type-3
h1$ ping 192.168.10.102 ; ping 192.168.10.103 ; ping 192.168.20.103
leaf1# vtysh -c 'show evpn mac vni all'
leaf1# bridge fdb show br br0                            # remote MACs with "vlan 10"/"vlan 20" + extern_learn
```

## Experiments

1. **RD uniqueness**: give leaf1 and leaf3 the same RD for VNI 10010 (`rd 10.0.0.1:10` on both). On spine1 `show bgp l2vpn evpn` — routes from leaf1 and leaf3 with the same RD+MAC compete; with distinct MACs it still works, but you've lost the ability to tell sources apart. Revert.
2. **RT as a filter**: on leaf2 import only `65000:10010` (it already has no VLAN 20 hosts) and remove VNI 10020 from its kernel (`ip link del vxlan10020`). `show evpn vni` on leaf1 now lists one remote VTEP for 10020.
3. **ARP suppression**: Linux needs the leaf to *know* host IPs, which it only learns through an IP on the bridge (an SVI). Add on leaf1 `ip link add link br0 name vlan10 type vlan id 10; bridge vlan add dev br0 vid 10 self; ip link set vlan10 up; ip addr add 192.168.10.251/24 dev vlan10` (and .252/.253 on leaf2/leaf3), then `bridge link set dev vxlan10010 neigh_suppress on` on all leaves. Ping around; `show evpn arp-cache vni 10010` fills, type-2s become MAC+IP, and a capture on the fabric shows ARP requests no longer flooded once the IP is known. (Lab 14 does this with real gateways.)
4. **Move to eBGP**: real designs often use eBGP underlay+overlay (leaf AS 65011/12/13, spines 65000). Explicit RTs (as here) matter then, because FRR's auto-RT uses the local AS.

## Break / fix

| Break it | Symptom |
|---|---|
| leaf3: export RT `65000:10011` for VNI 10010 | leaf1/leaf2 ignore leaf3's VLAN 10 routes; leaf3 still imports theirs → one-way |
| leaf2: put eth3 in VLAN 20 | h2 isolated (h2 is in 192.168.10.0/24) |
| leaf1: `bridge vlan del dev vxlan10020 vid 20` | VNI 10020 vanishes from `show evpn vni` on leaf1 (no VLAN = no VNI) |

## Questions

- Which is cheaper to scale: a VLAN-aware bridge with N vxlan devices, or N bridges? (Kernels ≥ 6.x also support a single vxlan device for all VNIs — "SVD" with `external vnifilter`.)
- Why does `rd auto` on Nexus look like `<router-id>:<vlan-ish number>`?
