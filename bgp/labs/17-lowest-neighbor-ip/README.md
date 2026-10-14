# Lab 17 — BGP - BGP Prefers the Lowest Neighbor IP Address

**Video:** [BGP - BGP Prefers the Lowest Neighbor IP Address](https://www.youtube.com/watch?v=VHe_w-zsNNY) (4:31)

The very last tie-breaker (step 13) is the **neighbor address**: lowest wins. You only get there when two
paths are identical in every other respect, including router ID: typically two parallel sessions to the
**same router**. R1 and R2 are connected by two cables with one iBGP session on each.

## What you will practise

- Build two parallel BGP sessions to the same router
- See `best (Neighbor IP)`
- Fail one link and watch the other take over

## Topology

2 FRR routers, 2 Linux hosts.

```
                  AS 100 (iBGP on both links)
+----+   +----+  eth0  10.0.12.0/24  eth0  +----+   +----+
| H1 |---| R1 |============================| R2 |---| H2 |
+----+   +----+  eth1  10.0.21.0/24  eth1  +----+   +----+
                =============================
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | R2 eth1 | 10.0.21.0/24 |
| 3 | R1 eth2 | H1 eth0 | 192.168.1.0/24 |
| 4 | R2 eth2 | H2 eth0 | 192.168.2.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.21.1/24 | R2 |
| **R1** | 100 | eth2 | 192.168.1.1/24 | LAN H1 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.21.2/24 | R1 |
| **R2** | 100 | eth2 | 192.168.2.1/24 | LAN H2 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H2** | - | eth0 | 192.168.2.10/24 | R2 |
| **H2** | - | default gw | 192.168.2.1 | |

## Bring the lab up

```powershell
cd bgp\labs\17-lowest-neighbor-ip
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-17-lowest-neighbor-ip`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Two identical paths

R1 receives 192.168.2.0/24 twice from R2: same router ID, same attributes, both connected next hops.
The neighbor address breaks the tie: 10.0.12.2 < 10.0.21.2.

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.2.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.2.0/24, version 2
Paths: (2 available, best #2, table default)
  Not advertised to any peer
  Local
    10.0.21.2 from 10.0.21.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath
      Last update: Wed Oct 14 06:50:30 2026
  Local
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath, best (Neighbor IP)
      Last update: Wed Oct 14 06:50:30 2026
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.2.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.2.10 (192.168.2.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.172 ms
 2  10.0.21.2  0.090 ms
 3  192.168.2.10  0.082 ms
```

</details>


### Step 2 — Fail the preferred link

Take R2's eth0 down. The session on 10.0.12.0/24 drops, the remaining path via 10.0.21.2 is used.

<details><summary>Show solution</summary>

On **R2** (Linux shell):
```bash
ip link set eth0 down
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.2.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.2.0/24, version 3
Paths: (2 available, best #1, table default)
  Not advertised to any peer
  Local
    10.0.21.2 from 10.0.21.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, best (First path received)
      Last update: Wed Oct 14 06:50:30 2026
  Local
    10.0.12.2 (inaccessible) from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, invalid, internal
      Last update: Wed Oct 14 06:50:30 2026
```

</details>


### Step 3 — Bring it back

Bring eth0 up again. Because these are iBGP paths there is no "keep the oldest" rule: as soon as the
session is back, 10.0.12.2 wins again.

<details><summary>Show solution</summary>

On **R2** (Linux shell):
```bash
ip link set eth0 up
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.2.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.2.0/24, version 4
Paths: (2 available, best #2, table default)
  Not advertised to any peer
  Local
    10.0.21.2 from 10.0.21.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath
      Last update: Wed Oct 14 06:50:30 2026
  Local
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath, best (Neighbor IP)
      Last update: Wed Oct 14 06:50:30 2026
```

</details>


## Extra challenges

1. Make the two sessions eBGP (R2 in AS 200). Which step decides now, and what happens after a link flap?
2. A better design for parallel links: one session between loopbacks with two static/OSPF routes (ECMP). Build it.
3. Use `maximum-paths ibgp 2` on R1 to load-share over both sessions.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
