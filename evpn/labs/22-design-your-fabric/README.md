# Lab 22 - High-Level Approach to Designing Data Center Networks

**Video:** [High-Level Approach to Designing Data Center Networks](https://www.youtube.com/watch?v=JtKccP5JYHI) (12 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  

Design starts from requirements, not from someone else's config. This lab is a **design worksheet plus a
config generator**: you write the decisions down (`design.py`), the generator renders a complete GNS3 lab
(underlay, overlay, VLANs, VRF, hosts) from them. Change a decision, regenerate, compare.

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| leaf4 | leaf | 4.4.4.4 |
| host1 | host | 10.10.10.101/24, gw 10.10.10.1, 00:00:00:00:01:01 |
| host2 | host | 10.20.20.102/24, gw 10.20.20.1, 00:00:00:00:02:02 |
| host3 | host | 10.10.10.103/24, gw 10.10.10.1, 00:00:00:00:03:03 |
| host4 | host | 10.20.20.104/24, gw 10.20.20.1, 00:00:00:00:04:04 |

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
| leaf2 | eth1 | host2 | eth1 |
| leaf3 | eth1 | host3 | eth1 |
| leaf4 | eth1 | host4 | eth1 |

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\22-design-your-fabric
python tools\gns3_lab.py check labs\22-design-your-fabric
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/default/` (see the top-level README).

## The worksheet (from the video)

Answer these *before* touching a config. Write the answers next to the matching key in `design.py`.

| Question | Typical options | Drives |
|---|---|---|
| Business goal - what must the network enable? | VM mobility, bare-metal K8s, AI/storage, multi-tenant | everything below |
| How many servers / racks today, in 3 years? | | leaves, spines, 3- vs 5-stage (labs 18-20) |
| Server NIC speed, dual-homing? | 25/100G, LACP/EVPN-MH | leaf model, MH (labs 11-13) |
| Do workloads need L2 stretched? | yes/no/some | L2VNI vs L3-only (lab 33) |
| Tenants / VRFs, inter-VRF policy? | | VRFs, service insertion (labs 14-16) |
| External connectivity | BGP/OSPF, how many borders | labs 07-09 |
| Underlay protocol | IS-IS / OSPF / eBGP / iBGP | labs 23-28 |
| Addressing | numbered /31, unnumbered, IPv6 LLA | lab 23 |
| Overlay control plane | iBGP+RR / eBGP | labs 25-27, 29-32 |
| Automation, monitoring, vendor diversity | | lab 35 |

RFC 7938 ("Use of BGP for Routing in Large-Scale Data Centers") is a great example of a design document that
starts from requirements and explains each trade-off - read it once.

## Use the generator

```powershell
cd evpn\labs\22-design-your-fabric
notepad design.py          # change spines/leaves/underlay/VLANs/...
python design.py           # -> labs\22-design-your-fabric-custom\
python ..\..\tools\gns3_lab.py up ..\22-design-your-fabric-custom
```

The prebuilt default (this folder) is 2 spines, 4 leaves, IS-IS, VLAN 10/20, VRF PROD with symmetric IRB.
The generator code lives in `tools/generator/` - it's the same code that produced every lab in this course,
so it is also a reference for "how would I template this?".

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant default*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.10.10.1` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.20.20.102` | ` 0% packet loss` |

