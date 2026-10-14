# Lab 01 — What is BGP?

**Video:** [What is BGP?](https://www.youtube.com/watch?v=fo9YxxKNO_g) (8:08)

BGP is the routing protocol *between* autonomous systems (AS). It is a path-vector
protocol that runs over TCP port 179 and only exchanges what you explicitly tell it to.
In this first lab you bring up a single eBGP session between two "companies" and make
their LANs reachable, while looking at what happens in Linux underneath.

## What you will practise

- Read Linux interface/route state with `ip -br addr`, `ip route`
- Configure an eBGP neighbor in FRR and watch the session reach *Established*
- Advertise prefixes with `network` and see them land in the Linux kernel FIB (`proto bgp`)
- Understand FRR's `bgp ebgp-requires-policy` safety default (RFC 8212)
- Capture BGP OPEN/KEEPALIVE/UPDATE messages with tcpdump

## Topology

2 FRR routers, 2 Linux hosts.

```
      AS 100                         AS 200
+----+  192.168.1.0/24  +----+ 10.0.12.0/24 +----+  192.168.2.0/24  +----+
| H1 |------------------| R1 |==============| R2 |------------------| H2 |
+----+ .10           .1 +----+ .1        .2 +----+ .1           .10 +----+
                      eth1   eth0      eth0   eth1
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | H1 eth0 | 192.168.1.0/24 |
| 3 | R2 eth1 | H2 eth0 | 192.168.2.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 192.168.1.1/24 | LAN H1 |
| **R2** | 200 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 200 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 200 | eth1 | 192.168.2.1/24 | LAN H2 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H2** | - | eth0 | 192.168.2.10/24 | R2 |
| **H2** | - | default gw | 192.168.2.1 | |

## Bring the lab up

```powershell
cd bgp\labs\01-what-is-bgp
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-01-what-is-bgp`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Look around before BGP exists

Log into R1 and look at the Linux side first. Every router is just a Debian box
with IP forwarding on; FRR programs routes into the kernel.
The hosts cannot reach each other yet: R1 has no route to 192.168.2.0/24.

**Verify:**

```
root@R1:~# ip -br addr
```
<details><summary>Expected output (captured from a test run)</summary>

```
lo               UNKNOWN        127.0.0.1/8 1.1.1.1/32
eth0             UP             10.0.12.1/24
eth1             UP             192.168.1.1/24
```

</details>

```
root@R1:~# ip route
```
<details><summary>Expected output (captured from a test run)</summary>

```
10.0.12.0/24 dev eth0 proto kernel scope link src 10.0.12.1
192.168.1.0/24 dev eth1 proto kernel scope link src 192.168.1.1
```

</details>

```
root@H1:~# ping -c2 -W1 192.168.2.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
PING 192.168.2.10 (192.168.2.10) 56(84) bytes of data.

--- 192.168.2.10 ping statistics ---
2 packets transmitted, 0 received, 100% packet loss, time 1029ms
```

</details>


### Step 2 — Bring up the eBGP session

Configure BGP on both routers: R1 is AS 100, R2 is AS 200. A neighbor with a
*different* remote AS is an **eBGP** neighbor.

Before you commit, start a capture on R2 so you can see the TCP handshake and the
BGP OPEN messages: `tcpdump -ni eth0 tcp port 179 -v` (Ctrl-C to stop).
Then watch `show bgp summary` go Idle → Connect/Active → OpenSent → OpenConfirm → Established.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 bgp router-id 1.1.1.1
 neighbor 10.0.12.2 remote-as 200
 neighbor 10.0.12.2 description R2-AS200
end
```

On **R2** (`vtysh`):
```
configure terminal
router bgp 200
 bgp router-id 2.2.2.2
 neighbor 10.0.12.1 remote-as 100
 neighbor 10.0.12.1 description R1-AS100
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
BGP table version 0
RIB entries 0, using 0 bytes of memory
Peers 1, using 724 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
10.0.12.2       4        200         3         3        0    0    0 00:00:01     (Policy) (Policy) R2-AS200

Total number of neighbors 1
```

</details>


### Step 3 — Notice: the session is up but nothing is exchanged (Policy)

Look at the `PfxRcd`/`PfxSnt` columns: they show **(Policy)**. FRR implements
RFC 8212: an eBGP session sends and accepts *nothing* until a policy (route-map)
is applied in each direction. This protects the Internet from route leaks.

Fix it the proper way: create a permit-all route-map and apply it in and out.
(In later labs we will use the shortcut `no bgp ebgp-requires-policy` to keep configs short.)
Then advertise each router's LAN with a `network` statement. The prefix must
exist in the routing table (it does: it is a connected route).

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
route-map ALLOW-ALL permit 10
router bgp 100
 address-family ipv4 unicast
  network 192.168.1.0/24
  neighbor 10.0.12.2 route-map ALLOW-ALL in
  neighbor 10.0.12.2 route-map ALLOW-ALL out
end
```

On **R2** (`vtysh`):
```
configure terminal
route-map ALLOW-ALL permit 10
router bgp 200
 address-family ipv4 unicast
  network 192.168.2.0/24
  neighbor 10.0.12.1 route-map ALLOW-ALL in
  neighbor 10.0.12.1 route-map ALLOW-ALL out
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
BGP table version 2
RIB entries 3, using 576 bytes of memory
Peers 1, using 724 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
10.0.12.2       4        200        10        10        0    0    0 00:00:03            1        2 R2-AS200

Total number of neighbors 1
```

</details>

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
*> 192.168.2.0/24   10.0.12.2                0             0 200 i

Displayed  2 routes and 2 total paths
```

</details>


### Step 4 — From the BGP table to the kernel

The best BGP path is installed into zebra's RIB and then into the Linux kernel.
Compare the FRR view with the kernel view. In `show ip route` the route shows `[20/0]`: 20 is the eBGP
administrative distance. In the kernel it is tagged `proto bgp metric 20`; that 20 is simply the
fixed metric FRR uses for every route it installs (an OSPF or iBGP route also gets metric 20 there).
Now the hosts can talk.

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

B>* 192.168.2.0/24 [20/0] via 10.0.12.2, eth0, weight 1, 00:00:03
```

</details>

```
root@R1:~# ip route show proto bgp
```
<details><summary>Expected output (captured from a test run)</summary>

```
192.168.2.0/24 nhid 8 via 10.0.12.2 dev eth0 metric 20
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.2.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.2.10 (192.168.2.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.037 ms
 2  10.0.12.2  0.013 ms
 3  192.168.2.10  0.013 ms
```

</details>


### Step 5 — Look at a single prefix in detail

`show bgp ipv4 unicast <prefix>` shows every path and its attributes: AS_PATH (`200`),
next hop, origin (`IGP`, because of the `network` statement), and which path is best.
You will read this output in almost every lab from now on.

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.2.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.2.0/24, version 2
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.12.2
  200
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, metric 0, valid, external, best (First path received)
      Last update: Tue Oct 13 22:00:59 2026
```

</details>


## Extra challenges

1. Shut the session with `neighbor 10.0.12.2 shutdown` on R1 and watch the route disappear from `ip route`. Then `no neighbor 10.0.12.2 shutdown`.
2. Run `tcpdump -ni eth0 tcp port 179` on R1 and clear the session with `clear bgp 10.0.12.2`. Identify OPEN, UPDATE and KEEPALIVE messages (KEEPALIVE every 60 s by default, hold time 180 s).
3. Change the hold timer with `neighbor 10.0.12.2 timers 5 15` on R1 only. Which value is negotiated? (Check `show bgp neighbors 10.0.12.2`.)
4. Configure the wrong remote AS on R2 (`neighbor 10.0.12.1 remote-as 101`) and look at the log with `journalctl -u frr`: you should see a NOTIFICATION *Bad Peer AS*.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
