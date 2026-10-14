# Lab 28 — BGP Answers (troubleshooting lab)

**Video:** [BGP Answers (troubleshooting lab)](https://www.youtube.com/watch?v=NMTtn5a6ZXU) (28:36)

The "BGP Answers" video works through viewer questions. This lab turns the most common questions
("why is my session not coming up?", "why is my route not in the table?") into a **troubleshooting exercise**.
The network has **seven faults** behind six symptoms. The intended design:

* R1 (AS 100) ↔ R2 (AS 200): eBGP on the link.
* R2 ↔ R3: iBGP between loopbacks, OSPF inside AS 200, next-hop-self on both.
* R3 ↔ R4 (AS 300): eBGP **between loopbacks** (3.3.3.3 ↔ 4.4.4.4) reached via static routes.
* R1 advertises 192.168.1.0/24, R4 advertises 192.168.4.0/24. H1 must reach H4.

Fix one symptom at a time. Each step gives the symptom and a hint; the solution is hidden.
Useful commands: `show bgp summary`, `show bgp neighbors X`, `journalctl -u frr -f`,
`show bgp ipv4 unicast <prefix>`, `show bgp nexthop`, `show ip route`, `ip route get <ip>`.

## What you will practise

- Diagnose sessions stuck in Idle/Active/Connect
- Find (Policy), wrong AS, update-source and multihop problems
- Find routes that are not advertised or not valid

## Topology

4 FRR routers, 2 Linux hosts.

```
   AS 100                   AS 200 (OSPF)                  AS 300
+----+  +----+ 10.0.12 +----+ 10.0.23 +----+ 10.0.34 +----+  +----+
| H1 |--| R1 |=========| R2 |---------| R3 |=========| R4 |--| H4 |
+----+  +----+  eBGP   +----+  iBGP   +----+  eBGP   +----+  +----+
                             lo-lo           lo-lo (multihop)
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R2 eth1 | R3 eth0 | 10.0.23.0/24 |
| 3 | R3 eth1 | R4 eth0 | 10.0.34.0/24 |
| 4 | R1 eth1 | H1 eth0 | 192.168.1.0/24 |
| 5 | R4 eth1 | H4 eth0 | 192.168.4.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 192.168.1.1/24 | LAN H1 |
| **R2** | 200 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 200 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 200 | eth1 | 10.0.23.2/24 | R3 |
| **R3** | 200 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 200 | eth0 | 10.0.23.3/24 | R2 |
| **R3** | 200 | eth1 | 10.0.34.3/24 | R4 |
| **R4** | 300 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 300 | eth0 | 10.0.34.4/24 | R3 |
| **R4** | 300 | eth1 | 192.168.4.1/24 | LAN H4 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |

## Bring the lab up

```powershell
cd bgp\labs\28-troubleshooting
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-28-troubleshooting`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Symptom: R1-R2 session never establishes

`show bgp summary` on R1 shows the session cycling; R2's log mentions a NOTIFICATION.
*Hint: compare what each side thinks the other side's AS is.* (`show bgp neighbors 10.0.12.2` →
"Last reset" / "Notification").

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 no neighbor 10.0.12.2 remote-as 201
 neighbor 10.0.12.2 remote-as 200
end
```

</details>

**Verify:**

```
R1# show bgp summary
```
<details><summary>Expected output (captured from a test run)</summary>

```
IPv4 Unicast Summary (VRF default):
BGP router identifier 1.1.1.1, local AS number 100 vrf-id 0
BGP table version 1
RIB entries 1, using 192 bytes of memory
Peers 1, using 724 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
10.0.12.2       4        200         3         3        0    0    0 00:00:02     (Policy) (Policy) N/A

Total number of neighbors 1
```

</details>


### Step 2 — Symptom: session up, R2 does not receive 192.168.1.0/24

The session is Established, but R1's summary shows `(Policy)`.
*Hint: lab 1, RFC 8212.* After changing it, reset the session so the routes are sent again.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 no bgp ebgp-requires-policy
end
```

On **R1** (`vtysh`):
```
clear bgp 10.0.12.2
```

</details>

**Verify:**

```
R2# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 1, local router ID is 2.2.2.2, vrf id 0
Default local pref 100, local AS 200
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.1.0/24   10.0.12.1                0             0 100 i

Displayed  1 routes and 1 total paths
```

</details>


### Step 3 — Symptom: iBGP R2-R3 stays Active

*Hints:* can R2 ping 3.3.3.3? (`ip route get 3.3.3.3`). From which address does R3 open the TCP session
towards 2.2.2.2, and will R2 accept a connection from that address? There are **two** things missing on R3.

<details><summary>Show solution</summary>

On **R3** (`vtysh`):
```
configure terminal
interface lo
 ip ospf area 0
router bgp 200
 neighbor 2.2.2.2 update-source lo
end
```

</details>

**Verify:**

```
R2# show ip route ospf
```
<details><summary>Expected output (captured from a test run)</summary>

```
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

O   2.2.2.2/32 [110/0] is directly connected, lo, weight 1, 00:00:21
O>* 3.3.3.3/32 [110/10] via 10.0.23.3, eth1, weight 1, 00:00:06
O   10.0.23.0/24 [110/10] is directly connected, eth1, weight 1, 00:00:21
```

</details>

```
R2# show bgp summary
```
<details><summary>Expected output (captured from a test run)</summary>

```
IPv4 Unicast Summary (VRF default):
BGP router identifier 2.2.2.2, local AS number 200 vrf-id 0
BGP table version 1
RIB entries 1, using 192 bytes of memory
Peers 2, using 1448 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
3.3.3.3         4        200         3         4        0    0    0 00:00:01            0        1 N/A
10.0.12.1       4        100         9         7        0    0    0 00:00:16            1        1 N/A

Total number of neighbors 2
```

</details>


### Step 4 — Symptom: R3 has 192.168.1.0/24 but does not use it

The route is in R3's table without `*>`. *Hint: look at the next hop and `show bgp nexthop`.*

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
router bgp 200
 address-family ipv4 unicast
  neighbor 3.3.3.3 next-hop-self
end
```

</details>

**Verify:**

```
R3# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 1
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  4.4.4.4
  100
    2.2.2.2 (metric 10) from 2.2.2.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, best (First path received)
      Last update: Wed Oct 14 06:55:57 2026
```

</details>


### Step 5 — Symptom: R3-R4 eBGP session stays down

Both sides peer between loopbacks with static routes, and pinging 4.4.4.4 from R3 works
(`ping -I 3.3.3.3 4.4.4.4`). *Hint: eBGP assumes the neighbor is directly connected (TTL 1). Compare
the two configs.*

<details><summary>Show solution</summary>

On **R4** (`vtysh`):
```
configure terminal
router bgp 300
 neighbor 3.3.3.3 ebgp-multihop 2
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
BGP router identifier 3.3.3.3, local AS number 200 vrf-id 0
BGP table version 1
RIB entries 1, using 192 bytes of memory
Peers 2, using 1448 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
2.2.2.2         4        200         5         3        0    0    0 00:00:06            1        0 N/A
4.4.4.4         4        300         8         6        0    0    0 00:00:00            0        0 N/A

Total number of neighbors 2
```

</details>


### Step 6 — Symptom: nobody learns H4's LAN

Everything is Established but R3 receives 0 prefixes from R4. *Hint: `network` only advertises a
prefix that exists in R4's routing table with exactly that mask.*

<details><summary>Show solution</summary>

On **R4** (`vtysh`):
```
configure terminal
router bgp 300
 address-family ipv4 unicast
  no network 192.168.40.0/24
  network 192.168.4.0/24
end
```

</details>

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
*> 192.168.4.0/24   10.0.12.2                              0 200 300 i

Displayed  2 routes and 2 total paths
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.051 ms
 2  10.0.12.2  0.112 ms
 3  10.0.23.3  0.015 ms
 4  10.0.34.4  0.093 ms
 5  192.168.4.10  0.015 ms
```

</details>


## Extra challenges

1. Write your own fault into a copy of a working lab and swap with a friend.
2. For each fault, find the exact log line in `journalctl -u frr` that would have told you.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
