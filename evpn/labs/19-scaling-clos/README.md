# Lab 19 - Scaling Clos fabrics in Data Center

**Video:** [Scaling Clos fabrics in Data Center](https://www.youtube.com/watch?v=fmRJkXP-ZZ4) (26 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  

When one spine layer runs out of ports you add a stage: a **5-stage Clos** of pods, each pod a 3-stage
leaf-spine, interconnected by **super-spines**. This lab builds two pods plus a super-spine layer, runs
one EVPN domain over it (VLAN 10 stretched across pods) and recreates the **transit leaf** problem of a
3-stage fabric with a failed link.

## Topology

```
      super1 (21.21.21.21)        super2 (22.22.22.22)    <- EVPN route reflectors
     /   |    |    \             /   |    |    \
spine1 spine2      spine3 spine4                         (each spine eth10->super1, eth11->super2)
 |  \  /  |        |  \  /  |
 |   \/   |        |   \/   |
leaf1   leaf2     leaf3   leaf4
  |       |         |       |
host1   host2     host3   host4       VLAN 10 / VNI 10010, 10.10.10.0/24
------ pod 1 ------  ------ pod 2 ------
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| super1 | super | 21.21.21.21 |
| super2 | super | 22.22.22.22 |
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| spine3 | spine | 13.13.13.13 |
| spine4 | spine | 14.14.14.14 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| leaf4 | leaf | 4.4.4.4 |
| host1 | host | 10.10.10.10/24, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.10.10.20/24, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.10.10.30/24, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.10.10.40/24, 00:dd:dd:dd:dd:dd |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine2 | eth1 | leaf1 | eth12 |
| spine1 | eth2 | leaf2 | eth11 |
| spine2 | eth2 | leaf2 | eth12 |
| spine3 | eth1 | leaf3 | eth11 |
| spine4 | eth1 | leaf3 | eth12 |
| spine3 | eth2 | leaf4 | eth11 |
| spine4 | eth2 | leaf4 | eth12 |
| super1 | eth1 | spine1 | eth10 |
| super2 | eth1 | spine1 | eth11 |
| super1 | eth2 | spine2 | eth10 |
| super2 | eth2 | spine2 | eth11 |
| super1 | eth3 | spine3 | eth10 |
| super2 | eth3 | spine3 | eth11 |
| super1 | eth4 | spine4 | eth10 |
| super2 | eth4 | spine4 | eth11 |
| leaf1 | eth1 | host1 | eth1 |
| leaf2 | eth1 | host2 | eth1 |
| leaf3 | eth1 | host3 | eth1 |
| leaf4 | eth1 | host4 | eth1 |

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\19-scaling-clos
python tools\gns3_lab.py check labs\19-scaling-clos
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/default/` (see the top-level README).

## What you will learn

* 5-stage Clos = leaf -> spine -> **super-spine** -> spine -> leaf. Paths between pods: 2 (spines) x 2
  (super-spines) = 4 equal-cost paths per destination; check them with `ip route show 3.3.3.3` on leaf1
  and on spine1.
* Where to put the EVPN route reflectors in a multi-stage fabric (here: super-spines, a single EVPN domain).
* The **transit leaf** problem of 3-stage fabrics, and why a fabric needs *at least* 2 spines + careful failure analysis.

## Step by step

```bash
# leaf1
vtysh -c 'show isis topology'           # hop counts across pods
ip route show 3.3.3.3                   # 2-way ECMP inside the pod
# spine1
ip route show 3.3.3.3                   # 2-way ECMP via super1 / super2
# host1
traceroute -n 10.10.10.40               # it's L2 for the host - trace the VXLAN path on the leaves instead:
# leaf1 (while host1 pings host4)
tcpdump -ni eth11 udp port 4789 -c 5 ; tcpdump -ni eth12 udp port 4789 -c 5
```

**Transit leaf**: in pod 1 shut the spine1<->leaf1 link (`ip link set eth11 down` on leaf1). How does
spine1 now reach leaf1's loopback? `vtysh -c 'show ip route 1.1.1.1'` on spine1 ->
via super-spine -> spine2 -> leaf1 (5-stage saves you here). In a plain 3-stage fabric the only way
back would be spine1 -> leaf2 -> spine2 -> leaf1 - a **leaf becomes transit**, carrying traffic its
uplinks were never sized for. To see that version, also shut spine1's super-spine links
(`ip link set eth10 down; ip link set eth11 down` on spine1) and look again.

## Scaling notes from the video

* Fixed-form (single ASIC) switches: radix R ports. 3-stage max leaves = R (spine ports),
  max spines = leaf uplinks. 5-stage multiplies by the super-spine radix. Lab 20 has a calculator.
* Modular chassis are internally a Clos themselves (line cards = leaves, fabric modules = spines).
* "Single SKU" designs use one switch model for every role - simpler sparing, predictable limits.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant default*

| node | command | expect |
|---|---|---|
| leaf1 | `ip route show 3.3.3.3` | `nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12` |
| spine1 | `ip route show 3.3.3.3` | `nexthop via 10\.21\.1\.21[\s\S]*nexthop via 10\.22\.1\.22` |
| host1 | `ping -c 3 -W 1 10.10.10.40` | ` 0% packet loss` |
| leaf1 | `vtysh -c 'show bgp l2vpn evpn summary'` | `21\.21\.21\.21\)?\s+4\s+65000[\s\S]*22\.22\.22\.22\)?\s+4\s+65000` |

