# Lab 15 - Multitenant Service Insertion in EVPN. Advanced VRF Sandwich

**Video:** [Multitenant Service Insertion in EVPN. Advanced VRF Sandwich](https://www.youtube.com/watch?v=JMo-iI2npy4) (57 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/service_insertion_multitenant  

Four tenants (A, B, C, D) share one firewall through two **service VRFs** on the service leaf:
`OUT` (towards the fw, collects every tenant's routes) and `IN` (from the fw, gives tenants the routes
they are allowed to reach). Which tenant can talk to which is pure **route policy** - full mesh or
partial mesh - and a sloppy policy creates loops.

## Topology

```
             spine1                      spine2
     leaf1                 leaf2                    leaf3 (service leaf)
   e1     e2             e1     e2            VRFs A B C D + OUT + IN
 host1   host3         host2   host4          eth1 (OUT)        eth2 (IN)
A VLAN10 C VLAN30     B VLAN20 D VLAN40         |                  |
10.10.10.10 10.30.30.30 10.20.20.20 10.40.40.40  eth1 ---- fw ---- eth2     AS 100
                                             172.16.31.0/24     172.16.32.0/24
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
| host2 | host | 10.20.20.20/24, gw 10.20.20.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.30.30.30/24, gw 10.30.30.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.40.40.40/24, gw 10.40.40.1, 00:dd:dd:dd:dd:dd |

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

- **full-mesh** - every tenant can reach every other tenant through the fw
- **partial-mesh** *(default)* - A<->B, A<->C only; D is isolated

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\15-service-insertion-multitenant   # default variant: partial-mesh
python tools\gns3_lab.py push labs\15-service-insertion-multitenant --variant full-mesh   # switch variant in place
python tools\gns3_lab.py check labs\15-service-insertion-multitenant
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/partial-mesh/` (see the top-level README).

## What you will learn

* **Dedicated service VRFs** so that adding tenant N doesn't need another pair of fw interfaces:
  * `OUT` imports every tenant's subnets and advertises them to the fw;
  * the fw sends them back (as-override) into `IN`;
  * each tenant VRF imports from `IN` only the prefixes it is allowed to reach -> **policy = route-maps**.
* **Loops**: if tenant A imported its *own* prefix back from `IN`, the service leaf would prefer the eBGP
  copy (via fw) over the EVPN one and hair-pin A's own traffic forever. Each `TO-<tenant>` prefix-list
  only permits *other* tenants.
* Route leaking chains on FRR: `import vrf` from tenant VRFs into OUT, from IN into tenant VRFs, each
  filtered by `import vrf route-map ...`.

## Linux vs the video

The video keeps the tenant VRFs **off** the service leaf and uses EVPN RT tricks (export with rewritten
RTs `101:101`, `202:202` ...). On Linux every VRF has exactly one L3VNI, and a route imported into VRF A
always egresses with **A's** L3VNI - so a type-5 route originated in `IN` (different L3VNI) can't be used
directly by VRF A on leaf1. The Linux-friendly equivalent is to instantiate the tenant VRFs on the service
leaf and do the leaking there, which is what this lab does. The policy logic (who imports what) is the same.

## Step by step

```bash
# leaf3
vtysh -c 'show bgp vrf OUT ipv4 unicast'     # all 4 tenant subnets (leaked)
vtysh -c 'show bgp vrf IN ipv4 unicast'      # same subnets learnt back from the fw (AS path 100 100)
vtysh -c 'show bgp vrf A ipv4 unicast'       # only the subnets A may reach, via IN
ip route show vrf A
# leaf1
ip route show vrf A ; ip route show vrf C    # what each tenant can reach fabric-wide
```

Partial mesh test matrix (`partial-mesh`): A<->B ok, A<->C ok, B<->C blocked, D isolated.
Edit `ip prefix-list TO-D` on leaf3 to allow D -> A (and TO-A to allow A -> D) and re-test.

**Build a loop on purpose** (video 31:43): on leaf3 add A's own subnet to `TO-A`
(`ip prefix-list TO-A seq 100 permit 10.10.10.0/24`), then `clear bgp vrf A *`. Compare
`vtysh -c 'show bgp vrf A ipv4 unicast 10.10.10.0/24'` before/after and ping host1 -> host3. Remove it again.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant full-mesh*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.40.40.40` | ` 0% packet loss` |
| host3 | `ping -c 3 -W 1 10.20.20.20` | ` 0% packet loss` |

*variant partial-mesh*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.20.20` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.30.30.30` | ` 0% packet loss` |
| host3 | `ping -c 2 -W 1 10.20.20.20` | `100% packet loss\|Unreachable` |
| host4 | `ping -c 2 -W 1 10.10.10.10` | `100% packet loss\|Unreachable` |
| fw | `nft list table inet fw` | `counter packets [1-9]` |

