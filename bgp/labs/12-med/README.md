# Lab 12 — BGP - What is the MED BGP Attribute?

**Video:** [BGP - What is the MED BGP Attribute?](https://www.youtube.com/watch?v=k04h52XZFTc) (5:30)

**MED** (MULTI_EXIT_DISC, optional non-transitive) lets *you* tell a **neighboring AS** which of
your several entry points it should use to reach you. Lower wins. It is only compared between paths
received from the **same neighboring AS** (unless `bgp always-compare-med`), sits at step 6, and a
missing MED counts as 0 (best) unless `bgp bestpath med missing-as-worst`.

AS 100 (R1, R2) connects to AS 200 (R3) over two links. You make AS 200 send traffic for H1 through R2.

## What you will practise

- Set MED outbound with `set metric`
- Steer a neighbor AS's inbound traffic into your network
- See how a missing MED is treated and change it

## Topology

3 FRR routers, 2 Linux hosts.

```
           AS 100                         AS 200
+----+   +----+ 10.0.13/24 (MED 50)  +----+   +----+
| H1 |---| R1 |======================| R3 |---| H3 |
+----+   +----+                      +----+   +----+
           | 10.0.12/24 iBGP            ||
         +----+ 10.0.23/24 (MED 10)     ||
         | R2 |=========================''
         +----+
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | R3 eth0 | 10.0.13.0/24 |
| 3 | R2 eth1 | R3 eth1 | 10.0.23.0/24 |
| 4 | R1 eth2 | H1 eth0 | 192.168.1.0/24 |
| 5 | R3 eth2 | H3 eth0 | 192.168.3.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.13.1/24 | R3 |
| **R1** | 100 | eth2 | 192.168.1.1/24 | LAN H1 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.23.2/24 | R3 |
| **R3** | 200 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 200 | eth0 | 10.0.13.3/24 | R1 |
| **R3** | 200 | eth1 | 10.0.23.3/24 | R2 |
| **R3** | 200 | eth2 | 192.168.3.1/24 | LAN H3 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H3** | - | eth0 | 192.168.3.10/24 | R3 |
| **H3** | - | default gw | 192.168.3.1 | |

## Bring the lab up

```powershell
cd bgp\labs\12-med
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-12-med`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Baseline

R3 receives 192.168.1.0/24 from R1 and from R2 (R2 learned it over iBGP). AS_PATH `100` on both,
MED 0 on both. R3 picks R1 (tie-break). Traffic H3 → H1 enters at R1.

**Verify:**

```
R3# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 2
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.13.1 10.0.23.2
  100
    10.0.13.1 from 10.0.13.1 (1.1.1.1)
      Origin IGP, metric 0, valid, external, multipath, best (Router ID)
      Last update: Tue Oct 13 22:03:58 2026
  100
    10.0.23.2 from 10.0.23.2 (2.2.2.2)
      Origin IGP, valid, external, multipath
      Last update: Tue Oct 13 22:03:58 2026
```

</details>

```
root@H3:~# traceroute -n -w1 -q1 192.168.1.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.1.10 (192.168.1.10), 30 hops max, 60 byte packets
 1  192.168.3.1  0.077 ms
 2  10.0.23.2  0.014 ms
 3  10.0.13.1  0.014 ms
 4  192.168.1.10  0.037 ms
```

</details>


### Step 2 — Advertise MED 50 from R1 and MED 10 from R2

AS 100 wants traffic to arrive via R2 (say, R1's link is the backup). Set the MED outbound
on both border routers. Lower MED wins, so R3 now sends traffic for H1 to R2.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
route-map MED50 permit 10
 set metric 50
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.13.3 route-map MED50 out
end
```

On **R2** (`vtysh`):
```
configure terminal
route-map MED10 permit 10
 set metric 10
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.23.3 route-map MED10 out
end
```

On **R1** (`vtysh`):
```
clear bgp 10.0.13.3 soft out
```

On **R2** (`vtysh`):
```
clear bgp 10.0.23.3 soft out
```

</details>

**Verify:**

```
R3# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 4, local router ID is 3.3.3.3, vrf id 0
Default local pref 100, local AS 200
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*  192.168.1.0/24   10.0.13.1               50             0 100 i
*>                  10.0.23.2               10             0 100 i
*> 192.168.3.0/24   0.0.0.0                  0         32768 i

Displayed  2 routes and 3 total paths
```

</details>

```
R3# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 4
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.13.1 10.0.23.2
  100
    10.0.13.1 from 10.0.13.1 (1.1.1.1)
      Origin IGP, metric 50, valid, external
      Last update: Tue Oct 13 22:04:00 2026
  100
    10.0.23.2 from 10.0.23.2 (2.2.2.2)
      Origin IGP, metric 10, valid, external, best (MED)
      Last update: Tue Oct 13 22:04:00 2026
```

</details>

```
root@H3:~# traceroute -n -w1 -q1 192.168.1.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.1.10 (192.168.1.10), 30 hops max, 60 byte packets
 1  192.168.3.1  0.036 ms
 2  10.0.23.2  0.013 ms
 3  10.0.13.1  0.012 ms
 4  192.168.1.10  0.013 ms
```

</details>


### Step 3 — Missing MED

Remove the MED on R2. Its path now has *no* MED, which FRR (like the RFC) treats as 0: still the
best. Then tell R3 to treat a missing MED as the worst possible value with
`bgp bestpath med missing-as-worst`: R1's MED 50 wins.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
router bgp 100
 address-family ipv4 unicast
  no neighbor 10.0.23.3 route-map MED10 out
end
```

On **R2** (`vtysh`):
```
clear bgp 10.0.23.3 soft out
```

On **R3** (`vtysh`):
```
configure terminal
router bgp 200
 bgp bestpath med missing-as-worst
end
```

</details>

**Verify:**

```
R3# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 6, local router ID is 3.3.3.3, vrf id 0
Default local pref 100, local AS 200
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.1.0/24   10.0.13.1               50             0 100 i
*                   10.0.23.2                              0 100 i
*> 192.168.3.0/24   0.0.0.0                  0         32768 i

Displayed  2 routes and 3 total paths
```

</details>


## Extra challenges

1. Add a third AS (another router, AS 300) that also advertises 192.168.1.0/24 to R3 with a lower MED. Is it compared? Turn on `bgp always-compare-med` and compare again.
2. Use `set metric +10` / `set metric -10` (relative MED). Where is that useful?
3. MED is compared only after AS_PATH: prepend on R2 and see the MED preference vanish.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
