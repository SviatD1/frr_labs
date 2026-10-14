# Lab 16 — BGP - BGP Algorithm Prefers the Lowest Router ID

**Video:** [BGP - BGP Algorithm Prefers the Lowest Router ID](https://www.youtube.com/watch?v=ZHlISG4l6TI) (7:48)

Step 11: if everything else is equal, prefer the path from the neighbor with the **lowest BGP router ID**
(for reflected routes the ORIGINATOR_ID is used instead, lab 25). For eBGP paths the "oldest path" step
(lab 15) usually decides first, unless it is disabled or neither path is currently best; for iBGP paths
router ID is reached directly.
The router ID is a 32-bit number written like an IPv4 address; set it explicitly with `bgp router-id`.

## What you will practise

- Find the router ID of each neighbor
- Change a router ID and see the best path follow
- Know how FRR picks a router ID automatically

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
cd bgp\labs\16-lowest-router-id
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-16-lowest-router-id`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — R1 picks the exit with the lowest router ID

R1's two iBGP paths are equal up to and including IGP metric (10 vs 10). iBGP paths skip the
"oldest" step, so the router ID decides: 2.2.2.2 < 3.3.3.3.

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
      Last update: Wed Oct 14 06:50:20 2026
  200
    3.3.3.3 (metric 10) from 3.3.3.3 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath
      Last update: Wed Oct 14 06:50:20 2026
```

</details>

```
R1# show bgp summary
```
<details><summary>Expected output (captured from a test run)</summary>

```
IPv4 Unicast Summary (VRF default):
BGP router identifier 1.1.1.1, local AS number 100 vrf-id 0
BGP table version 2
RIB entries 3, using 576 bytes of memory
Peers 2, using 1448 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
2.2.2.2         4        100         4         4        0    0    0 00:00:01            1        1 N/A
3.3.3.3         4        100         4         4        0    0    0 00:00:01            1        1 N/A

Total number of neighbors 2
```

</details>


### Step 2 — Lower R3's router ID

Change R3's BGP router ID to 2.0.0.3 (lower than 2.2.2.2). Changing the router ID resets R3's sessions.
R1 now prefers R3.

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
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 4
Paths: (2 available, best #1, table default)
  Not advertised to any peer
  200
    3.3.3.3 (metric 10) from 3.3.3.3 (2.0.0.3)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath, best (Router ID)
      Last update: Wed Oct 14 06:50:24 2026
  200
    2.2.2.2 (metric 10) from 2.2.2.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, multipath
      Last update: Wed Oct 14 06:50:20 2026
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.453 ms
 2  10.0.12.2  0.307 ms
 3  10.0.24.4  0.294 ms
 4  192.168.4.10  0.281 ms
```

</details>


### Step 3 — Automatic router ID

Remove `bgp router-id` from R2. FRR then takes zebra's router ID, which by default is the highest
loopback address (2.2.2.2 here), and failing that, the highest interface address. `show bgp summary`
on R2 shows the result (and `show router-id` shows zebra's choice). Always configure it explicitly in production: an automatic ID can change
when interfaces change.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
router bgp 100
 no bgp router-id
end
```

</details>

**Verify:**

```
R2# show bgp summary
```
<details><summary>Expected output (captured from a test run)</summary>

```
IPv4 Unicast Summary (VRF default):
BGP router identifier 2.2.2.2, local AS number 100 vrf-id 0
BGP table version 2
RIB entries 3, using 576 bytes of memory
Peers 3, using 2172 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
1.1.1.1         4        100         4         4        0    0    0 00:00:06            1        1 N/A
3.3.3.3         4        100        10        10        0    0    0 00:00:02            1        1 N/A
10.0.24.4       4        200         5         5        0    0    0 00:00:25            1        2 N/A

Total number of neighbors 3
```

</details>


## Extra challenges

1. Configure two routers with the same router ID. What does the session R1 log say?
2. Give R4 two eBGP paths into AS 100 and enable `bgp bestpath compare-routerid` on R4: which AS 100 router does R4 prefer?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
