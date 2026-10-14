# Lab 11 — BGP - What is the Origin Code BGP Attribute?

**Video:** [BGP - What is the Origin Code BGP Attribute?](https://www.youtube.com/watch?v=qiqENy217nE) (7:55)

ORIGIN (well-known mandatory) records *how* the prefix entered BGP at the originating AS:

| Code | Meaning | Created by |
|---|---|---|
| `i` IGP | injected on purpose | `network`, `aggregate-address` |
| `e` EGP | learned from the historic EGP protocol | today only via `set origin egp` |
| `?` incomplete | redistributed from somewhere else | `redistribute connected/static/ospf` |

Lower is preferred: **i < e < ?**, at step 5 (after AS_PATH length). Any AS on the path can
overwrite it with `set origin`, which makes it a (rarely used) traffic-engineering knob.

## What you will practise

- Produce `i` and `?` origins
- Rewrite ORIGIN with a route-map
- See ORIGIN break a tie between two equal-length AS paths

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
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |

## Bring the lab up

```powershell
cd bgp\labs\11-origin
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-11-origin`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Baseline: both paths have origin i

R4 uses `network`, so R1 sees two paths with origin `i` and the usual tie-break picks R2.

**Verify:**

```
R1# show bgp ipv4 unicast
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
*> 192.168.1.0/24   0.0.0.0                  0         32768 i
*> 192.168.4.0/24   10.0.12.2                              0 200 400 i
*                   10.0.13.3                              0 300 400 i

Displayed  2 routes and 3 total paths
```

</details>


### Step 2 — Change R4 to redistribute → origin ?

Replace the `network` statement on R4 with `redistribute connected`, limited by a route-map to the LAN.
Both paths on R1 now carry `?`. They still tie: the origin is the same on both.

<details><summary>Show solution</summary>

On **R4** (`vtysh`):
```
configure terminal
ip prefix-list LAN seq 5 permit 192.168.4.0/24
route-map CONNECTED permit 10
 match ip address prefix-list LAN
router bgp 400
 address-family ipv4 unicast
  no network 192.168.4.0/24
  redistribute connected route-map CONNECTED
end
```

</details>

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
*> 192.168.1.0/24   0.0.0.0                  0         32768 i
*> 192.168.4.0/24   10.0.12.2                              0 200 400 ?
*                   10.0.13.3                              0 300 400 ?

Displayed  2 routes and 3 total paths
```

</details>


### Step 3 — R3 rewrites origin to IGP → R1 prefers R3

On R3, outbound to R1, `set origin igp`. R1 now has `i` via R3 vs `?` via R2. Same AS_PATH length,
so step 5 decides: R3 wins.

<details><summary>Show solution</summary>

On **R3** (`vtysh`):
```
configure terminal
route-map TO-R1 permit 10
 set origin igp
router bgp 300
 address-family ipv4 unicast
  neighbor 10.0.13.1 route-map TO-R1 out
end
```

On **R3** (`vtysh`):
```
clear bgp 10.0.13.1 soft out
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 4
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3
  200 400
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin incomplete, valid, external
      Last update: Tue Oct 13 22:03:47 2026
  300 400
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin IGP, valid, external, best (Origin)
      Last update: Tue Oct 13 22:03:49 2026
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.063 ms
 2  10.0.13.3  0.013 ms
 3  10.0.24.4  0.018 ms
 4  192.168.4.10  0.039 ms
```

</details>


### Step 4 — EGP sits in the middle

Change R3's route-map to `set origin egp`. `e` is still better than `?`, so R3 keeps winning.

<details><summary>Show solution</summary>

On **R3** (`vtysh`):
```
configure terminal
route-map TO-R1 permit 10
 set origin egp
end
```

On **R3** (`vtysh`):
```
clear bgp 10.0.13.1 soft out
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
*> 192.168.1.0/24   0.0.0.0                  0         32768 i
*  192.168.4.0/24   10.0.12.2                              0 200 400 ?
*>                  10.0.13.3                              0 300 400 e

Displayed  2 routes and 3 total paths
```

</details>


## Extra challenges

1. On R2 set origin igp towards R1 as well. Who wins now and by which step?
2. Prepend once on R3 towards R1 while keeping origin egp. Which is stronger: a better origin or a shorter AS path?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
