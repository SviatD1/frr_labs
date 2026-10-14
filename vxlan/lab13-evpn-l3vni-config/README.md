# Lab 13 · Configuring MP-BGP EVPN for L3VNIs

**Video:** *VXLAN - Configuring MP-BGP EVPN for L3 VNIs on Cisco Nexus* (#13)
**Status:** ⚠️ FRR configs syntax-checked; same building blocks as lab 11 (not run on the VRF-less test kernel).

## Goal

Configure the L3 pieces yourself, for **two tenants**, and prove they're isolated:

| Tenant | VRF (table) | L3VNI | L2VNIs / subnets |
|---|---|---|---|
| RED | `RED` (1001) | 50001 | 10010 = 192.168.10.0/24, 10020 = 192.168.20.0/24 |
| BLUE | `BLUE` (1002) | 50002 | 10030 = 192.168.30.0/24 |

```
     [spine1] RR        [spine2] RR
   [leaf1]            [leaf2]            [leaf3]
  eth3   eth4          eth3             eth3   eth4
   h1     h4            h2               h3     h5
 RED     BLUE          RED              RED    BLUE
 .10.101 .30.101       .20.102          .10.103 .30.103
```

leaf2 has no BLUE hosts, so it doesn't get the BLUE VRF at all.

## NX-OS ↔ Linux/FRR, step by step

| Step | NX-OS | Linux / FRR (see `nodes/leaf1.sh` / `.frr.conf`) |
|---|---|---|
| 1. VRF | `vrf context RED` | `ip link add RED type vrf table 1001; ip link set RED up` |
| 2. L3VNI | `vrf context RED` / `vni 50001` | FRR: `vrf RED` / ` vni 50001` / `exit-vrf` |
| 3. L3VNI "VLAN" + SVI | `vlan 2001` / `vn-segment 50001` ; `interface Vlan2001` / `vrf member RED` / `ip forward` | `br50001` (bridge, master RED) + `vxlan50001` in it |
| 4. NVE | `member vni 50001 associate-vrf` | `vxlan50001 ... nolearning`, zebra binds it via step 2 |
| 5. Anycast gateway | `fabric forwarding anycast-gateway-mac 0200.5e00.0101` ; `interface Vlan10` / `fabric forwarding mode anycast-gateway` | `ip link set br10010 address 02:00:5e:00:01:01` + `ip addr add 192.168.10.1/24 dev br10010`, same on every leaf |
| 6. BGP VRF | `router bgp 65000` / `vrf RED` / `address-family ipv4 unicast` / `advertise l2vpn evpn` | `router bgp 65000 vrf RED` / `redistribute connected` / `address-family l2vpn evpn` / `advertise ipv4 unicast` |
| 7. RT | `vrf context RED` / `address-family ipv4 unicast` / `route-target both auto evpn` | auto: `65000:50001` |

## Build

Run `nodes/<node>.sh` on spine1-2, leaf1-3, h1-5. Then do the *verification first*, and as an exercise rebuild leaf2 from an empty FRR config by typing steps 2 and 6 yourself in `vtysh`.

## Verify

```bash
leaf1# ip -br link show type vrf                      # RED, BLUE
leaf1# ip link show master RED                        # br50001, br10010
leaf1# vtysh -c 'show vrf vni'                        # RED 50001, BLUE 50002, both Up
leaf1# vtysh -c 'show evpn vni'                       # L2: 10010 10030 ; L3: 50001 50002
h1$ ping 192.168.20.102   # RED -> RED, different subnet, across leaves  (works)
h1$ ping 192.168.10.103   # RED, same subnet  (bridged in VNI 10010)
h4$ ping 192.168.30.103   # BLUE (bridged in 10030)
h1$ ping 192.168.30.101   # RED -> BLUE : FAILS (different VRF)
leaf1# ip route show vrf RED ; ip route show vrf BLUE
leaf1# vtysh -c 'show bgp l2vpn evpn route type prefix'   # type-5s tagged RT:65000:50001 vs 65000:50002
```

## Experiments

1. **Packet walk RED inter-subnet**: capture while h1 pings h2 → VNI **50001** on the wire. h4→h5 → VNI **10030** (bridged).
2. **Overlapping IPs between tenants**: change BLUE's subnet to 192.168.10.0/24 on leaf1/leaf3 and h4/h5 (gateway 192.168.10.1 in BLUE as well). Both tenants keep working: separate VRFs, separate L3VNIs, separate tables.
3. **Route leaking (shared services)**: import RED's RT into BLUE on leaf1:
   ```
   router bgp 65000 vrf BLUE
    address-family l2vpn evpn
     route-target import 65000:50001
   ```
   Look at `ip route show vrf BLUE`. Discuss why the return path also needs the opposite import.
4. **Add a third leaf to BLUE**: give leaf2 a BLUE VRF and host — only kernel + `vrf BLUE / vni 50002` + `router bgp 65000 vrf BLUE` needed.

## Break / fix

| Break it | Symptom |
|---|---|
| leaf3: `vrf RED` / `vni 50002` (swap tenants' L3VNI) | RED routes from leaf3 land in BLUE elsewhere — tenant leak / blackhole |
| leaf1: forget `ip link set br10010 master RED` | h1's gateway lives in the default VRF: h1 can reach nothing routed |
| leaf2: different gateway MAC | works until h2 moves to another leaf (→ lab 14) |

## Questions

- Why does each tenant need its own L3VNI?
- What is the minimum a leaf needs to route for a tenant it has no hosts for? (Nothing — see leaf2/BLUE.)
