# Lab 20 — BGP - Understanding the iBGP Split-Horizon Rule

**Video:** [BGP - Understanding the iBGP Split-Horizon Rule](https://www.youtube.com/watch?v=lBWXBvyr6_Y) (9:45)

The iBGP split-horizon rule: **routes learned from an iBGP peer are not advertised to other iBGP peers**
(they *are* advertised to eBGP peers). Here four routers in AS 100 are cabled in a ring and the iBGP
sessions follow the ring, which looks reasonable but fails: R3, two iBGP hops from the border, never
learns external routes. Then you check which sessions a full mesh needs.

## What you will practise

- Apply the split-horizon rule by hand and predict who learns what
- Compare `advertised-routes` towards iBGP and eBGP peers
- Turn a ring of sessions into a full mesh (6 sessions for 4 routers)

## Topology

5 FRR routers, 2 Linux hosts.

```
                     AS 100 (OSPF on the ring + loopbacks)
+----+   +----+ 10.0.15 +----+ 10.0.12 +----+
| H5 |---| R5 |=========| R1 |---------| R2 |
+----+   +----+         +----+         +----+
         AS 200   10.0.14 |              | 10.0.23
                        +----+ 10.0.34 +----+   +----+
                        | R4 |---------| R3 |---| H3 |
                        +----+         +----+   +----+
iBGP at start: R1-R2, R2-R3, R3-R4, R4-R1 (follows the ring)
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R2 eth1 | R3 eth0 | 10.0.23.0/24 |
| 3 | R3 eth1 | R4 eth0 | 10.0.34.0/24 |
| 4 | R1 eth1 | R4 eth1 | 10.0.14.0/24 |
| 5 | R1 eth2 | R5 eth0 | 10.0.15.0/24 |
| 6 | R3 eth2 | H3 eth0 | 192.168.3.0/24 |
| 7 | R5 eth1 | H5 eth0 | 192.168.5.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.14.1/24 | R4 |
| **R1** | 100 | eth2 | 10.0.15.1/24 | R5 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.23.2/24 | R3 |
| **R3** | 100 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 100 | eth0 | 10.0.23.3/24 | R2 |
| **R3** | 100 | eth1 | 10.0.34.3/24 | R4 |
| **R3** | 100 | eth2 | 192.168.3.1/24 | LAN H3 |
| **R4** | 100 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 100 | eth0 | 10.0.34.4/24 | R3 |
| **R4** | 100 | eth1 | 10.0.14.4/24 | R1 |
| **R5** | 200 | lo | 5.5.5.5/32 | loopback / router-id |
| **R5** | 200 | eth0 | 10.0.15.5/24 | R1 |
| **R5** | 200 | eth1 | 192.168.5.1/24 | LAN H5 |
| **H3** | - | eth0 | 192.168.3.10/24 | R3 |
| **H3** | - | default gw | 192.168.3.1 | |
| **H5** | - | eth0 | 192.168.5.10/24 | R5 |
| **H5** | - | default gw | 192.168.5.1 | |

## Bring the lab up

```powershell
cd bgp\labs\20-ibgp-split-horizon
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-20-ibgp-split-horizon`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Predict, then check

Before looking, write down for each router whether it will have 192.168.5.0/24 (from AS 200 via R1)
and 192.168.3.0/24 (originated by R3).

* R1 learns 192.168.5.0/24 via **eBGP** → sends it to iBGP peers R2 and R4.
* R2 and R4 learned it via **iBGP** → do *not* send it to R3.
* R3's LAN goes to R2 and R4, which do not pass it to R1, so AS 200 never learns it.

**Verify:**

```
R3# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 1, local router ID is 3.3.3.3, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.3.0/24   0.0.0.0                  0         32768 i

Displayed  1 routes and 1 total paths
```

</details>

```
R2# show bgp ipv4 unicast neighbors 3.3.3.3 advertised-routes
```

*(No output: R2 learned 192.168.5.0/24 over iBGP, so it does not send it to its iBGP peer R3.)*
```
R1# show bgp ipv4 unicast neighbors 10.0.15.5 advertised-routes
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 1, local router ID is 1.1.1.1, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.5.0/24   0.0.0.0                                0 200 i

Total number of prefixes 1
```

</details>


### Step 2 — Why the rule exists

Imagine R2 *did* re-advertise to R3, R3 to R4 and R4 back to R1. The AS_PATH never changes
inside AS 100 (it is still `200`), so nobody could tell the route had gone round in a circle.
The split-horizon rule makes such loops impossible, at the price of needing direct sessions.

### Step 3 — Build the full mesh

4 routers → 4·3/2 = **6** sessions. Add the two diagonals: R1-R3 and R2-R4 (the TCP sessions are
routed over the ring by OSPF; they need no direct cable).

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 neighbor 3.3.3.3 remote-as 100
 neighbor 3.3.3.3 update-source lo
 address-family ipv4 unicast
  neighbor 3.3.3.3 next-hop-self
end
```

On **R3** (`vtysh`):
```
configure terminal
router bgp 100
 neighbor 1.1.1.1 remote-as 100
 neighbor 1.1.1.1 update-source lo
end
```

On **R2** (`vtysh`):
```
configure terminal
router bgp 100
 neighbor 4.4.4.4 remote-as 100
 neighbor 4.4.4.4 update-source lo
end
```

On **R4** (`vtysh`):
```
configure terminal
router bgp 100
 neighbor 2.2.2.2 remote-as 100
 neighbor 2.2.2.2 update-source lo
end
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
BGP table version 2
RIB entries 3, using 576 bytes of memory
Peers 4, using 2896 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
2.2.2.2         4        100         3         4        0    0    0 00:00:04            0        1 N/A
3.3.3.3         4        100         4         4        0    0    0 00:00:02            1        1 N/A
4.4.4.4         4        100         3         4        0    0    0 00:00:09            0        1 N/A
10.0.15.5       4        200         5         5        0    0    0 00:00:23            1        2 N/A

Total number of neighbors 4
```

</details>

```
R3# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 2, local router ID is 3.3.3.3, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.3.0/24   0.0.0.0                  0         32768 i
*>i192.168.5.0/24   1.1.1.1                  0    100      0 200 i

Displayed  2 routes and 2 total paths
```

</details>

```
root@H3:~# traceroute -n -w1 -q1 192.168.5.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.5.10 (192.168.5.10), 30 hops max, 60 byte packets
 1  192.168.3.1  0.345 ms
 2  10.0.34.4  0.304 ms
 3  10.0.12.1  0.224 ms
 4  10.0.15.5  0.125 ms
 5  192.168.5.10  0.111 ms
```

</details>


## Extra challenges

1. Remove the R2-R3 and R3-R4 sessions but keep R1-R3. Does everything still work? Which sessions are actually needed for *these* two prefixes?
2. Make R2 a route reflector (lab 21/22) instead of adding diagonals. How many sessions do you need then?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
