# Lab 14 - Service Insertion in EVPN. VRF Sandwich

**Video:** [Service Insertion in EVPN. VRF Sandwich](https://www.youtube.com/watch?v=roktYzoyW5U) (43 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/service_insertion  

Force traffic between two tenant VRFs through a firewall: the **VRF sandwich**. A service leaf
connects VRF A to the firewall's inside and VRF B to its outside; the firewall (a Linux box running
FRR, AS 100) peers eBGP with both VRFs and re-advertises one side's routes to the other. Because both
VRFs live in AS 65000, BGP loop prevention drops the routes - fixed with **as-override**.

## Topology

```
               spine1                  spine2
      leaf1                leaf2                leaf3 (service leaf)
    e1     e2            e1     e2           eth1 (VRF A)  eth2 (VRF B)
  host1   host3        host2   host4           |               |
VRF A VLAN10 10.10.10.0/24   VRF B VLAN20 10.20.20.0/24     eth1  fw  eth2     AS 100
                                               172.16.31.0/24   172.16.32.0/24
L3VNI: A 10100, B 10200
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
| host3 | host | 10.10.10.30/24, gw 10.10.10.1, 00:cc:cc:cc:cc:cc |
| host2 | host | 10.20.20.20/24, gw 10.20.20.1, 00:bb:bb:bb:bb:bb |
| host4 | host | 10.20.20.40/24, gw 10.20.20.1, 00:dd:dd:dd:dd:dd |

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
| leaf1 | eth2 | host3 | eth1 |
| leaf2 | eth1 | host2 | eth1 |
| leaf2 | eth2 | host4 | eth1 |
| leaf3 | eth1 | fw | eth1 |
| leaf3 | eth2 | fw | eth2 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **no-as-override** - routes are dropped by AS-path loop prevention
- **as-override** *(default)* - fw uses as-override -> traffic A <-> B flows through fw

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\14-service-insertion-vrf-sandwich   # default variant: as-override
python tools\gns3_lab.py push labs\14-service-insertion-vrf-sandwich --variant no-as-override   # switch variant in place
python tools\gns3_lab.py check labs\14-service-insertion-vrf-sandwich
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/as-override/` (see the top-level README).

## What you will learn

* The VRF sandwich: tenant VRFs never import each other's routes in EVPN; the only path between them is
  `VRF A -> service leaf -> fw -> service leaf -> VRF B`.
* **eBGP loop prevention**: fw receives `10.10.10.0/24` with AS path `65000` from VRF A and sends it to VRF B
  as `100 65000`; leaf3 (AS 65000) sees its own AS and drops it. Fixes: `as-override` on the fw
  (replace 65000 with 100) or `allowas-in` on the leaves.
* FRR detail from the video: FRR eBGP *does* advertise a route back to the peer it came from (the receiver
  drops it). `neighbor X solo` stops that - it puts the neighbor in its own update-group.
* A Linux box as a stateful firewall: nftables `forward` chain with conntrack and counters.

## Step by step

Push `no-as-override` first:

```bash
# fw
vtysh -c 'show ip bgp'                                     # has both tenants' subnets
vtysh -c 'show ip bgp neighbors 172.16.32.3 advertised-routes'   # 10.10.10.0/24 is sent to VRF B...
# leaf3
vtysh -c 'show bgp vrf B ipv4 unicast'                     # ...but not accepted (AS loop)
vtysh -c 'show bgp vrf B neighbors 172.16.32.1' | grep -i 'loop\|denied'
```

Then `as-override`:

```bash
# leaf3
vtysh -c 'show bgp vrf B ipv4 unicast 10.10.10.0/24'       # AS path "100 100"
# leaf1
vtysh -c 'show bgp l2vpn evpn route type prefix'           # 10.20.20.0/24 advertised by leaf3 in VRF A
ip route show vrf A
# host1
traceroute -n 10.20.20.20                                  # ... 172.16.31.1 (fw) ...
# fw
nft list table inet fw                                     # counters climb
journalctl -k | grep FW-NEW                                # new flows logged
```

**Block something on the "firewall"**: `nft insert rule inet fw forward ip daddr 10.20.20.40 icmp type echo-request drop`
and ping host4 from host1.

## Disadvantages (video 37:00) to think about

* Every inter-VRF flow hair-pins through the service leaf and the fw - bandwidth and latency.
* One sandwich per pair of VRFs doesn't scale -> lab 15 (dedicated service VRFs) and lab 16 (PBR).
* Firewall HA: with an active/standby pair, BGP sessions to the standby must not attract traffic
  (AS-path prepend / MED from the standby, or the fw cluster's single virtual IP).

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant no-as-override*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 2 -W 1 10.20.20.20` | `100% packet loss\|Unreachable` |
| fw | `vtysh -c 'show ip bgp'` | `10\.10\.10\.0/24` |

*variant as-override*

| node | command | expect |
|---|---|---|
| leaf1 | `ip route show vrf A 10.20.20.0/24` | `10\.20\.20\.0/24` |
| host1 | `ping -c 3 -W 1 10.20.20.20` | ` 0% packet loss` |
| host1 | `traceroute -n -w 1 -q 1 10.20.20.20` | `172\.16\.3[12]\.1` |
| fw | `nft list table inet fw` | `counter packets [1-9]` |

