# Lab 29 — BGP in one minute!

**Video:** [BGP in one minute!](https://www.youtube.com/watch?v=FJSor7jPptI) (1:00)

A one-minute video deserves a speed-run lab: build a three-AS chain with as few commands as possible,
using FRR conveniences: `remote-as external` (any AS other than mine), `redistribute connected`, and
peer-groups. Set a timer and try to get H1 pinging H3 in under 2 minutes.

## What you will practise

- Configure eBGP with `remote-as external`
- Use peer-groups to shorten configs
- Read AS_PATH across three ASes

## Topology

3 FRR routers, 2 Linux hosts.

```
   AS 100             AS 200             AS 300
+----+  +----+ 10.0.12 +----+ 10.0.23 +----+  +----+
| H1 |--| R1 |=========| R2 |=========| R3 |--| H3 |
+----+  +----+         +----+         +----+  +----+
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
| **R2** | 200 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 200 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 200 | eth1 | 10.0.23.2/24 | R3 |
| **R3** | 300 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 300 | eth0 | 10.0.23.3/24 | R2 |
| **R3** | 300 | eth1 | 192.168.3.1/24 | LAN H3 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H3** | - | eth0 | 192.168.3.10/24 | R3 |
| **H3** | - | default gw | 192.168.3.1 | |

## Bring the lab up

```powershell
cd bgp\labs\29-bgp-in-one-minute
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-29-bgp-in-one-minute`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Speed-run

Four lines per edge router, five on R2. `remote-as external` accepts any AS different from your own.
`redistribute connected` advertises every connected network (fine for a lab, never in production).

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 no bgp ebgp-requires-policy
 neighbor 10.0.12.2 remote-as external
 address-family ipv4 unicast
  redistribute connected
end
```

On **R2** (`vtysh`):
```
configure terminal
router bgp 200
 no bgp ebgp-requires-policy
 neighbor 10.0.12.1 remote-as external
 neighbor 10.0.23.3 remote-as external
 address-family ipv4 unicast
  redistribute connected
end
```

On **R3** (`vtysh`):
```
configure terminal
router bgp 300
 no bgp ebgp-requires-policy
 neighbor 10.0.23.2 remote-as external
 address-family ipv4 unicast
  redistribute connected
end
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 7, local router ID is 1.1.1.1, vrf id 0
Default local pref 100, local AS 100
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 1.1.1.1/32       0.0.0.0                  0         32768 ?
*> 2.2.2.2/32       10.0.12.2                0             0 200 ?
*> 3.3.3.3/32       10.0.12.2                              0 200 300 ?
*  10.0.12.0/24     10.0.12.2                0             0 200 ?
*>                  0.0.0.0                  0         32768 ?
*> 10.0.23.0/24     10.0.12.2                0             0 200 ?
*> 192.168.1.0/24   0.0.0.0                  0         32768 ?
*> 192.168.3.0/24   10.0.12.2                              0 200 300 ?

Displayed  7 routes and 8 total paths
```

</details>

```
root@H1:~# traceroute -n -w1 -q1 192.168.3.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.3.10 (192.168.3.10), 30 hops max, 60 byte packets
 1  192.168.1.1  0.295 ms
 2  10.0.12.2  0.200 ms
 3  10.0.23.3  0.181 ms
 4  192.168.3.10  0.164 ms
```

</details>


### Step 2 — BGP in one sentence

*Each AS tells its neighbors which prefixes it can reach and the list of ASes on the way; each router
picks one best path per prefix and only passes that one on.* Check it on R2's summary and table:
R2 knows the AS numbers of both neighbors, although you never typed them.

**Verify:**

```
R2# show bgp summary
```
<details><summary>Expected output (captured from a test run)</summary>

```
IPv4 Unicast Summary (VRF default):
BGP router identifier 2.2.2.2, local AS number 200 vrf-id 0
BGP table version 7
RIB entries 13, using 2496 bytes of memory
Peers 2, using 1448 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
10.0.12.1       4        100         8         8        0    0    0 00:00:01            3        7 N/A
10.0.23.3       4        300         8         8        0    0    0 00:00:01            3        7 N/A

Total number of neighbors 2
```

</details>


### Step 3 — Tidy up R2 with a peer-group

Replace R2's per-neighbor lines with a peer-group: one place for shared settings.

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
router bgp 200
 no neighbor 10.0.12.1
 no neighbor 10.0.23.3
 neighbor EXT peer-group
 neighbor EXT remote-as external
 neighbor 10.0.12.1 peer-group EXT
 neighbor 10.0.23.3 peer-group EXT
end
```

</details>

**Verify:**

```
R2# show bgp peer-group EXT
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP peer-group EXT, remote AS 0
  Peer-group type is external
  Configured address-families: IPv4 Unicast;
  Peer-group members:
    10.0.12.1  Established
    10.0.23.3  Established
```

</details>


## Extra challenges

1. **BGP unnumbered** (an FRR favourite, not verified in the test run because the test machine has no IPv6): remove the IPv4 neighbors and use `neighbor eth0 interface remote-as external` on both ends of each link. BGP then peers over IPv6 link-local addresses and carries IPv4 routes with IPv6 next hops (RFC 8950, formerly RFC 5549). Check `show bgp summary` and `ip route`.
2. Replace `redistribute connected` with `network` statements for the LANs only. What disappears from the tables?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
