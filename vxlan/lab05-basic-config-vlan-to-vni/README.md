# Lab 05 · Basic VXLAN configuration (the Nexus config, done on Linux)

**Video:** *VXLAN - Basic Configuration on Cisco Nexus Switches* (#5)
**Status:** ⚠️ scripts and FRR syntax-checked; not run end-to-end (the test kernel lacks VLAN filtering). Uses only standard iproute2 commands.

The video builds a static VXLAN on Nexus: OSPF underlay, loopback NVE source, VLAN → VNI mapping, static ingress-replication peers. Here is the same thing on Linux, with a **VLAN-aware bridge** so it really looks like a switch.

## Nexus ↔ Linux/FRR translation

| NX-OS | This lab |
|---|---|
| `feature ospf` / `router ospf UNDERLAY` | FRR `router ospf` |
| `interface loopback0` / `ip address 10.0.0.11/32` | `ip addr add 10.0.0.11/32 dev lo` |
| `feature nv overlay` + `feature vn-segment-vlan-based` | kernel `vxlan` + `bridge` modules |
| `vlan 10` / `vn-segment 10010` | `bridge vlan add dev vxlan10010 vid 10 pvid untagged` |
| `interface nve1` / `source-interface loopback0` | `ip link add vxlan10010 type vxlan id 10010 local 10.0.0.11` (one device per VNI) |
| `member vni 10010` / `ingress-replication protocol static` / `peer-ip 10.0.0.12` | `bridge fdb append 00:00:00:00:00:00 dev vxlan10010 dst 10.0.0.12` |
| `switchport mode trunk` / `allowed vlan 10,20` | `bridge vlan add dev eth3 vid 10` and `vid 20` |
| `show nve peers` / `show nve vni` | `bridge fdb show dev vxlan10010` / `ip -d link show type vxlan` |
| `show mac address-table` | `bridge fdb show br br0` |

## Topology

```
                 [spine1]  10.0.0.1   (OSPF only)
                 eth1  eth2
            [leaf1]      [leaf2]
             eth3         eth3        802.1Q trunks, VLAN 10 + 20
              h1           h2
   eth1.10 192.168.10.101    eth1.10 192.168.10.102
   eth1.20 192.168.20.101    eth1.20 192.168.20.102
```

VLAN 10 ↔ VNI 10010, VLAN 20 ↔ VNI 10020. The hosts use 802.1Q sub-interfaces so a single host stands in for "two servers in two VLANs".

## Build

Run `nodes/<node>.sh` on spine1, leaf1, leaf2, h1, h2.

## Verify

```bash
leaf1# bridge vlan show                         # eth3: 10, 20 ; vxlan10010: 10 PVID untagged ; vxlan10020: 20 PVID untagged
leaf1# ip -d link show vxlan10010               # id 10010 local 10.0.0.11 dstport 4789
leaf1# bridge fdb show dev vxlan10010           # 00:00:..:00 dst 10.0.0.12 (static peer)
h1$ ping 192.168.10.102                         # VLAN 10 across the fabric
h1$ ping 192.168.20.102                         # VLAN 20
leaf1# bridge fdb show br br0 | grep vlan       # MACs learned per VLAN
spine1# tcpdump -ni eth1 udp port 4789          # VNIs 10010 / 10020; inner frames are UNTAGGED
```

Key insight: the 802.1Q tag is **removed** at the ingress leaf and the VLAN is carried as the VNI. At the egress leaf the VNI is mapped back to a (possibly different!) local VLAN.

## Experiments

1. **VLANs are locally significant**: on leaf2 only, map VNI 10010 to **VLAN 110** instead of 10 (`bridge vlan del dev vxlan10010 vid 10; bridge vlan add dev vxlan10010 vid 110 pvid untagged`; change eth3 to carry 110; on h2 rename the sub-interface to VLAN 110). h1 (VLAN 10) and h2 (VLAN 110) still talk — they share VNI 10010.
2. **Access port**: change leaf2 eth3 to `bridge vlan add dev eth3 vid 10 pvid untagged` and give h2 a plain untagged IP in 192.168.10.0/24.
3. Compare with lab 02's "one bridge per VNI" model. Which one scales better to 1 000 VLANs?

## Break / fix

| Break it | Symptom |
|---|---|
| leaf1: `bridge vlan del dev eth3 vid 20` | VLAN 20 dead, VLAN 10 fine — "VLAN not allowed on trunk" |
| leaf2: map vxlan10020 to vid 10 too | two VNIs into one VLAN → loop / duplicate traffic; one VNI per VLAN per switch |
| leaf2: forget the static peer for 10020 | h1→h2 on VLAN 20 fails until h2 speaks first |

## Questions

- What does the Nexus `nve1` interface correspond to in this Linux design?
- Why does each VTEP need the *other* VTEP in its peer list, but never itself?
