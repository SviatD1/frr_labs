# Lab 20 - Calculating Clos Fabric Limits for Data Center Networks

**Video:** [Calculating Clos Fabric Limits for Data Center Networks](https://www.youtube.com/watch?v=j7mGuIrsU1k) (36 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  

Oversubscription, incast and the arithmetic of fabric size. You get a small **calculator**
(`clos-calc`, on every node of this lab) to reproduce the video's tables, and a fabric where three senders
blast one receiver at once so you can watch **incast congestion** - drops in the egress queue of the
receiver's leaf port - with `tc -s qdisc`.

## Topology

```
           spine1            spine2          (all links shaped to 100 Mbit/s)
       /     |     \       /    |     \
   leaf1   leaf2   leaf3  (all leaves to both spines)
     |       |   \      \
   host1   host2 host3  host4
 receiver  -------- senders --------
10.10.10.10 10.20.20.20 .30 10.30.30.40
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| host1 | host | 10.10.10.10/24, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.20.20.20/24, gw 10.20.20.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.20.20.30/24, gw 10.20.20.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.30.30.40/24, gw 10.30.30.1, 00:dd:dd:dd:dd:dd |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine1 | eth3 | leaf3 | eth11 |
| spine2 | eth1 | leaf1 | eth12 |
| spine2 | eth2 | leaf2 | eth12 |
| spine2 | eth3 | leaf3 | eth12 |
| leaf1 | eth1 | host1 | eth1 |
| leaf2 | eth1 | host2 | eth1 |
| leaf2 | eth2 | host3 | eth1 |
| leaf3 | eth1 | host4 | eth1 |

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\20-clos-limits
python tools\gns3_lab.py check labs\20-clos-limits
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/default/` (see the top-level README).

## What you will learn

* **Oversubscription** = server-facing bandwidth / uplink bandwidth of a leaf.
* Why even a 1:1 fabric congests: **incast** (many senders -> one receiver port) and **hash collisions** (lab 21).
* How to size a fabric: radix, port speeds, servers per rack, number of spines = number of leaf uplinks,
  max leaves = spine radix, and what a 5-stage design buys you. `clos-calc.py` (also in this folder) reproduces the
  video's formulas; run it with different inputs and fill the summary table yourself.

```bash
clos-calc --radix 64 --port 100 --server-port 25 --leaf-down-ports 48 --oversub 3
clos-calc --radix 32 --port 400 --server-port 100 --leaf-down-ports 24 --oversub 1 --five-stage --super-radix 64
```

## Incast experiment

```bash
# host2, host3, host4 at the same time (three consoles, or use & on one):
iperf3 -c 10.10.10.10 -u -b 90M -t 20 -p 5201      # host2
iperf3 -c 10.10.10.10 -u -b 90M -t 20 -p 5202      # host3 (start 2 more servers on host1: iperf3 -s -D -p 5202; -p 5203)
iperf3 -c 10.10.10.10 -u -b 90M -t 20 -p 5203      # host4
# leaf1 - the egress port towards the receiver is the bottleneck:
watch -n1 tc -s qdisc show dev eth1                # "dropped" climbs
```

270 Mbit/s of offered load into one 100 Mbit/s port: ~63 % loss, no matter how non-blocking the fabric is.
Repeat with TCP (`iperf3 -c ... -t 20` without `-u`): TCP backs off, the three flows share ~100 Mbit/s and
the drops are bursty - the classic incast pattern behind storage/AI "tail latency" problems.

## Things to think about (video chapters)

* Packet spraying vs flow hashing: spraying avoids collisions but reorders packets.
* "Don't forget about space": rack units, power and optics often limit servers-per-leaf before ports do.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant default*

| node | command | expect |
|---|---|---|
| host2 | `ping -c 3 -W 1 10.10.10.10` | ` 0% packet loss` |
| host1 | `clos-calc --radix 64 --port 100 --server-port 25 --oversub 3` | `oversubscription 3\.\d+:1\|oversubscription 2\.\d+:1` |

