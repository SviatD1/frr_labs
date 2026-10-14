# Lab 37 - DCI network for EVPN Multi-Fabric. MTU, BUM traffic, HA and Fault Isolation

**Video:** [DCI network for EVPN Multi-Fabric. MTU, BUM traffic, HA and Fault Isolation](https://www.youtube.com/watch?v=ulLjeL_tUts) (30 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_multi_fabric_ha  

Make the interconnect redundant: two spines per fabric, full-mesh DCI links, and loopbacks exchanged
by redistribution on all four spines. Done naively it **oscillates** (each fabric re-learns its own
loopbacks from the other side, and eBGP's distance 20 beats IS-IS's 115). Fix it with filters, tags and
administrative distance, then look at MTU and BUM across the DCI.

## Topology

```
    fabric 1 (AS 65001)                      fabric 2 (AS 65002)
spine111 eth10 ============== eth10 spine211
         eth11 ==\        /== eth10
                   \    /                    full mesh DCI, 4 x eBGP (ipv4 + evpn)
         eth10 ==/        \== eth11
spine112 eth11 ============== eth11 spine212
  |    \   /   |                |    \   /   |
leaf101  leaf102                leaf201   leaf202     same hosts/VLANs as lab 36
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine111 | spine | 111.111.111.111 fabric 1, AS 65001 |
| spine112 | spine | 112.112.112.112 fabric 1, AS 65001 |
| leaf101 | leaf | 101.101.101.101 fabric 1, AS 65001 |
| leaf102 | leaf | 102.102.102.102 fabric 1, AS 65001 |
| spine211 | spine | 211.211.211.211 fabric 2, AS 65002 |
| spine212 | spine | 212.212.212.212 fabric 2, AS 65002 |
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
| spine112 | eth1 | leaf101 | eth12 |
| spine112 | eth2 | leaf102 | eth12 |
| spine211 | eth1 | leaf201 | eth11 |
| spine211 | eth2 | leaf202 | eth11 |
| spine212 | eth1 | leaf201 | eth12 |
| spine212 | eth2 | leaf202 | eth12 |
| spine111 | eth10 | spine211 | eth10 |
| spine111 | eth11 | spine212 | eth10 |
| spine112 | eth10 | spine211 | eth11 |
| spine112 | eth11 | spine212 | eth11 |
| leaf101 | eth1 | host11 | eth1 |
| leaf102 | eth1 | host12 | eth1 |
| leaf102 | eth2 | host13 | eth1 |
| leaf201 | eth1 | host24 | eth1 |
| leaf202 | eth1 | host25 | eth1 |
| leaf202 | eth2 | host26 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **naive** - unfiltered mutual redistribution IS-IS <-> BGP on all spines
- **oscillation** - filtered + tagged, but eBGP distance 200 (Arista's default) -> oscillation
- **fixed** *(default)* - filtered + tagged, eBGP distance 20 (FRR default, set explicitly)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\37-multi-fabric-dci-ha   # default variant: fixed
python tools\gns3_lab.py push labs\37-multi-fabric-dci-ha --variant naive   # switch variant in place
python tools\gns3_lab.py check labs\37-multi-fabric-dci-ha
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/fixed/` (see the top-level README).

## What you will learn

* Redundant DCI = several redistribution points, so you must control *what* is redistributed and *which
  source wins*:
  * BGP -> IS-IS: tag the routes (`set tag 999`) so you can recognise them;
  * IS-IS -> BGP: only the fabric's own loopbacks (prefix-list `LOCAL-LOOPBACKS`), also as an outbound filter on
    the DCI sessions - otherwise a fabric can re-advertise the *other* fabric's loopbacks back to it (`naive`);
  * **administrative distance** - the root cause of the oscillation in the video. Arista's default distance for
    eBGP is **200**, worse than IS-IS (115). spine111 learns 201.201.201.201 via eBGP *and* via IS-IS (spine112
    redistributed its own eBGP copy). With eBGP at 200, spine111 picks IS-IS and stops redistributing; spine112 does
    the same with spine111's copy; both copies vanish, both fall back to eBGP, redistribute again... forever.
    Variant `oscillation` sets `distance bgp 200 200 200` to reproduce it on FRR. FRR's default is already
    `20 200 200` (eBGP 20 beats IS-IS), which is the fix (`fixed` sets it explicitly).
* **Disabling IPv4 unicast inside the DC**: leaves only run `l2vpn evpn` (`no bgp default ipv4-unicast`) - the
  underlay is IS-IS, so the DC never sees external IPv4 churn.
* **Fault isolation**: separate IS-IS domains; the DCI only carries a handful of /32s and EVPN.
* **MTU and BUM over DCI**: VXLAN +50 bytes end-to-end, ingress replication means one copy *per remote VTEP*
  crosses the DCI for every broadcast.

## Step by step

Start with `oscillation`:

```bash
# spine111
watch -n1 "vtysh -c 'show ip route 201.201.201.201' | head -4"    # flips between "bgp" and "isis"
vtysh -c 'show isis database detail' | grep -B2 -A6 201.201       # the redistributed copies come and go
# host11
ping -D -O 10.10.10.50                       # drops / jitter whenever the underlay flips
```

Then `fixed`: the route is stable, via eBGP with 2-way ECMP on each spine. Finally look at `naive`:
`vtysh -c 'show ip bgp'` on spine111 is full of fabric-1 *link* subnets and anything IS-IS knows - and with
unlucky timing a fabric can learn its own loopbacks back through the other fabric. Compare
`show ip route 101.101.101.101` on spine112 and spine211 across the variants.
Shut a DCI link (`ip link set eth10 down` on spine111) - ECMP shrinks, nothing else moves.

## MTU

```bash
# host11 (MTU 1450): fits
ping -M do -s 1422 10.10.10.50
# make the DCI path smaller than the VXLAN packet: on all four spines' DCI interfaces
ip link set eth10 mtu 1400 ; ip link set eth11 mtu 1400
ping -M do -s 1422 10.10.10.50              # silently dropped: the leaf sends 1450+50 byte VXLAN packets
                                            # with DF set, nobody tells the host -> black hole
```

Rule from the video: the DCI must carry at least host MTU + 50 (+ 4 per extra 802.1Q tag) everywhere.

## BUM

```bash
# leaf101
bridge fdb show dev vxlan10010 | grep 00:00:00:00:00:00     # 3 remote VTEPs, 2 of them across the DCI
# capture on spine111 eth10/eth11 while host11 runs: arping -c 5 -I eth1 10.10.10.99
```

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant fixed*

| node | command | expect |
|---|---|---|
| host11 | `ping -c 3 -W 1 10.10.10.50` | ` 0% packet loss` |
| host13 | `ping -c 3 -W 1 10.220.220.60` | ` 0% packet loss` |
| spine111 | `ip route show 201.201.201.201` | `nexthop via 10\.111\.211\.2[\s\S]*nexthop via 10\.111\.212\.2` |
| spine112 | `vtysh -c 'show ip route 101.101.101.101'` | `Known via \"isis\"` |

*variant oscillation*

| node | command | expect |
|---|---|---|
| spine111 | `vtysh -c 'show bgp summary'` | `10\.111\.211\.2\)?\s+4\s+65002` |

*variant naive*

| node | command | expect |
|---|---|---|
| spine111 | `vtysh -c 'show ip bgp'` | `10\.101\.111\.0/24` |

