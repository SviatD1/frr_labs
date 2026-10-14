# Lab 01 · What is VXLAN?

**Video:** *VXLAN - What is VXLAN?* (telecomTech playlist, #1)
**Status:** ✅ tested (FRR 8.4.4, kernel 6.x)

## The idea in one paragraph

Two hosts sit in the same subnet (192.168.100.0/24) but are separated by a **routed** network. A plain router would never forward their broadcast/ARP between the two sides. VXLAN fixes that by putting each Ethernet frame inside a UDP/IP packet: the routed core only sees "IP packet from 10.0.0.11 to 10.0.0.12, UDP 4789", while the hosts think they share one switch. That is the overlay (the stretched L2 segment) riding on the underlay (ordinary IP routing, OSPF here).

## Topology

```
 h1 ──eth3[vtep1]eth1── eth1[ core ]eth2 ──eth1[vtep2]eth3── h2
192.168.100.101    10.1.11.0/31     10.1.12.0/31    192.168.100.102
           lo 10.0.0.11        lo 10.0.0.1        lo 10.0.0.12
          └──────────────── VXLAN VNI 100 (UDP 4789) ───────────┘
```

| Node | Role | Key config |
|---|---|---|
| core | underlay router | OSPF only, knows nothing about VXLAN |
| vtep1/vtep2 | VTEPs | OSPF, `br100` = {eth3, vxlan100}, tunnel `local` lo → `remote` other lo |
| h1/h2 | hosts | one IP, MTU 1450 |

Cabling: `topology.txt`.

## Build

```bash
# core, vtep1, vtep2, h1, h2 — on each node:
cd /root/vxlan/lab01-what-is-vxlan && ./nodes/$(hostname).sh   # or name the script explicitly
```

(If your VM hostnames differ from the node names, run `./nodes/vtep1.sh` etc. explicitly.)

## Verify — underlay first, always

```bash
vtep1# vtysh -c 'show ip ospf neighbor'      # Full with core
vtep1# ping -c2 -I 10.0.0.11 10.0.0.12        # loopback-to-loopback MUST work before any VXLAN
```

## Verify — overlay

```bash
h1$ ping 192.168.100.102                       # works across a routed core
vtep1# ip -d link show vxlan100                # vxlan id 100 remote 10.0.0.12 local 10.0.0.11 ... dstport 4789
vtep1# bridge fdb show br br100                # h1's MAC on eth3, h2's MAC behind vxlan100
core#  tcpdump -ni eth1 udp port 4789 -c 4     # outer 10.0.0.11 > 10.0.0.12.4789, inner ICMP
core#  ip route                                # no 192.168.100.0/24 anywhere: the core is overlay-unaware
```

## Experiments

1. **Prove the core is L2-blind**: on core run `tcpdump -ni eth1 arp` while h1 pings a new IP — you see no ARP on the wire, only UDP. Then `tcpdump -ni eth1 -e udp port 4789` and note outer MACs belong to vtep1/core, not h1.
2. **Kill the underlay**: `ip link set eth2 down` on core. Overlay dies instantly. Bring it back — OSPF reconverges, overlay returns. Lesson: overlay health = underlay health.
3. **VLAN vs VXLAN**: a VLAN ID is 12 bits (4094 usable); a VNI is 24 bits (~16 million). Try `ip link add vx16m type vxlan id 16777215 dstport 4789 local 10.0.0.11 remote 10.0.0.12` — accepted. `id 16777216` is rejected.

## Break / fix

| Break it | Symptom | What to look at |
|---|---|---|
| On vtep2: `ip link del vxlan100`, then re-create it with `id 101` (copy the 5 vxlan lines from `nodes/vtep2.sh`) — the VNI of an existing device can't be changed in place | ping fails, tcpdump on core still shows UDP 4789 arriving | `ip -d link` on both ends — VNIs must match |
| On vtep1: remove `lo` from OSPF in `vtysh` (`interface lo` → `no ip ospf area 0`) | ping fails, no UDP on core | `show ip route 10.0.0.11` on vtep2 — the remote VTEP must be reachable |
| Re-add vxlan100 with `dstport 8472` on one side only | UDP seen on core, dropped at receiver | port mismatch; Linux' historic default is 8472 |

## Questions

- Why do the VTEPs source the tunnel from a loopback rather than eth1?
- What would break if two VTEPs used the same loopback address?
