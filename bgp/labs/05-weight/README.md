# Lab 05 — BGP - The BGP Weight Attribute

**Video:** [BGP - The BGP Weight Attribute](https://www.youtube.com/watch?v=akYzsBrrQ70) (7:08)

**Weight** is not a real BGP path attribute: it is a number that lives only inside one router
(Cisco and FRR), is never sent to any neighbor and is the **first** thing compared.
Default 0 for learned routes and 32768 for routes this router originates. Use it to make one
router prefer a particular exit, and nothing else.

## What you will practise

- Set weight per neighbor (`neighbor X weight N`)
- Set weight per prefix with a prefix-list + route-map
- Prove that weight is local and only affects outbound traffic of that router
- Spot asymmetric routing with traceroute in both directions

## Topology

4 FRR routers, 2 Linux hosts.

```
                               AS 200
                              +----+
                   10.0.12/24 | R2 | 10.0.24/24
                  .1 .------- +----+ -------. .4
  +----+   +----+ --'  eth0  eth0  eth1      '-- +----+   +----+
  | H1 |---| R1 |  AS 100                AS 400  | R4 |---| H4 |
  +----+   +----+ --.  eth1  eth0  eth1      .-- +----+   +----+
192.168.1.10   .1 '------- +----+ -------' .4        192.168.4.10
                   10.0.13/24 | R3 | 10.0.34/24
                              +----+
                               AS 300
  (R1: eth0->R2 eth1->R3 eth2->H1   R4: eth0->R2 eth1->R3 eth2->H4)
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | R3 eth0 | 10.0.13.0/24 |
| 3 | R2 eth1 | R4 eth0 | 10.0.24.0/24 |
| 4 | R3 eth1 | R4 eth1 | 10.0.34.0/24 |
| 5 | R1 eth2 | H1 eth0 | 192.168.1.0/24 |
| 6 | R4 eth2 | H4 eth0 | 192.168.4.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.13.1/24 | R3 |
| **R1** | 100 | eth2 | 192.168.1.1/24 | LAN H1 |
| **R2** | 200 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 200 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 200 | eth1 | 10.0.24.2/24 | R4 |
| **R3** | 300 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 300 | eth0 | 10.0.13.3/24 | R1 |
| **R3** | 300 | eth1 | 10.0.34.3/24 | R4 |
| **R4** | 400 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 400 | eth0 | 10.0.24.4/24 | R2 |
| **R4** | 400 | eth1 | 10.0.34.4/24 | R3 |
| **R4** | 400 | eth2 | 192.168.4.1/24 | LAN H4 |
| **R4** | 400 | lan44 (dummy) | 172.16.4.1/24 | extra prefix to advertise |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |

## Bring the lab up

```powershell
cd bgp\labs\05-weight
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-05-weight`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Baseline

R1 has two equal paths to AS 400's prefixes and picks the one via R2 (tie-breaker).
Note the `Weight` column: 0 for learned routes, 32768 for R1's own 192.168.1.0/24.

**Verify:**

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
*  172.16.4.0/24    10.0.13.3                              0 300 400 i
*>                  10.0.12.2                              0 200 400 i
*> 192.168.1.0/24   0.0.0.0                  0         32768 i
*  192.168.4.0/24   10.0.13.3                              0 300 400 i
*>                  10.0.12.2                              0 200 400 i

Displayed  3 routes and 5 total paths
```

</details>


### Step 2 — Prefer R3 for everything with neighbor weight

Give every route learned from R3 weight 100. Weight beats every other attribute.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.13.3 weight 100
end
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 5, local router ID is 1.1.1.1, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 172.16.4.0/24    10.0.13.3                            100 300 400 i
*                   10.0.12.2                              0 200 400 i
*> 192.168.1.0/24   0.0.0.0                  0         32768 i
*> 192.168.4.0/24   10.0.13.3                            100 300 400 i
*                   10.0.12.2                              0 200 400 i

Displayed  3 routes and 5 total paths
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.037 ms
 2  10.0.13.3  0.011 ms
 3  10.0.24.4  0.017 ms
 4  *
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
20  192.168.4.10  0.065 ms
```

</details>


### Step 3 — Weight is local only: look at the return path

Weight was not advertised to anyone. R4 still prefers to reach 192.168.1.0/24 via R2, so
traffic **from** H4 to H1 takes a different path than traffic **to** H4: asymmetric routing.
Weight (like local-pref) controls only the traffic *leaving* your network.

**Verify:**

```
R4# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 3
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.24.2 10.0.34.3
  300 100
    10.0.34.3 from 10.0.34.3 (3.3.3.3)
      Origin IGP, valid, external
      Last update: Tue Oct 13 22:02:07 2026
  200 100
    10.0.24.2 from 10.0.24.2 (2.2.2.2)
      Origin IGP, valid, external, best (Router ID)
      Last update: Tue Oct 13 22:02:07 2026
```

</details>

```
root@H4:~# traceroute -n -w1 -q1 192.168.1.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.1.10 (192.168.1.10), 30 hops max, 60 byte packets
 1  192.168.4.1  0.036 ms
 2  10.0.24.2  0.015 ms
 3  10.0.13.1  0.018 ms
 4  192.168.1.10  0.013 ms
```

</details>


### Step 4 — Per-prefix weight with a route-map

Remove the neighbor weight. Instead, prefer R3 **only** for 172.16.4.0/24 and keep the
default choice (R2) for 192.168.4.0/24. Match the prefix with a prefix-list; the empty
`permit 20` sequence lets every other route through unchanged.

Surprise: after removing the neighbor weight, 192.168.4.0/24 **stays** on R3 with reason
`Older Path`. Both candidates are eBGP and equal up to step 9, and FRR then keeps the path that is
*already* best to avoid flapping (step 10). Hard-reset the session to R3 so the R2 path becomes the
older one, and the per-prefix policy shows its effect.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
ip prefix-list P-172 seq 5 permit 172.16.4.0/24
route-map FROM-R3 permit 10
 match ip address prefix-list P-172
 set weight 200
route-map FROM-R3 permit 20
router bgp 100
 address-family ipv4 unicast
  no neighbor 10.0.13.3 weight 100
  neighbor 10.0.13.3 route-map FROM-R3 in
end
```

On **R1** (`vtysh`):
```
clear bgp 10.0.13.3 soft in
```

On **R1** (`vtysh`):
```
clear bgp 10.0.13.3
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 9, local router ID is 1.1.1.1, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 172.16.4.0/24    10.0.12.2                              0 200 400 i
*> 192.168.1.0/24   0.0.0.0                  0         32768 i
*> 192.168.4.0/24   10.0.12.2                              0 200 400 i

Displayed  3 routes and 3 total paths
```

</details>

```
R1# show route-map FROM-R3
```
<details><summary>Expected output (captured from a test run)</summary>

```
ZEBRA:
route-map: FROM-R3 Invoked: 0 Optimization: enabled Processed Change: true
 permit, sequence 10 Invoked 0
  Match clauses:
    ip address prefix-list P-172
  Set clauses:
  Call clause:
  Action:
    Exit routemap
 permit, sequence 20 Invoked 0
  Match clauses:
  Set clauses:
  Call clause:
  Action:
    Exit routemap
OSPF:
route-map: FROM-R3 Invoked: 0 Optimization: enabled Processed Change: false
 permit, sequence 10 Invoked 0
  Match clauses:
    ip address prefix-list P-172
  Set clauses:
  Call clause:
  Action:
    Exit routemap
 permit, sequence 20 Invoked 0
  Match clauses:
  Set clauses:
  Call clause:
  Action:
    Exit routemap
BGP:
route-map: FROM-R3 Invoked: 2 Optimization: enabled Processed Change: true
 permit, sequence 10 Invoked 1
  Match clauses:
    ip address prefix-list P-172
  Set clauses:
    weight 200
  Call clause:
  Action:
    Exit routemap
 permit, sequence 20 Invoked 1
  Match clauses:
  Set clauses:
  Call clause:
  Action:
    Exit routemap
```

</details>


## Extra challenges

1. Originate 192.168.4.0/24 on R1 as well (a static to blackhole + `network`). Which path wins, and why (look at weight 32768)?
2. Make R4 prefer R3 for the return traffic too. Which attribute could you use on R4, and which one could R1 use to influence R4 from the outside (see labs 10 and 12)?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
