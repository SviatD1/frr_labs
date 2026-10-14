# Lab 01 - EVPN Fundamentals

**Video:** [EVPN Fundamentals](https://www.youtube.com/watch?v=Dk-qNDrZDX4) (37 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  

The video explains *why* EVPN exists: classic STP bridging wastes links and converges slowly, MLAG/vPC
patches the problem only for pairs of switches, and a pure L3 fabric cannot stretch a subnet.
This lab lets you **see both problems on real Linux boxes** before you build your first EVPN fabric
in lab 02:

* **Part A - STP triangle**: three Linux bridges (`sw1..sw3`) running kernel 802.1D STP. One link is
  blocked, traffic between host1 and host2 takes the long way round, and a link failure takes ~30 s to heal.
* **Part B - L3-only leaf/spine fabric**: two spines, two leaves, IS-IS underlay, every link is used
  (ECMP) - but host3 and host4 are forced into different subnets. EVPN/VXLAN (next lab) gives you both:
  an L3 ECMP underlay *and* L2 stretched over it.

## Topology

```
    Part A (STP)                            Part B (L3 only, IS-IS)
        sw1 (root, prio 4096)               spine1        spine2
       /eth1   \eth2                          |  \      /  |
  eth1/          \eth1                         |    \  /    |
    sw2 -------- sw3                         leaf1        leaf2
   eth3 eth2  eth2 eth3                        |eth1         |eth1
    |              |                         host3         host4
  host1          host2                     10.1.1.10/24  10.2.2.10/24
192.168.1.1   192.168.1.2
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| sw1 | switch | bridge priority 4096 |
| sw2 | switch | bridge priority 8192 |
| sw3 | switch | bridge priority 32768 |
| host1 | host | 192.168.1.1/24, 00:aa:aa:aa:aa:aa |
| host2 | host | 192.168.1.2/24, 00:bb:bb:bb:bb:bb |
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| host3 | host | 10.1.1.10/24, gw 10.1.1.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.2.2.10/24, gw 10.2.2.1, 00:dd:dd:dd:dd:dd |

### Links

| A | | B | |
|---|---|---|---|
| sw1 | eth1 | sw2 | eth1 |
| sw1 | eth2 | sw3 | eth1 |
| sw2 | eth2 | sw3 | eth2 |
| sw2 | eth3 | host1 | eth1 |
| sw3 | eth3 | host2 | eth1 |
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine2 | eth1 | leaf1 | eth12 |
| spine2 | eth2 | leaf2 | eth12 |
| leaf1 | eth1 | host3 | eth1 |
| leaf2 | eth1 | host4 | eth1 |

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\01-evpn-fundamentals
python tools\gns3_lab.py check labs\01-evpn-fundamentals
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/default/` (see the top-level README).

## What you will learn

* How a Linux bridge does STP (`stp_state 1`) and how to read port roles/states with `bridge link`.
* Why STP blocks links and converges slowly.
* How an L3 leaf/spine fabric with an IGP uses **all** links (ECMP) and converges in about a second.
* Why neither design alone gives you "any subnet anywhere" - the motivation for EVPN.

## Part A - STP

Wait ~30 s after the push (listening + learning = 2 x forward_delay 15 s), then:

```bash
# on sw1, sw2, sw3
bridge link show                 # state forwarding / blocking per port
cat /sys/class/net/br0/bridge/root_id /sys/class/net/br0/bridge/bridge_id
cat /sys/class/net/br0/brif/eth2/state   # 0 disabled 1 listening 2 learning 3 forwarding 4 blocking
```

* `sw1` has the lowest priority -> root bridge. On the sw2-sw3 link, sw2 has the better bridge-id so
  **sw3 eth2 is blocking**.
* From host1 ping host2 and run `tcpdump -ni eth1 -e icmp` on sw1: the traffic hair-pins through the
  root even though sw2 and sw3 are directly connected.

**Break it:** `ip link set eth2 down` on sw1 (the sw1-sw3 link) while pinging host1 -> host2 with
`ping -D -O 192.168.1.2`. Count the lost pings (~30 s) until sw3 eth2 moves listening -> learning -> forwarding.
Bring it back up and watch STP re-block.

## Part B - L3 only fabric

```bash
# on leaf1
vtysh -c 'show isis neighbor'
vtysh -c 'show ip route 10.2.2.0/24'     # two next hops: spine1 and spine2
ip route show 10.2.2.0/24                # same, as installed in the kernel (ECMP)
```

* Ping host4 from host3 - routed through either spine. Shut one uplink (`ip link set eth11 down` on leaf1)
  and see that IS-IS reconverges in ~1 s (look at `ping -D -O`).
* Now try to move host4 into 10.1.1.0/24 (`ip addr flush dev eth1; ip addr add 10.1.1.20/24 dev eth1` on host4):
  it cannot talk to host3 - leaf2 has no idea about that subnet. **This** is the problem EVPN-VXLAN solves:
  keep this L3 underlay, and carry Ethernet frames on top of it (lab 02).

## Linux notes

* Kernel STP is plain 802.1D (no RSTP). Real switches would run RSTP/MSTP - faster, but the blocking problem stays.
* `ip -d link show br0` shows every bridge attribute (`stp_state`, `forward_delay`, `priority`, ...).

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant default*

| node | command | expect |
|---|---|---|
| sw3 | `bridge link show dev eth2` | `state blocking` |
| sw1 | `bridge link show dev eth1` | `state forwarding` |
| host1 | `ping -c 3 -W 1 192.168.1.2` | ` 0% packet loss` |
| leaf1 | `ip route show 10.2.2.0/24` | `nexthop via 10\.1\.11\.11[\s\S]*nexthop via 10\.1\.12\.12` |
| host3 | `ping -c 3 -W 1 10.2.2.10` | ` 0% packet loss` |

