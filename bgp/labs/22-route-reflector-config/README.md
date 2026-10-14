# Lab 22 — BGP - Route Reflectors Basic Configuration (FRR version of the Cisco IOS video)

**Video:** [BGP - Route Reflectors Basic Configuration (FRR version of the Cisco IOS video)](https://www.youtube.com/watch?v=ZwQ-lhRr7TU) (5:17)

The video configures RRs on Cisco IOS. The FRR syntax is nearly identical. Here you start with OSPF
working and no iBGP at all, and build an RR design from scratch with a **peer-group** on the RR.

| Cisco IOS | FRR |
|---|---|
| `neighbor CLIENTS peer-group` | same |
| `neighbor CLIENTS remote-as 100` | same |
| `neighbor CLIENTS update-source Loopback0` | `neighbor CLIENTS update-source lo` |
| `neighbor CLIENTS route-reflector-client` | same, under `address-family ipv4 unicast` |
| `show ip bgp` | `show bgp ipv4 unicast` (`show ip bgp` works too) |

## What you will practise

- Build an RR with a peer-group
- Configure clients with a single session
- Verify reflection, next hop, ORIGINATOR_ID and CLUSTER_LIST

## Topology

4 FRR routers, 2 Linux hosts.

```
                     AS 100 (OSPF already running)
+----+   +----+ 10.0.24 +----+ 10.0.12 +----+ 10.0.13 +----+   +----+
| H4 |---| R4 |=========| R2 |---------| R1 |---------| R3 |---| H3 |
+----+   +----+         +----+         +----+         +----+   +----+
         AS 200         client          RR            client
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | R3 eth0 | 10.0.13.0/24 |
| 3 | R2 eth1 | R4 eth0 | 10.0.24.0/24 |
| 4 | R3 eth1 | H3 eth0 | 192.168.3.0/24 |
| 5 | R4 eth1 | H4 eth0 | 192.168.4.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.13.1/24 | R3 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.24.2/24 | R4 |
| **R3** | 100 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 100 | eth0 | 10.0.13.3/24 | R1 |
| **R3** | 100 | eth1 | 192.168.3.1/24 | LAN H3 |
| **R4** | 200 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 200 | eth0 | 10.0.24.4/24 | R2 |
| **R4** | 200 | eth1 | 192.168.4.1/24 | LAN H4 |
| **H3** | - | eth0 | 192.168.3.10/24 | R3 |
| **H3** | - | default gw | 192.168.3.1 | |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |

## Bring the lab up

```powershell
cd bgp\labs\22-route-reflector-config
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-22-route-reflector-config`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Configure the route reflector (R1)

Put both clients in a peer-group so they share configuration.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 bgp router-id 1.1.1.1
 neighbor CLIENTS peer-group
 neighbor CLIENTS remote-as 100
 neighbor CLIENTS update-source lo
 neighbor 2.2.2.2 peer-group CLIENTS
 neighbor 3.3.3.3 peer-group CLIENTS
 address-family ipv4 unicast
  neighbor CLIENTS route-reflector-client
end
```

</details>

### Step 2 — Configure the clients

Each client has exactly one iBGP neighbor: the RR. R2 is also the border router, so it sets
next-hop-self towards the RR; R3 advertises its LAN.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
router bgp 100
 neighbor 1.1.1.1 remote-as 100
 neighbor 1.1.1.1 update-source lo
 address-family ipv4 unicast
  neighbor 1.1.1.1 next-hop-self
end
```

On **R3** (`vtysh`):
```
configure terminal
router bgp 100
 bgp router-id 3.3.3.3
 neighbor 1.1.1.1 remote-as 100
 neighbor 1.1.1.1 update-source lo
 address-family ipv4 unicast
  network 192.168.3.0/24
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
Peers 2, using 1448 KiB of memory
Peer groups 1, using 64 bytes of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
2.2.2.2         4        100         4         6        0    0    0 00:00:02            1        2 N/A
3.3.3.3         4        100         4         5        0    0    0 00:00:02            1        2 N/A

Total number of neighbors 2
```

</details>

```
R1# show bgp peer-group CLIENTS
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP peer-group CLIENTS, remote AS 100
  Peer-group type is internal
  Configured address-families: IPv4 Unicast;
  Peer-group members:
    2.2.2.2  Established
    3.3.3.3  Established
```

</details>


### Step 3 — Verify what the client receives

On R3: next hop is **2.2.2.2** (R2), not the RR: reflection never changes the next hop. Look for
`Originator: 2.2.2.2, Cluster list: 1.1.1.1`. On R4, AS 200 sees the reflected R3 LAN as plain `100`.

**Verify:**

```
R3# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 2
Paths: (1 available, best #1, table default)
  Not advertised to any peer
  200
    2.2.2.2 (metric 20) from 1.1.1.1 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, best (First path received)
      Originator: 2.2.2.2, Cluster list: 1.1.1.1
      Last update: Wed Oct 14 06:53:10 2026
```

</details>

```
R4# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 2, local router ID is 4.4.4.4, vrf id 0
Default local pref 100, local AS 200
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.3.0/24   10.0.24.2                              0 100 i
*> 192.168.4.0/24   0.0.0.0                  0         32768 i

Displayed  2 routes and 2 total paths
```

</details>

```
root@H3:~# traceroute -n -w1 -q1 192.168.4.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.4.10 (192.168.4.10), 30 hops max, 60 byte packets
 1  192.168.3.1  0.037 ms
 2  10.0.13.1  0.011 ms
 3  10.0.12.2  0.009 ms
 4  10.0.24.4  0.010 ms
 5  192.168.4.10  0.011 ms
```

</details>


## Extra challenges

1. Add a fourth router as a new client (connect it to R1, run OSPF, add one neighbor line on R1 with `peer-group CLIENTS`). Nothing changes on R2 or R3, which is the point of RRs.
2. Set `bgp cluster-id 10.10.10.10` on R1 and see the cluster list change on R3.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
