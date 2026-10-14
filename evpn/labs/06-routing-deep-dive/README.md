# Lab 06 - EVPN Routing Deep Dive: Route Types, Isolated VNIs, Inter-VRF Route Leaking

**Video:** [EVPN Routing Deep Dive: Route Types, Isolated VNIs, Inter-VRF Route Leaking](https://www.youtube.com/watch?v=Ntm772VEEdE) (49 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/routing_deep_dive  

Routing between a *stretched* subnet and an *isolated* one (a VNI that exists on a single leaf),
type-2 MAC/IP host routes vs type-5 IP-prefix routes, a second customer VRF and **inter-VRF route
leaking** with FRR's `import vrf`.

## Topology

```
                            spine1 (RR)
                 /eth1          |eth2          \eth3
             leaf1            leaf2             leaf3
              eth1             eth1          eth1      eth2
             host1            host2          host3     host4
VRF           A                 A              A         B
VLAN/VNI   10/10010         10/10010       30/10030  40/10040  (30 and 40 only on leaf3 = isolated)
         10.10.10.10      10.10.10.20    10.30.30.30 10.40.40.40
L3VNI: CUSTOMER_A 1000 (VLAN 4001), CUSTOMER_B 2000 (VLAN 4002)
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| host1 | host | 10.10.10.10/24, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.10.10.20/24, gw 10.10.10.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.30.30.30/24, gw 10.30.30.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.40.40.40/24, gw 10.40.40.1, 00:dd:dd:dd:dd:dd |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine1 | eth3 | leaf3 | eth11 |
| leaf1 | eth1 | host1 | eth1 |
| leaf2 | eth1 | host2 | eth1 |
| leaf3 | eth1 | host3 | eth1 |
| leaf3 | eth2 | host4 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **no-leak** - two VRFs fully isolated
- **leak** *(default)* - leaf3 leaks 10.40.40.0/24 into A and A's subnets into B (import vrf + route-maps)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\06-routing-deep-dive   # default variant: leak
python tools\gns3_lab.py push labs\06-routing-deep-dive --variant no-leak   # switch variant in place
python tools\gns3_lab.py check labs\06-routing-deep-dive
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/leak/` (see the top-level README).

## What you will learn

* **Stretched BD** (VNI 10010 on leaf1+leaf2) vs **isolated BD** (VNI 10030/10040 only on leaf3).
  Leaves without VNI 10030 cannot do asymmetric IRB to it - only symmetric IRB (L3VNI) works.
* How a route to a host in an isolated VNI is found: the type-2 MAC/IP route carries the L3VNI RT + RMAC,
  so leaf1 gets a /32. For hosts that never sent traffic (*silent hosts*) only the **type-5** subnet
  route (`redistribute connected` in the VRF) helps.
* Inter-VRF **route leaking** on FRR: `import vrf OTHER` (+ `import vrf route-map NAME`) in
  `address-family ipv4 unicast` of the VRF's BGP instance. Leaked routes keep their original next hop
  (an interface or L3VNI in the other VRF) and the kernel happily routes across VRFs. Leaked routes are
  re-advertised into EVPN as type-5 routes of the importing VRF - which is how leaf1/leaf2 learn about
  10.40.40.0/24 in VRF A without any leaking config of their own.

## Step by step

```bash
# leaf1
vtysh -c 'show bgp l2vpn evpn route type macip'     # host routes, with 2 labels when L3VNI exists
vtysh -c 'show bgp l2vpn evpn route type prefix'    # [5]:[0]:[24]:[10.30.30.0] etc.
vtysh -c 'show bgp vrf CUSTOMER_A ipv4 unicast'     # what got imported into the VRF
ip route show vrf CUSTOMER_A
```

* Ping host1 -> host3. Which route is used on leaf1, the /32 or the /24? (`ip route get vrf CUSTOMER_A 10.30.30.30`).
* **Silent host**: on leaf1 `ip route show vrf CUSTOMER_A 10.30.30.0/24` is the type-5 route. Add an
  extra IP on host3 (`ip addr add 10.30.30.31/24 dev eth1`) and ping it from host1 without sending
  anything from host3 first - the /24 carries the packet to leaf3, leaf3 ARPs, learns, advertises a /32.
  Then remove `redistribute connected` in CUSTOMER_A on leaf3 and repeat with `10.30.30.32`: it fails.

## Route leaking (variant `leak`)

```bash
vtysh -c 'show bgp vrf CUSTOMER_A ipv4 unicast 10.40.40.0/24'   # "Imported from ... vrf CUSTOMER_B"
ip route show vrf CUSTOMER_A 10.40.40.0/24                       # nexthop in another VRF
vtysh -c 'show bgp l2vpn evpn route type prefix'                 # is the leaked route re-advertised as type-5?
```

Questions to answer in the lab:

1. Leaking is configured on **leaf3 only**, and only for subnets. What would happen with unfiltered mutual
   `import vrf` on *every* leaf? Try it (add `import vrf CUSTOMER_B` to A and `import vrf CUSTOMER_A` to B on all
   three leaves, no route-maps) and look at `ip route show vrf CUSTOMER_A 10.10.10.10` on leaf1: host1's own /32
   comes back *through VRF B from a remote VTEP* (leaked -> advertised as type-5 -> imported -> leaked again).
   It is preferred over the local /24 (longest match) and traffic for a local host leaves the leaf. That is the
   route-leaking loop the video warns about; filters and a single leaking point avoid it.
2. Why is 10.30.30.0/24 in `A-SUBNETS`? (host4 in B must reach host3 too - remove it and test.)
3. The video's EVPN-native alternative is importing the other VRF's **RT** into the L3VNI
   (`route-target import 65000:2000` under `address-family l2vpn evpn` of CUSTOMER_A). Try it in `no-leak`:
   leaf1 installs the route, but Linux encapsulates with *A's* L3VNI (1000) and leaf3 delivers it into VRF A,
   where 10.40.40.0/24 does not exist. On Linux, leak locally instead.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant no-leak*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.30.30.30` | ` 0% packet loss` |
| leaf1 | `vtysh -c 'show bgp l2vpn evpn route type prefix'` | `\[5\]:\[0\]:\[24\]:\[10\.30\.30\.0\]` |
| host1 | `ping -c 2 -W 1 10.40.40.40` | `100% packet loss\|Unreachable` |

*variant leak*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.30.30.30` | ` 0% packet loss` |
| leaf1 | `vtysh -c 'show bgp l2vpn evpn route type prefix'` | `\[5\]:\[0\]:\[24\]:\[10\.30\.30\.0\]` |
| leaf1 | `ip route show vrf CUSTOMER_A 10.40.40.0/24` | `10\.40\.40\.0/24` |
| host1 | `ping -c 3 -W 1 10.40.40.40` | ` 0% packet loss` |
| host4 | `ping -c 3 -W 1 10.10.10.20` | ` 0% packet loss` |

