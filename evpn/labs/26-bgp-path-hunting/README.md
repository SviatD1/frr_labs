# Lab 26 - BGP Path Hunting / Path Exploration in Data Center. BGP MRAI

**Video:** [BGP Path Hunting / Path Exploration in Data Center. BGP MRAI](https://www.youtube.com/watch?v=CA4kklcCeHk) (52 min) - part of the [Sneaky Subnet EVPN playlist](https://www.youtube.com/playlist?list=PLWR_dLKO9z7E)  
**Author's original (Arista cEOS / containerlab) config:** https://github.com/sneakysubnet/evpn_with_clab/tree/main/design_underlay_bgp_hunt  

When a prefix disappears, BGP speakers don't learn "it's gone" in one step - they first try every
alternative path they still have (**path hunting / path exploration**), sending a burst of UPDATEs.
MRAI (Minimum Route Advertisement Interval) batches updates and changes the picture. You will flap
a prefix and count UPDATE messages across ASN designs and MRAI settings.

## Topology

```
    spine1          spine2          (AS 65100 each, or unique 65101/65102)
   / | | \         / | | \
leaf1 leaf2 leaf3 leaf4             AS 65001..65004
  10.255.255.1/32 originated on leaf1 (lo), flapped with `flap-prefix`
```

### Nodes

| Node | Role | Loopback / addressing |
|---|---|---|
| spine1 | spine | 11.11.11.11 AS 65101 |
| spine2 | spine | 12.12.12.12 AS 65102 |
| leaf1 | leaf | 1.1.1.1 AS 65001 |
| leaf2 | leaf | 2.2.2.2 AS 65002 |
| leaf3 | leaf | 3.3.3.3 AS 65003 |
| leaf4 | leaf | 4.4.4.4 AS 65004 |

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

### Variants

Each variant is a complete set of node scripts in `nodes/<variant>/`. Same GNS3 topology, just push a different variant.

- **unique-asn-mrai0** *(default)* - unique ASN on every switch, MRAI 0 (FRR datacenter default)
- **unique-asn-mrai5** - unique ASN, MRAI 5 s
- **same-asn-spines** - spines share AS 65100, MRAI 0

## Run it

```powershell
cd evpn
python tools\gns3_lab.py up labs\26-bgp-path-hunting   # default variant: unique-asn-mrai0
python tools\gns3_lab.py push labs\26-bgp-path-hunting --variant unique-asn-mrai5   # switch variant in place
python tools\gns3_lab.py check labs\26-bgp-path-hunting
```

Or by hand: open each node's console in GNS3 and run its script from `nodes/unique-asn-mrai0/` (see the top-level README).

## What you will learn

* BGP message types and the UPDATE/withdraw flow; why a withdrawal can produce *more* updates than an announcement.
* **Path hunting** in a Clos: with unique ASNs a spine knows 10.255.255.1/32 directly from leaf1 *and* via
  the other leaves (e.g. spine2 learns `65002 65101 65001` = leaf2 -> spine1 -> leaf1, because leaf2's best path goes
  through spine1). When leaf1 withdraws, spine2 switches to one of those stale alternatives, advertises it, then
  withdraws it when its source withdraws too... until nothing is left.
* **MRAI**: `neighbor X advertisement-interval N`. FRR `datacenter` defaults use 0 s (send immediately);
  RFC 4271 suggests 30 s for eBGP. Higher MRAI = fewer, batched updates but slower convergence.
* The structural fix from RFC 7938 / the video: **same ASN on all spines** (and, in 5-stage, per tier) so the
  alternative paths are never accepted in the first place.

## Step by step

```bash
# spine1 / spine2: how many paths for the test prefix?
vtysh -c 'show ip bgp 10.255.255.1/32'
# leaf4: watch updates arrive
bgp-updates                     # per-neighbor UPDATE counters (sent / rcvd)
journalctl -f -t bgpd           # with 'debug bgp updates' enabled (see below)
# leaf1
flap-prefix down ; sleep 10 ; flap-prefix up
```

Turn on update logging where you watch: `vtysh -c 'debug bgp updates'` (logs go to syslog: `journalctl -t bgpd`).
Count the UPDATE messages leaf4 received for one `flap-prefix down` in each variant (run `bgp-updates`
before and after). Typical result: `unique-asn-mrai0` shows several withdraw/re-announce rounds, `same-asn-spines`
just one withdrawal per spine; `unique-asn-mrai5` fewer messages but takes ~5 s+ to converge.

The video's capture approach: `tcpdump -ni eth11 -w /tmp/l4.pcap tcp port 179` on leaf4, open in Wireshark,
filter `bgp.type == 2`.

**EVPN impact** (video 48:20): VTEP loopbacks are underlay prefixes - while they "hunt", EVPN next hops stay
resolvable through stale paths, and type-2 routes keep pointing at a VTEP that may be gone.

## Automated checks

`gns3_lab.py check` runs these and compares against the regex:

*variant unique-asn-mrai0*

| node | command | expect |
|---|---|---|
| leaf4 | `vtysh -c 'show ip bgp 10.255.255.1/32'` | `65001` |
| spine2 | `vtysh -c 'show ip bgp 10.255.255.1/32'` | `6500[234] 65101 65001\|6500[234] 65102 65001` |

*variant unique-asn-mrai5*

| node | command | expect |
|---|---|---|
| leaf4 | `vtysh -c 'show ip bgp 10.255.255.1/32'` | `65001` |

*variant same-asn-spines*

| node | command | expect |
|---|---|---|
| leaf4 | `vtysh -c 'show ip bgp 10.255.255.1/32'` | `65001` |

