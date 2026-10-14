# Lab 09 — BGP - What is the Originate Attribute?

**Video:** [BGP - What is the Originate Attribute?](https://www.youtube.com/watch?v=xa9OfO6i1_M) (6:33)

After weight and local-pref, BGP prefers a path that **this router originated itself**
(via `network`, `redistribute` or `aggregate-address`). Locally originated routes show next hop
`0.0.0.0` and get weight 32768, so in practice they usually win already at step 1. In this lab you
neutralise the weight to see the "local route" step on its own, and you look at the three ways to
originate a prefix and the ORIGIN code each produces.

## What you will practise

- Originate prefixes with `network`, `redistribute static` and `aggregate-address`
- Recognise locally originated paths (next hop 0.0.0.0, weight 32768)
- See the *Local Route* best-path step decide
- Relate the origin method to the ORIGIN code (i / ?)

## Topology

2 FRR routers, 2 Linux hosts.

```
         AS 100                         AS 200
+----+   +----+   10.0.12.0/24   +----+   +----+
| H1 |---| R1 |==================| R2 |---| H2 |
+----+   +----+ .1   eBGP     .2 +----+   +----+
R1: dummies 172.16.1.0/24, 172.16.2.0/24 -> aggregate 172.16.0.0/16
R2: static 172.16.0.0/16 -> blackhole, advertised with network
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | H1 eth0 | 192.168.1.0/24 |
| 3 | R2 eth1 | H2 eth0 | 192.168.2.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 192.168.1.1/24 | LAN H1 |
| **R1** | 100 | lan1 (dummy) | 172.16.1.1/24 | extra prefix to advertise |
| **R1** | 100 | lan2 (dummy) | 172.16.2.1/24 | extra prefix to advertise |
| **R2** | 200 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 200 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 200 | eth1 | 192.168.2.1/24 | LAN H2 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H2** | - | eth0 | 192.168.2.10/24 | R2 |
| **H2** | - | default gw | 192.168.2.1 | |

## Bring the lab up

```powershell
cd bgp\labs\09-locally-originated
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-09-locally-originated`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Two paths: one from R2, one made by R1

R1 aggregates its two /24s into 172.16.0.0/16 and also receives 172.16.0.0/16 from R2.
The local path has next hop `0.0.0.0`, weight **32768** and wins at step 1 (Weight).

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
*  172.16.0.0/16    10.0.12.2                0             0 200 i
*>                  ::                       0         32768 i
*> 172.16.1.0/24    0.0.0.0                  0         32768 i
*> 172.16.2.0/24    0.0.0.0                  0         32768 i
*> 192.168.1.0/24   0.0.0.0                  0         32768 i
*> 192.168.2.0/24   10.0.12.2                0             0 200 i

Displayed  5 routes and 6 total paths
```

</details>

```
R1# show bgp ipv4 unicast 172.16.0.0/16
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 172.16.0.0/16, version 4
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.12.2
  200
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, valid, external
      Last update: Tue Oct 13 22:03:21 2026
  Local, (aggregated by 100 1.1.1.1)
    :: from :: (1.1.1.1)
      Origin IGP, metric 0, weight 32768, valid, aggregated, local, atomic-aggregate, best (Weight)
      Last update: Tue Oct 13 22:03:19 2026
```

</details>


### Step 2 — Neutralise weight and see the Local Route step

Give routes from R2 the same weight, 32768. Weight ties, LOCAL_PREF ties (100), and the next step is
*prefer locally originated* → R1's aggregate still wins, now with reason **Local Route**.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.12.2 weight 32768
end
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 172.16.0.0/16
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 172.16.0.0/16, version 4
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.12.2
  200
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, weight 32768, valid, external
      Last update: Tue Oct 13 22:03:22 2026
  Local, (aggregated by 100 1.1.1.1)
    :: from :: (1.1.1.1)
      Origin IGP, metric 0, weight 32768, valid, aggregated, local, atomic-aggregate, best (Local Route)
      Last update: Tue Oct 13 22:03:20 2026
```

</details>


### Step 3 — …but local-pref still comes first

Raise LOCAL_PREF on routes from R2 to 200. Local-pref is compared *before* the local-route step,
so now R2's path wins even though R1 originates the prefix itself.

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

On **R1** (`vtysh`):
```
clear bgp 10.0.12.2 soft in
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 172.16.0.0/16
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 172.16.0.0/16, version 7
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.12.2
  200
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 200, weight 32768, valid, external, best (Local Pref)
      Last update: Tue Oct 13 22:03:24 2026
  Local, (aggregated by 100 1.1.1.1)
    :: from :: (1.1.1.1)
      Origin IGP, metric 0, weight 32768, valid, aggregated, local, atomic-aggregate
      Last update: Tue Oct 13 22:03:20 2026
```

</details>


### Step 4 — Three ways to originate, two ORIGIN codes

Clean up (remove weight and route-map), then add a third method: a static route redistributed
into BGP. Compare the ORIGIN codes R2 receives: `network` and `aggregate-address` → `i` (IGP),
`redistribute` → `?` (incomplete).

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
ip route 10.99.0.0/24 blackhole
router bgp 100
 address-family ipv4 unicast
  no neighbor 10.0.12.2 weight 32768
  no neighbor 10.0.12.2 route-map FROM-R2 in
  redistribute static
end
```

On **R1** (`vtysh`):
```
clear bgp 10.0.12.2 soft in
```

</details>

**Verify:**

```
R2# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 6, local router ID is 2.2.2.2, vrf id 0
Default local pref 100, local AS 200
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 10.99.0.0/24     10.0.12.1                0             0 100 ?
*  172.16.0.0/16    10.0.12.1                0             0 100 i
*>                  0.0.0.0                  0         32768 i
*> 172.16.1.0/24    10.0.12.1                0             0 100 i
*> 172.16.2.0/24    10.0.12.1                0             0 100 i
*> 192.168.1.0/24   10.0.12.1                0             0 100 i
*> 192.168.2.0/24   0.0.0.0                  0         32768 i

Displayed  6 routes and 7 total paths
```

</details>


## Extra challenges

1. Make the aggregate `summary-only`. What does R2 receive now? What happens to R1's own 172.16.0.0/16 route in `ip route` (look for blackhole/unreachable)?
2. Why do operators add a static route to `blackhole` (Null0) for a prefix they originate with `network`?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
