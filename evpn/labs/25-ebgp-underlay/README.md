# Lab 25 - eBGP as Underlay for EVPN in Data Center

**Video:** [eBGP as Underlay for EVPN in Data Center](https://www.youtube.com/watch?v=ty5JxLFjtJQ) (47 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_underlay_ebgp  

RFC 7938 style: no IGP at all, **eBGP on every link**, and the EVPN address family on the same sessions.
Compare ASN schemes (same ASN on all spines vs unique ASN everywhere), see the **transit leaf** problem
appear with unique spine ASNs, and replace all link addressing with **BGP unnumbered** over IPv6 link-local.

## Topology

```
   spine1 AS 65100 (or 65101)       spine2 AS 65100 (or 65102)
      |   \     \                /    /   |
    leaf1      leaf2         leaf3          leaf1..3 = AS 65001..65003
      |          |             |
    host1      host2         host3        VLAN 10 / VNI 10010, 10.10.10.0/24
EVPN rides the same eBGP sessions; spines keep the leaves' next hops (VTEP IPs)
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 AS 65100 |
| spine2 | spine | 12.12.12.12 AS 65100 |
| leaf1 | leaf | 1.1.1.1 AS 65001 |
| leaf2 | leaf | 2.2.2.2 AS 65002 |
| leaf3 | leaf | 3.3.3.3 AS 65003 |
| host1 | host | 10.10.10.10/24, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.10.10.20/24, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.10.10.30/24, 00:cc:cc:cc:cc:cc |

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
| leaf3 | eth1 | host3 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **same-asn-spines** *(default)* - spines AS 65100, leaves 65001-65003, numbered links
- **unique-asn** - every switch its own AS (transit leaf possible)
- **unnumbered** - same as same-asn-spines but BGP unnumbered (IPv6 LLA, RFC 5549)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\25-ebgp-underlay   # default variant: same-asn-spines
python tools\gns3_lab.py push labs\25-ebgp-underlay --variant unique-asn   # switch variant in place
python tools\gns3_lab.py check labs\25-ebgp-underlay
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/same-asn-spines/` (see the top-level README).

## What you will learn

* eBGP-only underlay in FRR: `remote-as external`, peer-groups, `bgp bestpath as-path multipath-relax`
  (ECMP across paths with different AS numbers), `network <loopback>/32`.
* **EVPN over the same eBGP sessions**: spines activate `l2vpn evpn` but are not VTEPs; FRR keeps the
  original next hop (the VTEP loopback) on EVPN routes, so leaves build tunnels to each other, not to spines.
* ASN schemes:
  * **same ASN on all spines** (65100): a path leaf -> spine1 -> leaf2 -> spine2 is impossible (spine2 would
    see its own AS) - no transit leaf, automatically.
  * **unique ASN everywhere**: simpler to reason about, but leaves *can* become transit when a link fails.
* **BGP unnumbered**: `neighbor eth11 interface peer-group SPINES` - the session runs over IPv6 link-local
  (found via Router Advertisements), and IPv4 routes get **IPv6 next hops** (RFC 5549/8950).

## Step by step

```bash
# leaf1
vtysh -c 'show bgp summary'                  # ipv4 unicast + l2vpn evpn on the same peers
vtysh -c 'show ip bgp'                       # AS paths: 65100 65002, 65100 65003 ...
ip route show 3.3.3.3                        # ECMP
vtysh -c 'show bgp l2vpn evpn route type multicast'   # next hop = 2.2.2.2 / 3.3.3.3, not the spine
```

**Transit leaf** (video 32:34), variant `unique-asn`: on spine1 shut the link to leaf1 (`ip link set eth1 down`).
Then on spine1: `vtysh -c 'show ip bgp 1.1.1.1/32'` - spine1 still has a path ... via leaf2 -> spine2 -> leaf1
(AS path `65002 65102 65001`). Traffic for leaf1 that reaches spine1 is now carried by **leaf2's** uplinks.
Do the same in `same-asn-spines`: no path (spine1 rejects `65100` in the AS path) - good, the leaves simply stop
using spine1 for leaf1.

**Unnumbered**:

```bash
vtysh -c 'show bgp neighbors eth11' | grep -i 'hostname\|state\|extended nexthop'
ip -br addr show eth11                       # only fe80::
ip route show 3.3.3.3                        # nexthop via inet6 fe80::... dev eth11
ip neigh show dev eth11                      # FRR installs a fake IPv4 neighbor 169.254.0.1 on older kernels
```

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant same-asn-spines*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.30` | ` 0% packet loss` |
| leaf1 | `ip route show 3.3.3.3` | `nexthop via[\s\S]*nexthop via` |
| leaf1 | `vtysh -c 'show bgp l2vpn evpn route type macip'` | `00:cc:cc:cc:cc:cc` |
| leaf1 | `bridge fdb show dev vxlan10010` | `dst 3\.3\.3\.3` |
| leaf1 | `vtysh -c 'show ip bgp 3.3.3.3/32'` | `65100 65003` |

*variant unique-asn*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.30` | ` 0% packet loss` |
| leaf1 | `ip route show 3.3.3.3` | `nexthop via[\s\S]*nexthop via` |
| leaf1 | `vtysh -c 'show bgp l2vpn evpn route type macip'` | `00:cc:cc:cc:cc:cc` |
| leaf1 | `bridge fdb show dev vxlan10010` | `dst 3\.3\.3\.3` |

*variant unnumbered*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.30` | ` 0% packet loss` |
| leaf1 | `ip route show 3.3.3.3` | `nexthop via[\s\S]*nexthop via` |
| leaf1 | `vtysh -c 'show bgp l2vpn evpn route type macip'` | `00:cc:cc:cc:cc:cc` |
| leaf1 | `bridge fdb show dev vxlan10010` | `dst 3\.3\.3\.3` |
| leaf1 | `ip route show 3.3.3.3` | `via inet6 fe80::` |

