# Lab 14 — BGP - Route with the Lowest IGP Metric to the Next Hop is Preferred

**Video:** [BGP - Route with the Lowest IGP Metric to the Next Hop is Preferred](https://www.youtube.com/watch?v=2B0gshKX9Us) (4:36)

When two iBGP paths are otherwise equal, the router prefers the one whose NEXT_HOP is **closest
according to the IGP** (step 8). This is "hot-potato" routing: get the traffic out of your AS
through the nearest exit. R1 has two exits, R2 and R3; you change OSPF costs and watch BGP follow.

## What you will practise

- Read the IGP metric FRR shows next to a BGP next hop
- Change OSPF cost and watch the BGP best path move
- Understand hot-potato routing

## Topology

4 FRR routers, 2 Linux hosts.

```
                      AS 100 (OSPF + iBGP full mesh on loopbacks)
                    +----+ 10.0.24/24
         10.0.12/24 | R2 |============.
+----+   +----+ ----+----+ lo 2.2.2.2  \   +----+   +----+
| H1 |---| R1 |                         >==| R4 |---| H4 |
+----+   +----+ ----+----+ lo 3.3.3.3  /   +----+   +----+
      lo 1.1.1.1    | R3 |============'     AS 200
         10.0.13/24 +----+ 10.0.34/24
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
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.24.2/24 | R4 |
| **R3** | 100 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 100 | eth0 | 10.0.13.3/24 | R1 |
| **R3** | 100 | eth1 | 10.0.34.3/24 | R4 |
| **R4** | 200 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 200 | eth0 | 10.0.24.4/24 | R2 |
| **R4** | 200 | eth1 | 10.0.34.4/24 | R3 |
| **R4** | 200 | eth2 | 192.168.4.1/24 | LAN H4 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |

## Bring the lab up

```powershell
cd bgp\labs\14-igp-metric-to-next-hop
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-14-igp-metric-to-next-hop`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Equal costs

Both next hops (2.2.2.2, 3.3.3.3) are 10 away in OSPF. Steps 1 to 8 tie and the lower router ID
(2.2.2.2) wins. Note `(metric 10)` behind each next hop.

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 2
Paths: (2 available, best #1, table default)
  Not advertised to any peer
  200
    2.2.2.2 (metric 10) from 2.2.2.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath, best (Router ID)
      Last update: Wed Oct 14 06:49:36 2026
  200
    3.3.3.3 (metric 10) from 3.3.3.3 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath
      Last update: Wed Oct 14 06:49:36 2026
```

</details>

```
R1# show ip route ospf
```
<details><summary>Expected output (captured from a test run)</summary>

```
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

O   1.1.1.1/32 [110/0] is directly connected, lo, weight 1, 00:00:24
O>* 2.2.2.2/32 [110/10] via 10.0.12.2, eth0, weight 1, 00:00:04
O>* 3.3.3.3/32 [110/10] via 10.0.13.3, eth1, weight 1, 00:00:09
O   10.0.12.0/24 [110/10] is directly connected, eth0, weight 1, 00:00:24
O   10.0.13.0/24 [110/10] is directly connected, eth1, weight 1, 00:00:24
```

</details>


### Step 2 — Make the path to R2 expensive

Raise the OSPF cost of R1's link to R2 to 100. The IGP metric to 2.2.2.2 becomes 100 and
R1 switches to R3 with reason `IGP Metric`.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
interface eth0
 ip ospf cost 100
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
  Not advertised to any peer
  200
    2.2.2.2 (metric 100) from 2.2.2.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal
      Last update: Wed Oct 14 06:49:36 2026
  200
    3.3.3.3 (metric 10) from 3.3.3.3 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal, best (IGP Metric)
      Last update: Wed Oct 14 06:49:36 2026
```

</details>

```
R1# show bgp nexthop
```
<details><summary>Expected output (captured from a test run)</summary>

```
Current BGP nexthop cache:
 2.2.2.2 valid [IGP metric 100], #paths 1, peer 2.2.2.2
  gate 10.0.12.2, if eth0
  Last update: Wed Oct 14 06:49:38 2026

 3.3.3.3 valid [IGP metric 10], #paths 1, peer 3.3.3.3
  gate 10.0.13.3, if eth1
  Last update: Wed Oct 14 06:49:29 2026
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.048 ms
 2  10.0.13.3  0.013 ms
 3  10.0.24.4  0.030 ms
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
20  192.168.4.10  0.072 ms
```

</details>


### Step 3 — Hot potato vs. one policy-chosen exit

Each router chooses the exit nearest to *itself*. R2 and R3 still use their own eBGP path. If you
want the whole AS to use one exit regardless of IGP distance, you need something earlier in the
list, such as local-pref (lab 8). (The opposite of hot potato, "cold potato", means carrying traffic
on your own network to the exit closest to the *destination*, typically by honouring the neighbor's MED.) Try it: set local-pref 200 on R2 for routes from R4,
and R1 goes back to R2 despite the cost of 100.

Look closely at R1's table: there is now only **one** path. R3 also prefers R2's LOCAL_PREF 200 path
(iBGP) over its own eBGP path, and since BGP only advertises its best path, R3 withdraws its exit from
R1. Every router in the AS now uses R2.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
route-map LP200 permit 10
 set local-preference 200
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.24.4 route-map LP200 in
end
```

On **R2** (`vtysh`):
```
clear bgp 10.0.24.4 soft in
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
  200
    2.2.2.2 (metric 100) from 2.2.2.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 200, valid, internal, best (First path received)
      Last update: Wed Oct 14 06:49:42 2026
```

</details>

```
R3# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 3
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.34.4
  200
    2.2.2.2 (metric 110) from 2.2.2.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 200, valid, internal, best (Local Pref)
      Last update: Wed Oct 14 06:49:42 2026
  200
    10.0.34.4 from 10.0.34.4 (4.4.4.4)
      Origin IGP, metric 0, valid, external
      Last update: Wed Oct 14 06:49:17 2026
```

</details>


## Extra challenges

1. Set both costs equal again and add `maximum-paths ibgp 2` on R1. Check `ip route show 192.168.4.0/24` for two nexthops (ECMP).
2. What happens when the IGP metric changes while traffic flows? Ping continuously from H1 while changing the cost.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
