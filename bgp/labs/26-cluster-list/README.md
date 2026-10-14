# Lab 26 — BGP - What is the BGP Cluster List Attribute?

**Video:** [BGP - What is the BGP Cluster List Attribute?](https://www.youtube.com/watch?v=tMizyaaOJeQ) (9:40)

Every RR that reflects a route **prepends its CLUSTER_ID** to the CLUSTER_LIST (optional non-transitive).
By default the cluster ID is the RR's router ID. An RR that receives a route whose CLUSTER_LIST already
contains its own cluster ID drops it: this stops loops between RRs. A shorter cluster list is also preferred
at step 12.

Two RRs (R1, R2) serve the same two clients (R3, R4). You compare the behaviour with **different** cluster
IDs (default) and with the **same** cluster ID.

## What you will practise

- Read CLUSTER_LIST on reflected routes
- See step 12 (cluster-list length) decide
- Configure `bgp cluster-id` and see RR-to-RR updates dropped
- Understand the redundancy trade-off of shared cluster IDs

## Topology

5 FRR routers, 2 Linux hosts.

```
                   AS 100 (OSPF everywhere inside)
             +----+ 10.0.12 +----+
             | R1 |---------| R2 |          R1, R2 = route reflectors
             | RR |         | RR |          R3, R4 = clients of both
             +----+         +----+
        10.0.13|  \10.0.14 /  |10.0.23
               |   \  ___/   |   (10.0.24)
             +----+  X     +----+
H5--R5=======| R3 |       | R4 |--- H4
  AS 200     +----+       +----+
```

### Links (cable these in GNS3 if you build it by hand)

| # | Endpoint A | Endpoint B | Subnet |
|---|---|---|---|
| 1 | R1 eth0 | R2 eth0 | 10.0.12.0/24 |
| 2 | R1 eth1 | R3 eth0 | 10.0.13.0/24 |
| 3 | R1 eth2 | R4 eth0 | 10.0.14.0/24 |
| 4 | R2 eth1 | R3 eth1 | 10.0.23.0/24 |
| 5 | R2 eth2 | R4 eth1 | 10.0.24.0/24 |
| 6 | R3 eth2 | R5 eth0 | 10.0.35.0/24 |
| 7 | R4 eth2 | H4 eth0 | 192.168.4.0/24 |
| 8 | R5 eth1 | H5 eth0 | 192.168.5.0/24 |

### Addressing

| Node | AS | Interface | Address | Connects to |
|---|---|---|---|---|
| **R1** | 100 | lo | 1.1.1.1/32 | loopback / router-id |
| **R1** | 100 | eth0 | 10.0.12.1/24 | R2 |
| **R1** | 100 | eth1 | 10.0.13.1/24 | R3 |
| **R1** | 100 | eth2 | 10.0.14.1/24 | R4 |
| **R2** | 100 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 100 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 100 | eth1 | 10.0.23.2/24 | R3 |
| **R2** | 100 | eth2 | 10.0.24.2/24 | R4 |
| **R3** | 100 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 100 | eth0 | 10.0.13.3/24 | R1 |
| **R3** | 100 | eth1 | 10.0.23.3/24 | R2 |
| **R3** | 100 | eth2 | 10.0.35.3/24 | R5 |
| **R4** | 100 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 100 | eth0 | 10.0.14.4/24 | R1 |
| **R4** | 100 | eth1 | 10.0.24.4/24 | R2 |
| **R4** | 100 | eth2 | 192.168.4.1/24 | LAN H4 |
| **R5** | 200 | lo | 5.5.5.5/32 | loopback / router-id |
| **R5** | 200 | eth0 | 10.0.35.5/24 | R3 |
| **R5** | 200 | eth1 | 192.168.5.1/24 | LAN H5 |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |
| **H5** | - | eth0 | 192.168.5.10/24 | R5 |
| **H5** | - | default gw | 192.168.5.1 | |

## Bring the lab up

```powershell
cd bgp\labs\26-cluster-list
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-26-cluster-list`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Different cluster IDs (default)

R4 receives the route from both RRs: cluster list `1.1.1.1` via R1 and `2.2.2.2` via R2. Same
originator (3.3.3.3), same length → the lowest neighbor address (1.1.1.1) decides.

R1 also has two paths: directly from client R3 (no cluster list) and the copy R2 reflected to its
non-client peer R1 (cluster list `2.2.2.2`). The direct one wins at step 12, **Cluster length**,
because the router ID / originator ID (3.3.3.3) tied at step 11.

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 2
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  2.2.2.2 3.3.3.3 4.4.4.4
  200
    3.3.3.3 (metric 10) from 2.2.2.2 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal
      Originator: 3.3.3.3, Cluster list: 2.2.2.2
      Last update: Wed Oct 14 06:55:09 2026
  200, (Received from a RR-client)
    3.3.3.3 (metric 10) from 3.3.3.3 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal, best (Cluster length)
      Last update: Wed Oct 14 06:55:09 2026
```

</details>

```
R4# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 2
Paths: (2 available, best #1, table default)
  Not advertised to any peer
  200
    3.3.3.3 (metric 20) from 1.1.1.1 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal, best (Neighbor IP)
      Originator: 3.3.3.3, Cluster list: 1.1.1.1
      Last update: Wed Oct 14 06:55:09 2026
  200
    3.3.3.3 (metric 20) from 2.2.2.2 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal
      Originator: 3.3.3.3, Cluster list: 2.2.2.2
      Last update: Wed Oct 14 06:55:09 2026
```

</details>


### Step 2 — Same cluster ID on both RRs

Put both RRs into one cluster, 10.10.10.10, and refresh the sessions. Now R1 receives R2's
reflected copy with `10.10.10.10` already in the cluster list → it drops it. R1 has only one path.
R4 still gets two copies (one from each RR).

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 bgp cluster-id 10.10.10.10
end
```

On **R2** (`vtysh`):
```
configure terminal
router bgp 100
 bgp cluster-id 10.10.10.10
end
```

On **R1** (`vtysh`):
```
clear bgp *
```

On **R2** (`vtysh`):
```
clear bgp *
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 6
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  2.2.2.2 3.3.3.3 4.4.4.4
  200, (Received from a RR-client)
    3.3.3.3 (metric 10) from 3.3.3.3 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal, best (First path received)
      Last update: Wed Oct 14 06:55:13 2026
```

</details>

```
R4# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 4
Paths: (2 available, best #1, table default)
  Not advertised to any peer
  200
    3.3.3.3 (metric 20) from 1.1.1.1 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal, best (Neighbor IP)
      Originator: 3.3.3.3, Cluster list: 10.10.10.10
      Last update: Wed Oct 14 06:55:13 2026
  200
    3.3.3.3 (metric 20) from 2.2.2.2 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal
      Originator: 3.3.3.3, Cluster list: 10.10.10.10
      Last update: Wed Oct 14 06:55:13 2026
```

</details>


### Step 3 — The trade-off

Shut R1's session to R3 (as if that link failed). With a shared cluster ID, R1 refuses R2's copy and
has **no** route to 192.168.5.0/24 anymore. That matters if R1 is also in the data path: packets that
reach R1 for H5 are dropped. Clients still learn the route through R2.
With different cluster IDs, R1 would have kept R2's copy. Shared IDs save memory; separate IDs give
more redundancy.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 neighbor 3.3.3.3 shutdown
end
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
% Network not in table
```

</details>

```
R4# show bgp ipv4 unicast 192.168.5.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.5.0/24, version 5
Paths: (1 available, best #1, table default)
  Not advertised to any peer
  200
    3.3.3.3 (metric 20) from 2.2.2.2 (3.3.3.3)
      Origin IGP, metric 0, localpref 100, valid, internal, best (First path received)
      Originator: 3.3.3.3, Cluster list: 10.10.10.10
      Last update: Wed Oct 14 06:55:13 2026
```

</details>


## Extra challenges

1. Remove the cluster IDs again while R1's session to R3 is still shut. Does R1 get the route back (via R2)?
2. Ping H4 → H5 repeatedly during the last step. Whether it works depends on whether R4's OSPF path to 3.3.3.3 goes through R1 or R2. Use `ip ospf cost` to force each case.

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
