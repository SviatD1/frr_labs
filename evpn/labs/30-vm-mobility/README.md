# Lab 30 - EVPN Overlay Design for Virtual Machine Mobility in Data Center

**Video:** [EVPN Overlay Design for Virtual Machine Mobility in Data Center](https://www.youtube.com/watch?v=vgu2ZfYUYYM) (34 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_overlay_mobility  

A "VM" (MAC 00:aa:aa:aa:aa:aa, IP 10.10.10.10) moves from a server on leaf1 to a server on leaf3 -
the classic vMotion use case for stretched L2. Watch the **MAC Mobility** extended community and its
sequence number, the host route following the VM, and FRR's **duplicate address detection** freezing
a MAC that moves too often.

## Topology

```
          spine1                spine2
     leaf1      leaf2      leaf3      leaf4
       |          |          |          |
     host1      host2      host3      host4        VLAN 10, VRF A, anycast 10.10.10.1
  (VM here)               (moves here)
the "VM" = 00:aa:aa:aa:aa:aa / 10.10.10.10, helper: `vm up` / `vm down` on host1 and host3
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
| host1 | host | 10.10.10.10/24, gw 10.10.10.1, 00:aa:aa:aa:aa:aa |
| host3 | host | 10.10.10.30/24, gw 10.10.10.1, 00:cc:cc:cc:cc:cc |
| host4 | host | 10.10.10.40/24, gw 10.10.10.1, 00:dd:dd:dd:dd:dd |
| host2 | host | 10.20.20.20/24, gw 10.20.20.1, 00:bb:bb:bb:bb:bb |

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
| leaf3 | eth1 | host3 | eth1 |
| leaf4 | eth1 | host4 | eth1 |
| leaf2 | eth2 | host2 | eth1 |

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\30-vm-mobility
python tools\gns3_lab.py check labs\30-vm-mobility
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/default/` (see the top-level README).

## What you will learn

* **MAC mobility** (RFC 7432 s15): the new VTEP advertises the MAC with sequence number N+1
  (extended community `MM:<seq>`); everyone prefers the highest sequence, the old VTEP withdraws.
* With symmetric IRB the /32 host route moves too, so routed traffic follows the VM immediately.
* GARP after a move is what tells the new leaf about the VM (`arp_accept=1` on vlan10 lets the SVI create a neighbor
  entry from a gratuitous ARP; real hypervisors send RARP/GARP).
* **Duplicate address detection**: FRR default `dup-addr-detection max-moves 5 time 180` - more moves than
  that and the MAC/IP is flagged duplicate (and optionally frozen).

## Step by step

```bash
# leaf2 - before
vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa detail'
vtysh -c 'show evpn arp-cache vni 10010 ip 10.10.10.10 detail'
ip route show vrf A 10.10.10.10
# move the VM
host1$ vm down
host3$ vm up
# leaf2 - after
vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa detail'    # Remote VTEP 3.3.3.3, seq 1
vtysh -c 'show bgp l2vpn evpn route type macip detail' | grep -B3 -A12 aa:aa:aa   # MM:1
```

Keep `ping -D -O 10.10.10.10` running on host2 during the move and count lost packets.

**Duplicate detection**: move the VM back and forth 6 times quickly (`vm down`/`vm up` alternately on host1 and host3),
then on any leaf:

```bash
vtysh -c 'show evpn mac vni 10010 duplicate'
vtysh -c 'show evpn arp-cache vni 10010 duplicate'
vtysh -c 'clear evpn dup-addr vni 10010 mac 00:aa:aa:aa:aa:aa'
```

Tune it under `router bgp 65000` / `address-family l2vpn evpn`: `dup-addr-detection max-moves 3 time 60 freeze 30`.

Note: `gns3_lab.py check` for this lab performs the move itself (`vm down` on host1, `vm up` on host3).
Push the lab again (`gns3_lab.py push labs\30-vm-mobility`) to put the VM back on host1.

## Design notes (video)

* The mobility domain = the set of leaves that have the VNI. Every leaf in it holds every MAC of that VNI -
  bigger mobility domains cost table space (lab 29) and widen the BUM flooding domain.
* Limit broadcast domain size: stretch only the VLANs that really need mobility, keep the rest rack-local (lab 33).

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant default*

| node | command | expect |
|---|---|---|
| host2 | `ping -c 3 -W 1 10.10.10.10` | ` 0% packet loss` |
| leaf2 | `vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa'` | `remote\s+1\.1\.1\.1\|Remote VTEP: 1\.1\.1\.1` |
| host1 | `vm down` | `VM left` |
| host3 | `vm up` | `VM is now on` |
| leaf2 | `vtysh -c 'show evpn mac vni 10010 mac 00:aa:aa:aa:aa:aa'` | `3\.3\.3\.3` |
| leaf2 | `vtysh -c 'show bgp l2vpn evpn route type macip detail' \| grep -A12 'aa:aa:aa:aa:aa:aa' \| grep -i 'MM:'` | `MM:1\|MM:[2-9]` |
| host2 | `ping -c 3 -W 1 10.10.10.10` | ` 0% packet loss` |

