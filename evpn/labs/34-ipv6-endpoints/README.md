# Lab 34 - IPv6 Endpoints in EVPN

**Video:** [IPv6 Endpoints in EVPN](https://www.youtube.com/watch?v=miq6tTILvlU) (38 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_overlay_ipv6_endpoints  

Dual-stack tenants: IPv6 anycast gateways next to IPv4 ones, type-2 routes with IPv6 addresses, type-5
IPv6 prefixes, **ND suppression**, and the IPv6 side effects that matter at scale - **Router
Advertisements/SLAAC**, DAD, and the extra multicast that IPv6 endpoints generate. Underlay stays IPv4.

## Topology

```
            spine1               spine2
       leaf1          leaf2           leaf3
         |              |               |
       host1          host2           host3
     VLAN 10         VLAN 10         VLAN 20
10.10.10.10        10.10.10.20     10.20.20.30
fd00:10::10        fd00:10::20     fd00:20::30        gw 10.x.x.1 / fd00:x::1 (anycast, same MAC everywhere)
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| host1 | host | 10.10.10.10/24, fd00:10::10/64, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.10.10.20/24, fd00:10::20/64, gw 10.10.10.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.20.20.30/24, fd00:20::30/64, gw 10.20.20.1, 00:cc:cc:cc:cc:cc |

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

- **static** *(default)* - static IPv6 addresses on hosts, RAs suppressed
- **slaac** - leaves send RAs (prefix + default router), hosts autoconfigure (EUI-64)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\34-ipv6-endpoints   # default variant: static
python tools\gns3_lab.py push labs\34-ipv6-endpoints --variant slaac   # switch variant in place
python tools\gns3_lab.py check labs\34-ipv6-endpoints
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/static/` (see the top-level README).

## What you will learn

* Dual-stack SVIs (`ip -6 addr add fd00:10::1/64 dev vlan10`) - the anycast MAC also makes the **link-local**
  gateway address identical on every leaf (EUI-64 of 00:00:5e:00:01:01 = `fe80::200:5eff:fe00:101`).
* FRR: `address-family ipv6 unicast` / `redistribute connected` and `advertise ipv6 unicast` in the VRF's EVPN AF.
  Type-2 routes carry IPv6 addresses; IPv6 type-5 prefixes ride the same IPv4 VTEPs ("IPv6 overlay over IPv4
  underlay") - in the kernel they show up as IPv6 routes via an IPv4-mapped next hop on vlan4001.
* **ND suppression**: the same `neigh_suppress on` covers NS/NA.
* **RA control**: FRR (zebra) only sends Router Advertisements when you ask (`no ipv6 nd suppress-ra`).
  With RAs, hosts do **SLAAC** (EUI-64 or privacy addresses) - every host gets addresses you didn't plan,
  each one a type-2 route on every leaf (scale!). The video recommends suppressing RAs unless you need them,
  and disabling SLAAC on servers (`sysctl net.ipv6.conf.eth1.autoconf=0`, `accept_ra=0`).
* IPv6 BUM: DAD NS, RS, MLD reports - all multicast, all flooded by ingress replication.

## Step by step

```bash
# leaf1
vtysh -c 'show evpn arp-cache vni 10010'               # IPv4 and IPv6 entries
vtysh -c 'show bgp l2vpn evpn route type macip'        # [2]:...:[128]:[fd00:10::20]
vtysh -c 'show bgp l2vpn evpn route type prefix'       # [5]:[0]:[64]:[fd00:20::]
ip -6 route show vrf A
ip -6 neigh show vrf A
# host1
ping -6 fd00:20::30 ; ip -6 route ; ip -6 neigh
```

`slaac` variant:

```bash
# host1
ip -6 addr show dev eth1      # fd00:10::2aa:aaff:feaa:aaaa (EUI-64 from 00:aa:aa:aa:aa:aa)
ip -6 route                   # default via fe80::200:5eff:fe00:101 proto ra
# leaf1
vtysh -c 'show interface vlan10' | grep -A6 'ND advertised'
tcpdump -ni eth11 -e udp port 4789 and ip6     # RAs/NS/DAD crossing the fabric
```

Turn on privacy addresses on host1 (`sysctl -w net.ipv6.conf.eth1.use_tempaddr=2; ip link set eth1 down; ip link set eth1 up`) and count
how many IPv6 type-2 routes one host creates over time.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant static*

| node | command | expect |
|---|---|---|
| host1 | `ping -6 -c 3 -W 1 fd00:10::20` | ` 0% packet loss` |
| host1 | `ping -6 -c 3 -W 1 fd00:20::30` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.20.20.30` | ` 0% packet loss` |
| leaf1 | `vtysh -c 'show evpn arp-cache vni 10010'` | `fd00:10::20\s+remote` |
| leaf1 | `ip -6 route show vrf A fd00:20::30` | `via ::ffff:3\.3\.3\.3\|via 3\.3\.3\.3\|vlan4001` |

*variant slaac*

| node | command | expect |
|---|---|---|
| host1 | `ip -6 addr show dev eth1` | `fd00:10::2aa:aaff:feaa:aaaa` |
| host1 | `ping -6 -c 3 -W 1 fd00:20::2cc:ccff:fecc:cccc` | ` 0% packet loss` |

