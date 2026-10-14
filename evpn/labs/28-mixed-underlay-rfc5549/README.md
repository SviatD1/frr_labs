# Lab 28 - Mixed IPv4+IPv6 Underlay for EVPN. RFCs 5549 and 8950

**Video:** [Mixed IPv4+IPv6 Underlay for EVPN. RFCs 5549 and 8950](https://www.youtube.com/watch?v=M__PhG_GMx8) (23 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_underlay_mixed  

IPv4 loopbacks and VTEPs, but **no IPv4 on any fabric link**: eBGP unnumbered sessions run over IPv6
link-local addresses and carry IPv4 prefixes with **IPv6 next hops** (RFC 5549, updated by RFC 8950).
The Linux kernel forwards IPv4 packets to an IPv6 next hop natively (`via inet6 fe80::...`). A second
variant goes all the way: pure IPv6 core with IPv6 VTEPs.

## Topology

```
    spine1 AS 65100            spine2 AS 65100
      |  \                   /   |
    leaf1  AS 65001        leaf2  AS 65002      links: IPv6 link-local only
      |                      |
    host1                  host2                VLAN 10 / VNI 10010
v4-loopbacks: lo 1.1.1.1 / 2.2.2.2 (IPv4 VTEPs)  ipv6-core: lo fc00::1 / fc00::2 (IPv6 VTEPs)
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 AS 65100 |
| spine2 | spine | 12.12.12.12 AS 65100 |
| leaf1 | leaf | 1.1.1.1 AS 65001 |
| leaf2 | leaf | 2.2.2.2 AS 65002 |
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

- **v4-over-v6** *(default)* - IPv4 NLRI with IPv6 next hops (extended next hop), IPv4 VTEPs
- **ipv6-core** - IPv6 loopbacks + IPv6 VTEPs, EVPN over IPv6 sessions (FRR >= 10.6)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\28-mixed-underlay-rfc5549   # default variant: v4-over-v6
python tools\gns3_lab.py push labs\28-mixed-underlay-rfc5549 --variant ipv6-core   # switch variant in place
python tools\gns3_lab.py check labs\28-mixed-underlay-rfc5549
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/v4-over-v6/` (see the top-level README).

## What you will learn

* **Extended next hop** capability (RFC 8950): IPv4 NLRI whose next hop is an IPv6 address. FRR enables it
  automatically for interface-based (`neighbor eth11 interface`) sessions.
* Kernel side: `ip route show 2.2.2.2` -> `nexthop via inet6 fe80::xxxx dev eth11` - IPv4 forwarding uses the
  neighbor's MAC learnt via IPv6 ND. (Older kernels needed the 169.254.0.1 trick.)
* Why this is the sweet spot for many fabrics: zero link addressing, IPv4 overlay/VTEPs everyone understands,
  no dependence on vendors' IPv6-VTEP support.
* `ipv6-core` variant: everything IPv6 (loopbacks, VTEPs, BGP next hops), tenants still IPv4. IPv6 VTEPs (VXLAN over an IPv6 underlay) need **FRR 10.6 or newer** - the base image installs the current FRR stable release, check with `vtysh -c 'show version'`.

## Step by step

```bash
# leaf1
vtysh -c 'show bgp neighbors eth11' | grep -i -A2 'extended nexthop'
vtysh -c 'show ip bgp'                       # next hop column: fe80::... for IPv4 prefixes
ip route show 2.2.2.2
ip -6 neigh show dev eth11                   # the MAC used for IPv4 packets
tcpdump -ni eth11 -e udp port 4789           # outer IPv4 1.1.1.1 -> 2.2.2.2 over a link with no IPv4 address!
```

Compare with `ipv6-core`: `bridge fdb show dev vxlan10010` shows `dst fc00::2`, and the capture shows an
IPv6 outer header (70 bytes of overhead instead of 50).

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant v4-over-v6*

| node | command | expect |
|---|---|---|
| leaf1 | `ip route show 2.2.2.2` | `via inet6 fe80::` |
| leaf1 | `vtysh -c 'show ip bgp 2.2.2.2/32'` | `fe80::` |
| host1 | `ping -c 3 -W 1 10.10.10.20` | ` 0% packet loss` |

*variant ipv6-core*

| node | command | expect |
|---|---|---|
| leaf1 | `ip -6 route show fc00::2` | `via fe80::` |
| host1 | `ping -c 3 -W 1 10.10.10.20` | ` 0% packet loss` |

