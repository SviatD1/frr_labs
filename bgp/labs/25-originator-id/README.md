# Lab 25 — BGP - What is the BGP Originator ID?

**Video:** [BGP - What is the BGP Originator ID?](https://www.youtube.com/watch?v=c8dJPJLlU08) (9:31)

When an RR reflects a route it adds **ORIGINATOR_ID** (optional non-transitive): the router ID of the
router that injected the route into the AS. It is used for two things:

1. **Loop prevention**: a router that receives a route carrying its *own* router ID as originator drops it.
   (FRR, like most implementations, also avoids sending a route back to its originator in the first place.)
2. **Best-path step 11**: for a reflected route, the *originator ID* is compared instead of the router ID
   of the neighbor that sent it.

R1 is the RR. R2 and R3 are border routers to AS 200. R4 is a client that also has a direct (non-RR) iBGP
session with R2. OSPF costs are chosen so that R4 ends up comparing a reflected path with a direct one.

## What you will practise

- Read Originator and Cluster list on a reflected path
- See step 11 use ORIGINATOR_ID instead of the RR's router ID
- Explain how ORIGINATOR_ID prevents loops

## Topology

5 FRR routers, 2 Linux hosts.

```
                      AS 100 (OSPF, costs in [ ])
             +----+ [20] +----+ 10.0.25  +----+
             | R4 |------| R2 |==========| R5 |--- H5
      H4 ----+----+      +----+          +----+  AS 200
               |[10]       |[20]           ||
             +----+        |               ||
             | R1 |--------'               ||
             | RR |   [10]  +----+ 10.0.35 ||
             +----+---------| R3 |=========''
                            +----+
iBGP: R1(RR) <-> R2, R3, R4 (clients); plus a direct session R2 <-> R4
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | R3 eth0 | 10.0.13.0/24 |
| 3 | R1 eth2 | R4 eth0 | 10.0.14.0/24 |
| 4 | R2 eth1 | R4 eth1 | 10.0.24.0/24 |
| 5 | R2 eth2 | R5 eth0 | 10.0.25.0/24 |
| 6 | R3 eth1 | R5 eth1 | 10.0.35.0/24 |
| 7 | R4 eth2 | H4 eth0 | 192.168.4.0/24 |
| 8 | R5 eth2 | H5 eth0 | 192.168.5.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.13.1/24 | R3 |
| **R1** | 100 | eth2 | 10.0.14.1/24 | R4 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.24.2/24 | R4 |
| **R2** | 100 | eth2 | 10.0.25.2/24 | R5 |
| **R3** | 100 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 100 | eth0 | 10.0.13.3/24 | R1 |
| **R3** | 100 | eth1 | 10.0.35.3/24 | R5 |
| **R4** | 100 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 100 | eth0 | 10.0.14.4/24 | R1 |
| **R4** | 100 | eth1 | 10.0.24.4/24 | R2 |
| **R4** | 100 | eth2 | 192.168.4.1/24 | LAN H4 |
| **R5** | 200 | lo | 5.5.5.5/32 | loopback / router-id |
| **R5** | 200 | eth0 | 10.0.25.5/24 | R2 |
| **R5** | 200 | eth1 | 10.0.35.5/24 | R3 |
| **R5** | 200 | eth2 | 192.168.5.1/24 | LAN H5 |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |
| **H5** | - | eth0 | 192.168.5.10/24 | R5 |
| **H5** | - | default gw | 192.168.5.1 | |

## Bring the lab up

```powershell
cd bgp\labs\25-originator-id
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-25-originator-id`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — The RR picks R3's path and reflects it

R1 hears 192.168.5.0/24 from R2 (next hop 2.2.2.2, IGP cost 20) and R3 (3.3.3.3, cost 10) and picks
R3 by IGP metric. It reflects that path to its other clients with `Originator: 3.3.3.3` and
`Cluster list: 1.1.1.1`.

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 1
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  2.2.2.2 3.3.3.3 4.4.4.4
  200, (Received from a RR-client)
    2.2.2.2 (metric 20) from 2.2.2.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal
      Last update: Wed Oct 14 06:54:36 2026
  200, (Received from a RR-client)
    3.3.3.3 (metric 10) from 3.3.3.3 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal, best (IGP Metric)
      Last update: Wed Oct 14 06:54:35 2026
```

</details>


### Step 2 — R4 compares a reflected path with a direct one

R4 has two paths:
* reflected by R1: next hop 3.3.3.3 (cost 10+10 = 20), originator **3.3.3.3**
* direct from R2: next hop 2.2.2.2 (cost 20), router ID **2.2.2.2**

Everything ties up to step 11. If R4 compared the router ID of the *sender*, the RR's 1.1.1.1 would win.
It uses the **originator ID** 3.3.3.3 instead, so the direct path from R2 (2.2.2.2) wins with
reason `Router ID`. The rule makes the choice independent of which RR happened to deliver the route.

**Verify:**

```
R4# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 4
Paths: (2 available, best #2, table default)
  Not advertised to any peer
  200
    3.3.3.3 (metric 20) from 1.1.1.1 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath
      Originator: 3.3.3.3, Cluster list: 1.1.1.1
      Last update: Wed Oct 14 06:54:36 2026
  200
    2.2.2.2 (metric 20) from 2.2.2.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath, best (Router ID)
      Last update: Wed Oct 14 06:54:36 2026
```

</details>


### Step 3 — Prove it: lower R3's router ID

Change R3's router ID to 2.0.0.3. The RR still reflects R3's path, the RR's own ID (1.1.1.1) has not
changed, but now the originator ID 2.0.0.3 is lower than 2.2.2.2: the reflected path wins.

<details><summary>Show solution</summary>

On **R3** (`vtysh`):
```
configure terminal
router bgp 100
 bgp router-id 2.0.0.3
end
```

</details>

**Verify:**

```
R4# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 6
Paths: (2 available, best #1, table default)
  Not advertised to any peer
  200
    3.3.3.3 (metric 20) from 1.1.1.1 (2.0.0.3)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath, best (Router ID)
      Originator: 2.0.0.3, Cluster list: 1.1.1.1
      Last update: Wed Oct 14 06:54:43 2026
  200
    2.2.2.2 (metric 20) from 2.2.2.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath
      Last update: Wed Oct 14 06:54:36 2026
```

</details>


### Step 4 — Loop prevention

R3 never receives its own route back from the RR. Check R3's table: one path to 192.168.5.0/24, its own
eBGP path, and nothing reflected with `Originator: 2.0.0.3`. If an RR (or a chain of RRs) did send it
back, R3 would see its own router ID in ORIGINATOR_ID and drop the update.

**Verify:**

```
R3# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 5
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  1.1.1.1 10.0.35.5
  200
    10.0.35.5 from 10.0.35.5 (5.5.5.5)
      Origin IGP, metric 0, valid, external, best (First path received)
      Last update: Wed Oct 14 06:54:42 2026
```

</details>


## Extra challenges

1. Run `debug bgp updates in` on R3, follow the log with `journalctl -u frr -f` in a second console, and run `clear bgp * soft` on R1. Do you see any update for 192.168.5.0/24 coming from the RR?
2. Change OSPF costs so the RR picks R2's path. Which path does R4 pick now, and by which step?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
