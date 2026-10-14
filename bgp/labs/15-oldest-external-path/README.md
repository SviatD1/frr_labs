# Lab 15 — BGP - Algorithm Prefers the Oldest External Path

**Video:** [BGP - Algorithm Prefers the Oldest External Path](https://www.youtube.com/watch?v=O0wC43lwxSs) (4:42)

When two **eBGP** paths are equal through step 9, FRR (like Cisco) keeps the one that is **already
the best**, i.e. the oldest (step 10), instead of going on to compare router IDs (step 11). If neither
path is the current best (e.g. both arrive at the same time) the step does not apply and router ID decides. That avoids
flapping between equally good external paths every time one is refreshed. `bgp bestpath compare-routerid`
turns this step off.

## What you will practise

- See `best (Older Path)`
- Make a path younger by resetting its session
- Disable the rule with `bgp bestpath compare-routerid`

## Topology

4 FRR routers, 2 Linux hosts.

```
                               AS 200
                              +----+
                   10.0.12/24 | R2 | 10.0.24/24
                  .1 .------- +----+ -------. .4
  +----+   +----+ --'  eth0  eth0  eth1      '-- +----+   +----+
  | H1 |---| R1 |  AS 100                AS 400  | R4 |---| H4 |
  +----+   +----+ --.  eth1  eth0  eth1      .-- +----+   +----+
192.168.1.10   .1 '------- +----+ -------' .4        192.168.4.10
                   10.0.13/24 | R3 | 10.0.34/24
                              +----+
                               AS 300
  (R1: eth0->R2 eth1->R3 eth2->H1   R4: eth0->R2 eth1->R3 eth2->H4)
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
| **R2** | 200 | lo | 2.2.2.2/32 | loopback / router-id |
| **R2** | 200 | eth0 | 10.0.12.2/24 | R1 |
| **R2** | 200 | eth1 | 10.0.24.2/24 | R4 |
| **R3** | 300 | lo | 3.3.3.3/32 | loopback / router-id |
| **R3** | 300 | eth0 | 10.0.13.3/24 | R1 |
| **R3** | 300 | eth1 | 10.0.34.3/24 | R4 |
| **R4** | 400 | lo | 4.4.4.4/32 | loopback / router-id |
| **R4** | 400 | eth0 | 10.0.24.4/24 | R2 |
| **R4** | 400 | eth1 | 10.0.34.4/24 | R3 |
| **R4** | 400 | eth2 | 192.168.4.1/24 | LAN H4 |
| **H1** | - | eth0 | 192.168.1.10/24 | R1 |
| **H1** | - | default gw | 192.168.1.1 | |
| **H4** | - | eth0 | 192.168.4.10/24 | R4 |
| **H4** | - | default gw | 192.168.4.1 | |

## Bring the lab up

```powershell
cd bgp\labs\15-oldest-external-path
python ..\..\tools\lab.py build .
```
This creates GNS3 project `bgp-15-oldest-external-path`, wires it, attaches a cloud-init CD to every node and starts it. Give the VMs about a minute to boot, then open the consoles (login `root` / `lab`; the base image auto-logs in on the console). Building by hand instead? Cable it as in the links table, then paste `nodes/<NODE>.sh` into each node's console. See [../../SETUP.md](../../SETUP.md).

Quick sanity check on every router: `vtysh -c 'show bgp summary'`, and `ip -br addr` in the Linux shell.

## Steps

### Step 1 — Baseline

Two equal eBGP paths to 192.168.4.0/24. Note which one is best and the reason.

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 2
Paths: (2 available, best #1, table default)
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3
  200 400
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, valid, external, best (Router ID)
      Last update: Wed Oct 14 06:49:49 2026
  300 400
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin IGP, valid, external
      Last update: Wed Oct 14 06:49:49 2026
```

</details>


### Step 2 — Reset the session to R2

Hard-reset the session to R2. While it is down, R3's path becomes best. When R2's path comes
back it is *younger* than R3's; even though R2 has the lower router ID, R1 keeps R3.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
clear bgp 10.0.12.2
```

</details>

**Verify:**

```
R1# show bgp ipv4 unicast 192.168.4.0/24
```
<details><summary>Expected output (captured from a test run)</summary>

```
BGP routing table entry for 192.168.4.0/24, version 3
Paths: (2 available, best #2, table default)
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3
  200 400
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, valid, external
      Last update: Wed Oct 14 06:49:52 2026
  300 400
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin IGP, valid, external, best (Older Path)
      Last update: Wed Oct 14 06:49:49 2026
```

</details>


### Step 3 — compare-routerid

Configure `bgp bestpath compare-routerid`. The age step is skipped and the lowest router ID wins:
R2 (2.2.2.2).

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 bgp bestpath compare-routerid
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
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3
  200 400
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, valid, external, best (Router ID)
      Last update: Wed Oct 14 06:49:52 2026
  300 400
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin IGP, valid, external
      Last update: Wed Oct 14 06:49:49 2026
```

</details>


### Step 4 — Turn it off again

Remove `bgp bestpath compare-routerid`. R2's path is now the *current* best, so it stays: the age rule
favours whatever is selected right now. Reset R2 again and watch it flip back to R3.

<details><summary>Show solution</summary>

On **R1** (`vtysh`):
```
configure terminal
router bgp 100
 no bgp bestpath compare-routerid
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
  Advertised to non peer-group peers:
  10.0.12.2 10.0.13.3
  200 400
    10.0.12.2 from 10.0.12.2 (2.2.2.2)
      Origin IGP, valid, external, best (Older Path)
      Last update: Wed Oct 14 06:49:51 2026
  300 400
    10.0.13.3 from 10.0.13.3 (3.3.3.3)
      Origin IGP, valid, external
      Last update: Wed Oct 14 06:49:48 2026
```

</details>


## Extra challenges

1. Reset R3's session instead. Does anything change? Why not?
2. Why does this rule not apply to iBGP paths? (Think about route reflectors and consistency inside an AS.)

## Files in this folder

| File | What it is |
|---|---|
| `topology.json` | Machine-readable topology used by `tools/lab.py` |
| `nodes/<NODE>.sh` | Setup script for each node: interfaces (`/etc/lab/net.sh`) + start `frr.conf`. Used as cloud-init user-data; can also be pasted into the console |
| `configs/<ROUTER>.frr.conf` | Start FRR config of each router |
| `solution/<ROUTER>.frr.conf` | Running config of each router after all steps (captured from a test run) |
