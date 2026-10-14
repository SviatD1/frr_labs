# Lab 05 - Basic routing in EVPN: VRFs, Anycast Gateway, Asymmetric and Symmetric IRB

**Video:** [Basic routing in EVPN: VRFs, Anycast Gateway, Asymmetric and Symmetric IRB](https://www.youtube.com/watch?v=AJc1dd6_gBg) (32 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/basic_routing  

Add routing to the fabric: a tenant VRF, **anycast gateway** SVIs (same IP and MAC on every leaf) and the
two IRB models. *Asymmetric* IRB routes on the ingress leaf and bridges in the destination VNI (every
leaf needs every VLAN). *Symmetric* IRB routes on both leaves through an **L3VNI** using the remote
leaf's router MAC (RMAC).

## Topology

```
                spine1 (RR)
            eth1/       \eth2
          leaf1           leaf2         VRF CUSTOMER_A, anycast GW 10.10.10.1 / 10.20.20.1
       eth1  eth2      eth1  eth2       MAC 00:00:5e:00:01:01 on every leaf
      host1  host2    host3  host4
 VLAN  10     20       10     20
10.10.10.10 10.20.20.20 10.10.10.30 10.20.20.40
                          symmetric only: L3VNI 1000 (VLAN 4001)
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
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
| leaf1 | eth1 | host1 | eth1 |
| leaf1 | eth2 | host2 | eth1 |
| leaf2 | eth1 | host3 | eth1 |
| leaf2 | eth2 | host4 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **asymmetric** - SVIs on every leaf, no L3VNI
- **symmetric** *(default)* - SVIs + L3VNI 1000 (router MAC, type-2 with two labels)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\05-basic-routing-irb   # default variant: symmetric
python tools\gns3_lab.py push labs\05-basic-routing-irb --variant asymmetric   # switch variant in place
python tools\gns3_lab.py check labs\05-basic-routing-irb
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/symmetric/` (see the top-level README).

## What you will learn

* Linux **VRF** devices (`ip link add CUSTOMER_A type vrf table 1001`) and enslaving SVIs to them.
* **Anycast gateway**: every leaf has `vlan10` = 10.10.10.1 with MAC `00:00:5e:00:01:01`. Linux needs one
  extra trick for a VLAN device whose MAC differs from the bridge: a local FDB entry
  `bridge fdb replace 00:00:5e:00:01:01 dev br0 vlan 10 self local` so frames to that MAC are delivered up
  to the SVI.
* **Asymmetric IRB**: leaf1 routes 10.10.10.10 -> 10.20.20.40 into vlan20 *locally*, resolves host4's
  MAC from an ARP entry that FRR installed from host4's type-2 MAC+IP route, then bridges over VNI 10020.
  Return traffic is routed on leaf2 and bridged over VNI 10010 - different VNIs each way, hence "asymmetric".
* **Symmetric IRB**: both directions use the **L3VNI 1000**. leaf1 installs `10.20.20.40/32 via 2.2.2.2 dev vlan4001 onlink`,
  the inner destination MAC is leaf2's **router MAC** (its `br0`/`vlan4001` MAC, carried in the
  *Router's MAC* extended community).

## Why the hosts ping their gateway every 20 s

Every host in these labs runs a tiny keepalive (`lab-gw-keepalive-<host>`, started by its net.sh) that pings
its default gateway. Real servers talk constantly; lab hosts are silent - and a silent host is invisible to
EVPN routing on Linux:

* zebra learns a local host's **IP** only from the neighbor (ARP/ND) table of the SVI;
* if leaf1 itself has to ARP for host4 (10.20.20.40), the request leaves with the **anycast** source
  10.20.20.1 / `00:00:5e:00:01:01`. host4 replies to that MAC - and leaf2, which owns the same anycast MAC,
  swallows the reply. leaf1's entry stays `FAILED`.

Once host4 has ARPed *its* gateway (leaf2), leaf2 advertises a type-2 MAC+IP route and leaf1 installs the
neighbor entry (`extern_learn`) - no ARP needed. Kill the keepalive on host4
(`pkill -f lab-gw-keepalive`), flush leaf2's entry (`ip neigh flush dev vlan20`) and watch the asymmetric
variant break. (Production fabrics use the same trick: Cumulus/SONiC refresh neighbor entries periodically,
and Arista sends ARP from a unique per-leaf address.)

## Linux objects for symmetric IRB

```text
CUSTOMER_A (vrf, table 1001)
 ├─ vlan10   10.10.10.1/24  (anycast)      br0 vid 10   <-> vxlan10010
 ├─ vlan20   10.20.20.1/24  (anycast)      br0 vid 20   <-> vxlan10020
 └─ vlan4001 (no IP, MAC = RMAC)           br0 vid 4001 <-> vxlan1000  (L3VNI)
```

FRR side: `vrf CUSTOMER_A / vni 1000` and `router bgp 65000 vrf CUSTOMER_A / address-family l2vpn evpn / advertise ipv4 unicast`.

## Step by step

Push `asymmetric` first:

```bash
python tools\gns3_lab.py push labs\05-basic-routing-irb --variant asymmetric
```

```bash
# leaf1
ip -br link show master CUSTOMER_A
ip route show vrf CUSTOMER_A                        # only connected subnets!
ip neigh show vrf CUSTOMER_A                        # remote hosts appear as neighbors (from EVPN)
vtysh -c 'show evpn arp-cache vni 10020'
```

Ping host1 -> host4 and capture on leaf1 eth11: the VXLAN packet carries **VNI 10020** (destination VLAN).
Capture leaf2 eth11 on the return path: **VNI 10010**.

Then push `symmetric`:

```bash
# leaf1
vtysh -c 'show evpn vni'                 # L2 and L3 VNIs
vtysh -c 'show evpn rmac vni all'        # remote router MACs
vtysh -c 'show evpn next-hops vni all'
vtysh -c 'show bgp l2vpn evpn route type macip detail'   # two labels: 10020 and 1000, RT 65000:1000 + Rmac
ip route show vrf CUSTOMER_A             # 10.20.20.40 via 2.2.2.2 dev vlan4001 proto bgp onlink
ip neigh show dev vlan4001               # 2.2.2.2 lladdr <leaf2 RMAC> extern_learn
```

Capture: now both directions use **VNI 1000** and the inner destination MAC is the remote RMAC
(`44:38:39:ff:00:02` for leaf2).

## Things to try

* In `symmetric`, remove VLAN 20 from leaf1 entirely (`ip link del vlan20; ip link del vxlan10020`).
  host1 still reaches host4 - with symmetric IRB a leaf only needs the VLANs it has hosts in.
  Do the same in `asymmetric` and it breaks.
* Look at the type-5 routes too: `redistribute connected` in the VRF advertises 10.10.10.0/24 and
  10.20.20.0/24 as **type-5 IP prefix** routes (`show bgp l2vpn evpn route type prefix`). Lab 06 uses them.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant asymmetric*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.20.40` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.10.10.30` | ` 0% packet loss` |
| host1 | `ping -c 2 -W 1 10.10.10.1` | ` 0% packet loss` |
| leaf1 | `ip neigh show vrf CUSTOMER_A 10.20.20.40` | `lladdr 00:dd:dd:dd:dd:dd` |

*variant symmetric*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.20.40` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.10.10.30` | ` 0% packet loss` |
| host1 | `ping -c 2 -W 1 10.10.10.1` | ` 0% packet loss` |
| leaf1 | `vtysh -c 'show evpn vni 1000'` | `Type: L3\|L3` |
| leaf1 | `ip route show vrf CUSTOMER_A 10.20.20.40` | `via 2\.2\.2\.2 dev vlan4001` |
| leaf1 | `vtysh -c 'show evpn rmac vni all'` | `2\.2\.2\.2` |

