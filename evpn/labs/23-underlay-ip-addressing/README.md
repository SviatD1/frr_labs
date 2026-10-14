# Lab 23 - Designing Underlay IP Connectivity for Data Center Networks

**Video:** [Designing Underlay IP Connectivity for Data Center Networks](https://www.youtube.com/watch?v=wvRWIa6GK4s) (38 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_underlay_ip  

Four ways to address the fabric links, same IS-IS underlay and EVPN overlay on top: **numbered IPv4**,
**unnumbered IPv4** (links borrow the loopback address), **numbered IPv6** and **IPv6 link-local only**.
Compare how much addressing you have to plan, what the routing table looks like, and what still works.

## Topology

```
 spine1                spine2
  |    \            /    |
  |      \        /      |       ipv4-numbered:   10.<leaf>.<10+spine>.0/24 per link
  |        \    /        |       ipv4-unnumbered: 1.1.1.1/32 peer 11.11.11.11/32 on the link
  |          \/          |       ipv6-numbered:   fc00:10:<leaf>:<10+spine>::/64
leaf1                 leaf2      ipv6-lla:        fe80:: only; loopbacks fc00::N/128
  |eth1                 |eth1
host1                 host2      VLAN 10 / VNI 10010 (10.10.10.0/24) in every variant
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| host1 | host | 10.10.10.10/24, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.10.10.20/24, 00:bb:bb:bb:bb:bb |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine2 | eth1 | leaf1 | eth12 |
| spine2 | eth2 | leaf2 | eth12 |
| leaf1 | eth1 | host1 | eth1 |
| leaf2 | eth1 | host2 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **ipv4-numbered** *(default)* - classic /24 (or /31) per link
- **ipv4-unnumbered** - links carry the loopback /32 with a peer address
- **ipv6-numbered** - /64 per link, IPv6 loopbacks, IPv6 VTEPs (FRR >= 10.6)
- **ipv6-lla** - link-local only, IPv6 loopbacks, IPv6 VTEPs (FRR >= 10.6)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\23-underlay-ip-addressing   # default variant: ipv4-numbered
python tools\gns3_lab.py push labs\23-underlay-ip-addressing --variant ipv4-unnumbered   # switch variant in place
python tools\gns3_lab.py check labs\23-underlay-ip-addressing
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/ipv4-numbered/` (see the top-level README).

## What you will learn

| | IPv4 numbered | IPv4 unnumbered | IPv6 numbered | IPv6 LLA |
|---|---|---|---|---|
| addresses to plan per link | 2 (a /31 or /30) | 0 | 2 (a /64 or /127) | 0 |
| Linux config | `ip addr add 10.1.11.1/24 dev eth11` | `ip addr add 1.1.1.1/32 peer 11.11.11.11/32 dev eth11` | `ip -6 addr add fc00:10:1:11::1/64` | nothing - LLA is automatic |
| traceroute shows | link IPs | loopbacks | link IPs | loopbacks (ICMPv6 from global addr) |
| VTEP / BGP | IPv4 | IPv4 | IPv6 | IPv6 |

IPv6 VTEPs (VXLAN over an IPv6 underlay) need **FRR 10.6 or newer** - the base image installs the current FRR stable release, check with `vtysh -c 'show version'`.

## Step by step

For each variant (`python tools\gns3_lab.py push labs\23-underlay-ip-addressing --variant <name>`):

```bash
# leaf1
ip -br addr ; ip route ; ip -6 route
vtysh -c 'show isis neighbor'  ; vtysh -c 'show isis route'
vtysh -c 'show bgp l2vpn evpn summary'
bridge fdb show dev vxlan10010 | grep dst       # VTEP addresses: IPv4 or IPv6
traceroute -n 2.2.2.2   (IPv4 variants)  /  traceroute -6 -n fc00::2   (IPv6 variants)
```

Things to notice:

* **Unnumbered IPv4**: the `peer` form puts a /32 host route to the neighbor's loopback on the link, so the
  IS-IS next hop (the neighbor's loopback) is directly reachable. That's exactly what the author's FRR spines do
  (`ip address 11.11.11.11 peer 1.1.1.1/32`). Arista does `ip address unnumbered Loopback0` and resolves the
  next hop with ARP on the link.
* **IPv6 LLA**: every route's next hop is `fe80::...%ethX`. Nothing to plan, nothing to conflict, and
  the loopbacks are still the only global addresses. `ping -6 fe80::<x>%eth11` works only with the interface scope.
* VXLAN over IPv6 adds 70 bytes instead of 50 - hosts here still use MTU 1450; try 1500-70 = 1430 vs 1450 with `ping -M do -s ...`.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant ipv4-numbered*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.20` | ` 0% packet loss` |
| leaf1 | `ip route show 2.2.2.2` | `nexthop via 10\.1\.11\.11` |

*variant ipv4-unnumbered*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.20` | ` 0% packet loss` |
| leaf1 | `ip route show 2.2.2.2` | `nexthop via 11\.11\.11\.11 dev eth11` |

*variant ipv6-numbered*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.20` | ` 0% packet loss` |
| leaf1 | `ip -6 route show fc00::2` | `via fc00:10:1:11::11` |

*variant ipv6-lla*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.20` | ` 0% packet loss` |
| leaf1 | `ip -6 route show fc00::2` | `via fe80::` |

