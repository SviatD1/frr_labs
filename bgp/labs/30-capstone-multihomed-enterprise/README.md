# Lab 30 — Understanding and Mastering BGP - Complete BGP Course (capstone)

**Video:** [Understanding and Mastering BGP - Complete BGP Course (capstone)](https://www.youtube.com/watch?v=DIDex6WrX2E) (11:33)

A capstone that combines the whole playlist. Enterprise AS 100 (R1, R2) is multihomed to ISP-A
(AS 200: R3, R4) and ISP-B (AS 300: R5). Both ISPs reach a content provider, AS 400 (R6). Requirements:

1. ISP-A is primary for **outbound** traffic (LOCAL_PREF).
2. AS 100 must **never** be a transit between its ISPs (AS-path filter).
3. ISP-A is primary for **inbound** traffic too (AS_PATH prepending towards ISP-B).
4. If ISP-A fails, everything moves to ISP-B automatically, and back when it returns.

## What you will practise

- Combine iBGP + OSPF + eBGP in one design
- Implement primary/backup outbound and inbound
- Detect and fix a route leak
- Test failover and failback

## Topology

6 FRR routers, 2 Linux hosts.

```
         AS 100 (OSPF, iBGP lo-lo)       ISP-A AS 200 (iBGP)
+----+   +----+ 10.0.13 +----+ 10.0.34 +----+
| H1 |---| R1 |=========| R3 |---------| R4 |=====.
+----+   +----+         +----+         +----+      \ 10.0.46
           | 10.0.12                                 +----+   +----+
         +----+ 10.0.25 +----+ 10.0.56               | R6 |---| H6 |
         | R2 |=========| R5 |=======================+----+   +----+
         +----+         +----+                        AS 400
                      ISP-B AS 300
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | R3 eth0 | 10.0.13.0/24 |
| 3 | R2 eth1 | R5 eth0 | 10.0.25.0/24 |
| 4 | R3 eth1 | R4 eth0 | 10.0.34.0/24 |
| 5 | R4 eth1 | R6 eth0 | 10.0.46.0/24 |
| 6 | R5 eth1 | R6 eth1 | 10.0.56.0/24 |
| 7 | R1 eth2 | H1 eth0 | 192.168.1.0/24 |
| 8 | R6 eth2 | H6 eth0 | 192.168.6.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.13.1/24 | R3 |
| **R1** | 100 | eth2 | 192.168.1.1/24 | LAN H1 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.25.2/24 | R5 |
| **R3** | 200 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 200 | eth0 | 10.0.13.3/24 | R1 |
| **R3** | 200 | eth1 | 10.0.34.3/24 | R4 |
| **R4** | 200 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 200 | eth0 | 10.0.34.4/24 | R3 |
| **R4** | 200 | eth1 | 10.0.46.4/24 | R6 |
| **R5** | 300 | lo | 5.5.5.5/32 | loopback / router-id |
| **R5** | 300 | eth0 | 10.0.25.5/24 | R2 |
| **R5** | 300 | eth1 | 10.0.56.5/24 | R6 |
| **R6** | 400 | lo | 6.6.6.6/32 | loopback / router-id |
| **R6** | 400 | eth0 | 10.0.46.6/24 | R4 |
| **R6** | 400 | eth1 | 10.0.56.6/24 | R5 |
| **R6** | 400 | eth2 | 192.168.6.1/24 | LAN H6 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H6** | - | eth0 | 192.168.6.10/24 | R6 |
| **H6** | - | default gw | 192.168.6.1 | |

## Bring the lab up

```powershell
cd bgp\labs\30-capstone-multihomed-enterprise
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-30-capstone-multihomed-enterprise`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Survey the network

Check every session (`show bgp summary` on each router) and both paths. Right now each enterprise
router uses its own ISP (eBGP beats iBGP), and AS 400 picks whichever path to you it saw first.

**Verify:**

```
R2# show bgp ipv4 unicast 192.168.6.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.6.0/24, version 1
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  1.1.1.1 10.0.25.5
  200 400
    1.1.1.1 (metric 10) from 1.1.1.1 (1.1.1.1)
      Origin IGP, localpref 100, valid, internal
      Last update: Wed Oct 14 06:56:39 2026
  300 400
    10.0.25.5 from 10.0.25.5 (5.5.5.5)
      Origin IGP, valid, external, best (Peer Type)
      Last update: Wed Oct 14 06:56:20 2026
```

</details>

```
R6# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 2
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.46.4 10.0.56.5
  300 100
    10.0.56.5 from 10.0.56.5 (5.5.5.5)
      Origin IGP, valid, external
      Last update: Wed Oct 14 06:56:39 2026
  200 100
    10.0.46.4 from 10.0.46.4 (4.4.4.4)
      Origin IGP, valid, external, best (Older Path)
      Last update: Wed Oct 14 06:56:20 2026
```

</details>


### Step 2 — Requirement 1: outbound via ISP-A

Set LOCAL_PREF 200 on R1 for routes from ISP-A. R2 must now send its traffic via R1.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
route-map ISP-A-IN permit 10
 set local-preference 200
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.13.3 route-map ISP-A-IN in
end
```

On **R1** (`vtysh`):
```
clear bgp 10.0.13.3 soft in
```

</details>

**Verify:**

```
R2# show bgp ipv4 unicast 192.168.6.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.6.0/24, version 3
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.25.5
  200 400
    1.1.1.1 (metric 10) from 1.1.1.1 (1.1.1.1)
      Origin IGP, localpref 200, valid, internal, best (Local Pref)
      Last update: Wed Oct 14 06:56:40 2026
  300 400
    10.0.25.5 from 10.0.25.5 (5.5.5.5)
      Origin IGP, valid, external
      Last update: Wed Oct 14 06:56:20 2026
```

</details>


### Step 3 — Spot the route leak

Look at R5 (ISP-B). It now has **two** paths to AS 400, one of them `100 200 400`: through *you*.
R2's best path is the iBGP one via ISP-A, and R2 happily advertises it to ISP-B. If ISP-B preferred it,
you would be carrying traffic between your two providers on your own links.

**Verify:**

```
R5# show bgp ipv4 unicast 192.168.6.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.6.0/24, version 1
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.25.2 10.0.56.6
  100 200 400
    10.0.25.2 from 10.0.25.2 (2.2.2.2)
      Origin IGP, valid, external
      Last update: Wed Oct 14 06:56:40 2026
  400
    10.0.56.6 from 10.0.56.6 (6.6.6.6)
      Origin IGP, metric 0, valid, external, best (AS Path)
      Last update: Wed Oct 14 06:56:20 2026
```

</details>


### Step 4 — Requirement 2: no transit

On both border routers, only advertise routes that originate in AS 100 (empty AS_PATH, `^$`).

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
bgp as-path access-list OWN seq 5 permit ^$
route-map OWN-ONLY permit 10
 match as-path OWN
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.13.3 route-map OWN-ONLY out
end
```

On **R2** (`vtysh`):
```
configure terminal
bgp as-path access-list OWN seq 5 permit ^$
route-map OWN-ONLY permit 10
 match as-path OWN
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.25.5 route-map OWN-ONLY out
end
```

On **R1** (`vtysh`):
```
clear bgp * soft out
```

On **R2** (`vtysh`):
```
clear bgp * soft out
```

</details>

**Verify:**

```
R5# show bgp ipv4 unicast 192.168.6.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.6.0/24, version 1
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.25.2 10.0.56.6
  400
    10.0.56.6 from 10.0.56.6 (6.6.6.6)
      Origin IGP, metric 0, valid, external, best (First path received)
      Last update: Wed Oct 14 06:56:19 2026
```

</details>

```
R2# show bgp ipv4 unicast neighbors 10.0.25.5 advertised-routes
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 3, local router ID is 2.2.2.2, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.1.0/24   0.0.0.0                       100      0 i

Total number of prefixes 1
```

</details>


### Step 5 — Requirement 3: inbound via ISP-A

Make the path through ISP-B less attractive for the rest of the Internet: prepend twice on R2 towards R5.
R6 now sees `200 100` vs `300 100 100 100` and sends traffic for H1 via ISP-A.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
route-map OWN-ONLY permit 10
 set as-path prepend 100 100
end
```

On **R2** (`vtysh`):
```
clear bgp 10.0.25.5 soft out
```

</details>

**Verify:**

```
R6# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 2
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.46.4 10.0.56.5
  300 100 100 100
    10.0.56.5 from 10.0.56.5 (5.5.5.5)
      Origin IGP, valid, external
      Last update: Wed Oct 14 06:56:45 2026
  200 100
    10.0.46.4 from 10.0.46.4 (4.4.4.4)
      Origin IGP, valid, external, best (AS Path)
      Last update: Wed Oct 14 06:56:20 2026
```

</details>

```
root@H6:~# traceroute -n -w1 -q1 192.168.1.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.1.10 (192.168.1.10), 30 hops max, 60 byte packets
 1  192.168.6.1  0.286 ms
 2  10.0.46.4  0.240 ms
 3  10.0.34.3  0.224 ms
 4  10.0.13.1  0.208 ms
 5  *
 6  *
 7  *
 8  *
 9  *
10  *
11  *
12  *
13  *
14  *
15  *
16  *
17  *
18  *
19  *
20  *
21  192.168.1.10  0.086 ms
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.6.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.6.10 (192.168.6.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.024 ms
 2  10.0.13.3  0.010 ms
 3  10.0.34.4  0.008 ms
 4  10.0.46.6  0.009 ms
 5  192.168.6.10  0.008 ms
```

</details>


### Step 6 — Requirement 4: failover

Take the ISP-A link down on R1. Outbound: R2's own path via ISP-B becomes best. Inbound: R6 only has
the prepended path left. Both directions still work.

<details><summary>Show solution</summary>

On **R1** (Linux shell):
```bash
ip link set eth1 down
```

</details>

**Verify:**

```
root@H1:~# traceroute -n -w1 -q1 192.168.6.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.6.10 (192.168.6.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.028 ms
 2  10.0.12.2  0.009 ms
 3  10.0.25.5  0.009 ms
 4  10.0.56.6  0.009 ms
 5  192.168.6.10  0.008 ms
```

</details>

```
root@H6:~# traceroute -n -w1 -q1 192.168.1.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.1.10 (192.168.1.10), 30 hops max, 60 byte packets
 1  192.168.6.1  0.027 ms
 2  10.0.56.5  0.010 ms
 3  10.0.25.2  0.008 ms
 4  10.0.12.1  0.008 ms
 5  192.168.1.10  0.031 ms
```

</details>


### Step 7 — Failback

Bring the link back up. Within seconds everything returns to ISP-A.

<details><summary>Show solution</summary>

On **R1** (Linux shell):
```bash
ip link set eth1 up
```

</details>

**Verify:**

```
R1# show bgp summary
```
<details><summary>Expected output (captured from a test run)</summary>

```
IPv4 Unicast Summary (VRF default):
BGP router identifier 1.1.1.1, local AS number 100 vrf-id 0
BGP table version 6
RIB entries 3, using 576 bytes of memory
Peers 2, using 1448 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
2.2.2.2         4        100         7        10        0    0    0 00:00:16            0        2 N/A
10.0.13.3       4        200        20        23        0    0    0 00:00:03            1        1 N/A

Total number of neighbors 2
```

</details>

```
R2# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 5, local router ID is 2.2.2.2, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*>i192.168.1.0/24   1.1.1.1                  0    100      0 i
*>i192.168.6.0/24   1.1.1.1                       200      0 200 400 i
*                   10.0.25.5                              0 300 400 i

Displayed  2 routes and 3 total paths
```

</details>


## Extra challenges

1. Replace the prepending with a community that ISP-B honours (implement '300:80 = local-pref 80' on R5, as in lab 27).
2. Add inbound prefix-lists on R1 and R2 that reject your own prefix and RFC 1918 space from the ISPs (except what the lab needs).
3. Add `neighbor ... maximum-prefix 100` on the ISP sessions and think about what should happen if an ISP leaks a full table.
4. Add BFD (`neighbor 10.0.13.3 bfd`, bfdd is enabled in the base image) so failover no longer depends on interface state.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
