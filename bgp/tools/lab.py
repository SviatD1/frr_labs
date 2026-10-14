#!/usr/bin/env python3
"""
lab.py - build the BGP/FRR labs in GNS3 2.2 through its REST API (v2).

Requirements:  Python 3.8+  and  `pip install pycdlib`

Commands
  python lab.py check                          test the connection, list computes and templates
  python lab.py prep --image <debian.qcow2>    one-time: build the FRR base image inside GNS3
  python lab.py templates                      one-time: create the frr-router / frr-host templates
  python lab.py build <lab-folder> [--no-start] [--force]
                                               create the GNS3 project for one lab and start it
  python lab.py iso <lab-folder>               only write the cloud-init ISOs to <lab-folder>/iso/
  python lab.py delete <lab-folder>            delete the lab's GNS3 project

Common options
  --server http://127.0.0.1:3080   GNS3 controller (the GNS3 GUI's local server)
  --user / --password              only if you enabled authentication in GNS3
  --compute vm|local               where QEMU runs (default: "vm" if a GNS3 VM exists, else "local")
  --router-template frr-router --host-template frr-host

How it works: every node gets a small NoCloud cloud-init CD-ROM (volume label "cidata") whose
user-data is that node's nodes/<NODE>.sh script. On first boot cloud-init runs it: hostname,
interface addresses (/etc/lab/net.sh) and /etc/frr/frr.conf. See SETUP.md.
"""
import argparse, base64, io, json, os, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASE_IMAGE = "frr-base.qcow2"

# --------------------------------------------------------------------------- REST helper


class GNS3:
    def __init__(self, server, user=None, password=None):
        self.base = server.rstrip("/") + "/v2"
        self.auth = None
        if user:
            self.auth = "Basic " + base64.b64encode(f"{user}:{password or ''}".encode()).decode()

    def req(self, method, path, body=None, raw=None, ctype="application/json", timeout=600):
        data = None
        if raw is not None:
            data = raw
        elif body is not None:
            data = json.dumps(body).encode()
        r = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            r.add_header("Content-Type", ctype)
        if self.auth:
            r.add_header("Authorization", self.auth)
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                txt = resp.read()
                return json.loads(txt) if txt else None
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            raise SystemExit(f"GNS3 API error {e.code} on {method} {path}:\n{msg}")
        except urllib.error.URLError as e:
            raise SystemExit(f"Cannot reach GNS3 at {self.base}: {e.reason}\n"
                             "Is the GNS3 GUI running? Check Edit > Preferences > Server for host/port.")

    get = lambda s, p: s.req("GET", p)
    post = lambda s, p, b=None: s.req("POST", p, b if b is not None else {})
    put = lambda s, p, b: s.req("PUT", p, b)
    delete = lambda s, p: s.req("DELETE", p)

    def upload_image(self, compute, filename, data):
        q = urllib.parse.quote(filename)
        return self.req("POST", f"/computes/{compute}/qemu/images/{q}", raw=data,
                        ctype="application/octet-stream", timeout=3600)

    def images(self, compute):
        return [i["filename"] for i in self.get(f"/computes/{compute}/qemu/images") or []]


def pick_compute(api, wanted):
    comps = api.get("/computes")
    ids = [c["compute_id"] for c in comps]
    if wanted:
        if wanted not in ids:
            raise SystemExit(f"compute '{wanted}' not found; available: {ids}")
        return wanted
    for c in comps:
        if c["compute_id"] == "vm" and c.get("connected"):
            return "vm"
    if "vm" in ids:
        print("WARNING: GNS3 VM compute exists but is not connected; using 'local'.")
    return "local"


# --------------------------------------------------------------------------- cloud-init ISO


def make_iso(user_data: str, meta_data: str) -> bytes:
    try:
        import pycdlib
    except ImportError:
        raise SystemExit("pycdlib is missing: run  pip install pycdlib")
    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=3, joliet=3, rock_ridge="1.09", vol_ident="cidata")
    for name, txt in (("user-data", user_data), ("meta-data", meta_data)):
        b = txt.replace("\r\n", "\n").encode()
        iso.add_fp(io.BytesIO(b), len(b), "/" + name.upper().replace("-", "_") + ".;1",
                   rr_name=name, joliet_path="/" + name)
    out = io.BytesIO()
    iso.write_fp(out)
    iso.close()
    return out.getvalue()


def meta(instance_id, hostname):
    return f"instance-id: {instance_id}\nlocal-hostname: {hostname}\n"


PREP_USER_DATA = r"""#cloud-config
# One-time preparation of the FRR base image (see SETUP.md). Needs Internet (NAT node on eth0).
hostname: frr-base
disable_root: false
ssh_pwauth: true
chpasswd:
  expire: false
  users:
    - {name: root, password: lab, type: text}
package_update: true
packages: [frr, frr-pythontools, tcpdump, traceroute, mtr-tiny, iperf3, iputils-ping, iproute2,
           ethtool, netcat-openbsd, curl, nano, vim-tiny, bash-completion, less]
write_files:
  - path: /etc/systemd/system/lab-net.service
    content: |
      [Unit]
      Description=Lab interface configuration (/etc/lab/net.sh)
      After=systemd-udev-settle.service
      Wants=systemd-udev-settle.service
      Before=frr.service network-online.target
      ConditionPathExists=/etc/lab/net.sh
      [Service]
      Type=oneshot
      RemainAfterExit=yes
      ExecStartPre=-/bin/udevadm settle
      ExecStart=/bin/sh /etc/lab/net.sh
      [Install]
      WantedBy=multi-user.target
  - path: /etc/cloud/cloud.cfg.d/99-lab.cfg
    content: |
      network: {config: disabled}
      datasource_list: [NoCloud, None]
      ssh_pwauth: true
      disable_root: false
  - path: /etc/systemd/system/serial-getty@ttyS0.service.d/autologin.conf
    content: |
      [Service]
      ExecStart=
      ExecStart=-/sbin/agetty --autologin root --keep-baud 115200,57600,38400,9600 %I $TERM
  - path: /etc/default/grub.d/99-lab.cfg
    content: |
      GRUB_CMDLINE_LINUX="$GRUB_CMDLINE_LINUX net.ifnames=0 biosdevname=0"
      GRUB_TIMEOUT=1
  - path: /etc/ssh/sshd_config.d/99-lab.conf
    content: |
      PermitRootLogin yes
      PasswordAuthentication yes
  - path: /root/.bashrc.d-lab
    content: |
      alias v=vtysh
      alias sbs='vtysh -c "show bgp summary"'
runcmd:
  - sed -i 's/^bgpd=no/bgpd=yes/; s/^ospfd=no/ospfd=yes/; s/^bfdd=no/bfdd=yes/' /etc/frr/daemons
  - grep -q bashrc.d-lab /root/.bashrc || echo '. /root/.bashrc.d-lab' >> /root/.bashrc
  - update-grub
  - systemctl enable lab-net.service
  - systemctl disable systemd-networkd-wait-online.service || true
  - rm -f /etc/netplan/*.yaml /etc/network/interfaces.d/* || true
  - printf 'auto lo\niface lo inet loopback\n' > /etc/network/interfaces
  - rm -f /etc/frr/frr.conf.lab
  - cloud-init clean --logs --machine-id || cloud-init clean --logs
  - truncate -s 0 /etc/machine-id
  - sync
  - echo "=== FRR BASE IMAGE READY - powering off ==="
  - poweroff
"""


# --------------------------------------------------------------------------- lab model


def load_lab(folder):
    folder = os.path.abspath(folder)
    p = os.path.join(folder, "topology.json")
    if not os.path.exists(p):
        raise SystemExit(f"{p} not found (point me at a folder inside labs/)")
    topo = json.load(open(p, encoding="utf-8"))
    return folder, topo


def node_iso(folder, topo, name, stamp):
    script = open(os.path.join(folder, "nodes", f"{name}.sh"), encoding="utf-8").read()
    iid = f"{topo['lab']}-{name}-{stamp}"
    return make_iso(script, meta(iid, name))


def iso_name(topo, name):
    return f"bgp{topo['lab'][:2]}-{name}.iso"


# --------------------------------------------------------------------------- commands


def cmd_check(api, a):
    v = api.get("/version")
    print(f"GNS3 server version {v.get('version')}")
    for c in api.get("/computes"):
        print(f"  compute {c['compute_id']:<8} {c.get('name', ''):<20} connected={c.get('connected')}")
    print("Templates:")
    for t in api.get("/templates"):
        if t.get("template_type") in ("qemu", "nat"):
            print(f"  {t['name']:<24} {t['template_type']:<6} compute={t.get('compute_id')} image={t.get('hda_disk_image', '')}")
    comp = pick_compute(api, a.compute)
    imgs = api.images(comp)
    print(f"QEMU images on compute '{comp}': {', '.join(imgs) or '(none)'}")
    if BASE_IMAGE not in imgs:
        print(f"-> {BASE_IMAGE} not found yet: run  python lab.py prep --image <debian-13-genericcloud-amd64.qcow2>")


def find_project(api, name):
    for p in api.get("/projects"):
        if p["name"] == name:
            return p
    return None


def new_project(api, name, force):
    old = find_project(api, name)
    if old:
        if not force:
            raise SystemExit(f"GNS3 project '{name}' already exists. Use --force to delete and rebuild it, "
                             "or open it from File > Open project.")
        print(f"Deleting existing project {name}")
        if old.get("status") != "opened":
            api.post(f"/projects/{old['project_id']}/open")
        api.post(f"/projects/{old['project_id']}/nodes/stop")
        api.delete(f"/projects/{old['project_id']}")
    return api.post("/projects", {"name": name})


def cmd_prep(api, a):
    comp = pick_compute(api, a.compute)
    if not a.image or not os.path.exists(a.image):
        raise SystemExit("--image must point to the downloaded debian-13-genericcloud-amd64.qcow2")
    imgs = api.images(comp)
    if BASE_IMAGE in imgs and not a.force:
        raise SystemExit(f"{BASE_IMAGE} already exists on compute '{comp}'. Use --force to upload a fresh copy "
                         "(only needed if the preparation failed).")
    size = os.path.getsize(a.image) / 1e6
    print(f"Uploading {a.image} ({size:.0f} MB) to compute '{comp}' as {BASE_IMAGE} ... (can take a few minutes)")
    with open(a.image, "rb") as f:
        api.upload_image(comp, BASE_IMAGE, f.read())
    api.upload_image(comp, "frr-prep-seed.iso", make_iso(PREP_USER_DATA, meta(f"frr-prep-{int(time.time())}", "frr-base")))
    prj = new_project(api, "bgp-00-image-prep", True)
    pid = prj["project_id"]
    vm = api.post(f"/projects/{pid}/nodes", {
        "name": "frr-base-prep", "node_type": "qemu", "compute_id": comp, "x": 0, "y": 0,
        "console_type": "telnet",
        "properties": {"hda_disk_image": BASE_IMAGE, "cdrom_image": "frr-prep-seed.iso", "linked_clone": False,
                       "ram": 1024, "cpus": 1, "adapters": 1, "adapter_type": "virtio-net-pci",
                       "platform": "x86_64", "hda_disk_interface": "virtio", "boot_priority": "c"}})
    nat = api.post(f"/projects/{pid}/nodes", {"name": "NAT", "node_type": "nat", "compute_id": comp, "x": -250, "y": 0})
    api.post(f"/projects/{pid}/links", {"nodes": [
        {"node_id": vm["node_id"], "adapter_number": 0, "port_number": 0},
        {"node_id": nat["node_id"], "adapter_number": 0, "port_number": 0}]})
    api.post(f"/projects/{pid}/nodes/start")
    print("Started project 'bgp-00-image-prep'. Open it in GNS3 and watch the console of frr-base-prep.\n"
          "It installs FRR from the Internet and powers itself off when done (5-15 minutes).\n"
          "Waiting for the VM to stop ... (Ctrl-C is safe; you can run `python lab.py templates` later)")
    t0 = time.time()
    while time.time() - t0 < 3600:
        time.sleep(15)
        st = api.get(f"/projects/{pid}/nodes/{vm['node_id']}")["status"]
        print(f"  {int(time.time() - t0):>5}s  status={st}")
        if st == "stopped":
            print("Base image ready. Next:  python lab.py templates")
            api.post(f"/projects/{pid}/close")
            return
    print("Still running after 60 minutes - check the console for errors.")


def cmd_templates(api, a):
    comp = pick_compute(api, a.compute)
    existing = {t["name"]: t for t in api.get("/templates")}
    for name, ram, symbol, cat in ((a.router_template, 384, ":/symbols/router.svg", "router"),
                                   (a.host_template, 320, ":/symbols/computer.svg", "guest")):
        if name in existing:
            if not a.force:
                print(f"template {name} exists (use --force to recreate)")
                continue
            api.delete(f"/templates/{existing[name]['template_id']}")
        api.post("/templates", {
            "name": name, "template_type": "qemu", "compute_id": comp, "category": cat, "symbol": symbol,
            "hda_disk_image": BASE_IMAGE, "hda_disk_interface": "virtio", "ram": ram, "cpus": 1,
            "adapters": 8, "adapter_type": "virtio-net-pci", "console_type": "telnet", "platform": "x86_64",
            "linked_clone": True, "default_name_format": "{name}-{0}"})
        print(f"created template {name}")


def cmd_iso(api, a):
    folder, topo = load_lab(a.lab)
    os.makedirs(os.path.join(folder, "iso"), exist_ok=True)
    stamp = int(time.time())
    for name in topo["nodes"]:
        p = os.path.join(folder, "iso", iso_name(topo, name))
        open(p, "wb").write(node_iso(folder, topo, name, stamp))
        print("wrote", p)


def cmd_build(api, a):
    folder, topo = load_lab(a.lab)
    comp = pick_compute(api, a.compute)
    tmpl = {t["name"]: t for t in api.get("/templates")}
    for t in (a.router_template, a.host_template):
        if t not in tmpl:
            raise SystemExit(f"template '{t}' not found. Run `python lab.py templates` first (see SETUP.md).")
    pname = "bgp-" + topo["lab"]
    stamp = int(time.time())
    print(f"Uploading cloud-init ISOs for {len(topo['nodes'])} nodes to compute '{comp}' ...")
    for name in topo["nodes"]:
        api.upload_image(comp, iso_name(topo, name), node_iso(folder, topo, name, stamp))
    prj = new_project(api, pname, a.force)
    pid = prj["project_id"]
    ids = {}
    for name, n in topo["nodes"].items():
        t = tmpl[a.router_template if n["kind"] == "router" else a.host_template]
        node = api.post(f"/projects/{pid}/templates/{t['template_id']}",
                        {"x": int(n["x"]) - 30, "y": int(n["y"]) - 30, "compute_id": comp})
        props = {"adapters": max(1, int(n["adapters"])), "cdrom_image": iso_name(topo, name)}
        node = api.put(f"/projects/{pid}/nodes/{node['node_id']}", {"name": name, "properties": props})
        ids[name] = node["node_id"]
        print(f"  node {name:<4} ({n['kind']}, {props['adapters']} NICs)")
    for l in topo["links"]:
        ia, ib = int(l["a_iface"][3:]), int(l["b_iface"][3:])
        api.post(f"/projects/{pid}/links", {"nodes": [
            {"node_id": ids[l["a"]], "adapter_number": ia, "port_number": 0,
             "label": {"text": l["a_iface"], "x": 10, "y": -10}},
            {"node_id": ids[l["b"]], "adapter_number": ib, "port_number": 0,
             "label": {"text": l["b_iface"], "x": 10, "y": -10}}]})
        print(f"  link {l['a']} {l['a_iface']} <-> {l['b']} {l['b_iface']}  ({l['subnet']})")
    # a text note with the lab title
    api.post(f"/projects/{pid}/drawings", {
        "x": -300, "y": -260,
        "svg": f'<svg height="40" width="800"><text font-family="monospace" font-size="16" font-weight="bold">'
               f'Lab {topo["lab"]} - {xml_escape(topo["title"])}</text></svg>'})
    if not a.no_start:
        api.post(f"/projects/{pid}/nodes/start")
        print("Nodes started. Give them ~60-90 s to boot and apply their config.")
    print(f"Done: project '{pname}'. In GNS3 use File > Open project if it is not shown yet.")


def xml_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cmd_delete(api, a):
    folder, topo = load_lab(a.lab)
    p = find_project(api, "bgp-" + topo["lab"])
    if not p:
        print("no such project")
        return
    if p.get("status") != "opened":
        api.post(f"/projects/{p['project_id']}/open")
    api.post(f"/projects/{p['project_id']}/nodes/stop")
    api.delete(f"/projects/{p['project_id']}")
    print("deleted", p["name"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["check", "prep", "templates", "build", "iso", "delete"])
    ap.add_argument("lab", nargs="?", help="lab folder (for build/iso/delete)")
    ap.add_argument("--server", default=os.environ.get("GNS3_SERVER", "http://127.0.0.1:3080"))
    ap.add_argument("--user"); ap.add_argument("--password")
    ap.add_argument("--compute", help="compute id: vm or local (default: auto)")
    ap.add_argument("--image", help="prep: path to debian-13-genericcloud-amd64.qcow2")
    ap.add_argument("--router-template", default="frr-router")
    ap.add_argument("--host-template", default="frr-host")
    ap.add_argument("--no-start", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.command in ("build", "iso", "delete") and not a.lab:
        ap.error(f"{a.command} needs a lab folder, e.g. labs/01-what-is-bgp (or . inside it)")
    api = GNS3(a.server, a.user, a.password)
    {"check": cmd_check, "prep": cmd_prep, "templates": cmd_templates, "build": cmd_build,
     "iso": cmd_iso, "delete": cmd_delete}[a.command](api, a)


if __name__ == "__main__":
    main()
