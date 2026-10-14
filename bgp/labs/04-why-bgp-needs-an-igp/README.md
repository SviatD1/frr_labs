# Lab 04 — Why does BGP require an IGP to function?

**Video:** [Why does BGP require an IGP to function?](https://www.youtube.com/watch?v=SN_TDZ2eDAA) (6:17)

iBGP sessions are normally built between **loopbacks**, and iBGP routes carry a NEXT_HOP that
is usually not directly connected. BGP itself has no idea how to reach either of them: an IGP
(here OSPF) has to provide reachability *inside* the AS. You will also see the second reason
for an IGP + iBGP everywhere: every router in the transit path must know the external routes.

## What you will practise

- Build iBGP sessions between loopbacks with `update-source lo`
- See sessions stuck in Active/Connect without an IGP
- Configure OSPF (point-to-point, loopbacks) in FRR
- Understand recursive next-hop resolution (`show ip route` → *recursive via*)
- Create and observe a black hole when a transit router does not run BGP

## Topology

4 FRR routers, 2 Linux hosts.

```
                     AS 100 (OSPF area 0 inside)                       AS 200
+----+   +----+ 10.0.12/24 +----+ 10.0.23/24 +----+ 10.0.34/24 +----+   +----+
| H1 |---| R1 |------------| R2 |------------| R3 |============| R4 |---| H4 |
+----+   +----+ .1      .2 +----+ .2      .3 +----+ .3  eBGP .4 +----+   +----+
         lo 1.1.1.1        lo 2.2.2.2        lo 3.3.3.3
         iBGP full mesh between loopbacks: R1-R2, R1-R3, R2-R3
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
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.23.2/24 | R3 |
| **R3** | 100 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 100 | eth0 | 10.0.23.3/24 | R2 |
| **R3** | 100 | eth1 | 10.0.34.3/24 | R4 |
| **R4** | 200 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 200 | eth0 | 10.0.34.4/24 | R3 |
| **R4** | 200 | eth1 | 192.168.4.1/24 | LAN H4 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |

## Bring the lab up

```powershell
cd bgp\labs\04-why-bgp-needs-an-igp
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-04-why-bgp-needs-an-igp`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — iBGP sessions do not come up

All iBGP neighbors point at loopbacks. R1 has no route to 2.2.2.2 or 3.3.3.3 (only
connected routes), so the TCP connection can never be opened: the sessions sit in
*Active*/*Connect*. Even R1-R2, which share a cable, fail: the loopbacks are not on that cable.

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
Peers 2, using 1448 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
2.2.2.2         4        100         0         0        0    0    0    never       Active        0 N/A
3.3.3.3         4        100         0         0        0    0    0    never       Active        0 N/A

Total number of neighbors 2
```

</details>

```
root@R1:~# ip route get 3.3.3.3
```
<details><summary>Expected output (captured from a test run)</summary>

```
RTNETLINK answers: Network is unreachable
```

</details>


### Step 2 — Add OSPF inside AS 100

Enable OSPF on the internal links and on the loopbacks of R1, R2 and R3. Do **not** run OSPF
towards R4: the IGP stays inside the AS. Use point-to-point network type so adjacencies form
immediately (no DR election).

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
interface eth0
 ip ospf area 0
 ip ospf network point-to-point
exit
!
interface lo
 ip ospf area 0
exit
!
router ospf
 ospf router-id 1.1.1.1
exit
!
end
```

On **R2** (`vtysh`):
```
configure terminal
interface eth0
 ip ospf area 0
 ip ospf network point-to-point
exit
!
interface eth1
 ip ospf area 0
 ip ospf network point-to-point
exit
!
interface lo
 ip ospf area 0
exit
!
router ospf
 ospf router-id 2.2.2.2
exit
!
end
```

On **R3** (`vtysh`):
```
configure terminal
interface eth0
 ip ospf area 0
 ip ospf network point-to-point
exit
!
interface lo
 ip ospf area 0
exit
!
router ospf
 ospf router-id 3.3.3.3
exit
!
end
```

</details>

**Verify:**

```
R2# show ip ospf neighbor
```
<details><summary>Expected output (captured from a test run)</summary>

```
Neighbor ID     Pri State           Up Time         Dead Time Address         Interface                        RXmtL RqstL DBsmL
1.1.1.1           1 Full/-          11.772s           38.227s 10.0.12.1       eth0:10.0.12.2                       0     0     0
3.3.3.3           1 Full/-          11.714s           38.337s 10.0.23.3       eth1:10.0.23.2                       0     0     0
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

O   1.1.1.1/32 [110/0] is directly connected, lo, weight 1, 00:00:22
O>* 2.2.2.2/32 [110/10] via 10.0.12.2, eth0, weight 1, 00:00:02
O>* 3.3.3.3/32 [110/20] via 10.0.12.2, eth0, weight 1, 00:00:02
O   10.0.12.0/24 [110/10] is directly connected, eth0, weight 1, 00:00:22
O>* 10.0.23.0/24 [110/20] via 10.0.12.2, eth0, weight 1, 00:00:02
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
2.2.2.2         4        100         4         5        0    0    0 00:00:02            0        1 N/A
3.3.3.3         4        100         4         4        0    0    0 00:00:02            1        1 N/A

Total number of neighbors 2
```

</details>


### Step 3 — Recursive next hop

R1 learns 192.168.4.0/24 from R3 with NEXT_HOP 3.3.3.3 (R3 uses next-hop-self). 3.3.3.3 is not
connected, so zebra resolves it recursively through the OSPF route → 10.0.12.2. H1 can reach H4.

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 2
Paths: (1 available, best #1, table default)
  Not advertised to any peer
  200
    3.3.3.3 (metric 20) from 3.3.3.3 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal, best (First path received)
      Last update: Tue Oct 13 22:01:54 2026
```

</details>

```
R1# show ip route 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
Routing entry for 192.168.4.0/24
  Known via "bgp", distance 200, metric 0, best
  Last update 00:00:01 ago
    3.3.3.3 (recursive), weight 1
  *   10.0.12.2, via eth0, weight 1
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.056 ms
 2  10.0.12.2  0.024 ms
 3  10.0.23.3  0.067 ms
 4  10.0.34.4  0.028 ms
 5  192.168.4.10  0.027 ms
```

</details>


### Step 4 — Black hole: take BGP off the transit router R2

A tempting idea: R2 is "just in the middle", so remove BGP from it. R1 still learns
192.168.4.0/24 from R3 (session R1-R3 stays up thanks to OSPF) and sends packets towards
3.3.3.3 via R2… but R2 only knows OSPF routes and **drops** packets for 192.168.4.0/24.
Traceroute dies at R2. This is why every router in the forwarding path must run BGP (or
use MPLS / tunnels to hide the destination from the core).

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
no router bgp 100
end
```

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 no neighbor 2.2.2.2
end
```

On **R3** (`vtysh`):
```
configure terminal
router bgp 100
 no neighbor 2.2.2.2
end
```

</details>

**Verify:**

```
R2# show ip route 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
% Network not in table
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 -m4 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 4 hops max, 60 byte packets
 1  192.168.1.1  0.050 ms
 2  *
 3  *
 4  *
```

</details>


### Step 5 — Restore iBGP on R2

Put R2 back into the iBGP full mesh. Connectivity returns.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
router bgp 100
 bgp router-id 2.2.2.2
 neighbor 1.1.1.1 remote-as 100
 neighbor 1.1.1.1 update-source lo
 neighbor 3.3.3.3 remote-as 100
 neighbor 3.3.3.3 update-source lo
end
```

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 neighbor 2.2.2.2 remote-as 100
 neighbor 2.2.2.2 update-source lo
end
```

On **R3** (`vtysh`):
```
configure terminal
router bgp 100
 neighbor 2.2.2.2 remote-as 100
 neighbor 2.2.2.2 update-source lo
 address-family ipv4 unicast
  neighbor 2.2.2.2 next-hop-self
end
```

</details>

**Verify:**

```
R2# show ip route 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
Routing entry for 192.168.4.0/24
  Known via "bgp", distance 200, metric 0, best
  Last update 00:00:02 ago
    3.3.3.3 (recursive), weight 1
  *   10.0.23.3, via eth1, weight 1
```

</details>


## Extra challenges

1. Remove `next-hop-self` on R3. Which extra network must OSPF carry now so R1 can resolve the next hop? (Hint: `passive-interface eth1` on R3 plus `ip ospf area 0` on it.)
2. Instead of OSPF, make the sessions work with static routes only. Why does that not scale?
3. Break OSPF on R2 (`interface eth1` → `no ip ospf area 0`) and watch how long it takes until the iBGP R1-R3 session drops (hold timer 180 s). Then lower it with `neighbor 3.3.3.3 timers 3 9`.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
