"""
Lab generator framework.

Every lab is described in Python (labs_*.py).  This module turns that
description into:

  labs/NN-slug/README.md
  labs/NN-slug/topology.json          (consumed by tools/gns3_lab.py)
  labs/NN-slug/nodes/<variant>/<node>.sh   (self-contained apply script per VM)

A node script writes two things on the VM:
  /etc/lab/net.sh    - Linux data plane (ip/bridge commands)  -> "kernel side"
  /etc/frr/frr.conf  - FRR control plane                      -> "routing side"
and then calls `lab-apply` (installed by base-image/build-base.sh).
"""
import json
import os
import re
import textwrap
from collections import OrderedDict

ANYCAST_MAC = "00:00:5e:00:01:01"
ANYCAST_MAC6 = ANYCAST_MAC
ROUTER_ADAPTERS = 13      # eth0..eth12  (eth11/eth12 = uplinks, like the videos)
HOST_ADAPTERS = 3         # eth0..eth2
YT = "https://www.youtube.com/watch?v="
PLAYLIST = "https://www.youtube.com/playlist?list=PLWR_dLKO9z7E"
REF_REPO = "https://github.com/sneakysubnet/evpn_with_clab/tree/main/"


def dedent(s):
    return textwrap.dedent(s).strip("\n")


# --------------------------------------------------------------------------
# FRR configuration builder
# --------------------------------------------------------------------------
class Bgp:
    def __init__(self, asn, rid=None, vrf=None):
        self.asn, self.rid, self.vrf = asn, rid, vrf
        self.glob = []
        self.afs = OrderedDict()

    def g(self, *lines):
        self.glob.extend(lines)
        return self

    def af(self, name, *lines):
        self.afs.setdefault(name, []).extend(lines)
        return self

    def render(self):
        out = [f"router bgp {self.asn}" + (f" vrf {self.vrf}" if self.vrf else "")]
        if self.rid:
            out.append(f" bgp router-id {self.rid}")
        out += [" " + l for l in self.glob]
        for name, lines in self.afs.items():
            out.append(" !")
            out.append(f" address-family {name}")
            out += ["  " + l for l in lines]
            out.append(" exit-address-family")
        out.append("exit")
        return "\n".join(out)


class Frr:
    def __init__(self, hostname, defaults="datacenter"):
        self.hostname = hostname
        self.defaults = defaults
        self.top = []                 # global one-liners (ip forwarding, prefix-lists...)
        self.vrfs = OrderedDict()
        self.ifaces = OrderedDict()
        self.blocks = []              # router ... blocks / route-maps (rendered in order)
        self.bgps = []

    def line(self, *l):
        self.top.extend(l)
        return self

    def vrf(self, name, *lines):
        self.vrfs.setdefault(name, []).extend(lines)
        return self

    def iface(self, name, *lines):
        self.ifaces.setdefault(name, []).extend(lines)
        return self

    def block(self, text):
        self.blocks.append(dedent(text))
        return self

    def bgp(self, asn, rid=None, vrf=None):
        b = Bgp(asn, rid, vrf)
        self.bgps.append(b)
        return b

    def render(self):
        out = [f"frr defaults {self.defaults}", f"hostname {self.hostname}",
               "log syslog informational", "service integrated-vtysh-config", "!"]
        if self.top:
            out += self.top + ["!"]
        for name, lines in self.vrfs.items():
            out.append(f"vrf {name}")
            out += [" " + l for l in lines]
            out += ["exit-vrf", "!"]
        for name, lines in self.ifaces.items():
            out.append(f"interface {name}")
            out += [" " + l for l in lines]
            out += ["exit", "!"]
        for b in self.blocks:
            out += [b, "!"]
        for b in self.bgps:
            out += [b.render(), "!"]
        out.append("end")
        return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Node / Lab model
# --------------------------------------------------------------------------
class Node:
    def __init__(self, name, kind="router", role=None, adapters=None, ram=None):
        self.name = name
        self.kind = kind                  # router (runs FRR) | host (no FRR)
        self.role = role or kind          # spine / leaf / border / host / ext / fw ...
        self.adapters = adapters or (ROUTER_ADAPTERS if kind == "router" else HOST_ADAPTERS)
        self.ram = ram or (512 if kind == "router" else 256)
        self.netlines = []
        self.frr = Frr(name) if kind == "router" else None
        self.lo4 = None
        self.lo6 = None
        self.notes = []                   # shown in README node table
        self.files = OrderedDict()        # extra files written on the VM: path -> (content, mode)

    # ---- Linux side --------------------------------------------------
    def sh(self, *lines):
        for l in lines:
            self.netlines.extend(dedent(l).split("\n") if "\n" in l else [l])
        return self

    def comment(self, text):
        self.netlines.append("")
        self.netlines.append("# --- " + text + " ---")
        return self

    def render_net(self):
        return "\n".join(self.netlines) + "\n"


class Lab:
    def __init__(self, num, slug, title, video, minutes, summary, ref=None):
        self.num, self.slug, self.title = num, slug, title
        self.video, self.minutes, self.summary = video, minutes, summary
        self.ref = ref
        self.links = []          # (a, aif, b, bif)
        self.variants = OrderedDict()   # name -> dict(nodes=OrderedDict, desc=str)
        self.default_variant = None
        self.readme = ""
        self.checks = OrderedDict()     # variant -> [ {node, cmd, expect, desc} ]
        self.extra_files = {}           # relative path -> content
        self.positions = {}
        self.diagram = ""

    @property
    def dirname(self):
        return f"{self.num:02d}-{self.slug}"

    def variant(self, name, desc, default=False):
        v = self.variants.setdefault(name, {"nodes": OrderedDict(), "desc": desc})
        if default or self.default_variant is None:
            self.default_variant = name
        return v["nodes"]

    def link(self, a, aif, b, bif):
        self.links.append((a, aif, b, bif))

    def check(self, variant, node, cmd, expect, desc=""):
        self.checks.setdefault(variant, []).append(
            {"node": node, "cmd": cmd, "expect": expect, "desc": desc})


# --------------------------------------------------------------------------
# Building blocks (Linux side + FRR side)
# --------------------------------------------------------------------------
def loopback(n, ip4=None, ip6=None):
    n.comment("loopback (router-id / VTEP source)")
    if ip4:
        n.sh(f"ip addr add {ip4}/32 dev lo")
        n.lo4 = ip4
    if ip6:
        n.sh(f"ip -6 addr add {ip6}/128 dev lo")
        n.lo6 = ip6


def addr(n, ifname, ip=None, ip6=None, mtu=None, vrf=None, desc=None):
    if desc:
        n.sh(f"# {ifname}: {desc}")
    if mtu:
        n.sh(f"ip link set {ifname} mtu {mtu}")
    if vrf:
        n.sh(f"ip link set {ifname} master {vrf}")
    n.sh(f"ip link set {ifname} up")
    if ip:
        n.sh(f"ip addr add {ip} dev {ifname}")
    if ip6:
        n.sh(f"ip -6 addr add {ip6} dev {ifname}")


def bridge(n, mac):
    n.comment("VLAN-aware bridge (one per switch, like a hardware switch's VLAN table)")
    n.sh(f"ip link add br0 type bridge vlan_filtering 1 vlan_default_pvid 0 mcast_snooping 0 stp_state 0",
         f"ip link set br0 address {mac}",
         "ip link set br0 addrgenmode none",
         "ip link set br0 up")


def access_port(n, ifname, vlan, mtu=None):
    n.sh(f"ip link set {ifname} master br0",
         f"bridge vlan add dev {ifname} vid {vlan} pvid untagged")
    if mtu:
        n.sh(f"ip link set {ifname} mtu {mtu}")
    n.sh(f"ip link set {ifname} up")


def trunk_port(n, ifname, vlans):
    n.sh(f"ip link set {ifname} master br0")
    for v in vlans:
        n.sh(f"bridge vlan add dev {ifname} vid {v}")
    n.sh(f"ip link set {ifname} up")


def vxlan(n, vni, vlan, local, suppress=True, group=None, group_dev=None, mtu=None, learning=False):
    name = f"vxlan{vni}"
    n.comment(f"VNI {vni} <-> VLAN {vlan}")
    extra = ""
    if group:
        extra = f" group {group} dev {group_dev} ttl 10"
    n.sh(f"ip link add {name} type vxlan id {vni} local {local} dstport 4789 nolearning{extra}")
    if mtu:
        n.sh(f"ip link set {name} mtu {mtu}")
    n.sh(f"ip link set {name} master br0 addrgenmode none",
         f"bridge vlan del dev {name} vid 1 2>/dev/null || true",
         f"bridge vlan add dev {name} vid {vlan} pvid untagged",
         f"bridge link set dev {name} learning {'on' if learning else 'off'} neigh_suppress {'on' if suppress else 'off'}",
         f"ip link set {name} up")
    return name


def vrf_dev(n, name, table):
    n.comment(f"VRF {name} (kernel routing table {table})")
    n.sh(f"ip link add {name} type vrf table {table}",
         f"ip link set {name} up")


def svi(n, vlan, ip=None, ip6=None, vrf=None, mac=ANYCAST_MAC, comment=None):
    """L3 interface for a VLAN (Arista 'interface VlanX')."""
    name = f"vlan{vlan}"
    n.comment(comment or f"SVI {name}" + (f" in VRF {vrf}" if vrf else "") + (f" (anycast gw {ip})" if ip and mac == ANYCAST_MAC else ""))
    n.sh(f"bridge vlan add dev br0 vid {vlan} self",
         f"ip link add {name} link br0 type vlan id {vlan}")
    if mac:
        n.sh(f"ip link set {name} address {mac}",
             f"bridge fdb replace {mac} dev br0 vlan {vlan} self local")
    if vrf:
        n.sh(f"ip link set {name} master {vrf}")
    n.sh(f"ip link set {name} up")
    if ip:
        n.sh(f"ip addr add {ip} dev {name}")
    if ip6:
        n.sh(f"ip -6 addr add {ip6} dev {name}")
    return name


def l3vni(n, vrf, vni, vlan, local):
    """Symmetric IRB transit VNI: vxlan + SVI (no IP) inside the VRF."""
    n.comment(f"L3VNI {vni} for VRF {vrf} (transit VLAN {vlan}, router-MAC = br0 MAC)")
    vxlan(n, vni, vlan, local, suppress=True)
    n.sh(f"bridge vlan add dev br0 vid {vlan} self",
         f"ip link add vlan{vlan} link br0 type vlan id {vlan}",
         f"ip link set vlan{vlan} master {vrf} addrgenmode none",
         f"ip link set vlan{vlan} up")
    n.frr.vrf(vrf, f"vni {vni}")


def host(lab, nodes, name, ip=None, gw=None, mac=None, ifname="eth1", ip6=None, gw6=None,
         mtu=1450, vlan=None, extra=None, role="host", keepalive_extra=()):
    h = Node(name, "host", role)
    h.comment("host interface")
    dev = ifname
    if mac:
        h.sh(f"ip link set {ifname} address {mac}")
    h.sh(f"ip link set {ifname} mtu {mtu} up")
    if vlan:
        dev = f"{ifname}.{vlan}"
        h.sh(f"ip link add link {ifname} name {dev} type vlan id {vlan}",
             f"ip link set {dev} up")
    if ip:
        h.sh(f"ip addr add {ip} dev {dev}")
    if ip6:
        h.sh(f"ip -6 addr add {ip6} dev {dev} nodad")
    if gw:
        h.sh(f"ip route add default via {gw} dev {dev}")
    if gw6:
        h.sh(f"ip -6 route add default via {gw6} dev {dev}")
    if gw or gw6 or keepalive_extra:
        gw_keepalive(h, [x for x in (gw, gw6) if x] + list(keepalive_extra))
    if extra:
        h.sh(*extra)
    h.notes.append(", ".join(x for x in [ip, ip6, f"gw {gw}" if gw else None, mac] if x))
    nodes[name] = h
    return h


def gw_keepalive(h, gws, extra_cmds=()):
    """Real servers talk all the time; lab hosts are silent. A silent host's IP never reaches EVPN
    (the leaf learns IP<->MAC only from ARP/ND seen on its SVI), so ping the gateway every 20 s."""
    pings = "; ".join([f"ping -c1 -W1 {g} >/dev/null 2>&1" for g in gws] + list(extra_cmds))
    h.comment("keep the leaf's ARP/ND entry for this host fresh (see lab 05 README)")
    tag = f"lab-gw-keepalive-{h.name}"
    h.sh(f"pkill -f \"{tag} -c\" 2>/dev/null || true",
         f"setsid -f bash -c 'exec -a {tag} bash -c \"while true; do {pings}; sleep 20; done\"' </dev/null >/dev/null 2>&1")


def isis(n, ifaces, sysid, lo=True, ipv6=False, ipv4=True, area="49.0001", passive_lo=True, name="1"):
    for i in ifaces:
        lines = []
        if ipv4:
            lines.append(f"ip router isis {name}")
        if ipv6:
            lines.append(f"ipv6 router isis {name}")
        lines.append("isis network point-to-point")
        n.frr.iface(i, *lines)
    if lo:
        lines = []
        if ipv4:
            lines.append(f"ip router isis {name}")
        if ipv6:
            lines.append(f"ipv6 router isis {name}")
        if passive_lo:
            lines.append("isis passive")
        n.frr.iface("lo", *lines)
    n.frr.block(f"""
        router isis {name}
         net {area}.0000.0000.{sysid:04d}.00
         is-type level-2-only
         lsp-gen-interval 1
         spf-interval 1
        exit""")


def ospf(n, ifaces, rid, area=0, lo=True):
    for i in ifaces:
        n.frr.iface(i, f"ip ospf area {area}", "ip ospf network point-to-point")
    if lo:
        n.frr.iface("lo", f"ip ospf area {area}", "ip ospf passive")
    n.frr.block(f"""
        router ospf
         ospf router-id {rid}
        exit""")


def evpn_leaf_ibgp(n, asn, rid, rrs, extra_evpn=(), vni_lines=None):
    b = n.frr.bgp(asn, rid)
    b.g("no bgp default ipv4-unicast",
        "neighbor RR peer-group",
        f"neighbor RR remote-as {asn}",
        "neighbor RR update-source lo")
    for r in rrs:
        b.g(f"neighbor {r} peer-group RR")
    b.af("l2vpn evpn", "neighbor RR activate", "advertise-all-vni", *extra_evpn)
    if vni_lines:
        for vni, lines in vni_lines.items():
            b.af("l2vpn evpn", f"vni {vni}", *[" " + l for l in lines], "exit-vni")
    return b


def evpn_rr_ibgp(n, asn, rid, clients, extra=()):
    b = n.frr.bgp(asn, rid)
    b.g("no bgp default ipv4-unicast",
        f"bgp cluster-id {rid}",
        "neighbor LEAVES peer-group",
        f"neighbor LEAVES remote-as {asn}",
        "neighbor LEAVES update-source lo")
    for c in clients:
        b.g(f"neighbor {c} peer-group LEAVES")
    b.af("l2vpn evpn", "neighbor LEAVES activate", "neighbor LEAVES route-reflector-client", *extra)
    return b


def vrf_evpn(n, asn, rid, vrf, extra_v4=(), extra_evpn=(), adv=True, connected=True):
    b = n.frr.bgp(asn, rid, vrf)
    if connected:
        b.af("ipv4 unicast", "redistribute connected", *extra_v4)
    elif extra_v4:
        b.af("ipv4 unicast", *extra_v4)
    if adv:
        b.af("l2vpn evpn", "advertise ipv4 unicast", *extra_evpn)
    elif extra_evpn:
        b.af("l2vpn evpn", *extra_evpn)
    return b


def l2_services(l, i, services, suppress=True, mac=None, local=None):
    """services: list of (vlan, vni, [access ports])"""
    bridge(l, mac or leaf_mac(i))
    for vlan, vni, ports in services:
        vxlan(l, vni, vlan, local or leaf_lo(i), suppress)
        for p in ports:
            access_port(l, p, vlan)


# Standard address plan (same as the videos):
#   leafN  loopback N.N.N.N         spineM loopback (10+M)x4 -> 11.11.11.11
#   leafN eth(10+M) <-> spineM ethN :  10.N.(10+M).N/24 <-> 10.N.(10+M).(10+M)/24
def leaf_lo(i):
    return f"{i}.{i}.{i}.{i}"


def spine_lo(m):
    s = 10 + m
    return f"{s}.{s}.{s}.{s}"


def leaf_mac(i):
    return f"44:38:39:ff:00:{i:02x}"


def std_fabric(lab, nodes, n_spines, leaves, underlay="isis", spine_names=None, leaf_ids=None):
    """Create spines+leaves, p2p addressing, loopbacks and IGP. Returns (spines, leaves) dicts."""
    spines = OrderedDict()
    lv = OrderedDict()
    for m in range(1, n_spines + 1):
        s = Node(f"spine{m}", "router", "spine")
        loopback(s, spine_lo(m))
        nodes[s.name] = s
        spines[m] = s
    for i in leaves:
        l = Node(f"leaf{i}", "router", "leaf")
        loopback(l, leaf_lo(i))
        nodes[l.name] = l
        lv[i] = l
    for m, s in spines.items():
        s.comment("fabric links to leaves")
        for i, l in lv.items():
            sif, lif = f"eth{i}", f"eth{10 + m}"
            if lab is not None and (s.name, sif, l.name, lif) not in lab.links:
                lab.link(s.name, sif, l.name, lif)
            addr(s, sif, f"10.{i}.{10 + m}.{10 + m}/24")
    for i, l in lv.items():
        l.comment("uplinks to spines")
        for m in spines:
            addr(l, f"eth{10 + m}", f"10.{i}.{10 + m}.{i}/24")
    if underlay == "isis":
        for m, s in spines.items():
            isis(s, [f"eth{i}" for i in lv], 10 + m)
        for i, l in lv.items():
            isis(l, [f"eth{10 + m}" for m in spines], i)
    elif underlay == "ospf":
        for m, s in spines.items():
            ospf(s, [f"eth{i}" for i in lv], spine_lo(m))
        for i, l in lv.items():
            ospf(l, [f"eth{10 + m}" for m in spines], leaf_lo(i))
    return spines, lv


def std_overlay(spines, leaves, asn=65000):
    for m, s in spines.items():
        evpn_rr_ibgp(s, asn, spine_lo(m), [leaf_lo(i) for i in leaves])


def leaf_overlay(l, i, spines, asn=65000, extra_evpn=(), vni_lines=None):
    return evpn_leaf_ibgp(l, asn, leaf_lo(i), [spine_lo(m) for m in spines], extra_evpn, vni_lines)


# --------------------------------------------------------------------------
# Emission
# --------------------------------------------------------------------------
NODE_SCRIPT = """#!/bin/bash
# =====================================================================
# EVPN lab {num:02d} - {title}
# node: {node}   role: {role}   variant: {variant}
# Generated file. Apply on the VM as root:   bash {node}.sh
# (tools/gns3_lab.py push ... does this for you over the console)
# =====================================================================
set -e
install -d /etc/lab
echo "{lab}/{variant}/{node}" > /etc/lab/id
echo "{kind}" > /etc/lab/kind

# ---------------------------------------------------------------------
# 1) Linux data plane  ->  /etc/lab/net.sh  (re-run at every boot)
# ---------------------------------------------------------------------
cat > /etc/lab/net.sh <<'__LAB_NET__'
#!/bin/bash
# Linux networking for {node} (lab {num:02d}, variant {variant})
lab-reset          # remove everything a previous lab created
set -x
{net}
__LAB_NET__
chmod +x /etc/lab/net.sh
{frr_part}{files_part}
# ---------------------------------------------------------------------
# 3) apply: hostname, run net.sh, (re)start or stop FRR
# ---------------------------------------------------------------------
lab-apply {node}
"""

FRR_PART = """
# ---------------------------------------------------------------------
# 2) FRR control plane  ->  /etc/frr/frr.conf
# ---------------------------------------------------------------------
cat > /etc/frr/frr.conf <<'__LAB_FRR__'
{frr}__LAB_FRR__
"""

FRR_NONE = """
# 2) this node does not run FRR (plain Linux host)
"""


def render_files(n):
    if not n.files:
        return ""
    out = ["", "# ---------------------------------------------------------------------",
           "# helper files used in this lab", "# ---------------------------------------------------------------------"]
    for path, (content, mode) in n.files.items():
        out.append(f"install -d $(dirname {path})")
        out.append(f"cat > {path} <<'__LAB_FILE__'")
        out.append(dedent(content))
        out.append("__LAB_FILE__")
        out.append(f"chmod {mode} {path}")
    return "\n".join(out) + "\n"


def layout(lab, nodes):
    rows = {"super": 0, "dci": 0, "spine": 1, "leaf": 2, "border": 2, "fw": 3, "ext": 3, "host": 3, "exthost": 4}
    groups = OrderedDict()
    for n in nodes.values():
        r = lab.positions.get(n.name, {}).get("row", rows.get(n.role, 3))
        groups.setdefault(r, []).append(n.name)
    pos = {}
    for r, names in groups.items():
        w = (len(names) - 1) * 160
        for k, name in enumerate(names):
            p = lab.positions.get(name, {})
            pos[name] = {"x": p.get("x", -w // 2 + k * 160), "y": p.get("y", -300 + r * 170)}
    return pos


def emit(lab, root):
    d = os.path.join(root, "labs", lab.dirname)
    os.makedirs(d, exist_ok=True)
    # union of nodes over variants (topology is the same for all variants)
    allnodes = OrderedDict()
    for v in lab.variants.values():
        for k, n in v["nodes"].items():
            allnodes.setdefault(k, n)
    used = set()
    for a, ai, b, bi in lab.links:
        for nm, i in ((a, ai), (b, bi)):
            assert nm in allnodes, f"{lab.dirname}: link to unknown node {nm}"
            key = (nm, i)
            assert key not in used, f"{lab.dirname}: interface used twice {key}"
            used.add(key)
            num = int(i[3:])
            assert num < allnodes[nm].adapters, f"{lab.dirname}: {nm} {i} >= adapters"
    pos = layout(lab, allnodes)
    topo = {
        "lab": lab.dirname,
        "title": lab.title,
        "project": f"evpn-{lab.dirname}",
        "video": YT + lab.video,
        "variants": {k: v["desc"] for k, v in lab.variants.items()},
        "default_variant": lab.default_variant,
        "nodes": [{"name": n.name, "kind": n.kind, "role": n.role, "adapters": n.adapters,
                   "ram": n.ram, **pos[n.name]} for n in allnodes.values()],
        "links": [list(l) for l in lab.links],
        "checks": lab.checks,
    }
    with open(os.path.join(d, "topology.json"), "w") as f:
        json.dump(topo, f, indent=1)
    for vname, v in lab.variants.items():
        vd = os.path.join(d, "nodes", vname)
        os.makedirs(vd, exist_ok=True)
        for n in v["nodes"].values():
            frr_part = FRR_PART.format(frr=n.frr.render()) if n.kind == "router" else FRR_NONE
            txt = NODE_SCRIPT.format(num=lab.num, title=lab.title, node=n.name, role=n.role,
                                     variant=vname, lab=lab.dirname, kind=n.kind,
                                     net=n.render_net().rstrip("\n"), frr_part=frr_part,
                                     files_part=render_files(n))
            with open(os.path.join(vd, n.name + ".sh"), "w", newline="\n") as f:
                f.write(txt)
    for rel, content in lab.extra_files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", newline="\n") as f:
            f.write(dedent(content) + "\n")
    with open(os.path.join(d, "README.md"), "w", newline="\n") as f:
        f.write(render_readme(lab, allnodes))


def render_readme(lab, allnodes):
    v0 = lab.variants[lab.default_variant]["nodes"]
    out = [f"# Lab {lab.num:02d} - {lab.title}", ""]
    out.append(f"**Video:** [{lab.title}]({YT}{lab.video}) ({lab.minutes}) - part of the "
               f"[Sneaky Subnet EVPN playlist]({PLAYLIST})  ")
    if lab.ref:
        out.append(f"**Author's original (Arista cEOS / containerlab) config:** {REF_REPO}{lab.ref}  ")
    out.append("")
    out.append(lab.summary.strip())
    out.append("")
    if lab.diagram:
        out += ["## Topology", "", "```", dedent(lab.diagram), "```", ""]
    out += ["### Nodes", "", "| Node | Role | Loopback / addressing |", "|---|---|---|"]
    for n in allnodes.values():
        info = n.lo4 or ""
        if n.lo6:
            info = (info + " " + n.lo6).strip()
        if n.notes:
            info = (info + " " + "; ".join(n.notes)).strip()
        out.append(f"| {n.name} | {n.role} | {info} |")
    out += ["", "### Links", "", "| A | | B | |", "|---|---|---|---|"]
    for a, ai, b, bi in lab.links:
        out.append(f"| {a} | {ai} | {b} | {bi} |")
    out.append("")
    if len(lab.variants) > 1:
        out += ["### Variants", "", "Each variant is a complete set of node scripts in `nodes/<variant>/`. "
                "Same GNS3 topology, just push a different variant.", ""]
        for k, v in lab.variants.items():
            mark = " *(default)*" if k == lab.default_variant else ""
            out.append(f"- **{k}**{mark} - {v['desc']}")
        out.append("")
    out += ["## Run it", "", "```powershell",
            f"cd evpn",
            f"python tools\\gns3_lab.py up labs\\{lab.dirname}" +
            ("" if len(lab.variants) == 1 else f"   # default variant: {lab.default_variant}"),
            ]
    if len(lab.variants) > 1:
        other = [k for k in lab.variants if k != lab.default_variant][0]
        out.append(f"python tools\\gns3_lab.py push labs\\{lab.dirname} --variant {other}   # switch variant in place")
    out += [f"python tools\\gns3_lab.py check labs\\{lab.dirname}", "```", "",
            "Or by hand: open each node's console in GNS3 and run its script from "
            f"`nodes/{lab.default_variant}/` (see the top-level README).", ""]
    out.append(lab.readme.strip())
    out.append("")
    if lab.checks:
        out += ["## Automated checks", "", "`gns3_lab.py check` runs these and compares against the regex:", ""]
        for v, cl in lab.checks.items():
            out.append(f"*variant {v}*")
            out.append("")
            out += ["| node | command | expect |", "|---|---|---|"]
            for c in cl:
                cmd = c["cmd"].replace("|", "\\|")
                exp = c["expect"].replace("|", "\\|")
                out.append(f"| {c['node']} | `{cmd}` | `{exp}` |")
            out.append("")
    return "\n".join(out) + "\n"
