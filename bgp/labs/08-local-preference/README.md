# Lab 08 — BGP - What is the Local Preference BGP Attribute?

**Video:** [BGP - What is the Local Preference BGP Attribute?](https://www.youtube.com/watch?v=n-CYvVm8aUI) (7:15)

**LOCAL_PREF** is shared by all routers in an AS (sent over iBGP, never over eBGP), default 100,
higher is better, compared right after weight. It is *the* tool to choose which exit (which ISP)
your whole AS uses for outbound traffic.

AS 100 has two border routers: R1 connects to ISP AS 200, R2 connects to ISP AS 300. Both ISPs
reach the destination AS 400.

## What you will practise

- Run iBGP between loopbacks with OSPF underneath
- Set LOCAL_PREF inbound on one border router and see the whole AS follow
- Test failover to the backup exit
- See that LOCAL_PREF does not influence inbound traffic

## Topology

5 FRR routers, 2 Linux hosts.

```
             AS 100                          ISPs                AS 400
+----+   +----+ 10.0.13/24  +----+ 10.0.35/24
| H1 |---| R1 |=============| R3 | AS 200 ======.
+----+   +----+             +----+               \  +----+   +----+
           | 10.0.12/24                            >| R5 |---| H5 |
           | iBGP lo-lo + OSPF                    / +----+   +----+
         +----+ 10.0.24/24  +----+ 10.0.45/24    /
         | R2 |=============| R4 | AS 300 ======'
         +----+             +----+
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | R3 eth0 | 10.0.13.0/24 |
| 3 | R2 eth1 | R4 eth0 | 10.0.24.0/24 |
| 4 | R3 eth1 | R5 eth0 | 10.0.35.0/24 |
| 5 | R4 eth1 | R5 eth1 | 10.0.45.0/24 |
| 6 | R1 eth2 | H1 eth0 | 192.168.1.0/24 |
| 7 | R5 eth2 | H5 eth0 | 192.168.5.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.13.1/24 | R3 |
| **R1** | 100 | eth2 | 192.168.1.1/24 | LAN H1 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.24.2/24 | R4 |
| **R3** | 200 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 200 | eth0 | 10.0.13.3/24 | R1 |
| **R3** | 200 | eth1 | 10.0.35.3/24 | R5 |
| **R4** | 300 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 300 | eth0 | 10.0.24.4/24 | R2 |
| **R4** | 300 | eth1 | 10.0.45.4/24 | R5 |
| **R5** | 400 | lo | 5.5.5.5/32 | loopback / router-id |
| **R5** | 400 | eth0 | 10.0.35.5/24 | R3 |
| **R5** | 400 | eth1 | 10.0.45.5/24 | R4 |
| **R5** | 400 | eth2 | 192.168.5.1/24 | LAN H5 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H5** | - | eth0 | 192.168.5.10/24 | R5 |
| **H5** | - | default gw | 192.168.5.1 | |

## Bring the lab up

```powershell
cd bgp\labs\08-local-preference
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-08-local-preference`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Each border router uses its own ISP

R1 has two paths to 192.168.5.0/24: its own eBGP path via R3, and the iBGP path from R2
(next hop 2.2.2.2). Everything else equal, **eBGP beats iBGP** (step 7). R2 does the same with
its own ISP. Traffic from H1 leaves via AS 200.

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 2
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  2.2.2.2 10.0.13.3
  300 400
    2.2.2.2 (metric 10) from 2.2.2.2 (2.2.2.2)
      Origin IGP, localpref 100, valid, internal
      Last update: Tue Oct 13 22:03:06 2026
  200 400
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin IGP, valid, external, best (Peer Type)
      Last update: Tue Oct 13 22:02:52 2026
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.5.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.5.10 (192.168.5.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.028 ms
 2  10.0.13.3  0.012 ms
 3  10.0.35.5  0.012 ms
 4  192.168.5.10  0.011 ms
```

</details>


### Step 2 — Make AS 300 the primary ISP with LOCAL_PREF

Policy: *all* outbound traffic should use AS 300 (it is cheaper). Configure only **R2**:
set local-preference 200 on routes received from R4. R2 advertises them to R1 with LOCAL_PREF 200,
and R1 now prefers the iBGP path (step 2 beats step 7). You never touched R1.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
route-map FROM-ISP300 permit 10
 set local-preference 200
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.24.4 route-map FROM-ISP300 in
end
```

On **R2** (`vtysh`):
```
clear bgp 10.0.24.4 soft in
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 3
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.13.3
  300 400
    2.2.2.2 (metric 10) from 2.2.2.2 (2.2.2.2)
      Origin IGP, localpref 200, valid, internal, best (Local Pref)
      Last update: Tue Oct 13 22:03:07 2026
  200 400
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin IGP, valid, external
      Last update: Tue Oct 13 22:02:51 2026
```

</details>

```
R1# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 3, local router ID is 1.1.1.1, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.1.0/24   0.0.0.0                  0         32768 i
*>i192.168.5.0/24   2.2.2.2                       200      0 300 400 i
*                   10.0.13.3                              0 200 400 i

Displayed  2 routes and 3 total paths
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.5.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.5.10 (192.168.5.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.039 ms
 2  10.0.12.2  0.011 ms
 3  10.0.24.4  0.013 ms
 4  10.0.35.5  0.016 ms
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
21  192.168.5.10  0.065 ms
```

</details>


### Step 3 — Why does R1 still keep only one path…?

Look at R2's table: R2 has only its own path. R1 stopped advertising its eBGP path to R2 because
R1's *best* is now the iBGP path, and BGP only advertises its best path (and never sends an
iBGP-learned path to another iBGP peer). The backup is still in R1's table though, which you test next.

**Verify:**

```
R2# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 3
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  1.1.1.1 10.0.24.4
  300 400
    10.0.24.4 from 10.0.24.4 (4.4.4.4)
      Origin IGP, localpref 200, valid, external, best (First path received)
      Last update: Tue Oct 13 22:03:07 2026
```

</details>


### Step 4 — Failover

Simulate the AS 300 link failing: shut R2's interface towards R4. R2 withdraws the LP 200 route,
R1 falls back to its eBGP path. Bring the link back afterwards.

<details><summary>Show solution</summary>

On **R2** (Linux shell):
```bash
ip link set eth1 down
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 4
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  2.2.2.2 10.0.13.3
  200 400
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin IGP, valid, external, best (First path received)
      Last update: Tue Oct 13 22:02:52 2026
```

</details>


### Step 5 — Restore and check the return path

Bring the link up again (`ip link set eth1 up` on R2; the session re-establishes in a few seconds).
Now traceroute from H5 to H1: AS 400 decides itself how to send traffic to you, and LOCAL_PREF in
AS 100 has no influence on it. Inbound traffic needs AS_PATH prepending (lab 10) or MED (lab 12).

<details><summary>Show solution</summary>

On **R2** (Linux shell):
```bash
ip link set eth1 up
```

</details>

**Verify:**

```
root@H5:~# traceroute -n -w1 -q1 192.168.1.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.1.10 (192.168.1.10), 30 hops max, 60 byte packets
 1  192.168.5.1  0.037 ms
 2  10.0.35.3  0.013 ms
 3  10.0.12.1  0.022 ms
 4  192.168.1.10  0.017 ms
```

</details>


## Extra challenges

1. Instead of raising AS 300 to 200, lower AS 200 on R1 to 50. Is the result the same?
2. Set local-pref only for 192.168.5.0/24 and leave other prefixes at default (add a dummy prefix on R5 to test).
3. Make inbound traffic also use AS 300: on R1 prepend `100 100` outbound to R3. Verify with traceroute from H5.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
