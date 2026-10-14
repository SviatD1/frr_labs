# Lab 07 — BGP - Why is the BGP Best Path Algorithm so complex?

**Video:** [BGP - Why is the BGP Best Path Algorithm so complex?](https://www.youtube.com/watch?v=KGHk_y-nstM) (7:33)

BGP must make a *deterministic* choice between paths that can differ in many independent ways,
    while giving operators knobs for policy (weight, local-pref), for neighbors' wishes (MED, prepend)
    and for stable tie-breaking (oldest, router-id, address). Hence a long ordered list.

    Here R1 receives the **same anycast prefix 203.0.113.0/24 from three ASes**, each path different
    in a different attribute. You predict the winner, then remove the winner's advantage step by step.

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

## What you will practise

- Predict best path from several attributes at once
- Watch FRR's `best (<reason>)` change as you remove advantages
- Create origin `?` with `redistribute connected`
- Use `neighbor shutdown` to remove a path

## Topology

4 FRR routers, 1 Linux hosts.

```
                     +----+ AS 200 (prepends 200 200, R1 sets local-pref 150)
            .--------| R2 |  203.0.113.0/24
            |  10.0.12+----+
+----+   +----+ 10.0.13 +----+ AS 300 (origin incomplete '?')
| H1 |---| R1 |---------| R3 |  203.0.113.0/24
+----+   +----+         +----+
   AS 100   |  10.0.14+----+ AS 400 (plain: network, origin IGP)
            '--------| R4 |  203.0.113.0/24
                     +----+
203.0.113.1 lives on a dummy interface "svc" on R2, R3 and R4 (anycast)
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | R3 eth0 | 10.0.13.0/24 |
| 3 | R1 eth2 | R4 eth0 | 10.0.14.0/24 |
| 4 | R1 eth3 | H1 eth0 | 192.168.1.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.13.1/24 | R3 |
| **R1** | 100 | eth2 | 10.0.14.1/24 | R4 |
| **R1** | 100 | eth3 | 192.168.1.1/24 | LAN H1 |
| **R2** | 200 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 200 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 200 | svc (dummy) | 203.0.113.1/24 | extra prefix to advertise |
| **R3** | 300 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 300 | eth0 | 10.0.13.3/24 | R1 |
| **R3** | 300 | svc (dummy) | 203.0.113.1/24 | extra prefix to advertise |
| **R4** | 400 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 400 | eth0 | 10.0.14.4/24 | R1 |
| **R4** | 400 | svc (dummy) | 203.0.113.1/24 | extra prefix to advertise |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |

## Bring the lab up

```powershell
cd bgp\labs\07-best-path-complexity
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-07-best-path-complexity`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Predict the winner

Fill in this table from `show bgp ipv4 unicast 203.0.113.0/24` before reading on:

| Path via | Weight | Local-pref | AS_PATH length | Origin |
|---|---|---|---|---|
| R2 (AS 200) | 0 | **150** | 3 | i |
| R3 (AS 300) | 0 | 100 | 1 | **?** |
| R4 (AS 400) | 0 | 100 | 1 | i |

Local-pref is compared before AS_PATH, so R2 wins despite the longest path.

**Verify:**

```
R1# show bgp ipv4 unicast 203.0.113.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 203.0.113.0/24, version 2
Paths: (3 available, best #3, table default)
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3 10.0.14.4
  300
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin incomplete, metric 0, valid, external
      Last update: Tue Oct 13 22:02:36 2026
  400
    10.0.14.4 from 10.0.14.4 (4.4.4.4)
      Origin IGP, metric 0, valid, external
      Last update: Tue Oct 13 22:02:36 2026
  200 200 200
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 150, valid, external, best (Local Pref)
      Last update: Tue Oct 13 22:02:36 2026
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 203.0.113.1
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 203.0.113.1 (203.0.113.1), 30 hops max, 60 byte packets
 1  192.168.1.1  0.102 ms
 2  203.0.113.1  0.015 ms
```

</details>


### Step 2 — Remove local-pref → AS_PATH, then ORIGIN decide

Remove the inbound route-map from R2. Now R2's path is longest (3) and drops out at step 4.
R3 and R4 tie on AS_PATH length (1) and are separated at step 5, ORIGIN: `i` beats `?`. R4 wins.

Note: FRR compares paths **pairwise** (best-so-far against the next candidate) and prints the
reason of the *last* comparison the winner went through. With three paths that may say `AS Path`
(R4 vs R2) even though R4 beat R3 on `Origin`. Do the pairwise comparisons yourself to be sure.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 address-family ipv4 unicast
  no neighbor 10.0.12.2 route-map FROM-R2 in
end
```

On **R1** (`vtysh`):
```
clear bgp 10.0.12.2 soft in
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 203.0.113.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 203.0.113.0/24, version 3
Paths: (3 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3 10.0.14.4
  300
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin incomplete, metric 0, valid, external
      Last update: Tue Oct 13 22:02:36 2026
  400
    10.0.14.4 from 10.0.14.4 (4.4.4.4)
      Origin IGP, metric 0, valid, external, best (AS Path)
      Last update: Tue Oct 13 22:02:36 2026
  200 200 200
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, valid, external
      Last update: Tue Oct 13 22:02:38 2026
```

</details>


### Step 3 — Take R4 away

Shut the session to R4. Between R2 (`200 200 200`, origin i) and R3 (`300`, origin ?), AS_PATH
length is compared *before* origin, so R3 wins in spite of its worse origin.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 neighbor 10.0.14.4 shutdown
end
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 203.0.113.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 203.0.113.0/24, version 4
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3
  300
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin incomplete, metric 0, valid, external, best (AS Path)
      Last update: Tue Oct 13 22:02:36 2026
  200 200 200
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, valid, external
      Last update: Tue Oct 13 22:02:38 2026
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 203.0.113.1
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 203.0.113.1 (203.0.113.1), 30 hops max, 60 byte packets
 1  192.168.1.1  0.039 ms
 2  203.0.113.1  0.021 ms
```

</details>


### Step 4 — Weight trumps everything

Bring R4 back and set weight 10 on R2. Even with the longest AS_PATH, R2 wins at step 1.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 no neighbor 10.0.14.4 shutdown
 address-family ipv4 unicast
  neighbor 10.0.12.2 weight 10
end
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 203.0.113.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 203.0.113.0/24, version 5
Paths: (3 available, best #3, table default)
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3 10.0.14.4
  400
    10.0.14.4 from 10.0.14.4 (4.4.4.4)
      Origin IGP, metric 0, valid, external
      Last update: Tue Oct 13 22:02:45 2026
  300
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin incomplete, metric 0, valid, external
      Last update: Tue Oct 13 22:02:37 2026
  200 200 200
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, weight 10, valid, external, best (Weight)
      Last update: Tue Oct 13 22:02:43 2026
```

</details>


## Extra challenges

1. Remove the weight and enable `bgp bestpath as-path ignore` on R1. Which step decides now?
2. Make R3 originate with `network` too (origin i), then on R1 add `bgp bestpath as-path multipath-relax` (the AS_PATHs `300` and `400` differ) and `maximum-paths 2` under `address-family ipv4 unicast`. Look for `multipath` in the output and two next hops in `ip route`.
3. Write down which of the 13 steps you used in this lab. Which ones are policy knobs and which are pure tie-breakers?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
