# Lab 13 — BGP - Why does the BGP Algorithm Prefer eBGP routes over iBGP routes?

**Video:** [BGP - Why does the BGP Algorithm Prefer eBGP routes over iBGP routes?](https://www.youtube.com/watch?v=0ffgcK70MxU) (5:08)

At step 7, an eBGP-learned path beats an iBGP-learned one. Reasoning: an eBGP path leaves your AS
right here (no extra hop across your own network, "hot-potato" routing), and the iBGP copy is usually
just another border router's eBGP path anyway. It also matches administrative distance (eBGP 20 < iBGP 200).
But it is a *late* step: anything above it, such as MED, still overrides it.

## What you will practise

- See `best (Peer Type)` on both border routers
- Compare AD 20 vs 200
- Show that MED (step 6) beats peer type (step 7)

## Topology

3 FRR routers, 3 Linux hosts.

```
           AS 100                         AS 200
+----+   +----+ 10.0.13/24           +----+   +----+
| H1 |---| R1 |======================| R3 |---| H3 |
+----+   +----+                      +----+   +----+
           | 10.0.12/24 iBGP            ||
+----+   +----+ 10.0.23/24              ||
| H2 |---| R2 |=========================''
+----+   +----+
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | R3 eth0 | 10.0.13.0/24 |
| 3 | R2 eth1 | R3 eth1 | 10.0.23.0/24 |
| 4 | R1 eth2 | H1 eth0 | 192.168.1.0/24 |
| 5 | R2 eth2 | H2 eth0 | 192.168.2.0/24 |
| 6 | R3 eth2 | H3 eth0 | 192.168.3.0/24 |

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
| **R2** | 100 | eth2 | 192.168.2.1/24 | LAN H2 |
| **R3** | 200 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 200 | eth0 | 10.0.13.3/24 | R1 |
| **R3** | 200 | eth1 | 10.0.23.3/24 | R2 |
| **R3** | 200 | eth2 | 192.168.3.1/24 | LAN H3 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H2** | - | eth0 | 192.168.2.10/24 | R2 |
| **H2** | - | default gw | 192.168.2.1 | |
| **H3** | - | eth0 | 192.168.3.10/24 | R3 |
| **H3** | - | default gw | 192.168.3.1 | |

## Bring the lab up

```powershell
cd bgp\labs\13-ebgp-over-ibgp
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-13-ebgp-over-ibgp`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Both border routers prefer their own eBGP path

R2 has two paths to 192.168.3.0/24: its eBGP path (next hop 10.0.23.3) and the iBGP path from R1
(next hop 10.0.12.1). Weight, local-pref, AS_PATH, origin and MED are identical, so step 7 decides:
**eBGP wins**. R1 does the same mirrored. Each router hands traffic to AS 200 as soon as possible.

**Verify:**

```
R2# show bgp ipv4 unicast 192.168.3.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.3.0/24, version 2
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.12.1 10.0.23.3
  200
    10.0.12.1 from 10.0.12.1 (1.1.1.1)
      Origin IGP, metric 0, localpref 100, valid, internal
      Last update: Wed Oct 14 06:49:05 2026
  200
    10.0.23.3 from 10.0.23.3 (3.3.3.3)
      Origin IGP, metric 0, valid, external, best (Peer Type)
      Last update: Wed Oct 14 06:49:05 2026
```

</details>

```
root@H2:~# traceroute -n -w1 -q1 192.168.3.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.3.10 (192.168.3.10), 30 hops max, 60 byte packets
 1  192.168.2.1  0.227 ms
 2  10.0.13.3  0.023 ms
 3  192.168.3.10  0.113 ms
```

</details>


### Step 2 — Admin distance agrees

In the RIB, eBGP routes have distance 20 and iBGP routes 200. Compare R2's BGP route to
192.168.3.0/24 with its route to H1's LAN, which it only knows via iBGP.

**Verify:**

```
R2# show ip route bgp
```
<details><summary>Expected output (captured from a test run)</summary>

```
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

B>* 192.168.1.0/24 [200/0] via 10.0.12.1, eth0, weight 1, 00:00:02
B>* 192.168.3.0/24 [20/0] via 10.0.23.3, eth1, weight 1, 00:00:02
```

</details>


### Step 3 — MED is checked first

Make AS 200 (R3) advertise MED 100 to R2 and MED 0 to R1. R2 now compares MED 100 (eBGP)
with MED 0 (iBGP path via R1, same neighbor AS 200). Step 6 comes before step 7: **the iBGP path wins**,
and H2's traffic crosses R1.

<details><summary>Show solution</summary>

On **R3** (`vtysh`):
```
configure terminal
route-map MED100 permit 10
 set metric 100
router bgp 200
 address-family ipv4 unicast
  neighbor 10.0.23.2 route-map MED100 out
end
```

On **R3** (`vtysh`):
```
clear bgp 10.0.23.2 soft out
```

</details>

**Verify:**

```
R2# show bgp ipv4 unicast 192.168.3.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.3.0/24, version 4
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.23.3
  200
    10.0.12.1 from 10.0.12.1 (1.1.1.1)
      Origin IGP, metric 0, localpref 100, valid, internal, best (MED)
      Last update: Wed Oct 14 06:49:05 2026
  200
    10.0.23.3 from 10.0.23.3 (3.3.3.3)
      Origin IGP, metric 100, valid, external
      Last update: Wed Oct 14 06:49:07 2026
```

</details>

```
root@H2:~# traceroute -n -w1 -q1 192.168.3.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.3.10 (192.168.3.10), 30 hops max, 60 byte packets
 1  192.168.2.1  0.177 ms
 2  10.0.12.1  0.136 ms
 3  10.0.13.3  0.123 ms
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
20  192.168.3.10  0.091 ms
```

</details>


## Extra challenges

1. Remove the MED and instead lower local-pref on R2's eBGP path to 90. Same result, but which router(s) are affected now?
2. Why could preferring iBGP over eBGP create routing loops between two border routers that both point at each other?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
