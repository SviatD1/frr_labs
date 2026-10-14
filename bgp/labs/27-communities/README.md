# Lab 27 — BGP - What are BGP Communities?

**Video:** [BGP - What are BGP Communities?](https://www.youtube.com/watch?v=4nfOTEJUW80) (8:38)

A **community** is a 32-bit tag (written `ASN:value`) attached to routes (optional transitive). By itself it
does nothing; it becomes powerful when routers match on it. Typical uses:

* **Well-known**: `no-export` (do not send outside this AS/confederation), `no-advertise` (do not send to
  any peer), `local-AS` (do not send outside the sub-AS).
* **Action communities** published by a provider: "tag your route with 200:80 and we set LOCAL_PREF 80."
  The customer controls the provider's routing without touching their routers.

R1 (AS 100) is a customer dual-homed to provider AS 200 (R2 primary, R4 backup). AS 200 has already
implemented "200:80 = local-pref 80". AS 300 (R3) connects behind R4.

## What you will practise

- Set, read and match communities
- Use a provider's action community for primary/backup
- Use `no-export` to keep a prefix inside the neighbor AS

## Topology

4 FRR routers, 2 Linux hosts.

```
     AS 100                    AS 200                    AS 300
                   10.0.12 +----+
                .----------| R2 | (primary)
+----+   +----+ |          +----+
| H1 |---| R1 |-+             | 10.0.24 iBGP
+----+   +----+ |          +----+ 10.0.34  +----+   +----+
  lan11 192.168.11.0/24 '--| R4 |==========| R3 |---| H3 |
                   10.0.14 +----+ (backup) +----+   +----+
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | R4 eth0 | 10.0.14.0/24 |
| 3 | R2 eth1 | R4 eth1 | 10.0.24.0/24 |
| 4 | R3 eth0 | R4 eth2 | 10.0.34.0/24 |
| 5 | R1 eth2 | H1 eth0 | 192.168.1.0/24 |
| 6 | R3 eth1 | H3 eth0 | 192.168.3.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.14.1/24 | R4 |
| **R1** | 100 | eth2 | 192.168.1.1/24 | LAN H1 |
| **R1** | 100 | lan11 (dummy) | 192.168.11.1/24 | extra prefix to advertise |
| **R2** | 200 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 200 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 200 | eth1 | 10.0.24.2/24 | R4 |
| **R4** | 200 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 200 | eth0 | 10.0.14.4/24 | R1 |
| **R4** | 200 | eth1 | 10.0.24.4/24 | R2 |
| **R4** | 200 | eth2 | 10.0.34.4/24 | R3 |
| **R3** | 300 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 300 | eth0 | 10.0.34.3/24 | R4 |
| **R3** | 300 | eth1 | 192.168.3.1/24 | LAN H3 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H3** | - | eth0 | 192.168.3.10/24 | R3 |
| **H3** | - | default gw | 192.168.3.1 | |

## Bring the lab up

```powershell
cd bgp\labs\27-communities
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-27-communities`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Baseline

R4 reaches the customer directly (eBGP beats iBGP). Traffic from H3 enters AS 100 over the backup link.
Note AS 200's policy that is already in place on R2 and R4 (`show route-map FROM-CUSTOMER`).
Reading traceroute: each hop answers with the address of the interface it uses to send the reply
*back to H3* (Linux picks the source from its route to the sender), not necessarily the interface the
probe arrived on. So the key hop to look for is R2's `10.0.24.2`: it is absent now.

**Verify:**

```
R4# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 2
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.14.1 10.0.24.2 10.0.34.3
  100
    10.0.24.2 from 10.0.24.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal
      Last update: Wed Oct 14 06:55:24 2026
  100
    10.0.14.1 from 10.0.14.1 (1.1.1.1)
      Origin IGP, metric 0, valid, external, best (Peer Type)
      Last update: Wed Oct 14 06:55:24 2026
```

</details>

```
R4# show route-map FROM-CUSTOMER
```
<details><summary>Expected output (captured from a test run)</summary>

```
ZEBRA:
route-map: FROM-CUSTOMER Invoked: 0 Optimization: enabled Processed Change: false
 permit, sequence 10 Invoked 0
  Match clauses:
  Set clauses:
  Call clause:
  Action:
    Exit routemap
 permit, sequence 20 Invoked 0
  Match clauses:
  Set clauses:
  Call clause:
  Action:
    Exit routemap
OSPF:
route-map: FROM-CUSTOMER Invoked: 0 Optimization: enabled Processed Change: false
 permit, sequence 10 Invoked 0
  Match clauses:
  Set clauses:
  Call clause:
  Action:
    Exit routemap
 permit, sequence 20 Invoked 0
  Match clauses:
  Set clauses:
  Call clause:
  Action:
    Exit routemap
BGP:
route-map: FROM-CUSTOMER Invoked: 4 Optimization: enabled Processed Change: false
 permit, sequence 10 Invoked 0
  Match clauses:
    community BACKUP
  Set clauses:
    local-preference 80
  Call clause:
  Action:
    Exit routemap
 permit, sequence 20 Invoked 4
  Match clauses:
  Set clauses:
  Call clause:
  Action:
    Exit routemap
```

</details>

```
root@H3:~# traceroute -n -w1 -q1 192.168.1.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.1.10 (192.168.1.10), 30 hops max, 60 byte packets
 1  192.168.3.1  0.259 ms
 2  10.0.34.4  0.185 ms
 3  10.0.12.1  0.167 ms
 4  192.168.1.10  0.143 ms
```

</details>


### Step 2 — Tag routes with your own community

On R1 tag everything sent to AS 200 with `100:1` ("learned from customer 100"). It travels to AS 300 too.
Search by community with `show bgp ipv4 unicast community 100:1`.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
route-map TO-R2 permit 10
 set community 100:1
route-map TO-R4 permit 10
 set community 100:1
router bgp 100
 address-family ipv4 unicast
  neighbor 10.0.12.2 route-map TO-R2 out
  neighbor 10.0.14.4 route-map TO-R4 out
end
```

</details>

**Verify:**

```
R3# show bgp ipv4 unicast community 100:1
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 5, local router ID is 3.3.3.3, vrf id 0
Default local pref 100, local AS 300
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.1.0/24   10.0.34.4                              0 200 100 i
*> 192.168.11.0/24  10.0.34.4                              0 200 100 i

Displayed  2 routes and 3 total paths
```

</details>

```
R3# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 4
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.34.4
  200 100
    10.0.34.4 from 10.0.34.4 (4.4.4.4)
      Origin IGP, valid, external, best (First path received)
      Community: 100:1
      Last update: Wed Oct 14 06:55:25 2026
```

</details>


### Step 3 — Use the provider's action community 200:80

Tell AS 200 that the R4 link is a backup: add `200:80` on routes sent to R4. AS 200's own policy lowers
LOCAL_PREF to 80, so R4 prefers the iBGP path via R2 (LP 100). H3's traffic now enters at R2.
You changed AS 200's routing without touching their configuration. (In the traceroute, R2 now
appears as `10.0.24.2`.)

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
route-map TO-R4 permit 10
 set community 100:1 200:80
end
```

On **R1** (`vtysh`):
```
clear bgp 10.0.14.4 soft out
```

</details>

**Verify:**

```
R4# show bgp ipv4 unicast 192.168.1.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.1.0/24, version 6
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.14.1 10.0.34.3
  100
    10.0.24.2 from 10.0.24.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, best (Local Pref)
      Community: 100:1
      Last update: Wed Oct 14 06:55:25 2026
  100
    10.0.14.1 from 10.0.14.1 (1.1.1.1)
      Origin IGP, metric 0, localpref 80, valid, external
      Community: 100:1 200:80
      Last update: Wed Oct 14 06:55:27 2026
```

</details>

```
root@H3:~# traceroute -n -w1 -q1 192.168.1.10
```
<details><summary>Expected output (captured from a test run)</summary>

```
traceroute to 192.168.1.10 (192.168.1.10), 30 hops max, 60 byte packets
 1  192.168.3.1  0.157 ms
 2  10.0.34.4  0.121 ms
 3  10.0.24.2  0.110 ms
 4  10.0.12.1  0.098 ms
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
20  *
21  192.168.1.10  0.070 ms
```

</details>


### Step 4 — no-export

192.168.11.0/24 should be reachable from AS 200 only (say, a private peering service). Add the
well-known community `no-export` to it. R2 and R4 keep it, but do not advertise it to AS 300.
A route-map stops at the first matching sequence, so the new sequence 5 sets the complete list again
(`100:1 [200:80] no-export`); `set community no-export additive` would only add to existing ones.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
ip prefix-list P11 seq 5 permit 192.168.11.0/24
route-map TO-R2 permit 5
 match ip address prefix-list P11
 set community 100:1 no-export
route-map TO-R4 permit 5
 match ip address prefix-list P11
 set community 100:1 200:80 no-export
end
```

On **R1** (`vtysh`):
```
clear bgp * soft out
```

</details>

**Verify:**

```
R4# show bgp ipv4 unicast 192.168.11.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.11.0/24, version 8
Paths: (2 available, best #1, table default, not advertised to EBGP peer)
  Not advertised to any peer
  100
    10.0.24.2 from 10.0.24.2 (2.2.2.2)
      Origin IGP, metric 0, localpref 100, valid, internal, best (Local Pref)
      Community: 100:1 no-export
      Last update: Wed Oct 14 06:55:31 2026
  100
    10.0.14.1 from 10.0.14.1 (1.1.1.1)
      Origin IGP, metric 0, localpref 80, valid, external
      Community: 100:1 200:80 no-export
      Last update: Wed Oct 14 06:55:31 2026
```

</details>

```
R3# show bgp ipv4 unicast
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP table version is 6, local router ID is 3.3.3.3, vrf id 0
Default local pref 100, local AS 300
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

   Network          Next Hop            Metric LocPrf Weight Path
*> 192.168.1.0/24   10.0.34.4                              0 200 100 i
*> 192.168.3.0/24   0.0.0.0                  0         32768 i

Displayed  2 routes and 2 total paths
```

</details>


## Extra challenges

1. Replace `no-export` with `no-advertise`. Now R2 does not even pass it to R4 over iBGP. Verify.
2. Large communities (RFC 8092) carry 32-bit ASNs: `set large-community 100:1:1`. Try them and match with `bgp large-community-list`.
3. On R4, strip all communities you receive from the customer except 200:80. `set comm-list NAME delete` removes the communities the list *permits*, so build an expanded list that denies `200:80` and then permits `.*`.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
