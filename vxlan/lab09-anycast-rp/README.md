# Lab 09 · Multicast Anycast-RP underlay

**Video:** *VXLAN - Multicast Anycast RP Underlay Solution* (#9)
**Status:** ✅ tested (MSDP mesh-group, SAs exchanged, cross-spine BUM works)

## The problem and the fix

In lab 08 spine1 is the only RP: lose it and every new BUM flow breaks. **Anycast RP**: put the *same* RP address (10.255.255.1/32) on both spines and advertise it in OSPF. Each router uses the closest RP. But now a source registers with spine1 while a receiver joined spine2 — the two RPs must tell each other about active sources. That's **MSDP** (Source-Active messages) between the RPs, configured as a mesh-group. (Nexus also offers PIM Anycast-RP per RFC 4610 without MSDP; FRR uses the MSDP method.)

## Topology

Same as lab 08, plus on **both** spines:

```
 lo: 10.0.0.S/32 (unique, MSDP peering)   +   10.255.255.1/32 (anycast RP, identical)
 ip pim rp 10.255.255.1 239.0.0.0/8
 ip msdp mesh-group ANYCAST-RP source 10.0.0.S
 ip msdp mesh-group ANYCAST-RP member <other spine>
```

## Build

Run `nodes/<node>.sh` on spine1-2, leaf1-3, h1-5.

## Verify

```bash
spine1# vtysh -c 'show ip pim rp-info'        # 10.255.255.1  I am RP: yes   (on spine2 too!)
spine1# ip route show 10.255.255.1            # local (lo)
leaf3#  ip route show 10.255.255.1            # via spine2 — closest RP
spine1# vtysh -c 'show ip msdp peer'          # 10.0.0.2 established
h1$ ping -c2 192.168.100.103 ; h3$ ping -c2 192.168.100.101
spine1# vtysh -c 'show ip msdp sa'
#  10.1.11.1  239.1.1.100   local: y               <- registered at spine1
#  10.2.13.1  239.1.1.100   RP 10.0.0.2  local: n  <- learned from spine2 via MSDP
```

## Experiments

1. **Prove MSDP matters**: do this on a freshly started lab (before hosts have learned each other). On spine1 `vtysh -c 'conf t' -c 'no ip msdp mesh-group ANYCAST-RP member 10.0.0.2'`, and on spine2 the same with `member 10.0.0.1`. Now h1→h2 (both under spine1) works, but h1→h3 and h3→h1 fail: leaf1's BUM registers at spine1, leaf3 joined at spine2, and nobody tells the other RP. (Already-learned MACs keep unicast working, so restart the lab or wait for MAC/ARP ageing if you've pinged before.) Re-run the spine scripts to restore.
2. **RP failure**: shut spine1 completely (stop the VM). leaf1 and leaf2 lose their uplink in this topology (single-homed), so instead test RP-only failure: on spine1 `ip addr del 10.255.255.1/32 dev lo`. OSPF now routes 10.255.255.1 to spine2 for everyone, all (*,G) state re-forms toward spine2, BUM keeps working.
3. **Wire view**: capture spine1↔spine2, filter `msdp` (TCP 639). See the keepalives and SA messages carrying (S,G,RP).

## Break / fix

| Break it | Symptom |
|---|---|
| Use the anycast address as MSDP source/peer | MSDP never comes up — peering must use **unique** addresses |
| Forget `ip pim` on `lo` of a spine | spine doesn't consider itself RP (`I am RP: no`) |
| Advertise 10.255.255.1 only from spine1 | works, but it's no longer anycast — check `ip route show 10.255.255.1` on leaf3 |

## Questions

- Why must the anycast RP address never be used as the OSPF/BGP router-id?
- What does "mesh-group" save you compared to a full set of individual MSDP peers?
