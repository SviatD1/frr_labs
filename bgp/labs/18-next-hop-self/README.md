# Lab 18 — BGP - Determining the next hop IP (next-hop-self)

**Video:** [BGP - Determining the next hop IP (next-hop-self)](https://www.youtube.com/watch?v=KTrGzMcanZg) (9:35)

Rules for NEXT_HOP:
* Sending to an **eBGP** peer: next hop = my own address on that session.
* Sending to an **iBGP** peer: next hop is passed **unchanged** (for routes learned via eBGP it is the
  external neighbor's address).

So inside the AS, every router must be able to reach the external next hop. Two fixes: carry the
border link in the IGP, or use `next-hop-self` on the border router.

## What you will practise

- Spot an *inaccessible* next hop with `show bgp nexthop`
- Fix 1: advertise the external link into OSPF as a passive interface
- Fix 2: `next-hop-self` (the usual choice)

## Topology

3 FRR routers, 2 Linux hosts.

```
            AS 100 (OSPF on R1-R2 + loopbacks)          AS 200
+----+   +----+ 10.0.12/24 +----+    10.0.23/24     +----+   +----+
| H1 |---| R1 |------------| R2 |===================| R3 |---| H3 |
+----+   +----+   iBGP     +----+ .2    eBGP     .3 +----+   +----+
      lo 1.1.1.1 <-------> lo 2.2.2.2
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R2 eth1 | R3 eth0 | 10.0.23.0/24 |
| 3 | R1 eth1 | H1 eth0 | 192.168.1.0/24 |
| 4 | R3 eth1 | H3 eth0 | 192.168.3.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 192.168.1.1/24 | LAN H1 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.23.2/24 | R3 |
| **R3** | 200 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 200 | eth0 | 10.0.23.3/24 | R2 |
| **R3** | 200 | eth1 | 192.168.3.1/24 | LAN H3 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H3** | - | eth0 | 192.168.3.10/24 | R3 |
| **H3** | - | default gw | 192.168.3.1 | |

## Bring the lab up

```powershell
cd bgp\labs\18-next-hop-self
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-18-next-hop-self`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — The problem

R1 has 192.168.3.0/24 with next hop **10.0.23.3** (R3), unchanged by R2. R1 has no route to
10.0.23.0/24, so the path is not valid (no `*`, no `>`), not installed, and H1 cannot reach H3.
Meanwhile R3 sees R1's LAN with next hop 10.0.23.2: R2 *did* change the next hop on the eBGP side.

**Verify:**

```
R1# show bgp ipv4 unicast
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
*> 192.168.1.0/24   0.0.0.0                  0         32768 i
  i192.168.3.0/24   10.0.23.3                0    100      0 200 i

Displayed  2 routes and 2 total paths
```

</details>

```
R1# show bgp ipv4 unicast 192.168.3.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.3.0/24, version 0
Paths: (1 available, no best path)
  Not advertised to any peer
  200
    10.0.23.3 (inaccessible) from 2.2.2.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, invalid, internal
      Last update: Wed Oct 14 06:50:54 2026
```

</details>

```
R1# show bgp nexthop
```
<details><summary>Expected output (captured from a test run)</summary>

```
Current BGP nexthop cache:
 2.2.2.2 valid [IGP metric 10], #paths 0, peer 2.2.2.2
  gate 10.0.12.2, if eth0
  Last update: Wed Oct 14 06:50:53 2026

 10.0.23.3 invalid, #paths 1
  Last update: Wed Oct 14 06:50:54 2026
```

</details>

```
R3# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 2, local router ID is 3.3.3.3, vrf id 0
Default local pref 100, local AS 200
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.1.0/24   10.0.23.2                              0 100 i
*> 192.168.3.0/24   0.0.0.0                  0         32768 i

Displayed  2 routes and 2 total paths
```

</details>


### Step 2 — Fix 1: put the external link into OSPF (passive)

Enable OSPF on R2's eth1 but make it passive, so the subnet is advertised but no adjacency is
attempted with the other AS. R1 learns 10.0.23.0/24 via OSPF and the next hop resolves.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
interface eth1
 ip ospf area 0
router ospf
 passive-interface eth1
end
```

</details>

**Verify:**

```
R1# show ip route 10.0.23.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
Routing entry for 10.0.23.0/24
  Known via "ospf", distance 110, metric 20, best
  Last update 00:00:03 ago
  * 10.0.12.2, via eth0, weight 1
```

</details>

```
R1# show ip route 192.168.3.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
Routing entry for 192.168.3.0/24
  Known via "bgp", distance 200, metric 0, best
  Last update 00:00:03 ago
    10.0.23.3 (recursive), weight 1
  *   10.0.12.2, via eth0, weight 1
```

</details>


### Step 3 — Fix 2: next-hop-self

Undo fix 1 and use `next-hop-self` on R2 instead. R1 now sees next hop 2.2.2.2, R2's loopback, which
OSPF already knows. This keeps external subnets out of your IGP and is the usual practice.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
interface eth1
 no ip ospf area 0
router ospf
 no passive-interface eth1
router bgp 100
 address-family ipv4 unicast
  neighbor 1.1.1.1 next-hop-self
end
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.3.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.3.0/24, version 4
Paths: (1 available, best #1, table default)
  Not advertised to any peer
  200
    2.2.2.2 (metric 10) from 2.2.2.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, best (First path received)
      Last update: Wed Oct 14 06:50:57 2026
```

</details>

```
R1# show ip route 192.168.3.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
Routing entry for 192.168.3.0/24
  Known via "bgp", distance 200, metric 0, best
  Last update 00:00:03 ago
    2.2.2.2 (recursive), weight 1
  *   10.0.12.2, via eth0, weight 1
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.3.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.3.10 (192.168.3.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.035 ms
 2  10.0.12.2  0.012 ms
 3  10.0.23.3  0.075 ms
 4  192.168.3.10  0.010 ms
```

</details>


## Extra challenges

1. Route reflectors do not change the next hop when reflecting. Why is `next-hop-self` on the *border* router still enough?
2. Use `set ip next-hop` in an inbound route-map on R1 to rewrite the next hop yourself.
3. Third-party next hop: on a shared LAN with three eBGP routers, BGP keeps the next hop of the original speaker. Build it with a GNS3 switch.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
