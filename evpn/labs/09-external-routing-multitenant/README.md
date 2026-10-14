# Lab 09 - Multi-Tenant External Routing in EVPN

**Video:** [Multi-Tenant External Routing in EVPN](https://www.youtube.com/watch?v=Zcf54mN1awc) (35 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/external_routing_multi_tenancy  

Two tenants (VRF A and VRF B) need to reach the outside. Option 1: **VRF-lite hand-off** - one
802.1Q sub-interface and one eBGP session per VRF. Option 2: a **shared external connection** - one
`INTERNET` VRF on the border leaves, with routes leaked between the tenants and INTERNET. You will
also see how the shared design can quietly break tenant isolation.

## Topology

```
             spine1          spine2
    leaf1    leaf2     leaf3 (border)   leaf4 (border)
   e1   e2  e1   e2       | eth1            | eth1
 host1 host3 host2 host4  r1 ---- eth4 ---- r2       AS 65001
   A     B    A    B      | eth3            | eth3
                        host5            host6
                   192.168.5.5/24    192.168.6.6/24
VRF A: VLAN10 10.10.10.0/24, L3VNI 1000      VRF B: VLAN30 10.30.30.0/24, L3VNI 2000
vrf-lite:   leafX eth1.100 (A) 172.16.3X.0/24   leafX eth1.200 (B) 172.17.3X.0/24
shared:     leafX eth1 (INTERNET) 172.16.3X.0/24, r1/r2 send a default route
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
| r1 | ext | 172.16.1.1 |
| r2 | ext | 172.16.2.2 |
| host1 | host | 10.10.10.10/24, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.10.10.20/24, gw 10.10.10.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.30.30.30/24, gw 10.30.30.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.30.30.40/24, gw 10.30.30.1, 00:dd:dd:dd:dd:dd |
| host5 | exthost | 192.168.5.5/24, gw 192.168.5.1, 00:ee:ee:ee:ee:ee |
| host6 | exthost | 192.168.6.6/24, gw 192.168.6.1, 00:ff:ff:ff:ff:ff |

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
| leaf3 | eth1 | r1 | eth1 |
| leaf4 | eth1 | r2 | eth1 |
| r1 | eth4 | r2 | eth4 |
| leaf1 | eth1 | host1 | eth1 |
| leaf1 | eth2 | host3 | eth1 |
| leaf2 | eth1 | host2 | eth1 |
| leaf2 | eth2 | host4 | eth1 |
| r1 | eth3 | host5 | eth1 |
| r2 | eth3 | host6 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **vrf-lite** *(default)* - one sub-interface + eBGP session per tenant VRF
- **shared** - INTERNET VRF on the border leaves, route leaking with import vrf

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\09-external-routing-multitenant   # default variant: vrf-lite
python tools\gns3_lab.py push labs\09-external-routing-multitenant --variant shared   # switch variant in place
python tools\gns3_lab.py check labs\09-external-routing-multitenant
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/vrf-lite/` (see the top-level README).

## What you will learn

* 802.1Q sub-interfaces on Linux (`ip link add link eth1 name eth1.100 type vlan id 100`) placed in VRFs.
* **VRF-lite hand-off**: per-tenant eBGP sessions. Simple and isolated, but N tenants = N sessions/sub-interfaces per link.
* **Shared external connection**: one `INTERNET` VRF, routes **leaked** with FRR's `import vrf`:
  * INTERNET imports A and B (so the outside world can reach the tenants),
  * A and B import only the default route from INTERNET (route-map `ONLY-DEFAULT`).

## Step by step (vrf-lite)

```bash
# leaf3
ip -d link show eth1.100 ; ip -br addr show vrf A
vtysh -c 'show bgp vrf all summary'
# r1
vtysh -c 'show ip bgp'          # 10.10.10.0/24 from session .100 and 10.30.30.0/24 from session .200
```

Notice: r1 keeps both tenants in its **global** table. Can host1 (A) reach host3 (B)? Try
`ping 10.30.30.30` from host1 and `traceroute -n` it. Isolation is only as good as the external
router - in real life r1 would be a PE with its own VRFs.

## Step by step (shared)

```powershell
python tools\gns3_lab.py push labs\09-external-routing-multitenant --variant shared
```

```bash
# leaf3
vtysh -c 'show bgp vrf INTERNET ipv4 unicast'     # 0.0.0.0/0 from r1 + leaked tenant routes
vtysh -c 'show bgp vrf A ipv4 unicast 0.0.0.0/0'  # "Imported from ...:INTERNET"
ip route show vrf A default ; ip route show vrf INTERNET
# leaf1
vtysh -c 'show bgp l2vpn evpn route type prefix'  # default route advertised by leaf3/leaf4 in VRF A and B
```

**Breaking isolation:** from host1 (A) ping host3 (B) in the `shared` variant. VRF A only knows a default route...
which points into INTERNET... which knows 10.30.30.0/24 (leaked from B). The border leaf hair-pins
A -> INTERNET -> B. That's the trap the video warns about. Ways out:

* don't leak tenant prefixes into INTERNET at all (NAT/firewall instead),
* or add an nftables rule on the border leaves: `nft add rule inet filter forward iifname "A" oifname "B" drop`
  (and vice-versa) - Linux forwards between VRFs, so the kernel firewall can stop it,
* or use a firewall per tenant (labs 14-16).

## How this maps to the video

The video uses Arista's RT import/export between VRFs (INTERNET imports RT 100:100 and 200:200,
tenants import 10000:10000). On Linux, a route imported this way would be installed in the tenant VRF
pointing at the *INTERNET* L3VNI, but the remote leaf has no INTERNET VRF - so this lab uses FRR's
local `import vrf` leaking on the border leaves instead and re-advertises the leaked default route
inside each tenant's own L3VNI.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant vrf-lite*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 192.168.5.5` | ` 0% packet loss` |
| host4 | `ping -c 3 -W 1 192.168.6.6` | ` 0% packet loss` |
| r1 | `vtysh -c 'show ip bgp summary'` | `172\.16\.33\.3\)?\s+4\s+65000[\s\S]*172\.17\.33\.3\)?\s+4\s+65000` |

*variant shared*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 192.168.5.5` | ` 0% packet loss` |
| host4 | `ping -c 3 -W 1 192.168.6.6` | ` 0% packet loss` |
| leaf1 | `ip route show vrf A default` | `default` |

