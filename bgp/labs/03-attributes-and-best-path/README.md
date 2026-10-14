# Lab 03 — BGP Attributes and Determining the Best Path

**Video:** [BGP Attributes and Determining the Best Path](https://www.youtube.com/watch?v=ZZRsPcNllbU) (10:20)

When BGP holds several paths to the same prefix it picks **one** best path by comparing
    path attributes in a fixed order. R1 is dual-homed (AS 200 and AS 300) and receives two
    paths to H4's network. You will read the attributes and then override the decision three
    times, each time with an attribute that sits *higher* in the list than the previous one.

    FRR's decision process (same idea as Cisco's, with small differences):

| # | FRR best-path step | Prefer |
|---|---|---|
| 1 | Weight (local to the router) | highest |
| 2 | LOCAL_PREF | highest |
| 3 | Local route (network/redistribute/aggregate on this router) | locally originated |
| 4 | AS_PATH length | shortest |
| 5 | ORIGIN | IGP `i` < EGP `e` < incomplete `?` |
| 6 | MED (only between paths from the same neighbor AS) | lowest |
| 7 | Peer type | eBGP over iBGP |
| 8 | IGP metric to NEXT_HOP | lowest |
| 9 | Multipath check (if `maximum-paths` > 1) | - |
| 10 | Already-selected external path ("Older Path") | oldest eBGP path |
| 11 | Router ID (ORIGINATOR_ID if reflected) | lowest |
| 12 | CLUSTER_LIST length | shortest |
| 13 | Neighbor address | lowest |

    FRR prints the reason next to the winner, e.g. `best (AS Path)`.

## What you will practise

- Read every attribute of a BGP path in FRR
- Find the step that decided the best path (`best (<reason>)`)
- Override the decision with AS_PATH prepend, then LOCAL_PREF, then weight
- Use route-maps to set attributes inbound and outbound

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
cd bgp\labs\03-attributes-and-best-path
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-03-attributes-and-best-path`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Read the two paths

On R1 look at 192.168.4.0/24. Both paths have the same weight (0), local-pref (100),
AS_PATH length (2), origin (IGP) and MED (0), and both are eBGP. The winner is decided
by a late tie-breaker; FRR shows which one in brackets after `best`.

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 2
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3
  200 400
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, valid, external, best (Router ID)
      Last update: Tue Oct 13 22:01:20 2026
  300 400
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin IGP, valid, external
      Last update: Tue Oct 13 22:01:20 2026
```

</details>

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


### Step 2 — AS_PATH: make the path through AS 200 longer

On R2, prepend AS 200 twice on the routes it sends to R1. R1 now sees `200 200 200 400`
(length 4) vs `300 400` (length 2) and switches to R3.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
route-map PREPEND permit 10
 set as-path prepend 200 200
router bgp 200
 address-family ipv4 unicast
  neighbor 10.0.12.1 route-map PREPEND out
end
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 3
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3
  200 200 200 400
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, valid, external
      Last update: Tue Oct 13 22:01:20 2026
  300 400
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin IGP, valid, external, best (AS Path)
      Last update: Tue Oct 13 22:01:20 2026
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.075 ms
 2  10.0.13.3  0.013 ms
 3  10.0.24.4  0.019 ms
 4  192.168.4.10  0.036 ms
```

</details>


### Step 3 — LOCAL_PREF beats AS_PATH

Now on R1 set LOCAL_PREF 200 on everything received from R2. Local preference is evaluated
*before* AS_PATH length, so the long path through R2 wins again.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
route-map FROM-R2 permit 10
 set local-preference 200
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.12.2 route-map FROM-R2 in
end
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 4
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3
  200 200 200 400
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, localpref 200, valid, external, best (Local Pref)
      Last update: Tue Oct 13 22:01:22 2026
  300 400
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin IGP, valid, external
      Last update: Tue Oct 13 22:01:19 2026
```

</details>


### Step 4 — Weight beats LOCAL_PREF

Finally give the R3 path a weight of 1000. Weight is FRR/Cisco-local, never advertised,
and is the very first comparison, so R3 wins.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.13.3 weight 1000
end
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 5
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3
  200 200 200 400
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, localpref 200, valid, external
      Last update: Tue Oct 13 22:01:24 2026
  300 400
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin IGP, weight 1000, valid, external, best (Weight)
      Last update: Tue Oct 13 22:01:24 2026
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.040 ms
 2  10.0.13.3  0.014 ms
 3  10.0.24.4  0.016 ms
 4  192.168.4.10  0.013 ms
```

</details>


## Extra challenges

1. Remove the weight and the local-pref route-map one at a time and predict the winner before you look.
2. Look at the return path with `traceroute` from H4. Did any of your changes affect it? Why not? (All three only changed R1's own choice; R4 decides the return path.)
3. Use `show bgp ipv4 unicast 192.168.4.0/24 json` and find the `selectionReason` field.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
