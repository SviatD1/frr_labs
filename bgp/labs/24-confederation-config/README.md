# Lab 24 — BGP - Confederations Basic Config (FRR version of the Cisco IOS video)

**Video:** [BGP - Confederations Basic Config (FRR version of the Cisco IOS video)](https://www.youtube.com/watch?v=vf7CzMjdaUI) (10:09)

You convert AS 100 into a confederation. Start: OSPF runs inside, R1 has a plain `router bgp 100` with
the eBGP session to AS 200, and R2-R4 have no BGP yet.

| Cisco IOS | FRR |
|---|---|
| `router bgp 65001` | same |
| `bgp confederation identifier 100` | same |
| `bgp confederation peers 65002` | same |
| `neighbor X remote-as 65002` (confed peer) | same; no multihop needed on a direct link |

In FRR the BGP process number can't be changed in place: you must delete `router bgp 100` and recreate
it as `router bgp 65001`. That drops the session to AS 200 for a moment.

## What you will practise

- Rebuild a BGP process with a new local AS
- Configure confederation identifier and peers
- Verify the confederation from inside and outside

## Topology

5 FRR routers, 2 Linux hosts.

```
                   AS 100 = confederation of sub-AS 65001 and 65002 (OSPF inside)
         +-------- sub-AS 65001 --------+   +-------- sub-AS 65002 --------+
+----+   | +----+ 10.0.12 +----+        |   |    +----+ 10.0.34 +----+     |   +----+
| R5 |=====| R1 |---------| R2 |=============== | R3 |---------| R4 |---------| H4 |
+----+   | +----+  iBGP   +----+    10.0.23     +----+  iBGP   +----+     |   +----+
  |      +------------------------------+ confed-eBGP +------------------------+
+----+  AS 200 (sees only AS 100)
| H5 |
+----+
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R2 eth1 | R3 eth0 | 10.0.23.0/24 |
| 3 | R3 eth1 | R4 eth0 | 10.0.34.0/24 |
| 4 | R1 eth1 | R5 eth0 | 10.0.15.0/24 |
| 5 | R4 eth1 | H4 eth0 | 192.168.4.0/24 |
| 6 | R5 eth1 | H5 eth0 | 192.168.5.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.15.1/24 | R5 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.23.2/24 | R3 |
| **R3** | 100 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 100 | eth0 | 10.0.23.3/24 | R2 |
| **R3** | 100 | eth1 | 10.0.34.3/24 | R4 |
| **R4** | 100 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 100 | eth0 | 10.0.34.4/24 | R3 |
| **R4** | 100 | eth1 | 192.168.4.1/24 | LAN H4 |
| **R5** | 200 | lo | 5.5.5.5/32 | loopback / router-id |
| **R5** | 200 | eth0 | 10.0.15.5/24 | R1 |
| **R5** | 200 | eth1 | 192.168.5.1/24 | LAN H5 |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |
| **H5** | - | eth0 | 192.168.5.10/24 | R5 |
| **H5** | - | default gw | 192.168.5.1 | |

## Bring the lab up

```powershell
cd bgp\labs\24-confederation-config
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-24-confederation-config`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Convert R1 to sub-AS 65001

Remove the old process and create the new one. AS 200 still has `remote-as 100` configured and is
not touched: the confederation identifier makes R1 present itself as AS 100.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
no router bgp 100
router bgp 65001
 bgp router-id 1.1.1.1
 no bgp ebgp-requires-policy
 bgp confederation identifier 100
 bgp confederation peers 65002
 neighbor 2.2.2.2 remote-as 65001
 neighbor 2.2.2.2 update-source lo
 neighbor 10.0.15.5 remote-as 200
 address-family ipv4 unicast
  neighbor 2.2.2.2 next-hop-self
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
BGP router identifier 1.1.1.1, local AS number 65001 vrf-id 0
BGP table version 1
RIB entries 1, using 192 bytes of memory
Peers 2, using 1448 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
2.2.2.2         4      65001         0         0        0    0    0    never       Active        0 N/A
10.0.15.5       4        200         4         2        0    0    0 00:00:01            1        0 N/A

Total number of neighbors 2
```

</details>


### Step 2 — Configure R2 (sub-AS 65001)

<details><summary>Show solution</summary>

On **R2** (`vtysh`):
```
configure terminal
router bgp 65001
 bgp router-id 2.2.2.2
 no bgp ebgp-requires-policy
 bgp confederation identifier 100
 bgp confederation peers 65002
 neighbor 1.1.1.1 remote-as 65001
 neighbor 1.1.1.1 update-source lo
 neighbor 10.0.23.3 remote-as 65002
end
```

</details>

### Step 3 — Configure R3 and R4 (sub-AS 65002)

<details><summary>Show solution</summary>

On **R3** (`vtysh`):
```
configure terminal
router bgp 65002
 bgp router-id 3.3.3.3
 no bgp ebgp-requires-policy
 bgp confederation identifier 100
 bgp confederation peers 65001
 neighbor 4.4.4.4 remote-as 65002
 neighbor 4.4.4.4 update-source lo
 neighbor 10.0.23.2 remote-as 65001
end
```

On **R4** (`vtysh`):
```
configure terminal
router bgp 65002
 bgp router-id 4.4.4.4
 no bgp ebgp-requires-policy
 bgp confederation identifier 100
 bgp confederation peers 65001
 neighbor 3.3.3.3 remote-as 65002
 neighbor 3.3.3.3 update-source lo
 address-family ipv4 unicast
  network 192.168.4.0/24
end
```

</details>

**Verify:**

```
R3# show bgp summary
```
<details><summary>Expected output (captured from a test run)</summary>

```
IPv4 Unicast Summary (VRF default):
BGP router identifier 3.3.3.3, local AS number 65002 vrf-id 0
BGP table version 2
RIB entries 3, using 576 bytes of memory
Peers 2, using 1448 KiB of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
4.4.4.4         4      65002         4         4        0    0    0 00:00:01            1        1 N/A
10.0.23.2       4      65001         5         5        0    0    0 00:00:01            1        2 N/A

Total number of neighbors 2
```

</details>


### Step 4 — Verify

* R4 sees `(65001) 200` for AS 200's LAN, next hop 1.1.1.1.
* R5 sees `100` for R4's LAN.
* H4 can reach H5.

**Verify:**

```
R4# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 2, local router ID is 4.4.4.4, vrf id 0
Default local pref 100, local AS 65002
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.4.0/24   0.0.0.0                  0         32768 i
*>i192.168.5.0/24   1.1.1.1                  0    100      0 (65001) 200 i

Displayed  2 routes and 2 total paths
```

</details>

```
R5# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 2, local router ID is 5.5.5.5, vrf id 0
Default local pref 100, local AS 200
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.4.0/24   10.0.15.1                              0 100 i
*> 192.168.5.0/24   0.0.0.0                  0         32768 i

Displayed  2 routes and 2 total paths
```

</details>

```
root@H4:~# traceroute -n -w1 -q1 192.168.5.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.5.10 (192.168.5.10), 30 hops max, 60 byte packets
 1  192.168.4.1  0.046 ms
 2  10.0.34.3  0.097 ms
 3  10.0.23.2  0.085 ms
 4  10.0.12.1  0.089 ms
 5  10.0.15.5  0.081 ms
 6  192.168.5.10  0.015 ms
```

</details>


## Extra challenges

1. Make R2 a route reflector for sub-AS 65001 and add a third router to it.
2. Peer R2-R3 between loopbacks instead. Which extra command does the confed-eBGP session need (`ebgp-multihop` or `disable-connected-check`)?

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
