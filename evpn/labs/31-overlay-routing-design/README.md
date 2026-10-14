# Lab 31 - EVPN Overlay Design for Routing in Data Center

**Video:** [EVPN Overlay Design for Routing in Data Center](https://www.youtube.com/watch?v=jRbyPlaTZyQ) (34 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_overlay_l3  

Symmetric IRB by default installs a **/32 for every endpoint** in the VRF on every leaf. That's simple
and optimal, but it's the table that runs out first. Compare it with a design where leaves only use
**subnet (type-5) routes** across the fabric and resolve hosts locally via ARP/bridging.

## Topology

```
           spine1                 spine2
      leaf1        leaf2         leaf3        leaf4
     e1   e2      e1   e2         e1           e1
   host1 host2  host3 host4      host5        host6
   V10   V20    V10   V20        V30          V40
VLAN 10/20 stretched on leaf1+leaf2, VLAN 30 only on leaf3, VLAN 40 only on leaf4
VRF A, L3VNI 1000, every leaf advertises its subnets as type-5
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| leaf4 | leaf | 4.4.4.4 |
| host1 | host | 10.10.10.10/24, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.20.20.20/24, gw 10.20.20.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.10.10.30/24, gw 10.10.10.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.20.20.40/24, gw 10.20.20.1, 00:dd:dd:dd:dd:dd |
| host5 | host | 10.30.30.50/24, gw 10.30.30.1, 00:ee:ee:ee:ee:ee |
| host6 | host | 10.40.40.60/24, gw 10.40.40.1, 00:ff:ff:ff:ff:ff |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine1 | eth3 | leaf3 | eth11 |
| spine1 | eth4 | leaf4 | eth11 |
| spine2 | eth1 | leaf1 | eth12 |
| spine2 | eth2 | leaf2 | eth12 |
| spine2 | eth3 | leaf3 | eth12 |
| spine2 | eth4 | leaf4 | eth12 |
| leaf1 | eth1 | host1 | eth1 |
| leaf1 | eth2 | host2 | eth1 |
| leaf2 | eth1 | host3 | eth1 |
| leaf2 | eth2 | host4 | eth1 |
| leaf3 | eth1 | host5 | eth1 |
| leaf4 | eth1 | host6 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **host-routes** *(default)* - default symmetric IRB: /32 per endpoint on every leaf
- **subnets-only** - leaves strip the L3VNI RT from incoming type-2 -> no remote /32, only type-5 subnets

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\31-overlay-routing-design   # default variant: host-routes
python tools\gns3_lab.py push labs\31-overlay-routing-design --variant subnets-only   # switch variant in place
python tools\gns3_lab.py check labs\31-overlay-routing-design
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/host-routes/` (see the top-level README).

## What you will learn

* Where host routes come from: a type-2 MAC/IP route carries **two** RTs (L2VNI `65000:100xx` and L3VNI
  `65000:1000`). The L3 RT imports it into VRF A as a /32.
* FRR policy trick for "subnets only": an inbound route-map that deletes the L3VNI RT from type-2 routes:
  ```text
  bgp extcommunity-list standard L3VNI-RT seq 5 permit rt 65000:1000
  route-map NO-HOST-ROUTES permit 10
   match evpn route-type macip
   set extcomm-list L3VNI-RT delete
  ```
  MACs and ARP suppression still work (L2 RT untouched), but no /32 lands in the VRF.
* How traffic then flows:
  * to a **stretched** subnet you also have locally (10.20.20.0/24 on leaf1): routed into the local SVI, ARP is
    answered by suppression, then *bridged* over the L2VNI - asymmetric IRB for that hop;
  * to a **non-local** subnet (10.30.30.0/24 from leaf1): type-5 /24 via the L3VNI to the subnet's owner,
    which resolves the host locally.

## Step by step

```bash
# leaf4 (has only VLAN 40)
ip route show vrf A                 # host-routes: many /32 entries;  subnets-only: just /24s
vtysh -c 'show bgp vrf A ipv4 unicast'
vtysh -c 'show bgp l2vpn evpn route type macip detail' | grep -i 'extended community' | head
# leaf1
vtysh -c 'show evpn arp-cache vni 10020'     # still populated in both variants (suppression keeps working)
```

## Trade-offs to discuss (video)

* Subnets-only breaks **mobility of a single host out of its home subnet's leaves** - an isolated subnet
  advertised by two leaves is load-balanced, the wrong leaf has to bridge/flood to find the host.
* A **stretched subnet that is not local** needs the /32, otherwise traffic goes to *one of* the leaves
  announcing the /24 and may need an extra hop. "Dedicated leaves advertise subnets" (border/gateway leaves
  that have every VLAN) is the middle ground from the video - try advertising 10.10.10.0/24 only from leaf2
  (remove `redistribute connected` on leaf1, or filter it with a route-map).

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant host-routes*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.30.30.50` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.20.20.40` | ` 0% packet loss` |
| host5 | `ping -c 3 -W 1 10.40.40.60` | ` 0% packet loss` |
| leaf4 | `ip route show vrf A` | `10\.10\.10\.10 .*vlan4001` |

*variant subnets-only*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.30.30.50` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.20.20.40` | ` 0% packet loss` |
| host5 | `ping -c 3 -W 1 10.40.40.60` | ` 0% packet loss` |
| leaf4 | `ip route show vrf A` | `10\.10\.10\.0/24 .*vlan4001` |
| leaf4 | `ip route show vrf A 10.10.10.10` | `^$` |

