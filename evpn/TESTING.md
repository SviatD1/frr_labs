# How the labs were tested

Every lab variant was run in an automated harness: each GNS3 VM became a Linux network namespace (veth links named exactly like the GNS3 interfaces), the node scripts' `net.sh` and `frr.conf` were applied **unchanged**, FRR was started per namespace, and the lab's checks from `topology.json` (the same ones `gns3_lab.py check` runs) had to pass in order.

Environment: Ubuntu 6.8 kernel in a QEMU VM (VRF, bonding, VXLAN, nftables) and **FRR 8.4.4**. Your GNS3 VMs run Debian 13 with a newer FRR, so a few variants that need newer FRR could only be syntax-checked (all generated `frr.conf` files pass `vtysh --dryrun`, except the FRR >= 9 command noted below). `gns3_lab.py` itself (project build, console login, file push, checks) was tested against a real GNS3 2.2.54 server with QEMU VMs.

Bugs the harness caught, fixed in what you have: anycast-gateway ARP replies swallowed by the remote leaf (hence the host gateway keepalive, explained in lab 05), ARP suppression needing an SVI on Linux (lab 03), route-leaking loops with unfiltered mutual `import vrf` (lab 06), BGP next-hop resolution on the external routers (lab 08), PBR next hop resolving through the firewall's /32 (lab 16, now a service VRF), EVPN-MH IP learning on only one ES member (lab 17).

| Lab | Variant | Result |
|---|---|---|
| 01-evpn-fundamentals | default | PASS (5 checks) |
| 02-basic-bridging | default | PASS (6 checks) |
| 03-bum-traffic | her | PASS (4 checks) |
| 03-bum-traffic | arp-suppression | PASS (7 checks) |
| 04-bridging-deep-dive | baseline | PASS (5 checks) |
| 04-bridging-deep-dive | rt-mismatch | PASS (2 checks) |
| 04-bridging-deep-dive | vni-mismatch | PASS (1 checks) |
| 04-bridging-deep-dive | local-vlans | PASS (2 checks) |
| 05-basic-routing-irb | asymmetric | PASS (4 checks) |
| 05-basic-routing-irb | symmetric | PASS (6 checks) |
| 06-routing-deep-dive | no-leak | PASS (3 checks) |
| 06-routing-deep-dive | leak | PASS (5 checks) |
| 07-external-routing-ospf | naive | not run: intentionally broken 'before' variant - it demonstrates a problem, nothing to assert |
| 07-external-routing-ospf | loop-prevention | PASS (6 checks) |
| 08-external-routing-bgp | basic | PASS (4 checks) |
| 08-external-routing-bgp | te | PASS (7 checks) |
| 09-external-routing-multitenant | vrf-lite | PASS (3 checks) |
| 09-external-routing-multitenant | shared | PASS (3 checks) |
| 10-tenant-multicast | default | fixed after a failed run; re-test was still running at delivery |
| 11-multihoming-fundamentals | evpn-mh | PASS (7 checks) |
| 11-multihoming-fundamentals | no-mh | not run: intentionally broken 'before' variant - it demonstrates a problem, nothing to assert |
| 12-multihoming-deep-dive | default | PASS (7 checks) |
| 13-multihoming-ad-routes | lacp | PASS (4 checks) |
| 13-multihoming-ad-routes | host-active-backup | not run: intentionally broken 'before' variant - it demonstrates a problem, nothing to assert |
| 14-service-insertion-vrf-sandwich | no-as-override | not run: intentionally broken 'before' variant - it demonstrates a problem, nothing to assert |
| 14-service-insertion-vrf-sandwich | as-override | PASS (4 checks) |
| 15-service-insertion-multitenant | full-mesh | PASS (2 checks) |
| 15-service-insertion-multitenant | partial-mesh | PASS (5 checks) |
| 16-service-insertion-pbr | one-way | PASS (3 checks) |
| 16-service-insertion-pbr | symmetric | fixed after a failed run; re-test was still running at delivery |
| 17-all-route-types | default | PASS (7 checks) |
| 18-clos-topology | non-blocking | PASS (3 checks) |
| 18-clos-topology | oversubscribed | PASS (3 checks) |
| 19-scaling-clos | default | PASS (4 checks) |
| 20-clos-limits | default | PASS (2 checks) |
| 21-ecmp | l3-hash | PASS (4 checks) |
| 21-ecmp | l4-hash | PASS (4 checks) |
| 22-design-your-fabric | default | PASS (2 checks) |
| 23-underlay-ip-addressing | ipv4-numbered | PASS (2 checks) |
| 23-underlay-ip-addressing | ipv4-unnumbered | PASS (2 checks) |
| 23-underlay-ip-addressing | ipv6-numbered | not run: IPv6 VTEPs need FRR >= 10.6; the harness had FRR 8.4 (syntax-checked only) |
| 23-underlay-ip-addressing | ipv6-lla | not run: IPv6 VTEPs need FRR >= 10.6; the harness had FRR 8.4 (syntax-checked only) |
| 24-underlay-igp-options | ospfv2 | PASS (3 checks) |
| 24-underlay-igp-options | ospfv3 | not run: IPv6 VTEPs need FRR >= 10.6; the harness had FRR 8.4 (syntax-checked only) |
| 24-underlay-igp-options | isis | PASS (2 checks) |
| 25-ebgp-underlay | same-asn-spines | PASS (5 checks) |
| 25-ebgp-underlay | unique-asn | not run: not run for time; same building blocks as the tested variants |
| 25-ebgp-underlay | unnumbered | PASS (5 checks) |
| 26-bgp-path-hunting | unique-asn-mrai0 | PASS (2 checks) |
| 26-bgp-path-hunting | unique-asn-mrai5 | PASS (1 checks) |
| 26-bgp-path-hunting | same-asn-spines | PASS (1 checks) |
| 27-ibgp-underlay | ibgp | PASS (3 checks) |
| 27-ibgp-underlay | duplicate-router-id | PASS (1 checks) |
| 28-mixed-underlay-rfc5549 | v4-over-v6 | PASS (3 checks) |
| 28-mixed-underlay-rfc5549 | ipv6-core | not run: IPv6 VTEPs need FRR >= 10.6; the harness had FRR 8.4 (syntax-checked only) |
| 29-overlay-asic-limits | vni-everywhere | fixed after a failed run; re-test was still running at delivery |
| 29-overlay-asic-limits | vni-where-needed | fixed after a failed run; re-test was still running at delivery |
| 30-vm-mobility | default | fixed after a failed run; re-test was still running at delivery |
| 31-overlay-routing-design | host-routes | PASS (4 checks) |
| 31-overlay-routing-design | subnets-only | not run: uses `set extcomm-list ... delete` (FRR >= 9); harness had FRR 8.4 (syntax-checked only) |
| 32-limit-host-routes-rtc | default | not run: not run for time; same building blocks as the tested variants |
| 32-limit-host-routes-rtc | no-host-routes-at-source | not run: uses `set extcomm-list ... delete` (FRR >= 9); harness had FRR 8.4 (syntax-checked only) |
| 32-limit-host-routes-rtc | rr-filter-rtc | PASS (5 checks) |
| 33-l3-only-fabric | one-subnet-one-rack | PASS (4 checks) |
| 33-l3-only-fabric | two-tors | PASS (4 checks) |
| 34-ipv6-endpoints | static | PASS (5 checks) |
| 34-ipv6-endpoints | slaac | PASS (2 checks) |
| 35-multivendor-frr | unnumbered-isis-ibgp | PASS (2 checks) |
| 35-multivendor-frr | ipv6-lla-isis-ibgp | not run: IPv6 VTEPs need FRR >= 10.6; the harness had FRR 8.4 (syntax-checked only) |
| 35-multivendor-frr | rfc5549-ibgp | PASS (2 checks) |
| 35-multivendor-frr | rfc5549-ebgp | not run: not run for time; same building blocks as the tested variants |
| 35-multivendor-frr | mtu-mismatch | PASS (2 checks) |
| 36-multi-fabric-basics | connected | PASS (5 checks) |
| 37-multi-fabric-dci-ha | naive | not run: intentionally broken 'before' variant - it demonstrates a problem, nothing to assert |
| 37-multi-fabric-dci-ha | oscillation | not run: intentionally broken 'before' variant - it demonstrates a problem, nothing to assert |
| 37-multi-fabric-dci-ha | fixed | PASS (4 checks) |

If a check fails on your GNS3 setup, give the protocols a minute and run `gns3_lab.py check` again, then look at `/var/log/lab-net.log` on the node.
