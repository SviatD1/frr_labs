# Lab 18 - Clos / Leaf-Spine-Leaf Topology for EVPN Data Center

**Video:** [Clos / Leaf-Spine-Leaf Topology for EVPN Data Center](https://www.youtube.com/watch?v=WHt-zH8idDo) (27 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  

The video is about the theory: crossbar switches, Charles Clos' 3-stage network, blocking,
rearrangeably vs strict-sense non-blocking. This lab turns it into something you can measure:
a 3-stage *folded* Clos (2 spines, 2 leaves) whose links are **shaped to 100 Mbit/s** with `tc`, so you
can create congestion on purpose and see when the fabric "blocks".

## Topology

```
    spine1          spine2          <- middle stage (both directions folded)
     |    \        /    |
     |      \    /      |              every link shaped to 100 Mbit/s
     |        \/        |              (variant oversubscribed: uplinks 50 Mbit/s)
   leaf1             leaf2           <- ingress / egress stages
  e1    e2          e1    e2
host1  host2      host3  host4
  10.10.10.0/24      10.20.20.0/24     (L3 only, IS-IS, ECMP)
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| host1 | host | 10.10.10.10/24, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.10.10.20/24, gw 10.10.10.1, 00:bb:bb:bb:bb:bb |
| host3 | host | 10.20.20.30/24, gw 10.20.20.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.20.20.40/24, gw 10.20.20.1, 00:dd:dd:dd:dd:dd |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine2 | eth1 | leaf1 | eth12 |
| spine2 | eth2 | leaf2 | eth12 |
| leaf1 | eth1 | host1 | eth1 |
| leaf1 | eth2 | host2 | eth1 |
| leaf2 | eth1 | host3 | eth1 |
| leaf2 | eth2 | host4 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **non-blocking** *(default)* - 2 x 100M down, 2 x 100M up per leaf (1:1)
- **oversubscribed** - 2 x 100M down, 2 x 50M up per leaf (2:1)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\18-clos-topology   # default variant: non-blocking
python tools\gns3_lab.py push labs\18-clos-topology --variant oversubscribed   # switch variant in place
python tools\gns3_lab.py check labs\18-clos-topology
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/non-blocking/` (see the top-level README).

## Theory refresher (from the video)

* **Crossbar**: N inputs x N outputs, N^2 crosspoints, non-blocking, doesn't scale.
* **Clos (1953)**: 3 stages - ingress (r switches of n inputs), middle (m switches), egress.
  * strict-sense non-blocking if **m >= 2n - 1** (a new call never needs re-arranging),
  * rearrangeably non-blocking if **m >= n** (may need to move existing calls).
* A leaf-spine fabric is a **folded** Clos: leaves are both ingress and egress stage, spines are the middle stage.
* Packet networks don't set up "calls" - flows are placed by **ECMP hashing**, so blocking shows up as
  *collisions*: two big flows hashed onto the same spine while the other spine idles (labs 20/21).

## What you will do

1. Check the shaping: `tc -s qdisc show dev eth11` on a leaf (rate, sent bytes, drops).
2. `iperf3 -c 10.20.20.30 -t 20` from host1: ~95 Mbit/s.
3. **Two flows** host1 -> host3 and host2 -> host4 at the same time. In `non-blocking` both should get ~95
   Mbit/s *if* they hash to different spines. Look at `tc -s qdisc show dev eth11/eth12` on leaf1 to see which
   uplink carried which flow. Re-run with different source ports (`iperf3 --cport 40001`, `--cport 40002`, ...)
   until you get a collision - both flows on one spine, ~47 Mbit/s each: that's "blocking" in a
   packet-switched Clos. (Kernel default hashing is L3-only - see lab 21 to switch to L4 hashing.)
4. Push `oversubscribed` (uplinks 50 Mbit): now even a perfect spread gives 2 x 50 Mbit for 2 x 100 Mbit
   of host demand - a 2:1 oversubscribed leaf. Measure it.


`iperf3` is in the base image. Server: `iperf3 -s -D`. Client: `iperf3 -c <ip> -t 20` (TCP) or
`iperf3 -c <ip> -u -b 100M -t 20` (UDP, shows loss). Several parallel flows: `-P 4`.


## Linux notes

* `tc qdisc replace dev X root tbf rate 100mbit burst 32kb latency 20ms` - token bucket shaper on egress.
  Each side shapes its own egress, so a link is shaped in both directions.
* ECMP in the kernel: `ip route show 10.20.20.0/24` shows multiple `nexthop via` lines;
  `ip route get 10.20.20.30 from 10.10.10.10 ipproto tcp sport 40001 dport 5201` tells you which one a flow uses.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant non-blocking*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.20.30` | ` 0% packet loss` |
| leaf1 | `ip route show 10.20.20.0/24` | `nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12` |
| leaf1 | `tc qdisc show dev eth11` | `tbf .*rate 100Mbit` |

*variant oversubscribed*

| node | command | expect |
|---|---|---|
| host1 | `ping -c 3 -W 1 10.20.20.30` | ` 0% packet loss` |
| leaf1 | `ip route show 10.20.20.0/24` | `nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12` |
| leaf1 | `tc qdisc show dev eth11` | `tbf .*rate 50Mbit` |

