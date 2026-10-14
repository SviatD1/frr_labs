# VXLAN with Linux + FRR — a GNS3 lab per video

Hands-on companion to the telecomTech YouTube playlist **"VXLAN"** (15 videos):
https://www.youtube.com/playlist?list=PLmVr8r1kmMm1LucO47Ch5CDJWgBb2X6YE

The videos use Cisco Nexus. Every lab here rebuilds the same idea with **Linux VMs as hosts** and **Linux VMs running FRR as routers/VTEPs**, so you learn Linux networking (iproute2, bridges, vxlan devices, VRFs), FRR (OSPF, PIM, MSDP, BGP EVPN) and VXLAN at the same time. Labs that mirror a Nexus config include an NX-OS ↔ Linux/FRR translation table.

**Start with [`00-setup/README.md`](00-setup/README.md)** — one Debian 12 template for every node, interface/addressing conventions, how to run a lab.

## Video → lab map

| # | Video | Lab | What you build | Tested |
|---|---|---|---|---|
| 1 | What is VXLAN? | [lab01-what-is-vxlan](lab01-what-is-vxlan/) | 2 VTEPs over a routed OSPF core, one point-to-point VNI | ✅ |
| 2 | VNIs, VTEPs, and VXLAN Architecture | [lab02-vnis-vteps](lab02-vnis-vteps/) | 3 VTEPs, 2 VNIs with overlapping tenant IPs, head-end replication | ✅ |
| 3 | Encapsulation, Headers, and the Packet Transmission Process | [lab03-encapsulation](lab03-encapsulation/) | Packet walk in Wireshark, the 50-byte MTU problem | ✅ |
| 4 | Control Plane Operations | [lab04-flood-and-learn](lab04-flood-and-learn/) | Flood & learn: watch MAC→VTEP learning and ageing | ✅ |
| 5 | Basic Configuration on Cisco Nexus Switches | [lab05-basic-config-vlan-to-vni](lab05-basic-config-vlan-to-vni/) | VLAN-aware bridge, VLAN→VNI mapping, static ingress replication | ⚠️ |
| 6 | Spine and Leaf Architecture | [lab06-spine-leaf](lab06-spine-leaf/) | 2 spines / 3 leaves, OSPF ECMP, BFD failover, VXLAN entropy | ✅ |
| 7 | Understanding the Multicast Underlay | [lab07-multicast-underlay](lab07-multicast-underlay/) | VNI→group, IGMP joins, PIM-SM RP, (*,G)/(S,G) | ✅ |
| 8 | Multicast Underlay Configuration on Cisco Nexus | [lab08-multicast-config](lab08-multicast-config/) | Two PIM routers, register/SPT, two VNIs → two groups | ✅ |
| 9 | Multicast Anycast RP Underlay Solution | [lab09-anycast-rp](lab09-anycast-rp/) | Anycast RP on both spines + MSDP mesh-group | ✅ |
| 10 | Understanding the MP-BGP EVPN Underlay | [lab10-bgp-evpn-l2](lab10-bgp-evpn-l2/) | iBGP EVPN with RR spines, type-2/type-3 routes, RD/RT | ✅ |
| 11 | Understanding MP-BGP EVPN Layer 3 Operation | [lab11-evpn-l3-operation](lab11-evpn-l3-operation/) | Symmetric IRB, L3VNI, RMAC, type-5, border leaf + external router | ⚠️ |
| 12 | Configuring MP-BGP EVPN for L2 VNIs on Cisco Nexus | [lab12-evpn-l2vni-config](lab12-evpn-l2vni-config/) | VLAN-aware EVPN, explicit RD/RT, trunk/access, ARP suppression | ⚠️ |
| 13 | Configuring MP-BGP EVPN for L3 VNIs on Cisco Nexus | [lab13-evpn-l3vni-config](lab13-evpn-l3vni-config/) | Two tenants (RED/BLUE), two L3VNIs, isolation, route leaking | ⚠️ |
| 14 | EVPN Anycast Distributed Gateway | [lab14-anycast-gateway](lab14-anycast-gateway/) | Same gateway IP+MAC on every leaf, host mobility, MAC mobility seq | ⚠️ |
| 15 | Integrated Routing and Bridging | [lab15-irb](lab15-irb/) | Asymmetric vs symmetric IRB side by side | ⚠️ |

✅ = brought up end-to-end with FRR 8.4.4 (the Debian 12 version) in Linux network namespaces using these exact scripts; every verification in the README was checked.
⚠️ = scripts and every FRR config validated (`bash -n`, `vtysh --dryrun`), built from standard FRR EVPN patterns, but not run end-to-end because the test kernel lacked VRF / VLAN-filtering support. Your Debian VMs have both. If something misbehaves there, `vtysh -c 'show evpn vni'`, `show vrf vni` and `journalctl -u frr` are the first places to look.

## Suggested path

- **Week 1 — data plane** (labs 01–04): what a VTEP really is in Linux, packets, flooding, learning.
- **Week 2 — fabric** (05–06): VLAN mapping, spine-leaf, ECMP.
- **Week 3 — multicast** (07–09): optional for EVPN-only designs, but great PIM practice.
- **Week 4+ — EVPN** (10–15): the modern way; do 10 → 12 → 11 → 13 → 14 → 15 if you prefer config before theory.

Each lab README follows the same shape: concept → topology → build → verify (with expected output) → experiments → break/fix → questions. Do the break/fix tables — that's where it sticks.

## Layout

```
vxlan/
  00-setup/   prep-node.sh (template), apply-frr.sh, persist.sh, README.md
  labNN-*/    README.md, topology.txt, nodes/<node>.sh, nodes/<node>.frr.conf
```

Generated configs share one addressing plan (00-setup §3), so `show` output looks the same from lab to lab and differences are always the thing being taught.
