# Lab 02 - Basic Bridging/Switching in EVPN

**Video:** [Basic Bridging/Switching in EVPN](https://www.youtube.com/watch?v=a4Lfu9x3eyY) (39 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/basic_bridging  

Your first EVPN-VXLAN fabric: one spine (BGP route reflector), two leaves (VTEPs), IS-IS underlay,
iBGP EVPN overlay and a single stretched VLAN 10 <-> VNI 10010. host1 and host2 sit in the same
subnet on different leaves and talk over VXLAN.

## Topology

```
             spine1  lo 11.11.11.11  (IS-IS + BGP RR, not a VTEP)
          eth1/      \eth2
10.1.11.0/24/          \10.2.11.0/24
     eth11 /              \ eth11
  leaf1 1.1.1.1         leaf2 2.2.2.2      <- VTEPs, AS 65000
     eth1|                  |eth1   (access VLAN 10 -> VNI 10010)
    host1                 host2
10.10.10.10/24         10.10.10.20/24
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| host1 | host | 10.10.10.10/24, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.10.10.20/24, 00:bb:bb:bb:bb:bb |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| leaf1 | eth1 | host1 | eth1 |
| leaf2 | eth1 | host2 | eth1 |

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\02-basic-bridging
python tools\gns3_lab.py check labs\02-basic-bridging
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/default/` (see the top-level README).

## What you will learn

* The Linux objects that make a VTEP: a VLAN-aware **bridge** (`br0`), a **vxlan** device per VNI,
  access ports with a PVID.
* Who does what: **the kernel forwards** (bridge FDB + vxlan), **FRR/zebra** watches the kernel
  (local MACs) and **bgpd** exchanges MACs as EVPN type-2 routes; remote MACs are written back into
  the kernel FDB.
* The underlay: IS-IS point-to-point between loopbacks; iBGP sessions loopback-to-loopback with the spine as RR.

## How the Linux side maps to the Arista config in the video

| Arista (video) | Linux / FRR (this lab) |
|---|---|
| `vlan 10` + `switchport access vlan 10` | `bridge vlan add dev eth1 vid 10 pvid untagged` |
| `interface Vxlan1` / `vxlan vlan 10 vni 10010` | `ip link add vxlan10010 type vxlan id 10010 local 1.1.1.1 dstport 4789 nolearning` + `bridge vlan add dev vxlan10010 vid 10 pvid untagged` |
| `vxlan source-interface Loopback0` | `local 1.1.1.1` on the vxlan device |
| `router bgp` / `vlan 10` / `redistribute learned` | `address-family l2vpn evpn` / `advertise-all-vni` |
| `rd auto`, `route-target both auto` | FRR default: RD = router-id:auto-index, RT = AS:VNI |
| `router isis` / `isis enable` | `router isis 1` + `ip router isis 1` on interfaces |

## Step by step

1. **Underlay first.** On leaf1: `vtysh -c 'show isis neighbor'`, `ip route` -> you must reach `2.2.2.2`
   and `11.11.11.11` via eth11 *before* anything else works: `ping -I 1.1.1.1 2.2.2.2`.
2. **BGP**: `vtysh -c 'show bgp l2vpn evpn summary'` on spine1 shows both leaves.
3. **Local learning**: ping from host1 to host2, then on leaf1:
   ```bash
   bridge fdb show br br0 | grep -i aa:aa         # learnt on eth1 by the kernel
   vtysh -c 'show evpn mac vni 10010'              # local + remote MACs
   vtysh -c 'show evpn vni detail'
   ```
4. **Routes**: `vtysh -c 'show bgp l2vpn evpn route'` - one type-3 (IMET) per VTEP and one type-2
   per MAC. Look at a route in detail: `vtysh -c 'show bgp l2vpn evpn route type macip detail'`
   -> RD, RT `65000:10010`, label = VNI 10010, next hop = remote loopback.
5. **Kernel result**: `bridge fdb show dev vxlan10010` -> `00:bb:.. dst 2.2.2.2 ... extern_learn`
   (FRR-installed) and `00:00:00:00:00:00 dst 2.2.2.2` (the BUM flood list - lab 03).
6. **Data plane**: on leaf1 `tcpdump -ni eth11 -e udp port 4789` while pinging. Copy the capture to
   your PC (or run `tshark -V`) to see outer IP 1.1.1.1 -> 2.2.2.2, UDP 4789, VXLAN header VNI 10010,
   inner Ethernet aa:aa -> bb:bb.

## Things to break

* `ip link set eth11 down` on leaf2: the IS-IS route to 2.2.2.2 disappears, the BGP session drops
  after the hold timer (datacenter defaults: 9 s) and all of leaf2's MACs are withdrawn.
* `bridge link set dev vxlan10010 learning on` and stop FRR on leaf1 (`systemctl stop frr`) - the
  data plane keeps working for a while from the FDB, but no new MACs are signalled.
* MTU: hosts use MTU 1450 because VXLAN adds 50 bytes. Set host1 eth1 to 1500 and run
  `ping -M do -s 1472 10.10.10.20` - it fails. Lab 37 revisits MTU in depth.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant default*

| node | command | expect |
|---|---|---|
| leaf1 | `vtysh -c 'show ip route isis'` | `2\.2\.2\.2/32` |
| leaf1 | `vtysh -c 'show bgp neighbor 11.11.11.11'` | `BGP state = Established` |
| host1 | `ping -c 3 -W 1 10.10.10.20` | ` 0% packet loss` |
| leaf1 | `vtysh -c 'show evpn mac vni 10010'` | `00:bb:bb:bb:bb:bb\s+remote\s+2\.2\.2\.2` |
| leaf1 | `bridge fdb show dev vxlan10010` | `00:bb:bb:bb:bb:bb.*extern_learn\|00:bb:bb:bb:bb:bb dst 2\.2\.2\.2` |
| leaf1 | `vtysh -c 'show bgp l2vpn evpn route type multicast'` | `\[3\]:\[0\]:\[32\]:\[2\.2\.2\.2\]` |

