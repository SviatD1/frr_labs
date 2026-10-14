# EVPN-VXLAN on Linux + FRR - GNS3 labs for the Sneaky Subnet EVPN playlist

One hands-on GNS3 lab for every video of the [Sneaky Subnet **EVPN** playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)
(37 public videos as of Oct 2026 - YouTube hides 2 unavailable ones). The videos use Arista cEOS in
containerlab; these labs rebuild each scenario with **plain Linux VMs**: Linux does the data plane
(bridge, vxlan, vrf, bond, nftables, tc), **FRR** does the control plane (IS-IS/OSPF/BGP/EVPN/PIM/PBR).
Topologies, addresses and interface names follow the author's labs where possible
([github.com/sneakysubnet/evpn_with_clab](https://github.com/sneakysubnet/evpn_with_clab)) so you can watch the
video and type along.

```
evpn/
├─ README.md               <- you are here
├─ base-image/             <- build the one VM image every node uses (Debian 13 + FRR) - do this first
├─ tools/
│  ├─ gns3_lab.py          <- build / start / push config / check / exec - talks to the GNS3 API + consoles
│  └─ generator/           <- Python that generated every lab (edit + regenerate if you like)
└─ labs/NN-name/
   ├─ README.md            <- goals, theory recap, step-by-step commands, break/fix exercises
   ├─ topology.json        <- nodes, links, variants, automated checks
   └─ nodes/<variant>/<node>.sh   <- one self-contained script per VM (Linux config + frr.conf)
```

## Quick start

1. **Prerequisites**: GNS3 2.2.x or 3.x with the GNS3 VM (Windows/macOS) or a Linux GNS3 server with KVM;
   Python 3.8+ on your PC (`python --version`); 8 GB RAM for the GNS3 VM is comfortable (labs have 5-14 VMs at 256-512 MB).
2. **Build the base image and the `debian-frr` template** once - [base-image/README.md](base-image/README.md).
3. Run a lab:

   ```powershell
   cd C:\Users\<you>\my_vibe_coding\frr\evpn
   python tools\gns3_lab.py up labs\02-basic-bridging
   ```

   `up` = create the GNS3 project (nodes placed and wired), start all VMs, wait for their consoles, push each
   node's script over the serial console, then run the lab's automated checks. Open the project in GNS3 and use
   the consoles as usual.
4. Work through `labs\02-basic-bridging\README.md`.

Other commands:

```powershell
python tools\gns3_lab.py push  labs\05-basic-routing-irb --variant asymmetric     # switch variant in place
python tools\gns3_lab.py push  labs\05-basic-routing-irb --nodes leaf1            # re-push one node
python tools\gns3_lab.py check labs\05-basic-routing-irb --variant asymmetric
python tools\gns3_lab.py exec  labs\05-basic-routing-irb leaf1 "vtysh -c 'show evpn vni'"
python tools\gns3_lab.py stop  labs\05-basic-routing-irb
python tools\gns3_lab.py delete labs\05-basic-routing-irb
python tools\gns3_lab.py templates
```

The tool finds the local GNS3 server and its credentials from your GNS3 settings (`%APPDATA%\GNS3\...\gns3_server.ini`).
For a remote server: `--server http://192.168.x.y:3080 --user admin --password ...` (or `GNS3_SERVER`, `GNS3_USER`,
`GNS3_PASSWORD` environment variables).

**Without the tool**: build the topology by hand from the lab README's link table (interface `ethN` = GNS3
adapter N), then on each VM's console run the matching `nodes/<variant>/<node>.sh` (copy/paste it, or make it
available any way you like - it's plain bash).

## The labs

| # | Video | Lab | Variants |
|---|---|---|---|
| 01 | [EVPN Fundamentals](https://www.youtube.com/watch?v=Dk-qNDrZDX4) | [01-evpn-fundamentals](labs/01-evpn-fundamentals) - STP triangle vs L3 leaf/spine | 1 |
| 02 | [Basic Bridging/Switching in EVPN](https://www.youtube.com/watch?v=a4Lfu9x3eyY) | [02-basic-bridging](labs/02-basic-bridging) - first VXLAN fabric | 1 |
| 03 | [Handling BUM traffic in EVPN](https://www.youtube.com/watch?v=r9W8o7jCNzE) | [03-bum-traffic](labs/03-bum-traffic) - IMET, ingress replication, ARP suppression | 2 |
| 04 | [EVPN Bridging Deep Dive](https://www.youtube.com/watch?v=YRMEEhEaXgw) | [04-bridging-deep-dive](labs/04-bridging-deep-dive) - RD/RT/VNI/VLAN, multitenancy | 4 |
| 05 | [Basic routing in EVPN](https://www.youtube.com/watch?v=AJc1dd6_gBg) | [05-basic-routing-irb](labs/05-basic-routing-irb) - VRF, anycast GW, asym/sym IRB | 2 |
| 06 | [EVPN Routing Deep Dive](https://www.youtube.com/watch?v=Ntm772VEEdE) | [06-routing-deep-dive](labs/06-routing-deep-dive) - isolated VNIs, type-5, route leaking | 2 |
| 07 | [External Routing using OSPF](https://www.youtube.com/watch?v=EEXWnOcnE1g) | [07-external-routing-ospf](labs/07-external-routing-ospf) - mutual redistribution, loops | 2 |
| 08 | [External Routing using BGP](https://www.youtube.com/watch?v=uuUZyg-tZ20) | [08-external-routing-bgp](labs/08-external-routing-bgp) - eBGP borders, host-route filter, TE | 2 |
| 09 | [Multi-Tenant External Routing](https://www.youtube.com/watch?v=Zcf54mN1awc) | [09-external-routing-multitenant](labs/09-external-routing-multitenant) - VRF-lite vs shared | 2 |
| 10 | [Tenant Multicast, OISM with SSM](https://www.youtube.com/watch?v=vi3Q1ibzB7w) | [10-tenant-multicast](labs/10-tenant-multicast) - OISM-style egress routing with pimd | 1 |
| 11 | [EVPN Multihoming Fundamentals](https://www.youtube.com/watch?v=PvIDqq3bwRw) | [11-multihoming-fundamentals](labs/11-multihoming-fundamentals) - LACP + ES | 2 |
| 12 | [Multihoming Deep Dive: ES route, DF, split horizon](https://www.youtube.com/watch?v=EMA8-csnilA) | [12-multihoming-deep-dive](labs/12-multihoming-deep-dive) | 1 |
| 13 | [Multihoming: AD routes, fast convergence, aliasing](https://www.youtube.com/watch?v=Q-oBiCV_EO0) | [13-multihoming-ad-routes](labs/13-multihoming-ad-routes) | 2 |
| 14 | [Service Insertion. VRF Sandwich](https://www.youtube.com/watch?v=roktYzoyW5U) | [14-service-insertion-vrf-sandwich](labs/14-service-insertion-vrf-sandwich) - as-override | 2 |
| 15 | [Multitenant Service Insertion](https://www.youtube.com/watch?v=JMo-iI2npy4) | [15-service-insertion-multitenant](labs/15-service-insertion-multitenant) - service VRFs, policy | 2 |
| 16 | [Service Insertion using PBR](https://www.youtube.com/watch?v=VsSOVx5P3UM) | [16-service-insertion-pbr](labs/16-service-insertion-pbr) - pbrd, symmetric PBR | 2 |
| 17 | [All BGP EVPN Route Types](https://www.youtube.com/watch?v=9JJrcvuVYfU) | [17-all-route-types](labs/17-all-route-types) - types 1-5 in one fabric | 1 |
| 18 | [Clos / Leaf-Spine-Leaf Topology](https://www.youtube.com/watch?v=WHt-zH8idDo) | [18-clos-topology](labs/18-clos-topology) - shaped links, blocking | 2 |
| 19 | [Scaling Clos fabrics](https://www.youtube.com/watch?v=fmRJkXP-ZZ4) | [19-scaling-clos](labs/19-scaling-clos) - 5-stage, transit leaf | 1 |
| 20 | [Calculating Clos Fabric Limits](https://www.youtube.com/watch?v=j7mGuIrsU1k) | [20-clos-limits](labs/20-clos-limits) - calculator + incast | 1 |
| 21 | [Why ECMP Algorithm is Critical](https://www.youtube.com/watch?v=LKp1RzZRMDg) | [21-ecmp](labs/21-ecmp) - hash policies, resilient groups | 2 |
| 22 | [High-Level Approach to DC Design](https://www.youtube.com/watch?v=JtKccP5JYHI) | [22-design-your-fabric](labs/22-design-your-fabric) - design worksheet + generator | 1 |
| 23 | [Designing Underlay IP Connectivity](https://www.youtube.com/watch?v=wvRWIa6GK4s) | [23-underlay-ip-addressing](labs/23-underlay-ip-addressing) - numbered/unnumbered/v6/LLA | 4 |
| 24 | [Routing Protocol Options for Underlay](https://www.youtube.com/watch?v=JsiWm88AKLA) | [24-underlay-igp-options](labs/24-underlay-igp-options) - OSPFv2/v3, IS-IS | 3 |
| 25 | [eBGP as Underlay](https://www.youtube.com/watch?v=ty5JxLFjtJQ) | [25-ebgp-underlay](labs/25-ebgp-underlay) - ASN schemes, unnumbered | 3 |
| 26 | [BGP Path Hunting, MRAI](https://www.youtube.com/watch?v=CA4kklcCeHk) | [26-bgp-path-hunting](labs/26-bgp-path-hunting) | 3 |
| 27 | [iBGP as Underlay](https://www.youtube.com/watch?v=jfGXKxvVfMg) | [27-ibgp-underlay](labs/27-ibgp-underlay) - RR, next-hop-self, router-id | 2 |
| 28 | [Mixed IPv4+IPv6 Underlay, RFC 5549/8950](https://www.youtube.com/watch?v=M__PhG_GMx8) | [28-mixed-underlay-rfc5549](labs/28-mixed-underlay-rfc5549) | 2 |
| 29 | [Designing EVPN Overlay. ASICs and limits](https://www.youtube.com/watch?v=jzDw9H-bM_Q) | [29-overlay-asic-limits](labs/29-overlay-asic-limits) - table scale | 2 |
| 30 | [Overlay Design for VM Mobility](https://www.youtube.com/watch?v=vgu2ZfYUYYM) | [30-vm-mobility](labs/30-vm-mobility) - MAC mobility, dup detection | 1 |
| 31 | [Overlay Design for Routing](https://www.youtube.com/watch?v=jRbyPlaTZyQ) | [31-overlay-routing-design](labs/31-overlay-routing-design) - host routes vs subnets | 2 |
| 32 | [Limiting host routes. RT Constraint](https://www.youtube.com/watch?v=lhVBoaH4Kxo) | [32-limit-host-routes-rtc](labs/32-limit-host-routes-rtc) | 3 |
| 33 | [Layer 3 Only Fabric with EVPN](https://www.youtube.com/watch?v=8tKi73LWPRM) | [33-l3-only-fabric](labs/33-l3-only-fabric) | 2 |
| 34 | [IPv6 Endpoints in EVPN](https://www.youtube.com/watch?v=miq6tTILvlU) | [34-ipv6-endpoints](labs/34-ipv6-endpoints) - dual stack, RA/SLAAC, ND suppression | 2 |
| 35 | [Multi-vendor EVPN using Arista and FRR](https://www.youtube.com/watch?v=576MaUMsmig) | [35-multivendor-frr](labs/35-multivendor-frr) - 4 underlay styles, IS-IS MTU trap | 5 |
| 36 | [Interconnecting multiple EVPN fabrics](https://www.youtube.com/watch?v=JMBQiF4DbNA) | [36-multi-fabric-basics](labs/36-multi-fabric-basics) | 1 |
| 37 | [DCI for EVPN Multi-Fabric: MTU, BUM, HA](https://www.youtube.com/watch?v=ulLjeL_tUts) | [37-multi-fabric-dci-ha](labs/37-multi-fabric-dci-ha) - redistribution oscillation | 3 |

## Conventions used everywhere

* **Addressing** (same as the videos): leafN loopback `N.N.N.N`, spineM loopback `(10+M)` x4 (`11.11.11.11`);
  leafN `eth(10+M)` <-> spineM `ethN` on `10.N.(10+M).0/24` (leaf `.N`, spine `.(10+M)`); AS 65000 unless
  the lab is about ASNs. Hosts `host1..` with MACs `00:aa:aa:..`, `00:bb:bb:..` ... so you can spot them in tables.
* **Interfaces**: `eth11`/`eth12` = leaf uplinks, `eth1..eth4` = server ports, `eth0` unused. GNS3 adapter N = `ethN`.
* **VLAN N <-> VNI 10000+N**, anycast gateway `.1` with MAC `00:00:5e:00:01:01`, L3VNI transit VLAN `4001`.
* **Router MAC** of each leaf = its `br0` MAC `44:38:39:ff:00:<leaf>`.
* Hosts use **MTU 1450** (VXLAN adds 50 bytes over 1500-byte GNS3 links).

## What each node script does (and where to look on a VM)

| file on the VM | content |
|---|---|
| `/etc/lab/net.sh` | all Linux networking: `ip link add ... type bridge/vxlan/vrf/bond/vlan`, `bridge vlan ...`, addresses, sysctls, `nft`, `tc` - read it, it's the Linux half of the lesson |
| `/etc/frr/frr.conf` | FRR config (`vtysh -c 'show running-config'`) |
| `/etc/lab/id` | which lab/variant/node is applied |
| `/var/log/lab-net.log` | output of net.sh (errors land here) |
| `lab-info` | one-screen summary: links, addresses, routes, BGP, VNIs |

Linux-for-EVPN mini cheat sheet:

```bash
ip -br link ; ip -br addr ; ip -d link show vxlan10010     # devices, VNI, local VTEP, neigh_suppress, learning
bridge vlan show                                         # VLAN membership per port (PVID = access VLAN)
bridge fdb show br br0 | grep -v permanent               # learnt + EVPN-installed MACs (extern_learn = from FRR)
bridge fdb show dev vxlan10010 | grep 00:00:00:00:00:00  # flood list (ingress replication)
ip neigh show vrf A ; ip route show vrf A                # tenant ARP / routing tables
ip nexthop show                                          # nexthop groups (EVPN-MH, ECMP)
vtysh -c 'show evpn vni' -c 'show evpn mac vni all' -c 'show evpn arp-cache vni all'
vtysh -c 'show bgp l2vpn evpn summary' -c 'show bgp l2vpn evpn route type macip'
tcpdump -ni eth11 -e udp port 4789                       # VXLAN on the wire
```

## Where FRR/Linux differs from the videos (and how the labs handle it)

| Video topic (Arista) | Linux/FRR reality | Lab |
|---|---|---|
| VLAN-aware bundle service | not implemented - FRR is VLAN-based only | 04 explains, shows the closest equivalent |
| OISM (EVPN route types 6/7/8) | not implemented | 10 builds OISM's data-plane model with pimd + nftables |
| Single-active multihoming | not implemented (all-active only) | 13 shows the failure mode with an active-backup host |
| BGP RT-Constraint (RFC 4684) | not implemented | 32 emulates it with RR outbound policies |
| Importing another VRF's EVPN routes by RT (different L3VNI) | Linux always encapsulates with the *local* VRF's L3VNI | 09/15 use FRR `import vrf` leaking on the border/service leaf instead |
| IPv6 VTEPs (`vxlan encapsulation ipv6`) | FRR >= 10.6 | 23/24/28/35 IPv6-core variants |
| EVPN gateways re-originating VXLAN (multi-site) | not implemented | 36 does end-to-end VXLAN between fabrics |

## How the labs were tested

Every lab is generated from Python (`tools/generator`) and was run in an automated harness before being
delivered: each VM became a Linux network namespace with veth links, the node scripts' `net.sh` and `frr.conf`
were applied unchanged, FRR was started per namespace, and the lab's automated checks (the same ones
`gns3_lab.py check` runs) had to pass. See [TESTING.md](TESTING.md) for per-lab results and the known gaps
(the harness ran FRR 8.4 on an Ubuntu 6.8 kernel; your VMs run newer FRR on Debian 13).

## Regenerating / customising

```bash
cd tools/generator
python build.py ../..            # rewrite every lab
python build.py ../.. 5 6        # only labs 05 and 06
```

Each lab is a function in `labs_*.py`; `gen.py` has the building blocks (`bridge()`, `vxlan()`, `svi()`,
`l3vni()`, `isis()`, `evpn_leaf_ibgp()` ...). Lab 22 is built around this: edit a design dict, get a lab.
