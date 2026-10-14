# Lab 23 — BGP - Understanding BGP Confederations

**Video:** [BGP - Understanding BGP Confederations](https://www.youtube.com/watch?v=__ZlyKm4du0) (7:51)

A **confederation** splits one AS into several private **sub-ASes**. Inside a sub-AS you run normal iBGP
(full mesh or RRs); between sub-ASes you run *confederation eBGP*, which behaves like eBGP for loop
prevention (sub-AS numbers are recorded in AS_PATH as `AS_CONFED_SEQUENCE`, shown in brackets) but like
iBGP for attributes (LOCAL_PREF, MED and NEXT_HOP are kept). The outside world sees only the
confederation identifier, AS 100.

This lab is pre-configured; you observe. Lab 24 has you build it.

## What you will practise

- Read `(65001)` sub-AS segments in AS_PATH
- See the sub-ASes hidden from AS 200
- See LOCAL_PREF and NEXT_HOP survive confed-eBGP

## Topology

5 FRR routers, 2 Linux hosts.

```
                   AS 100 = confederation of sub-AS 65001 and 65002 (OSPF inside)
         +-------- sub-AS 65001 --------+   +-------- sub-AS 65002 --------+
+----+   | +----+ 10.0.12 +----+        |   |    +----+ 10.0.34 +----+     |   +----+
| R5 |=====| R1 |---------| R2 |=============== | R3 |---------| R4 |---------| H4 |
+----+   | +----+  iBGP   +----+    10.0.23     +----+  iBGP   +----+     |   +----+
  |      +------------------------------+ confed-eBGP +------------------------+
+----+  AS 200 (sees only AS 100)
| H5 |
+----+
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R2 eth1 | R3 eth0 | 10.0.23.0/24 |
| 3 | R3 eth1 | R4 eth0 | 10.0.34.0/24 |
| 4 | R1 eth1 | R5 eth0 | 10.0.15.0/24 |
| 5 | R4 eth1 | H4 eth0 | 192.168.4.0/24 |
| 6 | R5 eth1 | H5 eth0 | 192.168.5.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.15.1/24 | R5 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.23.2/24 | R3 |
| **R3** | 100 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 100 | eth0 | 10.0.23.3/24 | R2 |
| **R3** | 100 | eth1 | 10.0.34.3/24 | R4 |
| **R4** | 100 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 100 | eth0 | 10.0.34.4/24 | R3 |
| **R4** | 100 | eth1 | 192.168.4.1/24 | LAN H4 |
| **R5** | 200 | lo | 5.5.5.5/32 | loopback / router-id |
| **R5** | 200 | eth0 | 10.0.15.5/24 | R1 |
| **R5** | 200 | eth1 | 192.168.5.1/24 | LAN H5 |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |
| **H5** | - | eth0 | 192.168.5.10/24 | R5 |
| **H5** | - | default gw | 192.168.5.1 | |

## Bring the lab up

```powershell
cd bgp\labs\23-confederations
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-23-confederations`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Inside: sub-AS numbers in brackets

R4 (sub-AS 65002) sees AS 200's LAN with AS_PATH `(65001) 200`: the route came from sub-AS 65001.
The bracketed part is AS_CONFED_SEQUENCE; it does not count for AS_PATH length in best-path selection.
Note that the next hop is still **1.1.1.1** (R1's next-hop-self), unchanged across the sub-AS border.

**Verify:**

```
R4# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 2
Paths: (1 available, best #1, table default)
  Not advertised to any peer
  (65001) 200
    1.1.1.1 (metric 30) from 3.3.3.3 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, confed-internal, best (First path received)
      Last update: Wed Oct 14 06:53:35 2026
```

</details>

```
R2# show bgp summary
```
<details><summary>Expected output (captured from a test run)</summary>

```
IPv4 Unicast Summary (VRF default):
BGP router identifier 2.2.2.2, local AS number 65001 vrf-id 0
BGP table version 2
RIB entries 3, using 576 bytes of memory
Peers 2, using 1448 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
1.1.1.1         4      65001         4         4        0    0    0 00:00:02            1        1 N/A
10.0.23.3       4      65002         5         6        0    0    0 00:00:21            1        2 N/A

Total number of neighbors 2
```

</details>


### Step 2 — Outside: only AS 100

AS 200 has a normal eBGP session with "AS 100" and sees R4's LAN with AS_PATH `100`. The sub-ASes are
stripped at the confederation edge.

**Verify:**

```
R5# show bgp summary
```
<details><summary>Expected output (captured from a test run)</summary>

```
IPv4 Unicast Summary (VRF default):
BGP router identifier 5.5.5.5, local AS number 200 vrf-id 0
BGP table version 2
RIB entries 3, using 576 bytes of memory
Peers 1, using 724 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
10.0.15.1       4        100         5         5        0    0    0 00:00:21            1        2 N/A

Total number of neighbors 1
```

</details>

```
R5# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 2
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.15.1
  100
    10.0.15.1 from 10.0.15.1 (1.1.1.1)
      Origin IGP, valid, external, best (First path received)
      Last update: Wed Oct 14 06:53:36 2026
```

</details>

```
root@H5:~# traceroute -n -w1 -q1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 30 hops max, 60 byte packets
 1  192.168.5.1  0.054 ms
 2  10.0.15.1  0.013 ms
 3  10.0.12.2  0.012 ms
 4  10.0.23.3  0.011 ms
 5  10.0.34.4  0.009 ms
 6  192.168.4.10  0.010 ms
```

</details>


### Step 3 — LOCAL_PREF crosses sub-AS boundaries

On R1, set LOCAL_PREF 300 for routes from AS 200. With real eBGP it would stop at R2's border; inside a
confederation it reaches R4.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
route-map FROM-AS200 permit 10
 set local-preference 300
router bgp 65001
 address-family ipv4 unicast
  neighbor 10.0.15.5 route-map FROM-AS200 in
end
```

On **R1** (`vtysh`):
```
clear bgp 10.0.15.5 soft in
```

</details>

**Verify:**

```
R4# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 3
Paths: (1 available, best #1, table default)
  Not advertised to any peer
  (65001) 200
    1.1.1.1 (metric 30) from 3.3.3.3 (3.3.3.3)
      Origin IGP, metric 0, localpref 300, valid, confed-internal, best (First path received)
      Last update: Wed Oct 14 06:53:37 2026
```

</details>


## Extra challenges

1. Remove `bgp confederation peers 65002` on R2. What does R2 now think AS 65002 is, and what does R3/R4 see in the AS_PATH?
2. Why do big networks combine confederations with route reflectors inside each sub-AS?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
