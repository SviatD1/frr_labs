# Linux networking + FRR cheat sheet

## Linux: look at the network

| Command | Shows |
|---|---|
| `ip -br link` | interfaces, up/down, MAC (brief) |
| `ip -br addr` | interfaces with IPv4/IPv6 addresses |
| `ip addr show dev eth0` | full detail for one interface |
| `ip route` | IPv4 routing table (kernel FIB). `proto bgp`/`proto ospf` = installed by FRR |
| `ip route show proto bgp` | only BGP routes |
| `ip route get 192.168.4.10` | which route/interface/source address the kernel would use for that destination |
| `ip neigh` | ARP table |
| `ss -tnp 'sport = :179 or dport = :179'` | BGP TCP sessions |
| `sysctl net.ipv4.ip_forward` | 1 = router, 0 = host |
| `sysctl -a 2>/dev/null \| grep rp_filter` | reverse-path filter; Linux uses the higher of `all` and the per-interface value, so the labs set both to 0 (asymmetric routing works) |

## Linux: change the network (not persistent: the labs persist them in `/etc/lab/net.sh`)

```bash
ip link set eth1 up
ip addr add 10.0.99.1/24 dev eth1
ip addr del 10.0.99.1/24 dev eth1
ip route add 10.9.9.0/24 via 10.0.12.2
ip route replace default via 192.168.1.1
ip link add lan9 type dummy && ip link set lan9 up      # extra "LAN" for advertising
ip link set eth0 down                                     # simulate a link failure
```

## Linux: test and capture

```bash
ping -c3 192.168.4.10
ping -I 1.1.1.1 4.4.4.4            # choose the source address
traceroute -n 192.168.4.10         # -n: no DNS
mtr -n 192.168.4.10                # live traceroute
tcpdump -ni eth0 tcp port 179      # BGP packets
tcpdump -ni eth0 -vvv tcp port 179 # decoded BGP messages (OPEN, UPDATE attributes…)
tcpdump -ni eth0 icmp
iperf3 -s   /   iperf3 -c <ip>     # bandwidth test between hosts
```

**Traceroute note:** each hop replies from the address of the interface it uses to send the reply *back to
you* (its route to the sender), not necessarily the interface the probe came in on.

## FRR basics

| What | Where / how |
|---|---|
| Enable daemons | `/etc/frr/daemons` (`bgpd=yes`, `ospfd=yes`, …) then `systemctl restart frr` |
| Config file | `/etc/frr/frr.conf` (integrated config for all daemons) |
| Shell | `vtysh` (Cisco-like CLI). One-off: `vtysh -c "show bgp summary"` |
| Configure | `configure terminal` … `end` |
| Save | `write memory` (or `vtysh -w`) |
| Logs | `journalctl -u frr -f` (FRR logs to syslog). `debug bgp ...` output also goes there; `show logging` only shows the logging settings |
| Service | `systemctl status|restart frr` |

## FRR: most used show commands

```
show bgp summary                               # neighbors, state, prefixes received/sent
show bgp ipv4 unicast                          # BGP table (*> = valid + best)
show bgp ipv4 unicast 192.168.4.0/24           # every path + attributes + "best (reason)"
show bgp ipv4 unicast 192.168.4.0/24 json      # same, machine-readable (selectionReason)
show bgp neighbors 10.0.12.2                   # session details, timers, capabilities, last reset
show bgp ipv4 unicast neighbors 10.0.12.2 advertised-routes
show bgp ipv4 unicast neighbors 10.0.12.2 received-routes    # needs soft-reconfiguration inbound
show bgp ipv4 unicast neighbors 10.0.12.2 routes             # accepted from that neighbor
show bgp nexthop                               # next-hop tracking: valid/invalid, IGP metric
show bgp ipv4 unicast community 100:1
show bgp ipv4 unicast regexp _300_
show ip route                                  # zebra RIB (all protocols)
show ip route bgp
show ip ospf neighbor
show route-map
show running-config
```

## FRR: BGP config skeleton

```
router bgp 100
 bgp router-id 1.1.1.1
 no bgp ebgp-requires-policy            ! lab shortcut; otherwise apply route-maps in+out on eBGP peers
 neighbor 10.0.12.2 remote-as 200       ! eBGP ("remote-as external" also works)
 neighbor 2.2.2.2 remote-as 100         ! iBGP between loopbacks
 neighbor 2.2.2.2 update-source lo
 !
 address-family ipv4 unicast
  network 192.168.1.0/24                ! must exist in the RIB with exactly this mask
  neighbor 2.2.2.2 next-hop-self
  neighbor 10.0.12.2 route-map FROM-R2 in
 exit-address-family
```

Resetting after policy changes: `clear bgp 10.0.12.2 soft in` / `soft out` (no session flap),
`clear bgp 10.0.12.2` (hard reset), `clear bgp *` (everything).

## Route-map building blocks

```
ip prefix-list P1 seq 5 permit 192.168.4.0/24
bgp as-path access-list A1 seq 5 permit ^$          ! routes originated in my AS (empty AS_PATH)
bgp community-list standard C1 seq 5 permit 200:80
route-map EXAMPLE permit 10
 match ip address prefix-list P1        ! or: match as-path A1 / match community C1
 set local-preference 200               ! weight, metric (MED), as-path prepend, community, origin, ip next-hop
route-map EXAMPLE permit 20             ! everything else unchanged (route-maps end with an implicit deny)
```

## FRR best-path order

Weight → Local-pref → Locally originated → AS_PATH length → Origin (i<e<?) → MED → eBGP over iBGP →
IGP metric to next hop → (multipath) → oldest eBGP path → Router ID / Originator ID → Cluster-list length →
Neighbor address.
