# Lab 03 - Handling BUM traffic in EVPN

**Video:** [Handling BUM traffic in EVPN](https://www.youtube.com/watch?v=r9W8o7jCNzE) (33 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/bum_with_her  

Broadcast, Unknown-unicast and Multicast (BUM) frames have to reach every VTEP in the VNI. EVPN
signals the flood list with **type-3 IMET** routes and the Linux vxlan device does **head-end
(ingress) replication** using all-zero FDB entries. Then **ARP/ND suppression** lets the local VTEP
answer ARP requests from the EVPN-learnt MAC+IP table so most broadcasts never leave the leaf.

## Topology

```
                spine1 (RR)
    /eth1     /eth2     \eth3    \eth4
 leaf1      leaf2      leaf3      leaf4        all VLAN 10 / VNI 10010
   |          |          |          |
 host1      host2      host3      host4
.10 aa     .20 bb     .30 cc     .40 dd        10.10.10.0/24
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| leaf4 | leaf | 4.4.4.4 |
| host1 | host | 10.10.10.10/24, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.10.10.20/24, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.10.10.30/24, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.10.10.40/24, 00:dd:dd:dd:dd:dd |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine1 | eth3 | leaf3 | eth11 |
| spine1 | eth4 | leaf4 | eth11 |
| leaf1 | eth1 | host1 | eth1 |
| leaf2 | eth1 | host2 | eth1 |
| leaf3 | eth1 | host3 | eth1 |
| leaf4 | eth1 | host4 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **her** *(default)* - head-end replication, no ARP suppression
- **arp-suppression** - head-end replication + ARP/ND suppression (+ SVI so the leaves learn host IPs)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\03-bum-traffic   # default variant: her
python tools\gns3_lab.py push labs\03-bum-traffic --variant arp-suppression   # switch variant in place
python tools\gns3_lab.py check labs\03-bum-traffic
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/her/` (see the top-level README).

## What you will learn

* EVPN **type-3 Inclusive Multicast Ethernet Tag (IMET)** routes = "I am a VTEP for VNI X, send me BUM".
* How Linux implements **head-end replication**: one `00:00:00:00:00:00 dst <vtep>` FDB entry per
  remote VTEP on the vxlan device; a broadcast is copied once per entry.
* How **ARP suppression** works on Linux: `neigh_suppress on` on the vxlan bridge port + FRR installing
  remote MAC+IP (type-2) as neighbor entries -> the bridge answers ARP locally.

## Step by step (variant `her`)

```bash
# leaf1
vtysh -c 'show bgp l2vpn evpn route type multicast'   # one IMET per VTEP: [3]:[0]:[32]:[x.x.x.x]
bridge fdb show dev vxlan10010 | grep 00:00:00:00:00:00
vtysh -c 'show evpn vni 10010'                         # remote VTEP list
```

Capture on leaf2/leaf3/leaf4 uplinks (`tcpdump -ni eth11 -e udp port 4789`) and from host1 run
`arping -c1 -I eth1 10.10.10.40`: **every** leaf receives a copy of the ARP broadcast, from source 1.1.1.1.
Count the copies leaving leaf1 on eth11: 3 - one per remote VTEP (that's the "head-end" cost).

Unknown unicast: on host1 `ip neigh replace 10.10.10.99 lladdr 00:12:34:56:78:9a dev eth1` and ping it - the frame is
flooded to all VTEPs because no VTEP advertised that MAC.

## Step by step (variant `arp-suppression`)

```bash
python tools\gns3_lab.py push labs\03-bum-traffic --variant arp-suppression
```

```bash
# leaf1
bridge -d link show dev vxlan10010 | grep -o 'neigh_suppress [a-z]*'
vtysh -c 'show evpn arp-cache vni 10010'      # IP->MAC from type-2 routes
ip neigh show                                  # (nothing on br0 - the bridge itself answers)
```

From host1 `ip neigh flush all; arping -c1 -I eth1 10.10.10.40` while capturing on leaf2..4 eth11:
the ARP request is **not** flooded anymore; leaf1's bridge replies with dd:dd:.. on behalf of host4.
(If a host was quiet for a long time its neighbor entry on its leaf may have been garbage-collected and the
type-2 route lost its IP - ping the gateway from it again.)

Important Linux detail: a VTEP can only suppress ARP for hosts it has a MAC+IP for, and a type-2 route carries
an IP only if the originating leaf knows it. On Linux, zebra learns a local host's IP from the **SVI's neighbor
table** - so the leaf needs an SVI in that VLAN (`vlan10`, here anycast 10.10.10.1 without any VRF) and the host
must ARP for it (hosts use it as their gateway and ping it once at boot). Without an SVI (variant `her`) the
type-2 routes are MAC-only and there is nothing to suppress with. Remote entries show up in
`ip neigh show dev vlan10` as `extern_learn` - that's what the bridge answers ARP requests from.

## Multicast underlay (theory / extra credit)

The video also covers **PIM-SM/BiDir/SSM underlay** for BUM. Linux can do it: create the vxlan device with
`group 239.1.1.10 dev <underlay-if>` instead of relying on the zero-MAC flood list, and run `pimd` in the
underlay (`ip pim` on fabric links and `lo`, RP on the spine). FRR supports this
("PIM-SM over VXLAN for BUM") but expect some fiddling; head-end replication is what nearly every
production EVPN data center uses.

## Things to break

* Remove the flood list on leaf1: `bridge fdb del 00:00:00:00:00:00 dev vxlan10010 dst 4.4.4.4` -> host1
  can't ARP host4 (in `her`), but can still ping it if the ARP entry already exists. FRR re-adds the entry
  when you `vtysh -c 'clear bgp l2vpn evpn *'`.
* `ip link set eth1 down` on leaf4 - leaf4 keeps advertising IMET (the VNI is still up) but host4's MAC is withdrawn.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant her*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.40` | ` 0% packet loss` |
| leaf1 | `bridge fdb show dev vxlan10010 \| grep 00:00:00:00:00:00` | `dst 2\.2\.2\.2[\s\S]*dst 3\.3\.3\.3[\s\S]*dst 4\.4\.4\.4\|dst 4\.4\.4\.4[\s\S]*dst 3\.3\.3\.3` |
| leaf1 | `vtysh -c 'show evpn vni 10010'` | `Number of Remote VTEPs: 3\|Remote VTEPs for this VNI:` |
| leaf1 | `bridge -d link show dev vxlan10010` | `neigh_suppress off` |

*variant arp-suppression*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.40` | ` 0% packet loss` |
| leaf1 | `bridge fdb show dev vxlan10010 \| grep 00:00:00:00:00:00` | `dst 2\.2\.2\.2[\s\S]*dst 3\.3\.3\.3[\s\S]*dst 4\.4\.4\.4\|dst 4\.4\.4\.4[\s\S]*dst 3\.3\.3\.3` |
| leaf1 | `vtysh -c 'show evpn vni 10010'` | `Number of Remote VTEPs: 3\|Remote VTEPs for this VNI:` |
| leaf1 | `bridge -d link show dev vxlan10010` | `neigh_suppress on` |
| host4 | `ping -c 2 -W 1 10.10.10.1` | ` 0% packet loss` |
| leaf1 | `vtysh -c 'show evpn arp-cache vni 10010'` | `10\.10\.10\.40\s+remote` |
| leaf1 | `ip neigh show dev vlan10` | `10\.10\.10\.40 lladdr 00:dd:dd:dd:dd:dd.*extern_learn` |

