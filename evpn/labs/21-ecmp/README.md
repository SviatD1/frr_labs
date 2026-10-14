# Lab 21 - Why ECMP Algorithm is Critical in Data Center Networks

**Video:** [Why ECMP Algorithm is Critical in Data Center Networks](https://www.youtube.com/watch?v=LKp1RzZRMDg) (40 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/ecmp  

ECMP decides which spine carries each flow. You will look at Linux's hash policies (L3 vs L4),
measure the flow spread over four spines, watch flows **remap** when a path disappears (modulo-style
hashing) and fix that with **resilient nexthop groups** (hash buckets) - exactly the demo in the video.

## Topology

```
spine1     spine2     spine3     spine4
  |  \       |  \     /  |      /  |
  |   \______|___\___/___|_____/   |      every leaf connects to every spine
  |          |    \ /    |         |      leaf eth11..eth14 -> spine1..4
leaf1 ------------X------------- leaf2
  |eth1                           |eth1
host1 10.10.10.10            host2 10.20.20.20
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| spine3 | spine | 13.13.13.13 |
| spine4 | spine | 14.14.14.14 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| host1 | host | 10.10.10.10/24, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host2 | host | 10.20.20.20/24, gw 10.20.20.1, 00:bb:bb:bb:bb:bb |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine2 | eth1 | leaf1 | eth12 |
| spine2 | eth2 | leaf2 | eth12 |
| spine3 | eth1 | leaf1 | eth13 |
| spine3 | eth2 | leaf2 | eth13 |
| spine4 | eth1 | leaf1 | eth14 |
| spine4 | eth2 | leaf2 | eth14 |
| leaf1 | eth1 | host1 | eth1 |
| leaf2 | eth1 | host2 | eth1 |

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **l3-hash** - fib_multipath_hash_policy=0 (src/dst IP only)
- **l4-hash** *(default)* - fib_multipath_hash_policy=1 (5-tuple)

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\21-ecmp   # default variant: l4-hash
python tools\gns3_lab.py push labs\21-ecmp --variant l3-hash   # switch variant in place
python tools\gns3_lab.py check labs\21-ecmp
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/l4-hash/` (see the top-level README).

## What you will learn

* Linux ECMP knobs: `net.ipv4.fib_multipath_hash_policy` (0 = L3, 1 = L4, 2 = L3 inner for tunnels, 3 = custom
  fields via `fib_multipath_hash_fields`) - same for IPv6 under `net.ipv6.*`.
* How to ask the kernel which path a flow takes: `ip route get <dst> from <src> iif eth1 ipproto tcp sport X dport Y`.
* **Static hashing** = hash mod N. Remove one path and most flows move (*remapping*) - bad for stateful
  middleboxes and for TCP (reordering).
* **Resilient hashing**: a nexthop group with buckets (`type resilient buckets 128`) - when a member
  fails, only *its* buckets move.

## Step by step

```bash
# leaf1
ip route show 10.20.20.0/24                # 4 nexthops
ecmp-test 10.20.20.20 10.10.10.10 100      # how 100 TCP flows spread over eth11..eth14
sysctl net.ipv4.fib_multipath_hash_policy
```

In `l3-hash` all 100 flows (same src/dst IP) land on **one** uplink. Push `l4-hash`: ~25 per uplink.
Try `sysctl -w net.ipv4.fib_multipath_hash_policy=3` with
`sysctl -w net.ipv4.fib_multipath_hash_fields=0x0037` (custom field set) and compare.

## Remapping vs resilient hashing (manual, same as the author's `commands.txt`)

```bash
# leaf1: record where 20 flows go
ecmp-test 10.20.20.20 10.10.10.10 20 > /tmp/before   # (or run the loop without | uniq -c to keep per-flow lines)
ip link set eth14 down; sleep 2
ecmp-test 10.20.20.20 10.10.10.10 20 > /tmp/after    # compare per-flow: many flows changed uplink, not just eth14's
ip link set eth14 up

# resilient group, built by hand for a test prefix
ip nexthop add id 101 via 10.1.11.11 dev eth11
ip nexthop add id 102 via 10.1.12.12 dev eth12
ip nexthop add id 103 via 10.1.13.13 dev eth13
ip nexthop add id 104 via 10.1.14.14 dev eth14
ip nexthop add id 1000 group 101/102/103/104 type resilient buckets 128 idle_timer 60 unbalanced_timer 300
ip route add 10.99.99.0/24 nhid 1000
ip nexthop bucket show id 1000 | head          # bucket -> nexthop map
ip link set eth14 down; ip nexthop bucket show id 1000 | awk '{print $NF}' | sort | uniq -c
```

Only the buckets that pointed at eth14 are reassigned. (FRR itself installs normal nexthop groups;
resilient groups are a kernel feature you configure directly or via `nexthop-group` + `resilient buckets` in FRR's `sharpd`/`pbrd` configs on recent versions.)

Note the leaves here have **15 adapters** (eth0-eth14) because of the four uplinks eth11-eth14.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant l3-hash*

| node | command | expect |
|---|---|---|
| leaf1 | `ip route show 10.20.20.0/24` | `(nexthop via[\s\S]*){4}` |
| leaf1 | `sysctl net.ipv4.fib_multipath_hash_policy` | `= 0` |
| host1 | `ping -c 3 -W 1 10.20.20.20` | ` 0% packet loss` |
| leaf1 | `ecmp-test 10.20.20.20 10.10.10.10 64 \| wc -l` | `^\s*1\s*$` |

*variant l4-hash*

| node | command | expect |
|---|---|---|
| leaf1 | `ip route show 10.20.20.0/24` | `(nexthop via[\s\S]*){4}` |
| leaf1 | `sysctl net.ipv4.fib_multipath_hash_policy` | `= 1` |
| host1 | `ping -c 3 -W 1 10.20.20.20` | ` 0% packet loss` |
| leaf1 | `ecmp-test 10.20.20.20 10.10.10.10 64 \| wc -l` | `^\s*4\s*$` |

