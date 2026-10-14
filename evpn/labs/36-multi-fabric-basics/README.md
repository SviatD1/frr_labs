# Lab 36 - Interconnecting multiple EVPN fabrics. Multi Domain, Inter Domain, Multi Pod, Multi Site.

**Video:** [Interconnecting multiple EVPN fabrics. Multi Domain, Inter Domain, Multi Pod, Multi Site.](https://www.youtube.com/watch?v=JMBQiF4DbNA) (29 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_multi_fabric_basics  

Two independent EVPN fabrics (own AS, own IS-IS, own route reflector) joined spine-to-spine. Only the
**bare minimum** crosses the boundary: leaf loopbacks (IPv4 unicast) and EVPN routes with their
**original next hops**, so VXLAN tunnels run end-to-end leaf-to-leaf. VLAN 10 is stretched across both
fabrics, each fabric also has a local subnet routed through VRF A.

## Topology

```
  fabric 1 (AS 65001)                       fabric 2 (AS 65002)
     spine111  eth10 ----------------- eth10  spine211           10.111.211.0/24, eBGP ipv4 + evpn
     /      \                                 /      \
 leaf101   leaf102                       leaf201    leaf202
   |       |    \                          |        |     \
host11  host12  host13                  host24   host25   host26
V10      V10    V120 10.120.120.30       V10      V10     V220 10.220.220.60
10.10.10.10 .20                          .40      .50
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine111 | spine | 111.111.111.111 fabric 1, AS 65001 |
| leaf101 | leaf | 101.101.101.101 fabric 1, AS 65001 |
| leaf102 | leaf | 102.102.102.102 fabric 1, AS 65001 |
| spine211 | spine | 211.211.211.211 fabric 2, AS 65002 |
| leaf201 | leaf | 201.201.201.201 fabric 2, AS 65002 |
| leaf202 | leaf | 202.202.202.202 fabric 2, AS 65002 |
| host11 | host | 10.10.10.10/24, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host12 | host | 10.10.10.20/24, gw 10.10.10.1, 00:bb:bb:bb:bb:bb |
| host13 | host | 10.120.120.30/24, gw 10.120.120.1, 00:cc:cc:cc:cc:cc |
| host24 | host | 10.10.10.40/24, gw 10.10.10.1, 00:dd:dd:dd:dd:dd |
| host25 | host | 10.10.10.50/24, gw 10.10.10.1, 00:ee:ee:ee:ee:ee |
| host26 | host | 10.220.220.60/24, gw 10.220.220.1, 00:ff:ff:ff:ff:ff |

### Links

| A | | B | |
|---|---|---|---|
| spine111 | eth1 | leaf101 | eth11 |
| spine111 | eth2 | leaf102 | eth11 |
| spine211 | eth1 | leaf201 | eth11 |
| spine211 | eth2 | leaf202 | eth11 |
| spine111 | eth10 | spine211 | eth10 |
| leaf101 | eth1 | host11 | eth1 |
| leaf102 | eth1 | host12 | eth1 |
| leaf102 | eth2 | host13 | eth1 |
| leaf201 | eth1 | host24 | eth1 |
| leaf202 | eth1 | host25 | eth1 |
| leaf202 | eth2 | host26 | eth1 |

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\36-multi-fabric-basics
python tools\gns3_lab.py check labs\36-multi-fabric-basics
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/connected/` (see the top-level README).

## What you will learn

* Fabric boundaries: separate IS-IS domains (`49.0001` / `49.0002`), separate ASNs, separate RRs - a failure or
  flap in one fabric stays there.
* The minimum to interconnect:
  1. **underlay**: each side's VTEP loopbacks reach the other side (eBGP IPv4 between spines, redistributed into the
     local IS-IS);
  2. **overlay**: EVPN routes exchanged over eBGP **without changing the next hop**
     (`neighbor DCI attribute-unchanged next-hop` under `address-family l2vpn evpn`), so leaf101 tunnels directly to leaf201;
  3. **matching RTs** - auto-RT is `AS:VNI`, which differs between AS 65001 and 65002, so the RTs are set by hand
     (`route-target import/export 10:10` for VNI 10010, `100:100` for VRF A).
* "Fixing the next hop" (video 19:50 / 21:16): see what happens without step 2, and without step 1.

## Step by step

```bash
# spine111
vtysh -c 'show bgp summary'                        # ipv4 unicast + l2vpn evpn with 10.111.211.2
vtysh -c 'show ip bgp'                             # 201.201.201.201/32, 202.202.202.202/32 from AS 65002
vtysh -c 'show isis database detail' | grep -A3 201  # redistributed into IS-IS for the leaves
# leaf101
vtysh -c 'show bgp l2vpn evpn route rd 201.201.201.201:2'   # next hop 201.201.201.201 (unchanged)
bridge fdb show dev vxlan10010 | grep dst
tcpdump -ni eth11 -e udp port 4789                 # outer IP 101.101.101.101 -> 201.201.201.201
```

## Break it

* Remove `neighbor DCI attribute-unchanged next-hop` on both spines (`clear bgp *`): leaves now see next hop
  10.111.211.x / spine loopback, try to build tunnels to the spine (which is not a VTEP) -> traffic dies.
* Remove `redistribute ipv4 bgp level-2` from spine111's IS-IS: EVPN routes arrive but leaf101 can't resolve
  201.201.201.201 -> routes stay invalid (`show bgp l2vpn evpn route` without `*`).
* Use the auto RTs (delete the `route-target` lines on fabric-2 leaves): control plane up, nothing imported.

## Design discussion (video)

Multi-pod vs multi-site vs multi-domain: this lab is the simplest "flat end-to-end VXLAN" interconnect. Real
multi-site designs often terminate and re-originate VXLAN at border gateways (EVPN *Interconnect*, RFC 9014) to
hide one fabric's VTEPs from the other - FRR doesn't implement re-origination, so it's left as theory here.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant connected*

| node | command | expect |
|---|---|---|
| spine111 | `vtysh -c 'show ip bgp'` | `201\.201\.201\.201/32` |
| leaf101 | `ip route show 201.201.201.201` | `201\.201\.201\.201` |
| host11 | `ping -c 3 -W 1 10.10.10.40` | ` 0% packet loss` |
| host13 | `ping -c 3 -W 1 10.220.220.60` | ` 0% packet loss` |
| leaf101 | `bridge fdb show dev vxlan10010` | `dst 201\.201\.201\.201` |

