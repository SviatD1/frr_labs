# Lab 13 - EVPN Multihoming. Auto Discovery Routes. Fast Convergence. Aliasing.

**Video:** [EVPN Multihoming. Auto Discovery Routes. Fast Convergence. Aliasing.](https://www.youtube.com/watch?v=Q-oBiCV_EO0) (46 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/multihoming_auto_discovery  

**Type-1 Ethernet Auto-Discovery** routes: *per-ES* (used for **mass withdraw** - one route
withdrawal invalidates every MAC behind the ES) and *per-EVI* (used for **aliasing** - remote VTEPs
can load-balance to a MAC even if only one of the ES members learnt it). You will measure failover
time and compare an LACP bond with an active-backup bond on the host.

## Topology

```
         spine1                spine2
 leaf1        leaf2       leaf3        leaf4
   e1          e1          e1           e1
    \         /            |            |
     host1 (bond0)        host5        host6
ES 03:44:38:39:ff:ff:01:00:00:01, VLAN 10, 10.10.10.0/24
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
| host1 | host | 10.10.10.10/24, 00:aa:aa:aa:aa:aa, bond 802.3ad |
| host5 | host | 10.10.10.50/24, 00:ee:ee:ee:ee:ee |
| host6 | host | 10.10.10.60/24, 00:ff:ff:ff:ff:ff |

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
| leaf2 | eth1 | host1 | eth2 |
| leaf3 | eth1 | host5 | eth1 |
| leaf4 | eth1 | host6 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **lacp** *(default)* - all-active ES, LACP bond on host1
- **host-active-backup** - same ES config, but host1 uses an active-backup bond (no LACP)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\13-multihoming-ad-routes   # default variant: lacp
python tools\gns3_lab.py push labs\13-multihoming-ad-routes --variant host-active-backup   # switch variant in place
python tools\gns3_lab.py check labs\13-multihoming-ad-routes
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/lacp/` (see the top-level README).

## What you will learn

* EAD **per-ES** route `[1]:[4294967295]:[ESI]...` (Ethernet Tag MAX-ET) - one per ES per VTEP. Withdrawn when the
  ES goes down -> remote VTEPs immediately remove that VTEP from **all** MACs on the ES (*fast convergence /
  mass withdraw*), without waiting for hundreds of type-2 withdrawals.
* EAD **per-EVI** route `[1]:[0]:[ESI]...` (Ethernet Tag 0) - one per ES per VNI. Lets a remote VTEP send to
  *any* VTEP that has the ES in this VNI -> **aliasing**, plus a backup path.
* On Linux, FRR programs remote ES MACs as `bridge fdb ... nhid N` pointing at an `ip nexthop` **group**,
  so a single nexthop-group update moves all MACs.

## Step by step

```bash
# leaf3
vtysh -c 'show bgp l2vpn evpn route type ead'
vtysh -c 'show evpn es detail'                # VTEP list per ES
bridge fdb show dev vxlan10010 | grep aa:aa  # ... nhid 2xx
ip nexthop show                               # id 2xx group <leaf1-nh>/<leaf2-nh> fdb
```

**Aliasing**: make host1 talk through one link only (`ip link set eth2 down` on host1, then
`ip neigh flush all; ping 10.10.10.50`). Only leaf1 learns 00:aa..., but leaf3 still has the
ES nexthop group with *both* leaf1 and leaf2 - thanks to leaf2's per-EVI EAD route.

**Fast convergence**: run `lab-ping 10.10.10.10` on host5, then on leaf1 `ip link set eth1 down`.
Count lost packets. Capture BGP on leaf1's uplinks during the failure (`tcpdump -ni eth11 -w /tmp/bgp.pcap tcp port 179`)
and look for a single EAD-per-ES withdrawal. Compare with `evpn mh` features disabled on leaf3:
`conf t` -> `router bgp 65000` -> `address-family l2vpn evpn` -> `disable-ead-evi-rx` (aliasing off).

## Variant `host-active-backup` - the single-active problem

FRR implements **all-active** multihoming only (no single-active / port-active redundancy mode).
In this variant host1 uses an active-backup bond and the leaves don't run LACP, so **both** leaves
consider the ES up. leaf3 aliases traffic to leaf2 as well - and host1's *backup* slave silently
drops frames arriving on it. Watch `lab-ping` from host5 and capture on host1 eth2: some flows vanish.
Lessons:

* single-active (DF-only forwarding) exists in the RFC precisely for hosts that can't do LACP;
* with FRR, make sure the non-active link is really down (LACP, or `ip link set down` on the standby).

The video also shows DF election in **VLAN-aware bundle** mode; FRR only does VLAN-based (see lab 04).

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant lacp*

| node | command | expect |
|---|---|---|
| host5 | `ping -c 3 -W 1 10.10.10.10` | ` 0% packet loss` |
| leaf3 | `vtysh -c 'show bgp l2vpn evpn route type ead'` | `\[1\]:\[0\]:\[03:44:38:39:ff:ff:01:00:00:01\]:\[128\]:\[0\.0\.0\.0\]\|\[1\]:\[4294967295\]` |
| leaf3 | `bridge fdb show dev vxlan10010` | `00:aa:aa:aa:aa:aa .*nhid \d+` |
| leaf3 | `ip nexthop show` | `group \d+/\d+` |

*variant host-active-backup*

| node | command | expect |
|---|---|---|
| host5 | `ping -c 3 -W 1 10.10.10.10` | ` 0% packet loss` |

