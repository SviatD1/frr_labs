# Lab 06 — BGP Attribute Categories - well-known/optional, mandatory/discretionary, transitive/non-transitive

**Video:** [BGP Attribute Categories - well-known/optional, mandatory/discretionary, transitive/non-transitive](https://www.youtube.com/watch?v=9sHoHr82odQ) (6:45)

Path attributes fall into four categories:

| Category | Must every BGP speaker understand it? | Must be present? | Passed on? | Examples |
|---|---|---|---|---|
| Well-known mandatory | yes | yes, in every UPDATE | yes | ORIGIN, AS_PATH, NEXT_HOP |
| Well-known discretionary | yes | no | yes (within its scope) | LOCAL_PREF, ATOMIC_AGGREGATE |
| Optional transitive | no | no | yes, even if not understood | COMMUNITY, AGGREGATOR |
| Optional non-transitive | no | no | not passed on by a router that does not recognise it | MED, ORIGINATOR_ID, CLUSTER_LIST |

"Transitive" is about what a router does with an optional attribute it does **not** understand. Separately,
each attribute has its own propagation rules: MED is never passed from one neighboring AS on to another
(RFC 4271), and ORIGINATOR_ID / CLUSTER_LIST never leave the AS.

A route from R1 (AS 100) travels through AS 200 (R2, R3 with iBGP) to AS 300 (R4). You attach
attributes at different points and check which ones survive each hop.

## What you will practise

- Find ORIGIN, AS_PATH, NEXT_HOP on every route
- Watch MED (optional non-transitive) stop at the AS boundary
- Watch COMMUNITY (optional transitive) travel end to end
- Watch LOCAL_PREF stay inside AS 200
- Create ATOMIC_AGGREGATE + AGGREGATOR with `aggregate-address`

## Topology

4 FRR routers, 2 Linux hosts.

```
   AS 100              AS 200 (iBGP R2-R3)            AS 300
+----+  +----+ 10.0.12 +----+ 10.0.23 +----+ 10.0.34 +----+  +----+
| H1 |--| R1 |=========| R2 |---------| R3 |=========| R4 |--| H4 |
+----+  +----+  eBGP   +----+  iBGP   +----+  eBGP   +----+  +----+
        dummies 172.16.0.0/24, 172.16.1.0/24 on R1
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
| **R1** | 100 | lan160 (dummy) | 172.16.0.1/24 | extra prefix to advertise |
| **R1** | 100 | lan161 (dummy) | 172.16.1.1/24 | extra prefix to advertise |
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
cd bgp\labs\06-attribute-categories
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-06-attribute-categories`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Well-known mandatory attributes

Look at 192.168.1.0/24 on R4. Every route always carries **ORIGIN** (`IGP`), **AS_PATH**
(`200 100`) and **NEXT_HOP** (10.0.34.3). Originally (RFC 4271) an UPDATE missing one of them reset
the session; today (RFC 7606, implemented by FRR) the route is treated as withdrawn instead.

**Verify:**

```
R4# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 3
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.34.3
  200 100
    10.0.34.3 from 10.0.34.3 (3.3.3.3)
      Origin IGP, valid, external, best (First path received)
      Last update: Tue Oct 13 22:02:21 2026
```

</details>


### Step 2 — Attach MED and a community on R1

On R1, outbound to R2: set MED 50 and community 100:1.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
route-map TO-R2 permit 10
 set metric 50
 set community 100:1
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.12.2 route-map TO-R2 out
end
```

</details>

**Verify:**

```
R2# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 6
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.12.1 10.0.23.3
  100
    10.0.12.1 from 10.0.12.1 (1.1.1.1)
      Origin IGP, metric 50, valid, external, best (First path received)
      Community: 100:1
      Last update: Tue Oct 13 22:02:21 2026
```

</details>

```
R3# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 7
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.34.4
  100
    10.0.23.2 from 10.0.23.2 (2.2.2.2)
      Origin IGP, metric 50, localpref 100, valid, internal, best (First path received)
      Community: 100:1
      Last update: Tue Oct 13 22:02:21 2026
```

</details>

```
R4# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 6
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.34.3
  200 100
    10.0.34.3 from 10.0.34.3 (3.3.3.3)
      Origin IGP, valid, external, best (First path received)
      Community: 100:1
      Last update: Tue Oct 13 22:02:21 2026
```

</details>


### Step 3 — What you should notice

* R2 and R3 (AS 200, which received it from AS 100) see `metric 50`.
* R4 (AS 300) does **not**: RFC 4271 forbids passing a MED received from one AS on to another AS.
  MED only describes the links between two neighboring ASes.
* The community `100:1` is visible on R2, R3 *and* R4: optional **transitive**. (FRR sends standard
  communities to all neighbors by default; on Cisco you need `send-community`.)

### Step 4 — LOCAL_PREF stays inside the AS

On R2, set LOCAL_PREF 250 for routes from R1. R3 (iBGP) sees `localpref 250`. R4 sees nothing:
LOCAL_PREF (well-known **discretionary**) is only sent to iBGP peers and stripped on eBGP.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
route-map FROM-R1 permit 10
 set local-preference 250
router bgp 200
 address-family ipv4 unicast
  neighbor 10.0.12.1 route-map FROM-R1 in
end
```

</details>

**Verify:**

```
R3# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 10
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.34.4
  100
    10.0.23.2 from 10.0.23.2 (2.2.2.2)
      Origin IGP, metric 50, localpref 250, valid, internal, best (First path received)
      Community: 100:1
      Last update: Tue Oct 13 22:02:23 2026
```

</details>

```
R4# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 6
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.34.3
  200 100
    10.0.34.3 from 10.0.34.3 (3.3.3.3)
      Origin IGP, valid, external, best (First path received)
      Community: 100:1
      Last update: Tue Oct 13 22:02:24 2026
```

</details>


### Step 5 — ATOMIC_AGGREGATE and AGGREGATOR

Summarise the two 172.16.x.0/24 networks on R1 into 172.16.0.0/16 and suppress the specifics
(`summary-only`). Downstream routers now see **atomic-aggregate** (well-known discretionary:
"information was lost") and **aggregated by 100 1.1.1.1** (AGGREGATOR, optional transitive).

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 address-family ipv4 unicast
  aggregate-address 172.16.0.0/16 summary-only
end
```

</details>

**Verify:**

```
R4# show bgp ipv4 unicast 172.16.0.0/16
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 172.16.0.0/16, version 10
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.34.3
  200 100, (aggregated by 100 1.1.1.1)
    10.0.34.3 from 10.0.34.3 (3.3.3.3)
      Origin IGP, valid, external, atomic-aggregate, best (First path received)
      Community: 100:1
      Last update: Tue Oct 13 22:02:26 2026
```

</details>

```
R4# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 10, local router ID is 4.4.4.4, vrf id 0
Default local pref 100, local AS 300
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 172.16.0.0/16    10.0.34.3                              0 200 100 i
*> 192.168.1.0/24   10.0.34.3                              0 200 100 i
*> 192.168.4.0/24   0.0.0.0                  0         32768 i

Displayed  3 routes and 3 total paths
```

</details>


## Extra challenges

1. Capture the UPDATE from R3 to R4 with `tcpdump -ni eth1 -vvv tcp port 179` on R4 (clear the session first) and find the attribute flags (Optional/Transitive bits) in the decode.
2. Use `set metric 50` on R3 *outbound* to R4. Is the MED now visible on R4? (Yes: it is set by the neighboring AS, which is the only place MED is meaningful.)
3. Try `aggregate-address 172.16.0.0/16 as-set summary-only`. What changes in AS_PATH, and does ATOMIC_AGGREGATE remain?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
