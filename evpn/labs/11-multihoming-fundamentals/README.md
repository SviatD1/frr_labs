# Lab 11 - EVPN Multihoming Fundamentals

**Video:** [EVPN Multihoming Fundamentals](https://www.youtube.com/watch?v=PvIDqq3bwRw) (41 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/multihoming_fundamentals  

Active/active dual-homing of a server to two leaves **without MLAG**: the server runs an ordinary
LACP bond, both leaves present the same LACP system-id and the same **Ethernet Segment (ES)** in EVPN.
FRR's EVPN-MH (zebra `evpn mh ...`) signals the ES and load-balances towards it from remote leaves.

## Topology

```
              spine1                    spine2
       /    /      \    \         /    /     \
    leaf1        leaf2          leaf3          leaf4
   e1   e2      e1   e2           e1
    \    |     /     |            |
     \ host2  /    host3         host5
      \  ___ /
       host1  bond0 (LACP) = ES 03:44:38:39:ff:ff:01:00:00:01
everything in VLAN 10 / VNI 10010, 10.10.10.0/24
host1 .10 (aa)  host2 .20 orphan on leaf1   host3 .30 orphan on leaf2   host5 .50 on leaf3
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
| host2 | host | 10.10.10.20/24, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.10.10.30/24, 00:cc:cc:cc:cc:cc |
| host5 | host | 10.10.10.50/24, 00:ee:ee:ee:ee:ee |

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
| leaf1 | eth2 | host2 | eth1 |
| leaf2 | eth2 | host3 | eth1 |
| leaf3 | eth1 | host5 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **evpn-mh** *(default)* - LACP bond on host1, ES on leaf1+leaf2
- **no-mh** - host1 still runs LACP, but the leaves have plain access ports (what goes wrong?)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\11-multihoming-fundamentals   # default variant: evpn-mh
python tools\gns3_lab.py push labs\11-multihoming-fundamentals --variant no-mh   # switch variant in place
python tools\gns3_lab.py check labs\11-multihoming-fundamentals
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/evpn-mh/` (see the top-level README).

## What you will learn

* Linux **bonding** in 802.3ad (LACP) mode on both sides: on the host (`bond0`) and on each leaf (`bond1`).
* The trick that makes two independent leaves look like one LACP partner: the same
  `ad_actor_system 44:38:39:ff:ff:01` on both leaves' bonds (Arista: `lacp system-id`).
* FRR EVPN multihoming:
  ```text
  interface bond1
   evpn mh es-id 1                     <- local discriminator
   evpn mh es-sys-mac 44:38:39:ff:ff:01 -> ESI type 3 = 03:44:38:39:ff:ff:01:00:00:01
  interface eth11 / eth12
   evpn mh uplink                      <- if all uplinks fail, the ES is protodown'ed
  evpn mh startup-delay 10             <- default is 180 s of protodown after boot!
  ```

## Step by step

```bash
# host1
cat /proc/net/bonding/bond0      # both slaves in the same aggregator, partner = 44:38:39:ff:ff:01
# leaf1 / leaf2
cat /proc/net/bonding/bond1
vtysh -c 'show evpn es'           # ESI, Type L (local) R (remote) -> LR on leaf1/leaf2, R on leaf3
vtysh -c 'show evpn es detail'    # VTEPs in the ES, DF status (lab 12)
vtysh -c 'show evpn mac vni 10010'
# leaf3
vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa'    # remote ES, not a single VTEP
bridge fdb show dev vxlan10010 | grep aa:aa                 # ... nhid N  -> a nexthop group
ip nexthop show                                             # group N = 1.1.1.1 + 2.2.2.2
```

**Load balancing from leaf3**: `ip nexthop show` shows the group used for host1's MAC. Send many
flows from host5 to host1 (e.g. `for p in $(seq 5000 5100); do echo x | nc -u -w0 10.10.10.10 $p; done`)
while running `tcpdump -ni eth11 udp port 4789` on leaf1 and leaf2: both receive some of the flows.
The video uses Scapy for the same test; Scapy is installed in the base image (`python3 -m scapy`).

**Orphan ports**: host2 hangs off leaf1 only. Shut leaf1's link to host1 (`ip link set eth1 down` on leaf1)
and ping host1 from host2 - traffic now goes leaf1 -> VXLAN -> leaf2 -> host1.

## Variant `no-mh` - "LAG only on the endpoint"

The leaves don't speak LACP. On host1 `cat /proc/net/bonding/bond0` shows partner MAC 00:00:00:00:00:00
and only one slave in the active aggregator - the bond falls back to a single link. Now replace the host
bond with a static `balance-xor` bond (`ip link del bond0` and recreate with `mode balance-xor`):
both links are used, leaf1 and leaf2 both learn 00:aa:.. and advertise it -> **MAC flapping** between the
two VTEPs (`vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa detail'` - watch the sequence number grow).
That's exactly why you need either MLAG or EVPN-MH.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant evpn-mh*

| node | command | expect |
|---|---|---|
| host1 | `cat /proc/net/bonding/bond0` | `Number of ports: 2` |
| leaf1 | `vtysh -c 'show evpn es'` | `03:44:38:39:ff:ff:01:00:00:01\s+LR` |
| leaf3 | `vtysh -c 'show evpn es'` | `03:44:38:39:ff:ff:01:00:00:01\s+R\s` |
| host5 | `ping -c 3 -W 1 10.10.10.10` | ` 0% packet loss` |
| host2 | `ping -c 3 -W 1 10.10.10.10` | ` 0% packet loss` |
| host3 | `ping -c 3 -W 1 10.10.10.10` | ` 0% packet loss` |
| leaf3 | `vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa'` | `03:44:38:39:ff:ff:01:00:00:01` |

*variant no-mh*

| node | command | expect |
|---|---|---|
| host1 | `cat /proc/net/bonding/bond0` | `Partner Mac Address: 00:00:00:00:00:00` |

