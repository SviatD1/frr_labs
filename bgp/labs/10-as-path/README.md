# Lab 10 — BGP - What is the AS_Path Attribute?

**Video:** [BGP - What is the AS_Path Attribute?](https://www.youtube.com/watch?v=Rw1Ps2JTtPc) (5:24)

AS_PATH lists every AS a route has crossed (most recent first). It does two jobs:
**loop prevention** (a router drops routes containing its own AS) and **path selection**
(shorter is better, step 4). Four ASes form a ring so both are easy to see, and you will use
**AS_PATH prepending** to steer traffic.

## What you will practise

- Read AS_PATH and count its length
- Observe eBGP loop prevention with `soft-reconfiguration inbound` and `received-routes`
- Prepend to make a path less attractive to a neighbor
- Filter with an AS-path access-list

## Topology

4 FRR routers, 2 Linux hosts.

```
+----+   +----+ 10.0.12/24 +----+
| H1 |---| R1 |------------| R2 |      R1 AS100   R2 AS200
+----+   +----+            +----+      R3 AS300   R4 AS400
           |10.0.14/24       |10.0.23/24
         +----+ 10.0.34/24 +----+
+----+---| R4 |------------| R3 |
| H4 |   +----+            +----+
+----+
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R2 eth1 | R3 eth0 | 10.0.23.0/24 |
| 3 | R3 eth1 | R4 eth0 | 10.0.34.0/24 |
| 4 | R1 eth1 | R4 eth1 | 10.0.14.0/24 |
| 5 | R1 eth2 | H1 eth0 | 192.168.1.0/24 |
| 6 | R4 eth2 | H4 eth0 | 192.168.4.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.14.1/24 | R4 |
| **R1** | 100 | eth2 | 192.168.1.1/24 | LAN H1 |
| **R2** | 200 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 200 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 200 | eth1 | 10.0.23.2/24 | R3 |
| **R3** | 300 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 300 | eth0 | 10.0.23.3/24 | R2 |
| **R3** | 300 | eth1 | 10.0.34.3/24 | R4 |
| **R4** | 400 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 400 | eth0 | 10.0.34.4/24 | R3 |
| **R4** | 400 | eth1 | 10.0.14.4/24 | R1 |
| **R4** | 400 | eth2 | 192.168.4.1/24 | LAN H4 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |

## Bring the lab up

```powershell
cd bgp\labs\10-as-path
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-10-as-path`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Shortest AS_PATH wins

First note R1's outbound policy `OWN-ONLY`: the AS-path access-list `^$` matches an *empty*
AS_PATH, i.e. only routes R1 originates itself. R1 is a customer, not a transit AS, so it must
never pass routes from one provider to another (that would be a *route leak*).

R1 gets 192.168.4.0/24 directly from R4 (`400`, length 1) and around the ring (`200 300 400`,
length 3). Shortest wins.

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 2
Paths: (2 available, best #2, table default)
  Not advertised to any peer
  200 300 400
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, valid, external
      Last update: Wed Oct 14 06:48:55 2026
  400
    10.0.14.4 from 10.0.14.4 (4.4.4.4)
      Origin IGP, metric 0, valid, external, best (AS Path)
      Last update: Wed Oct 14 06:48:55 2026
```

</details>


### Step 2 — Loop prevention

R1's own 192.168.1.0/24 is passed around the ring and offered back to R1 by R2 with an
AS_PATH that ends in `100`. R1 sees its own AS and drops it. Because the start config enables
`soft-reconfiguration inbound` towards R2, R1 keeps a copy of everything R2 *sent* (received-routes),
so you can see the update that was rejected: it is in received-routes but not in the BGP table.

**Verify:**

```
R1# show bgp ipv4 unicast neighbors 10.0.12.2 received-routes
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 2, local router ID is 1.1.1.1, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.1.0/24   10.0.12.2                              0 200 100 i
*> 192.168.4.0/24   10.0.12.2                              0 200 300 400 i

Total number of prefixes 2
```

</details>

```
R1# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 1
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.12.2 10.0.14.4
  Local
    0.0.0.0 from 0.0.0.0 (1.1.1.1)
      Origin IGP, metric 0, weight 32768, valid, sourced, local, best (First path received)
      Last update: Wed Oct 14 06:48:50 2026
```

</details>


### Step 3 — Prepend to push traffic around the ring

AS 400 wants R1 to stop using the direct link (maybe it is a slow backup link). On **R4**, prepend
its own AS three extra times towards R1. R1 now sees `400 400 400 400` (4) vs `200 300 400` (3).
Prepending is how an AS influences **inbound** traffic from others.

<details><summary>Show solution</summary>

On **R4** (`vtysh`):
```
configure terminal
route-map PREPEND-R1 permit 10
 set as-path prepend 400 400 400
router bgp 400
 address-family ipv4 unicast
  neighbor 10.0.14.1 route-map PREPEND-R1 out
end
```

On **R4** (`vtysh`):
```
clear bgp 10.0.14.1 soft out
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 3
Paths: (2 available, best #1, table default)
  Not advertised to any peer
  200 300 400
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, valid, external, best (AS Path)
      Last update: Wed Oct 14 06:48:55 2026
  400 400 400 400
    10.0.14.4 from 10.0.14.4 (4.4.4.4)
      Origin IGP, metric 0, valid, external
      Last update: Wed Oct 14 06:48:56 2026
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.186 ms
 2  10.0.12.2  0.144 ms
 3  10.0.23.3  0.131 ms
 4  10.0.14.4  0.119 ms
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
21  192.168.4.10  0.059 ms
```

</details>


### Step 4 — Filter on AS_PATH

AS-path access-lists match AS_PATH with regular expressions. On R1, deny anything that passed
through AS 300 when it comes from R2 (`_300_`), permit the rest. R1 falls back to the
prepended direct path.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
bgp as-path access-list VIA300 seq 5 permit _300_
route-map FROM-R2 deny 10
 match as-path VIA300
route-map FROM-R2 permit 20
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.12.2 route-map FROM-R2 in
end
```

On **R1** (`vtysh`):
```
clear bgp 10.0.12.2 soft in
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 4
Paths: (1 available, best #1, table default)
  Not advertised to any peer
  400 400 400 400
    10.0.14.4 from 10.0.14.4 (4.4.4.4)
      Origin IGP, metric 0, valid, external, best (First path received)
      Last update: Wed Oct 14 06:48:56 2026
```

</details>

```
R1# show bgp ipv4 unicast neighbors 10.0.12.2 routes
```

*(No output: every route from R2 crossed AS 300 and was denied by FROM-R2.)*

## Extra challenges

1. On R1 use `neighbor 10.0.12.2 allowas-in 1`. Does the looped 192.168.1.0/24 now appear in the table? Why is this dangerous (and when is it legitimately used, e.g. a customer with one AS at several sites)?
2. Enable `bgp bestpath as-path ignore` on R1. Which step decides now?
3. AS-path poisoning: on R4, prepend someone else's AS towards R3 (`set as-path prepend 300` in a route-map applied out to 10.0.34.3). What happens to 192.168.4.0/24 on R3 (loop prevention), and how does R3 now reach H4?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
