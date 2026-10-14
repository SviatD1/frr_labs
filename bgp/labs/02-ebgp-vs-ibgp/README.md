# Lab 02 — eBGP vs iBGP - What's the difference?

**Video:** [eBGP vs iBGP - What's the difference?](https://www.youtube.com/watch?v=3x7yztGSY-g) (10:07)

The same protocol behaves differently depending on whether the neighbor is in **another AS
(eBGP)** or **the same AS (iBGP)**. In this lab R2 has one of each and you compare them side by side:
administrative distance (20 vs 200), AS_PATH handling, NEXT_HOP handling and TTL.

## What you will practise

- Configure an iBGP neighbor (same AS) next to an existing eBGP neighbor
- See that eBGP prepends the local AS to AS_PATH, iBGP does not
- See that iBGP does **not** change NEXT_HOP, making the route unusable on R1
- Fix reachability with `next-hop-self`
- Compare admin distance 20 (eBGP) vs 200 (iBGP) in `show ip route` and TTL 1 vs 255 in tcpdump

## Topology

3 FRR routers, 2 Linux hosts.

```
               AS 100                                  AS 200
  +----+       +----+  10.0.12.0/24  +----+ 10.0.23.0/24 +----+       +----+
  | H1 |-------| R1 |----------------| R2 |==============| R3 |-------| H3 |
  +----+       +----+ .1   iBGP   .2 +----+ .2  eBGP  .3 +----+       +----+
192.168.1.10      eth1  eth0       eth0  eth1        eth0  eth1    192.168.3.10
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R2 eth1 | R3 eth0 | 10.0.23.0/24 |
| 3 | R1 eth1 | H1 eth0 | 192.168.1.0/24 |
| 4 | R3 eth1 | H3 eth0 | 192.168.3.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 192.168.1.1/24 | LAN H1 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.23.2/24 | R3 |
| **R3** | 200 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 200 | eth0 | 10.0.23.3/24 | R2 |
| **R3** | 200 | eth1 | 192.168.3.1/24 | LAN H3 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H3** | - | eth0 | 192.168.3.10/24 | R3 |
| **H3** | - | default gw | 192.168.3.1 | |

## Bring the lab up

```powershell
cd bgp\labs\02-ebgp-vs-ibgp
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-02-ebgp-vs-ibgp`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Inspect the existing eBGP session

R2 already peers with R3 (AS 200) over eBGP. Look at the summary and at how the
route is installed: `[20/0]` means administrative distance 20 = eBGP.
In the neighbor details note *"External BGP neighbor may be up to 1 hops away"*:
eBGP packets are sent with TTL 1 by default.

**Verify:**

```
R2# show bgp summary
```
<details><summary>Expected output (captured from a test run)</summary>

```
IPv4 Unicast Summary (VRF default):
BGP router identifier 2.2.2.2, local AS number 100 vrf-id 0
BGP table version 1
RIB entries 1, using 192 bytes of memory
Peers 1, using 724 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
10.0.23.3       4        200         4         5        0    0    0 00:00:01            1        1 N/A

Total number of neighbors 1
```

</details>

```
R2# show ip route 192.168.3.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
Routing entry for 192.168.3.0/24
  Known via "bgp", distance 20, metric 0, best
  Last update 00:00:00 ago
  * 10.0.23.3, via eth1, weight 1
```

</details>

```
root@R2:~# vtysh -c 'show bgp neighbors 10.0.23.3' | grep -E 'BGP neighbor is|link|hops away'
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP neighbor is 10.0.23.3, remote AS 200, local AS 100, external link
  External BGP neighbor may be up to 1 hops away.
```

</details>


### Step 2 — Configure iBGP between R1 and R2

Same AS on both sides = iBGP. Configure R1 (AS 100) to peer with R2 and advertise its LAN;
add the neighbor on R2.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 bgp router-id 1.1.1.1
 neighbor 10.0.12.2 remote-as 100
 address-family ipv4 unicast
  network 192.168.1.0/24
end
```

On **R2** (`vtysh`):
```
configure terminal
router bgp 100
 neighbor 10.0.12.1 remote-as 100
end
```

</details>

**Verify:**

```
root@R2:~# vtysh -c 'show bgp neighbors 10.0.12.1' | grep -E 'BGP neighbor is|link|hops away'
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP neighbor is 10.0.12.1, remote AS 100, local AS 100, internal link
  Internal BGP neighbor may be up to 255 hops away.
```

</details>


### Step 3 — Compare what the two neighbors see

*AS_PATH*: on R2 the iBGP-learned route 192.168.1.0/24 has an **empty** AS_PATH
(`Local`), but R3 sees it as `100`: R2 prepended its AS when sending over eBGP.

*NEXT_HOP*: on R1, 192.168.3.0/24 arrives with next hop **10.0.23.3**, R3's address.
iBGP passes the next hop unchanged, and R1 has no route to 10.0.23.0/24, so the path is
**inaccessible** and not installed. Ping H1 → H3 fails.

**Verify:**

```
R2# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 2
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.23.3
  Local
    10.0.12.1 from 10.0.12.1 (1.1.1.1)
      Origin IGP, metric 0, localpref 100, valid, internal, best (First path received)
      Last update: Tue Oct 13 22:01:10 2026
```

</details>

```
R3# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 2
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.23.2
  100
    10.0.23.2 from 10.0.23.2 (2.2.2.2)
      Origin IGP, valid, external, best (First path received)
      Last update: Tue Oct 13 22:01:10 2026
```

</details>

```
R1# show bgp ipv4 unicast 192.168.3.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.3.0/24, version 0
Paths: (1 available, no best path)
  Not advertised to any peer
  200
    10.0.23.3 (inaccessible) from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, invalid, internal
      Last update: Tue Oct 13 22:01:10 2026
```

</details>


### Step 4 — Fix the next hop with next-hop-self

Tell R2 to put its own address as next hop when it sends routes to its iBGP peer R1.
(The alternative is to make 10.0.23.0/24 reachable inside AS 100 through an IGP; see lab 18.)

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.12.1 next-hop-self
end
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.3.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.3.0/24, version 2
Paths: (1 available, best #1, table default)
  Not advertised to any peer
  200
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, best (First path received)
      Last update: Tue Oct 13 22:01:10 2026
```

</details>

```
R1# show ip route 192.168.3.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
Routing entry for 192.168.3.0/24
  Known via "bgp", distance 200, metric 0, best
  Last update 00:00:03 ago
  * 10.0.12.2, via eth0, weight 1
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.3.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.3.10 (192.168.3.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.030 ms
 2  10.0.12.2  0.014 ms
 3  10.0.23.3  0.015 ms
 4  192.168.3.10  0.013 ms
```

</details>


### Step 5 — Admin distance: eBGP 20, iBGP 200

Compare `show ip route` on R1 (iBGP route, `[200/0]`) with R2 (eBGP route, `[20/0]`).
200 is deliberately worse than any IGP: if a prefix is known via OSPF (110) and iBGP, the
IGP wins. In the Linux kernel you see the same with `ip route show proto bgp` (metric 20 for both:
FRR puts the distance into the RIB, not the kernel metric).

Optional: run `tcpdump -ni eth0 -v tcp port 179` on R2 and clear the sessions (`clear bgp *`):
packets to R3 have **ttl 1**, packets to R1 have **ttl 255**.

**Verify:**

```
R1# show ip route bgp
```
<details><summary>Expected output (captured from a test run)</summary>

```
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

B>* 192.168.3.0/24 [200/0] via 10.0.12.2, eth0, weight 1, 00:00:03
```

</details>

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

B>* 192.168.1.0/24 [200/0] via 10.0.12.1, eth0, weight 1, 00:00:03
B>* 192.168.3.0/24 [20/0] via 10.0.23.3, eth1, weight 1, 00:00:06
```

</details>


## Extra challenges

1. Peer R1 and R2 between loopbacks (1.1.1.1/2.2.2.2) instead of interface IPs. You need a route to the loopbacks (static or OSPF) and `neighbor 2.2.2.2 update-source lo`.
2. Try the same loopback trick on the eBGP session R2-R3. It stays down until you add `neighbor ... ebgp-multihop 2` (TTL) or `disable-connected-check`. Why?
3. On R2 run `show bgp neighbors 10.0.12.1 advertised-routes` and `... 10.0.23.3 advertised-routes` and compare the Next Hop column.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
