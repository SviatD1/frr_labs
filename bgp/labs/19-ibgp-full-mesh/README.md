# Lab 19 — BGP - Why does iBGP require full mesh peering?

**Video:** [BGP - Why does iBGP require full mesh peering?](https://www.youtube.com/watch?v=03Gl1YGeZYc) (8:30)

eBGP prevents loops with AS_PATH. Inside an AS the AS_PATH does not change, so it cannot detect loops.
BGP solves this with a rule: **a route learned from an iBGP peer is never advertised to another iBGP peer.**
Consequence: every iBGP router must peer directly with every other one, a **full mesh** of n(n-1)/2 sessions,
or routes do not get everywhere.

## What you will practise

- See a route stop at the second iBGP hop
- Check what is (not) advertised with `advertised-routes`
- Complete the full mesh

## Topology

4 FRR routers, 2 Linux hosts.

```
                AS 100 (OSPF; iBGP only R1-R2 and R2-R3 at start)
+----+   +----+   +----+ 10.0.12 +----+ 10.0.23 +----+   +----+
| H4 |---| R4 |===| R1 |---------| R2 |---------| R3 |---| H3 |
+----+   +----+   +----+         +----+         +----+   +----+
         AS 200  10.0.14
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R2 eth1 | R3 eth0 | 10.0.23.0/24 |
| 3 | R1 eth1 | R4 eth0 | 10.0.14.0/24 |
| 4 | R3 eth1 | H3 eth0 | 192.168.3.0/24 |
| 5 | R4 eth1 | H4 eth0 | 192.168.4.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.14.1/24 | R4 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.23.2/24 | R3 |
| **R3** | 100 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 100 | eth0 | 10.0.23.3/24 | R2 |
| **R3** | 100 | eth1 | 192.168.3.1/24 | LAN H3 |
| **R4** | 200 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 200 | eth0 | 10.0.14.4/24 | R1 |
| **R4** | 200 | eth1 | 192.168.4.1/24 | LAN H4 |
| **H3** | - | eth0 | 192.168.3.10/24 | R3 |
| **H3** | - | default gw | 192.168.3.1 | |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |

## Bring the lab up

```powershell
cd bgp\labs\19-ibgp-full-mesh
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-19-ibgp-full-mesh`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Routes stop after one iBGP hop

R1 learns 192.168.4.0/24 via eBGP and passes it to R2 (iBGP). R2 learned it from an iBGP peer, so
it does **not** pass it on to R3. Likewise R3's LAN reaches R2 but never R1, so AS 200 never hears of it.

**Verify:**

```
R2# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 2, local router ID is 2.2.2.2, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*>i192.168.3.0/24   3.3.3.3                  0    100      0 i
*>i192.168.4.0/24   1.1.1.1                  0    100      0 200 i

Displayed  2 routes and 2 total paths
```

</details>

```
R2# show bgp ipv4 unicast neighbors 3.3.3.3 advertised-routes
```

*(No output: R2 sends nothing to R3, which is the point of this step.)*
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
root@H3:~# ping -c2 -W1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
PING 192.168.4.10 (192.168.4.10) 56(84) bytes of data.
From 192.168.3.1 icmp_seq=1 Destination Net Unreachable
From 192.168.3.1 icmp_seq=2 Destination Net Unreachable

--- 192.168.4.10 ping statistics ---
2 packets transmitted, 0 received, +2 errors, 100% packet loss, time 1030ms
```

</details>


### Step 2 — Complete the full mesh

Add the missing session R1 ↔ R3. Three routers need 3 sessions (n(n-1)/2). Now R3 learns the route
directly from R1, and R1 learns R3's LAN directly and passes it to AS 200 (eBGP).

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

</details>

**Verify:**

```
R3# show bgp summary
```
<details><summary>Expected output (captured from a test run)</summary>

```
IPv4 Unicast Summary (VRF default):
BGP router identifier 3.3.3.3, local AS number 100 vrf-id 0
BGP table version 2
RIB entries 3, using 576 bytes of memory
Peers 2, using 1448 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
1.1.1.1         4        100         4         4        0    0    0 00:00:03            1        1 N/A
2.2.2.2         4        100         3         5        0    0    0 00:00:08            0        1 N/A

Total number of neighbors 2
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
*>i192.168.4.0/24   1.1.1.1                  0    100      0 200 i

Displayed  2 routes and 2 total paths
```

</details>

```
root@H3:~# traceroute -n -w1 -q1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 30 hops max, 60 byte packets
 1  192.168.3.1  0.548 ms
 2  10.0.23.2  0.482 ms
 3  10.0.12.1  0.336 ms
 4  10.0.14.4  0.237 ms
 5  192.168.4.10  0.151 ms
```

</details>


### Step 3 — Do the maths

| Routers | Full-mesh sessions |
|---|---|
| 3 | 3 |
| 10 | 45 |
| 100 | 4950 |

Every new router means a new session on *every* existing router. Labs 21-26 cover the two fixes:
route reflectors and confederations.

## Extra challenges

1. Remove the R1-R2 session. Does R2 still forward traffic correctly? (It has no BGP route anymore, see lab 4's black hole.)
2. Why is AS_PATH not usable for loop detection inside an AS?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
