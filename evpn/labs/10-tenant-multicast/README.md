# Lab 10 - Tenant Multicast in EVPN. OISM with Source Specific Multicast (SSM)

**Video:** [Tenant Multicast in EVPN. OISM with Source Specific Multicast (SSM)](https://www.youtube.com/watch?v=vi3Q1ibzB7w) (1 h 12 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/multicast_routing  

Multicast *inside* a tenant VRF, between subnets, with SSM (IGMPv3). FRR does not implement OISM's
EVPN route types 6/7/8 (SMET / IGMP join/leave sync), but you can build OISM's **data-plane model**
on Linux: every leaf has every tenant VLAN, the ingress leaf floods the source's traffic in the
*source* VNI, and each egress leaf **routes it locally** (PIM SSM in the VRF) to its own receivers -
routed copies never go back into the fabric.

## Topology

```
                          spine1 (RR)
             /eth1           |eth2           \eth3
         leaf1             leaf2              leaf3
          eth1              eth1           eth1   eth2
         host1             host2          host3   host4
       SOURCE            receiver        receiver receiver
     VLAN10 .10.10      VLAN20 .20.20   VLAN10 .10.30 VLAN20 .20.40
VLAN 10 and 20 + VRF A (L3VNI 1000) on every leaf, pimd (SSM 232/8) + IGMPv3 on the SVIs
group (10.10.10.10, 232.1.1.1)
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| host1 | host | 10.10.10.10/24, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.20.20.20/24, gw 10.20.20.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.10.10.30/24, gw 10.10.10.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.20.20.40/24, gw 10.20.20.1, 00:dd:dd:dd:dd:dd |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine1 | eth3 | leaf3 | eth11 |
| leaf1 | eth1 | host1 | eth1 |
| leaf2 | eth1 | host2 | eth1 |
| leaf3 | eth1 | host3 | eth1 |
| leaf3 | eth2 | host4 | eth1 |

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\10-tenant-multicast
python tools\gns3_lab.py check labs\10-tenant-multicast
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/default/` (see the top-level README).

## What you will learn

* SSM basics: receivers join **(S,G)** with IGMPv3; no RP, no shared tree.
* FRR `pimd` inside a VRF: `ip pim` + `ip igmp` + `ip igmp version 3` on the SVIs, kernel multicast
  routing tables per VRF (`ip mroute show table <vrf-table>` / `vtysh -c 'show ip mroute vrf A'`).
* The **OISM** idea (RFC 9625) in data-plane terms:
  1. every leaf is attached to every tenant BD (or a Supplementary BD), so the source subnet is "local" everywhere;
  2. the ingress VTEP sends traffic only in the **source** BD (bridged, here by head-end replication);
  3. egress VTEPs **route locally** from the source BD to their receivers' BDs;
  4. routed traffic is never sent back into the fabric - here that rule is one nftables line in the
     bridge `output` hook (`oifname vxlan100* ip daddr 224.0.0.0/4 drop`).
* What FRR **does not** do here: OISM signalling (SMET type-6 routes to send traffic only to VTEPs with
  receivers, IGMP sync types 7/8 for multihoming). In this lab the source BD is flooded to *all*
  VTEPs - fine for a lab, but that's the inefficiency SMET removes.

`ip pim passive` stops PIM hellos on the SVIs: all leaves share the same anycast IP on the SVI and must
not become PIM neighbors of each other over the stretched VLAN.

## Step by step

Helper tools are in the base image: `mcast-send GROUP` and `mcast-recv GROUP SOURCE` (IGMPv3 SSM join).

```bash
# host1 (source)
mcast-send 232.1.1.1 -n 0.5
# host2 / host4 (receivers in VLAN 20 on other leaves)
mcast-recv 232.1.1.1 10.10.10.10
# host3 (receiver in the source VLAN on leaf3) - pure bridging
mcast-recv 232.1.1.1 10.10.10.10
```

On the leaves:

```bash
vtysh -c 'show ip igmp vrf A groups'
vtysh -c 'show ip igmp vrf A sources'
vtysh -c 'show ip mroute vrf A'             # iif vlan10 -> oif vlan20
vtysh -c 'show ip pim vrf A upstream'
nft list table bridge oism                  # counter = routed copies we refused to flood
tcpdump -ni eth11 -e udp port 4789          # only VNI 10010 carries the stream across the fabric
```

## Experiments (match the video's chapters)

* **Sender only**: stop all receivers. Traffic still floods VNI 10010 to every leaf (no SMET pruning).
* **Receiver only**: start a receiver without a sender; check `show ip igmp vrf A sources` - state exists, no traffic.
* **Remove the OISM rule** on leaf2 (`nft delete table bridge oism`): leaf2's routed copy is flooded into
  VNI 10020 and host4 on leaf3 receives **duplicates** (`mcast-recv` shows each seq twice).
* **Mapping groups to VNIs** (video 1:06): with an underlay-multicast design each tenant BD maps to a
  provider group; here we use ingress replication, so think about how many copies leaf1 sends per packet.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant default*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 2 -W 1 10.20.20.40` | ` 0% packet loss` |
| host1 | `kill -0 $(cat /tmp/ms.pid 2>/dev/null) 2>/dev/null \|\| { setsid mcast-send 232.1.1.1 -n 0.5 >/dev/null 2>&1 & echo $! > /tmp/ms.pid; }; echo started` | `started` |
| host2 | `timeout 20 mcast-recv 232.1.1.1 10.10.10.10 -c 3` | `received 3` |
| host4 | `timeout 20 mcast-recv 232.1.1.1 10.10.10.10 -c 3` | `received 3` |
| host3 | `timeout 20 mcast-recv 232.1.1.1 10.10.10.10 -c 3` | `received 3` |
| leaf2 | `vtysh -c 'show ip mroute vrf A'` | `10\.10\.10\.10\s+232\.1\.1\.1` |

