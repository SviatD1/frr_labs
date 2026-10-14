# Lab 27 - iBGP as Underlay for EVPN in Data Center

**Video:** [iBGP as Underlay for EVPN in Data Center](https://www.youtube.com/watch?v=jfGXKxvVfMg) (24 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_underlay_ibgp  

The other BGP-only option: **iBGP** in one AS, spines as route reflectors, sessions on the link
addresses - no IGP. You must deal with next hops (`next-hop-self force` on the RRs for the underlay
AF, but *not* for EVPN) and with **router-ids**: a duplicated router-id silently breaks route reflection.

## Topology

```
    spine1 (RR)          spine2 (RR)        all AS 65000
   /    |    \          /    |    \
leaf1  leaf2  leaf3   (every leaf to both spines, iBGP on link addresses)
  |      |      |
host1  host2  host3      VLAN 10 / VNI 10010
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
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

- **ibgp** *(default)* - iBGP underlay + EVPN, RR on spines
- **duplicate-router-id** - leaf2 and leaf3 share router-id 9.9.9.9 - spot the problem

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\27-ibgp-underlay   # default variant: ibgp
python tools\gns3_lab.py push labs\27-ibgp-underlay --variant duplicate-router-id   # switch variant in place
python tools\gns3_lab.py check labs\27-ibgp-underlay
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/ibgp/` (see the top-level README).

## What you will learn

* iBGP doesn't change next hops and doesn't re-advertise iBGP routes - hence **route reflectors**.
* For the underlay AF the RR must rewrite the next hop to itself (`next-hop-self force` - plain
  `next-hop-self` doesn't touch reflected routes); for EVPN it must **not** (the next hop *is* the VTEP).
  That's why the two address families have different neighbor settings on the spines.
* `bgp cluster-id` per RR, ORIGINATOR_ID and CLUSTER_LIST loop prevention.
* **Router-id matters**: in an IPv6-only fabric there is no IPv4 address to derive it from, and a duplicated
  router-id makes the RR-reflected route look like the receiver's own (ORIGINATOR_ID == my router-id) -> dropped.

## Step by step

```bash
# leaf1
vtysh -c 'show ip bgp'                         # next hop = spine link address (next-hop-self force)
vtysh -c 'show ip bgp 3.3.3.3/32'              # Originator: 3.3.3.3, Cluster list: 11.11.11.11
vtysh -c 'show bgp l2vpn evpn route type multicast'   # next hop 3.3.3.3 untouched
```

Variant `duplicate-router-id`: leaf2 and leaf3 both use router-id 9.9.9.9.

```bash
# leaf2
vtysh -c 'show ip bgp 3.3.3.3/32'              # missing!
vtysh -c 'show bgp l2vpn evpn route'           # leaf3's routes missing too
journalctl -t bgpd | grep -i originator        # or: debug bgp updates in
```

host2 <-> host3 breaks while everything *looks* up (`show bgp summary` is all Established). Fix the
router-id and `clear bgp *`.

## eBGP vs iBGP underlay (video 22:34)

* iBGP: one AS, no AS-path tricks, but needs RRs, next-hop handling, and has no AS-path loop protection inside the fabric.
* eBGP: per-hop next-hop-self for free, AS-path loop prevention, but ASN planning and path hunting (lab 26).

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant ibgp*

| node | command | expect |
|---|---|---|
| leaf1 | `ip route show 3.3.3.3` | `nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12` |
| host1 | `ping -c 3 -W 1 10.10.10.30` | ` 0% packet loss` |
| leaf1 | `vtysh -c 'show bgp l2vpn evpn route type multicast'` | `\[3\]:\[0\]:\[32\]:\[3\.3\.3\.3\]` |

*variant duplicate-router-id*

| node | command | expect |
|---|---|---|
| leaf2 | `vtysh -c 'show ip bgp 3.3.3.3/32'` | `Network not in table\|not in table` |

