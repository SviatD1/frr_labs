# Lab 21 — BGP - What are iBGP Route Reflectors?

**Video:** [BGP - What are iBGP Route Reflectors?](https://www.youtube.com/watch?v=9-9Tw8yIqPM) (9:27)

A **route reflector** (RR) is an iBGP router that is allowed to break the split-horizon rule for its
**clients**. Each client only needs one session (to the RR) instead of a full mesh. Reflection rules:

| Route learned from | RR sends it to |
|---|---|
| eBGP peer | clients and non-clients |
| client | other clients **and** non-clients |
| non-client (normal iBGP peer) | clients only |

To prevent loops the RR adds ORIGINATOR_ID and CLUSTER_LIST (labs 25, 26). It does **not** change the next hop.
Here R2 is the RR; you switch R1/R3/R4 between client and non-client and check each rule.

## What you will practise

- Configure `route-reflector-client`
- Verify all three reflection rules
- Read ORIGINATOR_ID / CLUSTER_LIST on reflected routes

## Topology

5 FRR routers, 3 Linux hosts.

```
                        AS 100 (OSPF everywhere inside)
+----+   +----+ 10.0.15 +----+ 10.0.12 +----+ 10.0.23 +----+   +----+
| H5 |---| R5 |=========| R1 |---------| R2 |---------| R3 |---| H3 |
+----+   +----+         +----+         +----+         +----+   +----+
         AS 200                          | 10.0.24
                                       +----+   +----+
                                       | R4 |---| H4 |
                                       +----+   +----+
iBGP sessions: only R2-R1, R2-R3, R2-R4 (hub and spoke, loopbacks)
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R2 eth1 | R3 eth0 | 10.0.23.0/24 |
| 3 | R2 eth2 | R4 eth0 | 10.0.24.0/24 |
| 4 | R1 eth1 | R5 eth0 | 10.0.15.0/24 |
| 5 | R3 eth1 | H3 eth0 | 192.168.3.0/24 |
| 6 | R4 eth1 | H4 eth0 | 192.168.4.0/24 |
| 7 | R5 eth1 | H5 eth0 | 192.168.5.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.15.1/24 | R5 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.23.2/24 | R3 |
| **R2** | 100 | eth2 | 10.0.24.2/24 | R4 |
| **R3** | 100 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 100 | eth0 | 10.0.23.3/24 | R2 |
| **R3** | 100 | eth1 | 192.168.3.1/24 | LAN H3 |
| **R4** | 100 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 100 | eth0 | 10.0.24.4/24 | R2 |
| **R4** | 100 | eth1 | 192.168.4.1/24 | LAN H4 |
| **R5** | 200 | lo | 5.5.5.5/32 | loopback / router-id |
| **R5** | 200 | eth0 | 10.0.15.5/24 | R1 |
| **R5** | 200 | eth1 | 192.168.5.1/24 | LAN H5 |
| **H3** | - | eth0 | 192.168.3.10/24 | R3 |
| **H3** | - | default gw | 192.168.3.1 | |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |
| **H5** | - | eth0 | 192.168.5.10/24 | R5 |
| **H5** | - | default gw | 192.168.5.1 | |

## Bring the lab up

```powershell
cd bgp\labs\21-route-reflectors
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-21-route-reflectors`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Without reflection

R2 has every route, but as a normal iBGP speaker it passes none of them on to its other iBGP peers.
R3 and R4 have no route to AS 200, and R1 knows nothing about 192.168.3.0/24 or 192.168.4.0/24.

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
*>i192.168.5.0/24   1.1.1.1                  0    100      0 200 i

Displayed  2 routes and 2 total paths
```

</details>

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


### Step 2 — Make R1 and R3 clients (R4 stays a non-client)

Configuration happens **only on the RR**. Clients need no special config.
Predict before checking:
* 192.168.5.0/24 (from client R1) → reflected to client R3 **and** non-client R4.
* 192.168.3.0/24 (from client R3) → reflected to R1 and R4.
* 192.168.4.0/24 (from non-client R4) → reflected to clients R1 and R3.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
router bgp 100
 address-family ipv4 unicast
  neighbor 1.1.1.1 route-reflector-client
  neighbor 3.3.3.3 route-reflector-client
end
```

</details>

**Verify:**

```
R2# show bgp ipv4 unicast neighbors 4.4.4.4 advertised-routes
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 7, local router ID is 2.2.2.2, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.3.0/24   3.3.3.3                  0    100      0 i
*> 192.168.5.0/24   1.1.1.1                  0    100      0 200 i

Total number of prefixes 2
```

</details>

```
R3# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 3
Paths: (1 available, best #1, table default)
  Not advertised to any peer
  200
    1.1.1.1 (metric 20) from 2.2.2.2 (1.1.1.1)
      Origin IGP, metric 0, localpref 100, valid, internal, best (First path received)
      Originator: 1.1.1.1, Cluster list: 2.2.2.2
      Last update: Wed Oct 14 06:52:29 2026
```

</details>


### Step 3 — Non-client to non-client is not reflected

Remove client status from R1, so R1 and R4 are both non-clients. Routes from R1 (192.168.5.0/24,
learned by R1 from AS 200) now go to the client R3 only; R4 loses them. R4's LAN reaches R3 but no
longer R1. Non-clients must still be fully meshed with each other, just as without an RR.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
router bgp 100
 address-family ipv4 unicast
  no neighbor 1.1.1.1 route-reflector-client
end
```

</details>

**Verify:**

```
R4# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 4, local router ID is 4.4.4.4, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*>i192.168.3.0/24   3.3.3.3                  0    100      0 i
*> 192.168.4.0/24   0.0.0.0                  0         32768 i

Displayed  2 routes and 2 total paths
```

</details>

```
R3# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 5, local router ID is 3.3.3.3, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.3.0/24   0.0.0.0                  0         32768 i
*>i192.168.4.0/24   4.4.4.4                  0    100      0 i
*>i192.168.5.0/24   1.1.1.1                  0    100      0 200 i

Displayed  3 routes and 3 total paths
```

</details>


### Step 4 — Typical design: every edge router is a client

Make R1, R3 and R4 clients. Everyone has every route with only 3 iBGP sessions (full mesh would need 6).
Look at the extra attributes on a reflected route: `Originator` (who injected it into the AS) and
`Cluster list` (which RRs it passed through).

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
router bgp 100
 address-family ipv4 unicast
  neighbor 1.1.1.1 route-reflector-client
  neighbor 4.4.4.4 route-reflector-client
end
```

</details>

**Verify:**

```
R4# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 7
Paths: (1 available, best #1, table default)
  Not advertised to any peer
  200
    1.1.1.1 (metric 20) from 2.2.2.2 (1.1.1.1)
      Origin IGP, metric 0, localpref 100, valid, internal, best (First path received)
      Originator: 1.1.1.1, Cluster list: 2.2.2.2
      Last update: Wed Oct 14 06:52:40 2026
```

</details>

```
root@H4:~# traceroute -n -w1 -q1 192.168.5.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.5.10 (192.168.5.10), 30 hops max, 60 byte packets
 1  192.168.4.1  0.200 ms
 2  10.0.24.2  0.158 ms
 3  10.0.12.1  0.143 ms
 4  10.0.15.5  0.128 ms
 5  192.168.5.10  0.115 ms
```

</details>


## Extra challenges

1. The RR is a single point of failure for the control plane. Add a cable R1-R3 (with OSPF), shut R2's iBGP sessions (`neighbor 1.1.1.1 shutdown` etc.) and see that traffic which would no longer need to pass through R2 still breaks.
2. Add a second RR (see lab 26).

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
