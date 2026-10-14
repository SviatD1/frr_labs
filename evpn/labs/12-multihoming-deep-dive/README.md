# Lab 12 - EVPN Multihoming Deep Dive. Ethernet Segment Route. Designated Forwarder. Split Horizon.

**Video:** [EVPN Multihoming Deep Dive. Ethernet Segment Route. Designated Forwarder. Split Horizon.](https://www.youtube.com/watch?v=EMA8-csnilA) (1 h 05 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/multihoming_deep_dive  

Two multihomed servers with **trunk bonds** (VLAN 10 and 20 sub-interfaces on the host), manually
configured **type-0 ESIs**, the **type-4 Ethernet Segment route** and its ES-Import RT, **Designated
Forwarder** election (who sends BUM to the ES) and **split horizon** (don't send BUM back into the ES it came from).

## Topology

```
               spine1                  spine2
        leaf1         leaf2        leaf3       leaf4
      e1 e2 e3      e1 e2 e3        e1
      |  |  |       |  |  |          |
      |  |  host3   |  |  host4     host5
      |  +----------|--+-- host2  (bond0, ES 00:22:22:22:22:22:22:22:22:22)
      +------------ +----- host1  (bond0, ES 00:11:11:11:11:11:11:11:11:11)
host1/host2: bond0.10 and bond0.20 (trunk)   10.10.10.x / 10.20.20.x
host3 VLAN10 on leaf1 (orphan)  host4 VLAN10 on leaf2 (orphan)  host5 VLAN10 on leaf3
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 |
| spine2 | spine | 12.12.12.12 |
| leaf1 | leaf | 1.1.1.1 |
| leaf2 | leaf | 2.2.2.2 |
| leaf3 | leaf | 3.3.3.3 |
| leaf4 | leaf | 4.4.4.4 |
| host1 | host | 10.10.10.10/24, 10.20.20.10/24, 00:aa:aa:aa:aa:aa, bond 802.3ad |
| host2 | host | 10.10.10.20/24, 10.20.20.20/24, 00:bb:bb:bb:bb:bb, bond 802.3ad |
| host3 | host | 10.10.10.30/24, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.10.10.40/24, 00:dd:dd:dd:dd:dd |
| host5 | host | 10.10.10.50/24, 00:ee:ee:ee:ee:ee |

### Links

| A | | B | |
|---|---|---|---|
| spine1 | eth1 | leaf1 | eth11 |
| spine1 | eth2 | leaf2 | eth11 |
| spine1 | eth3 | leaf3 | eth11 |
| spine1 | eth4 | leaf4 | eth11 |
| spine2 | eth1 | leaf1 | eth12 |
| spine2 | eth2 | leaf2 | eth12 |
| spine2 | eth3 | leaf3 | eth12 |
| spine2 | eth4 | leaf4 | eth12 |
| leaf1 | eth1 | host1 | eth1 |
| leaf2 | eth1 | host1 | eth2 |
| leaf1 | eth2 | host2 | eth1 |
| leaf2 | eth2 | host2 | eth2 |
| leaf1 | eth3 | host3 | eth1 |
| leaf2 | eth3 | host4 | eth1 |
| leaf3 | eth1 | host5 | eth1 |

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\12-multihoming-deep-dive
python tools\gns3_lab.py check labs\12-multihoming-deep-dive
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/default/` (see the top-level README).

## What you will learn

* **ESI formats**: type 0 (operator-configured 9 bytes: `00:11:11:...`) vs type 3 (MAC + discriminator, lab 11).
  FRR: `evpn mh es-id 00:11:11:11:11:11:11:11:11:11` on the bond (plus `es-sys-mac` only for LACP).
* **Type-4 ES route** `[4]:[ESI]:[32]:[VTEP-IP]` with the **ES-Import RT** (derived from the ESI's MAC bytes) -
  only VTEPs attached to the same ES import it. Used for DF election.
* **DF election**: per ES (and per VLAN in the standard modulo algorithm). FRR implements the
  **preference-based** DF election (RFC draft "df-pref"): highest `evpn mh es-df-pref` wins, tie -> lowest IP.
  leaf1 is configured with 50000 for ES 00:11:..; ES 00:22:.. uses the defaults.
* **Split horizon**: a BUM frame that arrives at leaf2 *from leaf1* and belongs to an ES both share must not be
  sent back to that ES. With VXLAN this is done by **local bias** (RFC 8365): the ingress VTEP delivers BUM to its
  own local ES ports; the other ES peers never forward VXLAN-received BUM from that VTEP to the shared ES.
  zebra programs the kernel for DF and local-bias filtering - you only see the effect (and `show evpn es detail`).
* VLAN sub-interfaces on a bond (host side trunk) and `bridge vlan add dev bond1 vid 10` (tagged) on the leaf.

## Step by step

```bash
# leaf1
vtysh -c 'show evpn es detail'                          # VTEPs, DF pref, "DF status: df"
vtysh -c 'show evpn es-evi'                             # ES per VNI
vtysh -c 'show bgp l2vpn evpn route type es'            # type-4
vtysh -c 'show bgp l2vpn evpn route type es detail'     # ES-Import RT (ES-Import Rt:11:11:11:11:11:11)
bridge -d link show dev bond1                           # protodown state, etc.
```

**DF in action**: from host5 send a broadcast (`arping -c 3 -I eth1 10.10.10.99`) and capture on **host1**
eth1 and eth2 (`tcpdump -ni eth1 arp` / `-ni eth2 arp`): host1 receives it only on the link to the DF (leaf1).
Change preference (`evpn mh es-df-pref 1000` on leaf1, `60000` on leaf2), re-check, re-capture.

**Without EVPN-MH** (video 27:43): on leaf2, `ip link set eth1 nomaster`... easier: remove the `evpn mh es-id`
lines on leaf2 only (`vtysh` -> `conf t` -> `interface bond1` -> `no evpn mh es-id`) and watch duplicates
and MAC moves on leaf3 (`show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa detail`).

**Split horizon**: from host1 send a broadcast in VLAN 10 (`arping -I bond0.10 10.10.10.99`). It hashes to
one link, say leaf1. leaf1 floods to host3 and to leaf2/3/4 via VXLAN. Capture on host1: the frame must
**not** come back to host1 via leaf2 (`tcpdump -ni eth2 arp` on host1 stays quiet).

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant default*

| node | command | expect |
|---|---|---|
| leaf1 | `vtysh -c 'show evpn es'` | `00:11:11:11:11:11:11:11:11:11\s+LR[\s\S]*00:22:22:22:22:22:22:22:22:22\s+LR` |
| leaf1 | `vtysh -c 'show bgp l2vpn evpn route type es'` | `\[4\]:\[00:11:11:11:11:11:11:11:11:11\]:\[32\]:\[2\.2\.2\.2\]` |
| leaf1 | `vtysh -c 'show evpn es 00:11:11:11:11:11:11:11:11:11'` | `DF status: df` |
| leaf2 | `vtysh -c 'show evpn es 00:11:11:11:11:11:11:11:11:11'` | `DF status: non-df` |
| host5 | `ping -c 3 -W 1 10.10.10.10` | ` 0% packet loss` |
| host1 | `ping -c 3 -W 1 10.20.20.20` | ` 0% packet loss` |
| host3 | `ping -c 3 -W 1 10.10.10.20` | ` 0% packet loss` |

