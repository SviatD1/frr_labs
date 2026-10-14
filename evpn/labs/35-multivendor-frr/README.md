# Lab 35 - Multi-vendor EVPN design using Arista and FRR

**Video:** [Multi-vendor EVPN design using Arista and FRR](https://www.youtube.com/watch?v=576MaUMsmig) (46 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/multivendor_spines_frr  

A vendor-agnostic EVPN design means picking options every box supports the same way. The video runs
Arista leaves with **FRR spines**; here everything is FRR (so it runs on plain Linux VMs), but the
leaf configs stick to the "common denominator" choices, and `arista/` holds an EOS config you can drop
onto a vEOS leaf2 to make it truly multi-vendor. Four underlay/overlay combinations from the video,
plus the **IS-IS MTU / hello-padding** trap.

## Topology

```
     spine1 (FRR, RR)            spine2 (FRR, RR)
      |      \                 /      |
    leaf1      \______________/     leaf2   (FRR here; Arista in the video - see arista/)
  e1    e2                         e1    e2
host1  host2                     host3  host4
V10    V20                        V10    V20     VRF A, L3VNI 10100, anycast GWs
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| host1 | host | 10.10.10.10/24, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.20.20.20/24, gw 10.20.20.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.10.10.30/24, gw 10.10.10.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.20.20.40/24, gw 10.20.20.1, 00:dd:dd:dd:dd:dd |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine2 | eth1 | leaf1 | eth12 |
| spine2 | eth2 | leaf2 | eth12 |
| leaf1 | eth1 | host1 | eth1 |
| leaf1 | eth2 | host2 | eth1 |
| leaf2 | eth1 | host3 | eth1 |
| leaf2 | eth2 | host4 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **unnumbered-isis-ibgp** *(default)* - IPv4 unnumbered links, IS-IS, iBGP EVPN with RR on spines
- **ipv6-lla-isis-ibgp** - IPv6 link-local links, IS-IS IPv6, iBGP over IPv6 loopbacks, IPv6 VTEPs (FRR >= 10.6)
- **rfc5549-ibgp** - no IGP: iBGP unnumbered (interface) sessions, spines RR + next-hop-self for IPv4
- **rfc5549-ebgp** - no IGP: eBGP unnumbered, spines AS 65100, leaves AS 65001/65002
- **mtu-mismatch** - unnumbered-isis-ibgp with leaf2 eth11 MTU 9000 and spine1 eth2 MTU 1500

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\35-multivendor-frr   # default variant: unnumbered-isis-ibgp
python tools\gns3_lab.py push labs\35-multivendor-frr --variant ipv6-lla-isis-ibgp   # switch variant in place
python tools\gns3_lab.py check labs\35-multivendor-frr
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/unnumbered-isis-ibgp/` (see the top-level README).

## What you will learn

* The vendor-neutral checklist from the video: **same RTs** (set explicitly or rely on the common AS:VNI auto
  scheme), **same RD style** doesn't matter, **same MTU**, same anycast-gateway MAC, VLAN-based service (FRR has
  no VLAN-aware bundle, lab 04), standard route types only.
* Four ways to build the underlay/overlay - all interoperable with Arista:

| variant | links | underlay | overlay |
|---|---|---|---|
| unnumbered-isis-ibgp | IPv4 unnumbered | IS-IS | iBGP EVPN to spine RRs |
| ipv6-lla-isis-ibgp | IPv6 LLA | IS-IS (IPv6) | iBGP over IPv6 loopbacks, IPv6 VTEPs |
| rfc5549-ibgp | IPv6 LLA | iBGP unnumbered (RR + next-hop-self force) | same sessions |
| rfc5549-ebgp | IPv6 LLA | eBGP unnumbered | same sessions |

* **IS-IS hello padding**: IS-IS pads hellos up to the interface MTU, so an MTU mismatch (Arista defaults to
  9214, Linux to 1500) prevents the adjacency - a classic multi-vendor gotcha. Variant `mtu-mismatch`
  reproduces it: spine1 never forms an adjacency with leaf2. Fix: same MTU on both ends
  (`ip link set eth11 mtu 1500` on leaf2), or `no isis hello padding` (FRR) / `isis hello padding disabled`... on
  one side (hides the problem rather than fixing it).
* **IPv6 forwarding in Linux** (video 25:55): FRR routes nothing unless `net.ipv6.conf.all.forwarding=1` -
  the base image sets it for every router.

IPv6 VTEPs (VXLAN over an IPv6 underlay) need **FRR 10.6 or newer** - the base image installs the current FRR stable release, check with `vtysh -c 'show version'`.

## Step by step

```bash
vtysh -c 'show isis neighbor'  ; vtysh -c 'show bgp summary'
vtysh -c 'show bgp l2vpn evpn route type macip detail' | grep -i 'extended community'
# mtu-mismatch:
vtysh -c 'show isis neighbor'                  # leaf2 missing on spine1
tcpdump -ni eth2 -c 3 isis                     # leaf2's hellos are ~9000 bytes -> dropped by spine1's 1500-byte NIC
ip -d link show eth11                          # mtu on leaf2
```

## Going truly multi-vendor

In GNS3, add an Arista vEOS (or cEOS via Docker) appliance, replace leaf2 with it on the same links (Ethernet11/12
to the spines, Ethernet1/2 to host3/host4) and paste `arista/leaf2-unnumbered-isis-ibgp.eos`. The FRR side is the
`unnumbered-isis-ibgp` variant unchanged. Things that differ and must be aligned by hand: the virtual-router MAC,
RTs (EOS `route-target both auto` uses the same AS:VNI scheme as FRR, but setting them explicitly is safer),
IS-IS area/NET format, MTU.

The video's last point: FRR on a VM uses a fraction of the RAM/CPU of a vendor NOS image - which is why this whole
course runs on FRR.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant unnumbered-isis-ibgp*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.20.40` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.10.10.30` | ` 0% packet loss` |

*variant ipv6-lla-isis-ibgp*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.20.40` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.10.10.30` | ` 0% packet loss` |

*variant rfc5549-ibgp*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.20.40` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.10.10.30` | ` 0% packet loss` |

*variant rfc5549-ebgp*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.20.40` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.10.10.30` | ` 0% packet loss` |

*variant mtu-mismatch*

| node | command | expect |
|---|---|---|
| spine1 | `vtysh -c 'show isis neighbor'` | `\seth1\s+2\s+Up` |
| spine1 | `vtysh -c 'show isis neighbor' \| grep -c 'eth2 .*Up'` | `^0` |

