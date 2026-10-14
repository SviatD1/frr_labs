# Lab 16 - Service Insertion in EVPN using PBR

**Video:** [Service Insertion in EVPN using PBR](https://www.youtube.com/watch?v=VsSOVx5P3UM) (50 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/service_insertion_pbr  

Instead of a VRF sandwich, steer only *selected* flows to the firewall with **policy-based routing**
on the ingress leaf's SVI. The firewall sits in a stretched **service VLAN 999**; FRR's `pbrd`
installs Linux `ip rule`s that send 10.10.10.0/24 -> 10.20.20.0/24 to the fw instead of the normal route.

## Topology

```
             spine1                     spine2
     leaf1                 leaf2                 leaf3 (service leaf)
      e1                    e1                 e1 (VLAN 999)   e2 (VRF A, routed)
    host1                 host2                  |               |
VLAN10 10.10.10.10    VLAN20 10.20.20.20        eth1     fw     eth2
                                           10.100.100.100/24   172.16.32.1/24
all in VRF A (L3VNI 10100); VLAN 999 (VNI 10999, 10.100.100.0/24) on every leaf
VLAN 999 SVIs live in VRF SVC (no L3VNI), the tenant (hosts, L3VNI) in VRF A
pbr on leaf1 vlan10: src 10.10.10.0/24 dst 10.20.20.0/24 -> nexthop 10.100.100.100 in VRF SVC
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| fw | fw | Linux 'firewall': FRR + nftables counters |
| host1 | host | 10.10.10.10/24, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.20.20.20/24, gw 10.20.20.1, 00:bb:bb:bb:bb:bb |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine1 | eth3 | leaf3 | eth11 |
| spine2 | eth1 | leaf1 | eth12 |
| spine2 | eth2 | leaf2 | eth12 |
| spine2 | eth3 | leaf3 | eth12 |
| leaf1 | eth1 | host1 | eth1 |
| leaf2 | eth1 | host2 | eth1 |
| leaf3 | eth1 | fw | eth1 |
| leaf3 | eth2 | fw | eth2 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **one-way** - PBR on leaf1 only (asymmetric through the fw)
- **symmetric** *(default)* - PBR on leaf1 and on leaf2 for the return direction

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\16-service-insertion-pbr   # default variant: symmetric
python tools\gns3_lab.py push labs\16-service-insertion-pbr --variant one-way   # switch variant in place
python tools\gns3_lab.py check labs\16-service-insertion-pbr
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/symmetric/` (see the top-level README).

## What you will learn

* FRR **pbrd**: `pbr-map` (match src/dst, set nexthop) applied with `pbr-policy` on an interface.
  Under the hood it is plain Linux policy routing - look at `ip rule` and the extra routing table.
* Why the service VLAN's SVI sits in its **own VRF `SVC` without an L3VNI**: if vlan999 were in VRF A, the fw's
  MAC/IP type-2 route would carry A's L3VNI RT and every leaf would install a **/32 host route** for 10.100.100.100
  via the L3VNI to leaf3. The PBR next hop would resolve through it, the packet would arrive at leaf3 in VRF A and
  be routed straight to host2 - past the firewall. That's the video's "disable host-route advertisement in the
  service VNI" (38:43); on Linux/FRR the clean way is to keep the service SVI out of the tenant VRF. FRR then
  resolves the next hop via the connected 10.100.100.0/24 on vlan999 and bridges to the fw over VNI 10999.
* Asymmetric vs **symmetric PBR**: a stateful fw must see both directions.

## Step by step

```bash
# leaf1
vtysh -c 'show pbr map'                 # installed? which table?
vtysh -c 'show pbr interface'
ip rule show                            # 300: from 10.10.10.0/24 to 10.20.20.0/24 iif vlan10 lookup 10000
ip route show table 10000               # default via 10.100.100.100 dev vlan999
ip neigh show dev vlan999               # fw's MAC (from EVPN type-2)
# host1
traceroute -n 10.20.20.20               # 10.10.10.1 -> 172.16.32.1 (fw; it answers from its egress IP) -> 172.16.32.3 -> 10.20.20.1 -> host2
# fw
nft list table inet fw
```

In `one-way`, traceroute from host2 back to host1 does **not** traverse the fw - a stateful fw would see
only half of each TCP session (conntrack `INVALID`). Push `symmetric` and compare.

## Experiments

* Move `vlan999` into VRF A on all leaves (`ip link set vlan999 master A`) and point the pbr-map at
  `nexthop-vrf A`: `show pbr map detail` now resolves 10.100.100.100 via `vlan4001` (the /32), and a capture on leaf3
  shows the PBR'd packets arriving on the **L3VNI** (VNI 10100) and routed straight to host2 - fw bypassed.
* The video's bug (42:19): detach the policy (`no pbr-policy TO-FW` on vlan10) and check that `ip rule` is cleaned up.
* **Resilient hashing** (47:32): with two firewalls you would use a nexthop-group in the pbr-map
  (`nexthop-group FWS` + `set nexthop-group FWS`); lab 21 shows resilient nexthop groups on Linux.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant one-way*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.20.20` | ` 0% packet loss` |
| leaf1 | `ip rule show` | `from 10\.10\.10\.0/24 to 10\.20\.20\.0/24 iif vlan10` |
| host1 | `traceroute -n -w 1 -q 1 10.20.20.20` | `172\.16\.32\.1 ` |

*variant symmetric*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.20.20` | ` 0% packet loss` |
| leaf1 | `ip rule show` | `from 10\.10\.10\.0/24 to 10\.20\.20\.0/24 iif vlan10` |
| host1 | `traceroute -n -w 1 -q 1 10.20.20.20` | `172\.16\.32\.1 ` |
| host2 | `traceroute -n -w 1 -q 1 10.10.10.10` | `172\.16\.32\.1 ` |

