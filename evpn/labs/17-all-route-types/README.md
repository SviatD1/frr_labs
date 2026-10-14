# Lab 17 - Explaining all BGP EVPN Route Types for Data Center

**Video:** [Explaining all BGP EVPN Route Types for Data Center](https://www.youtube.com/watch?v=9JJrcvuVYfU) (46 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/evpn_routes  

One fabric that produces **every unicast EVPN route type** so you can study them side by side:
type-1 (EAD) and type-4 (ES) from a multihomed host, type-2 (MAC and MAC/IP), type-3 (IMET), and
type-5 (IP prefix) for an isolated subnet, a silent host and an external network behind a border leaf.

## Topology

```
                 spine1 (RR)            spine2 (RR)
  leaf1      leaf2         leaf3            leaf4 (border)
   e1         e1        e1     e2             e1
    \        /          |       |              |
     host1 (bond)     host3   host4            r1  AS 65001, lo 10.100.100.100
VLAN10 10.10.10.10   VLAN10  VLAN30 (only leaf3, isolated)
                    .10.30   10.30.30.40
VRF A, L3VNI 1000 on all leaves.  leaf4 eth1 <-> r1 eth1  172.16.41.0/24 (eBGP in VRF A)
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
| r1 | ext | 10.100.100.100 |
| host1 | host | 10.10.10.10/24, 00:aa:aa:aa:aa:aa, bond 802.3ad |
| host3 | host | 10.10.10.30/24, gw 10.10.10.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.30.30.40/24, gw 10.30.30.1, 00:dd:dd:dd:dd:dd |

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
| leaf3 | eth1 | host3 | eth1 |
| leaf3 | eth2 | host4 | eth1 |
| leaf4 | eth1 | r1 | eth1 |

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\17-all-route-types
python tools\gns3_lab.py check labs\17-all-route-types
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/default/` (see the top-level README).

## What you will learn

| Type | Name | Who sends it here | Purpose |
|---|---|---|---|
| 1 | Ethernet Auto-Discovery (per-ES / per-EVI) | leaf1, leaf2 | mass withdraw, aliasing |
| 2 | MAC/IP Advertisement | every leaf with hosts | MAC learning (L2), host routes (L3, 2 labels) |
| 3 | Inclusive Multicast Ethernet Tag | every VTEP per L2VNI | BUM flood list |
| 4 | Ethernet Segment | leaf1, leaf2 | ES discovery, DF election |
| 5 | IP Prefix | all leaves (connected subnets), leaf4 (external) | subnets, silent hosts, external routes |
| 6-8 | SMET / IGMP join & leave sync | - | multicast (OISM), not implemented in FRR - see lab 10 |

## Step by step

On spine1 (the RR sees everything):

```bash
vtysh -c 'show bgp l2vpn evpn route type ead'
vtysh -c 'show bgp l2vpn evpn route type es'
vtysh -c 'show bgp l2vpn evpn route type macip'
vtysh -c 'show bgp l2vpn evpn route type multicast'
vtysh -c 'show bgp l2vpn evpn route type prefix'
vtysh -c 'show bgp l2vpn evpn route detail' | less     # attributes: RTs, Rmac, ESI, MM seq, label(s)
```

Questions to answer:

1. Which type-2 routes have **one** label and which have **two**? (MAC-only vs MAC+IP with L3VNI.)
2. Which type-5 routes have a gateway IP / ESI? (all 0 here - "interface-less" model of RFC 9136.)
3. **Silent hosts** (video 19:20): add `10.30.30.41/24` to host4 but never send traffic from it.
   From host1 ping 10.30.30.41: works only because of the type-5 10.30.30.0/24 route. Remove
   `redistribute connected` from VRF A on leaf3 -> 10.30.30.41 unreachable, 10.30.30.40 still OK (it has a type-2).
4. **Second route reflector** (video 43:05): with two RRs every leaf receives each route twice
   (`show bgp l2vpn evpn route rd 3.3.3.3:2` shows 2 paths). Why don't they loop? (CLUSTER_LIST / ORIGINATOR_ID.)
   Each spine here has a different `bgp cluster-id` - try giving both the same and compare path counts.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant default*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.30.30.40` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.100.100.100` | ` 0% packet loss` |
| spine1 | `vtysh -c 'show bgp l2vpn evpn route type ead'` | `\[1\]:` |
| spine1 | `vtysh -c 'show bgp l2vpn evpn route type es'` | `\[4\]:` |
| spine1 | `vtysh -c 'show bgp l2vpn evpn route type macip'` | `\[2\]:\[0\]:\[48\]:\[00:aa:aa:aa:aa:aa\]:\[32\]` |
| spine1 | `vtysh -c 'show bgp l2vpn evpn route type multicast'` | `\[3\]:` |
| spine1 | `vtysh -c 'show bgp l2vpn evpn route type prefix'` | `\[5\]:\[0\]:\[32\]:\[10\.100\.100\.100\]` |

