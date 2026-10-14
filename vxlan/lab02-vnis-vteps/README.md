# Lab 02 · VNIs, VTEPs and VXLAN architecture

**Video:** *VXLAN - VNIs, VTEPs, and VXLAN Architecture* (#2)
**Status:** ✅ tested

## Concepts you will touch

- **VTEP** — the device that encapsulates/decapsulates. Here: Linux `vxlanN` devices on vtep1-3, sourced from each VTEP's loopback.
- **VNI** — the 24-bit segment ID. Each VNI is its own broadcast domain = its own Linux bridge (`br100`, `br200`).
- **Multi-tenancy** — two tenants use the *same* subnet and even the *same* IP addresses, and never see each other.
- **Ingress (head-end) replication** — with no multicast and no control plane, each VTEP holds a static list of the other VTEPs in a VNI and unicasts a copy of every broadcast/unknown frame to each.

## Topology

```
                         [ core ] lo 10.0.0.1
                eth1/       |eth2       \eth3
          [vtep1]        [vtep2]        [vtep3]
         eth3  eth4       eth3          eth3  eth4
          h1    h2         h3            h4    h5
```

| Host | VTEP:port | VNI | IP |
|---|---|---|---|
| h1 | vtep1:eth3 | 100 (tenant A) | 192.168.10.1 |
| h2 | vtep1:eth4 | 200 (tenant B) | 192.168.10.1 ← same IP as h1 |
| h3 | vtep2:eth3 | 100 | 192.168.10.2 |
| h4 | vtep3:eth3 | 100 | 192.168.10.3 |
| h5 | vtep3:eth4 | 200 | 192.168.10.2 ← same IP as h3 |

VNI 100 lives on all three VTEPs; VNI 200 only on vtep1 and vtep3 (vtep2 doesn't even have it).

## Build

Run `nodes/<node>.sh` on core, vtep1-3, h1-h5.

## Verify

```bash
h1$ ping 192.168.10.2      # reaches h3 (VNI 100)
h2$ ping 192.168.10.2      # reaches h5 (VNI 200) — same IP, different host
h2$ ping 192.168.10.3      # FAILS: h4 is in VNI 100
h1$ ip neigh               # compare the MAC for .2 with `ip link show eth1` on h3 and on h5

vtep1# bridge fdb show dev vxlan100 | grep 00:00:00:00:00:00   # flood list: 10.0.0.12 and 10.0.0.13
vtep1# bridge fdb show dev vxlan200 | grep 00:00:00:00:00:00   # flood list: only 10.0.0.13
vtep1# ip -d link show type vxlan                               # two VTEP "interfaces", one per VNI
```

## Experiments

1. **Watch replication**: on core run `tcpdump -ni any udp port 4789` and from h1 `arping -c1 -I eth1 192.168.10.99` (a non-existent host). One broadcast from h1 becomes **two** unicast VXLAN packets leaving vtep1 (to .12 and .13). Do the same from h2 (VNI 200): only **one** copy (to .13). That's why head-end replication scales badly with many VTEPs — and why labs 07-10 exist.
2. **Read the VNI on the wire**: start a GNS3 capture on core-vtep3. Filter `vxlan.vni == 200`. Every packet from h2 carries VNI 200; that number is the only thing separating tenants.
3. **Add a tenant**: on vtep2 create VNI 200 (copy the VNI 200 block from `nodes/vtep1.sh`, attach a new host on vtep2:eth4 with 192.168.10.4) and add `10.0.0.12` to the VNI 200 flood list on vtep1 and vtep3 with `bridge fdb append 00:00:00:00:00:00 dev vxlan200 dst 10.0.0.12`.

## Break / fix

| Break it | Symptom | Fix |
|---|---|---|
| vtep3: `bridge fdb del 00:00:00:00:00:00 dev vxlan100 dst 10.0.0.11` | h4 → h1 fails *until* h1 talks first (asymmetric) | flood list must be complete on every VTEP |
| vtep1: put eth4 in `br100` instead of `br200` | h2 now sees tenant A, duplicate-IP chaos | port-to-VNI mapping is the tenant boundary |

## Questions

- Where is the "VLAN" in this lab? (There is none — the bridge *is* the segment.)
- How many flood-list entries would 50 VTEPs × 200 VNIs need?
