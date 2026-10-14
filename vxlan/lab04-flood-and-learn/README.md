# Lab 04 · VXLAN control plane operations (flood & learn)

**Video:** *VXLAN - Control Plane Operations* (#4)
**Status:** ✅ tested

## What "control plane" means for plain VXLAN

The original VXLAN RFC has no signalling protocol. A VTEP finds out "which MAC lives behind which VTEP" exactly like a switch does: **data-plane learning**. When a frame arrives *from* VTEP 10.0.0.12 with inner source MAC X, the VTEP records "X → 10.0.0.12". Unknown destinations and broadcasts are **flooded** to every VTEP in the VNI (here via a static head-end list; in labs 07-09 via multicast). Lab 10 replaces all of this with BGP EVPN.

## Topology

```
              [core]
         /      |      \
     vtep1    vtep2    vtep3        VNI 100 on all, learning ON, ageing 120 s
       h1       h2       h3         192.168.100.101 / .102 / .103
```

## Build

Run `nodes/<node>.sh` on core, vtep1-3, h1-h3.

## Walk through the learning process

Do these in order and look at the table after every step:

```bash
vtep1# watch -n1 'bridge fdb show dev vxlan100'
```

1. **Before any traffic**: only `00:00:00:00:00:00 dst 10.0.0.12 / 10.0.0.13 permanent` — the flood list.
2. `h1$ ping -c1 192.168.100.103`
   - h1's ARP broadcast is replicated to vtep2 *and* vtep3 (check with `tcpdump -ni eth1 udp port 4789` on core).
   - vtep2 and vtep3 **learn** "h1's MAC → 10.0.0.11". vtep2 learned it even though h2 never asked — side effect of flooding.
   - h3's unicast ARP reply goes straight to 10.0.0.11 (known MAC).
   - vtep1 learns "h3's MAC → 10.0.0.13".
3. On vtep2: `bridge fdb show dev vxlan100` — h1 is there, h3 is not (vtep2 never received anything from h3).
4. Wait 2 minutes without traffic. Learned entries age out (`ageing 120`), only the permanent flood list stays.

## Experiments

1. **Unknown unicast flooding**: on vtep1 `bridge fdb del <h3-mac> dev vxlan100` while h1 keeps pinging h3 — first packet after deletion is flooded to both VTEPs, then relearned.
2. **Static mode — no learning at all**: on all VTEPs recreate vxlan100 with `nolearning` and add per-MAC entries by hand:
   `bridge fdb append <h3-mac> dev vxlan100 dst 10.0.0.13` … 6 entries for 3 hosts. Imagine 10 000 hosts — this is what EVPN automates.
3. **Host move**: unplug h3 (in GNS3 delete the h3–vtep3 link) and plug it into vtep2:eth4 (add `ip link set eth4 master br100; ip link set eth4 up` on vtep2). How long until vtep1 sends to the right VTEP? (Until h3 talks, or until ageing.) Send a gratuitous ARP from h3: `arping -U -c1 -I eth1 192.168.100.103`.
4. **Count the flood copies** as the fabric grows: one broadcast = N−1 copies. Multicast (lab 07) turns that into one copy on the uplink.

## Break / fix

| Break it | Symptom | Explanation |
|---|---|---|
| vtep2: `bridge fdb del 00:00:00:00:00:00 dev vxlan100 dst 10.0.0.11` | h1 can reach h2 only if h2 talks first | vtep2 can't flood back to vtep1 |
| vtep1: recreate vxlan100 with `nolearning` and add no static MACs | pings still work, but tcpdump on core shows every unicast frame from vtep1 copied to *both* vtep2 and vtep3 | no learning + no control plane = every frame is "unknown unicast" |

## Questions

- What is the difference between the bridge FDB entry `master br100` and the `self` entry on vxlan100?
- Why is flood-and-learn a problem for ARP-heavy environments with VM mobility?
