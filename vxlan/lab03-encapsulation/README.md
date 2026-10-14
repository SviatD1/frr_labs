# Lab 03 · Encapsulation, headers and the packet transmission process

**Video:** *VXLAN - Encapsulation, Headers, and the Packet Transmission Process* (#3)
**Status:** ✅ tested

Same wiring as lab 01, but **hosts keep MTU 1500 on purpose** so you can feel the 50-byte overhead.

## The packet, outside in

```
| outer Ethernet 14 | outer IPv4 20 | UDP 8 | VXLAN 8 | inner Ethernet 14 | inner IP ... |
                                      ^dst 4789   ^flags 0x08 + 24-bit VNI + reserved
            = 50 bytes added in front of the original frame (54 with an outer 802.1Q tag)
```

- Outer src/dst IP = the two VTEP loopbacks.
- UDP **source** port = hash of the inner flow → entropy for ECMP in the underlay (lab 06).
- UDP destination port = 4789.
- VXLAN header: I-flag set, VNI 100.

## Topology

```
 h1(1500) ── vtep1 ── core ── vtep2 ── h2(1500)
                ^ capture here (core eth1 / eth2)
```

## Build

Run `nodes/<node>.sh` on all five nodes.

## Walk the packet

1. GNS3: right-click **vtep1 ↔ core** link → *Start capture*. Also run `tcpdump -ni eth3 -e icmp` on vtep1 (inner side).
2. `h1$ ping -c1 192.168.100.102`
3. In Wireshark expand every layer and fill in this table:

| Layer | Field | Value you see |
|---|---|---|
| outer Ethernet | src / dst MAC | vtep1 eth1 / core eth1 |
| outer IP | src / dst, TTL, DF | 10.0.0.11 / 10.0.0.12 |
| UDP | src port / dst port | random-looking / 4789 |
| VXLAN | flags, VNI | 0x08, 100 |
| inner Ethernet | src / dst MAC | h1 / h2 |
| inner IP | src / dst | 192.168.100.101 / .102 |

4. Ping again with different flows (`ping`, then `iperf3`/`curl` traffic) and note the **UDP source port changes per inner flow, but is stable within one flow**.

## The MTU problem

```bash
h1$ ping -M do -s 1422 192.168.100.102   # 1422+28 = 1450  → works
h1$ ping -M do -s 1472 192.168.100.102   # 1472+28 = 1500  → fails
vtep1# ip -d link show vxlan100 | grep mtu  # vxlan100 mtu 1450 (1500 − 50)
vtep1# ip -s link show vxlan100             # TX/RX drop counters grow
```

Real-world symptom: pings and SSH work, but big transfers stall. Two fixes — try both:

- **Shrink the host MTU** (what the other labs do): `h1$ ip link set eth1 mtu 1450` (and on h2).
- **Grow the underlay MTU** (what data centres do — 9000/9216): on vtep1, core, vtep2 set `ip link set ethX mtu 1600` on every underlay link, then on the VTEPs `ip link set vxlan100 mtu 1500`. GNS3/virtio usually passes 1600-byte frames; if it doesn't on your setup, you'll see it right away with `ping -M do -s 1572` between loopbacks.

## Experiments

1. **Port 4789 vs 8472**: recreate vxlan100 on *both* VTEPs with `dstport 8472`. Wireshark no longer decodes it as VXLAN → *Decode As… UDP 8472 → VXLAN*.
2. **TTL**: the outer TTL is set by the VTEP; inner TTL is untouched by the core (count hops with `traceroute` from h1 — the core is invisible).
3. **UDP checksum**: add `udpcsum` to the vxlan link options on one side and look at the UDP checksum field.

## Questions

- Why did the VXLAN designers use UDP rather than raw IP (like GRE)?
- How big must the underlay MTU be for 9000-byte host jumbo frames?
