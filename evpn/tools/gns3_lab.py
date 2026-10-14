#!/usr/bin/env python3
"""
gns3_lab.py - build, configure and check the EVPN labs on a GNS3 server.

Pure Python 3 standard library (works on Windows, macOS, Linux).

  python tools/gns3_lab.py templates                        # list GNS3 templates
  python tools/gns3_lab.py up      labs/02-basic-bridging   # build + start + push config + check
  python tools/gns3_lab.py build   labs/02-basic-bridging   # create project, nodes, links
  python tools/gns3_lab.py start   labs/02-basic-bridging
  python tools/gns3_lab.py push    labs/05-basic-routing-irb --variant asymmetric [--nodes leaf1,leaf2]
  python tools/gns3_lab.py check   labs/05-basic-routing-irb --variant asymmetric
  python tools/gns3_lab.py exec    labs/02-basic-bridging leaf1 "vtysh -c 'show evpn vni'"
  python tools/gns3_lab.py stop    labs/02-basic-bridging
  python tools/gns3_lab.py delete  labs/02-basic-bridging
  python tools/gns3_lab.py run-script --project evpn-base --node base base-image/build-base.sh

Server/credentials: --server http://HOST:3080 --user U --password P, or env GNS3_SERVER/GNS3_USER/
GNS3_PASSWORD. If nothing is given the local GNS3 GUI's gns3_server.ini/.conf is read automatically.
"""
import argparse
import base64
import configparser
import hashlib
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

DEFAULT_TEMPLATE = "debian-frr"
PROMPT = "LABSHELL# "


# --------------------------------------------------------------------------
# GNS3 REST API
# --------------------------------------------------------------------------
def find_local_server_config():
    """Look for the GNS3 GUI's local server config (host/port/user/password)."""
    cands = []
    appdata = os.environ.get("APPDATA")
    home = os.path.expanduser("~")
    for base in filter(None, [appdata and os.path.join(appdata, "GNS3"), os.path.join(home, ".config", "GNS3"),
                              os.path.join(home, "Library", "Application Support", "GNS3")]):
        if os.path.isdir(base):
            for ver in sorted(os.listdir(base), reverse=True):
                for fn in ("gns3_server.ini", "gns3_server.conf"):
                    p = os.path.join(base, ver, fn)
                    if os.path.isfile(p):
                        cands.append(p)
    for p in cands:
        cp = configparser.ConfigParser()
        try:
            cp.read(p, encoding="utf-8")
        except Exception:
            continue
        if cp.has_section("Server"):
            s = cp["Server"]
            host = s.get("host", "127.0.0.1")
            if host in ("0.0.0.0", "::", ""):
                host = "127.0.0.1"
            return {"server": f"http://{host}:{s.get('port', '3080')}",
                    "user": s.get("user", ""), "password": s.get("password", ""),
                    "auth": s.get("auth", "false").lower() == "true", "file": p}
    return None


class Gns3:
    def __init__(self, server, user=None, password=None):
        self.server = server.rstrip("/")
        self.user, self.password = user, password
        self.token = None
        self.ver = None
        self._detect()

    def _req(self, method, path, body=None, raw=False, quiet=False):
        url = self.server + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        elif self.user:
            req.add_header("Authorization", "Basic " + base64.b64encode(f"{self.user}:{self.password}".encode()).decode())
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                txt = r.read().decode() if r.length != 0 else ""
                return txt if raw else (json.loads(txt) if txt else None)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if quiet:
                raise
            raise SystemExit(f"GNS3 API error {e.code} on {method} {path}: {msg[:500]}")
        except urllib.error.URLError as e:
            raise SystemExit(f"Cannot reach GNS3 server at {self.server}: {e.reason}\n"
                             "Is GNS3 running? Use --server http://HOST:PORT (and --user/--password).")

    def _detect(self):
        for v in ("v3", "v2"):
            try:
                info = self._req("GET", f"/{v}/version", quiet=True)
                self.ver = v
                break
            except urllib.error.HTTPError as e:
                if e.code == 401 and v == "v2":
                    raise SystemExit("GNS3 server requires authentication: pass --user/--password "
                                     "(see gns3_server.ini, section [Server]).")
                continue
            except SystemExit:
                raise
        if not self.ver:
            raise SystemExit("Could not talk to the GNS3 server API (tried /v3 and /v2).")
        if self.ver == "v3":
            user = self.user or "admin"
            pw = self.password or "admin"
            try:
                r = self._req("POST", "/v3/access/users/authenticate", {"username": user, "password": pw}, quiet=True)
                self.token = r["access_token"]
            except urllib.error.HTTPError:
                raise SystemExit("GNS3 v3 login failed - pass --user/--password")
        self.p = "/" + self.ver

    # helpers
    def get(self, path):
        return self._req("GET", self.p + path)

    def post(self, path, body=None):
        return self._req("POST", self.p + path, body if body is not None else {})

    def put(self, path, body):
        return self._req("PUT", self.p + path, body)

    def delete(self, path):
        return self._req("DELETE", self.p + path)

    def templates(self):
        return self.get("/templates")

    def template_by_name(self, name):
        for t in self.templates():
            if t["name"] == name:
                return t
        raise SystemExit(f"GNS3 template '{name}' not found. Create it first (see base-image/README.md) "
                         f"or pass --template. Existing: {', '.join(t['name'] for t in self.templates())}")

    def project_by_name(self, name):
        for p in self.get("/projects"):
            if p["name"] == name:
                return p
        return None

    def open_project(self, p):
        if p.get("status") != "opened":
            self.post(f"/projects/{p['project_id']}/open")
        return p

    def nodes(self, pid):
        return {n["name"]: n for n in self.get(f"/projects/{pid}/nodes")}


# --------------------------------------------------------------------------
# Serial console over telnet
# --------------------------------------------------------------------------
IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240


class Console:
    def __init__(self, host, port, name="", verbose=False, retry=120):
        self.host, self.port, self.name, self.verbose = host, port, name, verbose
        end = time.time() + retry
        while True:
            try:
                self.sock = socket.create_connection((host, port), timeout=15)
                break
            except OSError as e:
                if time.time() > end:
                    raise ConnectionError(f"{name}: cannot connect to console {host}:{port} ({e})")
                time.sleep(3)
        self.sock.settimeout(0.3)
        self.buf = ""

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass

    def _read(self):
        try:
            data = self.sock.recv(65536)
        except socket.timeout:
            return ""
        if not data:
            raise ConnectionError(f"{self.name}: console connection closed")
        out = bytearray()
        i = 0
        while i < len(data):
            b = data[i]
            if b == IAC and i + 1 < len(data):
                cmd = data[i + 1]
                if cmd in (DO, DONT, WILL, WONT) and i + 2 < len(data):
                    opt = data[i + 2]
                    if cmd == DO:
                        self.sock.sendall(bytes([IAC, WONT, opt]))
                    elif cmd == WILL:
                        self.sock.sendall(bytes([IAC, DO if opt in (1, 3, 0) else DONT, opt]))
                    i += 3
                    continue
                if cmd == SB:
                    j = data.find(bytes([IAC, SE]), i)
                    i = j + 2 if j >= 0 else len(data)
                    continue
                if cmd == IAC:
                    out.append(IAC)
                i += 2
                continue
            out.append(b)
            i += 1
        txt = out.decode("utf-8", errors="replace")
        if self.verbose and txt:
            sys.stdout.write(txt)
            sys.stdout.flush()
        return txt

    def send(self, s):
        self.sock.sendall(s.encode())

    def expect(self, pattern, timeout=30):
        rx = re.compile(pattern)
        end = time.time() + timeout
        while True:
            m = rx.search(self.buf)
            if m:
                out = self.buf[:m.end()]
                self.buf = self.buf[m.end():]
                return m, out
            if time.time() > end:
                return None, self.buf
            self.buf += self._read()

    def drain(self, secs=0.5):
        end = time.time() + secs
        while time.time() < end:
            self.buf += self._read()
        self.buf = ""

    def login(self, password=None, boot_timeout=300):
        """Get a root shell with a predictable prompt."""
        end = time.time() + boot_timeout
        while time.time() < end:
            self.send("\r")
            m, _ = self.expect(r"(login:\s*$|Password:\s*$|[#$]\s*$|" + re.escape(PROMPT.strip()) + ")", timeout=5)
            if not m:
                continue
            s = m.group(1)
            if s.startswith("login"):
                self.send("root\r")
                continue
            if s.startswith("Password"):
                self.send((password or "") + "\r")
                continue
            break
        else:
            raise TimeoutError(f"{self.name}: no shell prompt on the console after {boot_timeout}s")
        init = (f"export PS1='{PROMPT}' TERM=dumb VTYSH_PAGER=cat PAGER=cat SYSTEMD_PAGER=; "
                "stty -echo cols 2000 2>/dev/null; dmesg -n 1 2>/dev/null; "
                "bind 'set enable-bracketed-paste off' 2>/dev/null\r")
        self.send(init)
        self.expect(re.escape(PROMPT), 20)
        self.drain(0.5)
        self.send("\r")
        m, _ = self.expect(re.escape(PROMPT), 20)
        if not m:
            raise TimeoutError(f"{self.name}: could not set up the shell prompt")
        self.drain(0.3)

    def run(self, cmd, timeout=60):
        """Run a command, return (rc, output)."""
        self.buf = ""
        self.send(f"printf '%s\\n' '__BEG''IN__'; {cmd}; printf '__E''ND__%s\\n' \"$?\"\r")
        m, out = self.expect(r"__END__(\d+)", timeout)
        if not m:
            return None, out
        txt = out
        b = txt.find("__BEGIN__")
        body = txt[b + len("__BEGIN__"):m.start()] if b >= 0 else txt[:m.start()]
        body = body.replace("\r", "")
        return int(m.group(1)), body.strip("\n")

    def put_file(self, content, remote, chunk=400):
        data = content.encode()
        b64 = base64.b64encode(data).decode()
        md5 = hashlib.md5(data).hexdigest()
        for attempt in range(3):
            self.run("rm -f /tmp/.lab.b64", 10)
            for i in range(0, len(b64), chunk):
                rc, _ = self.run(f"echo -n '{b64[i:i + chunk]}' >> /tmp/.lab.b64", 20)
                if rc is None:
                    break
            rc, out = self.run(f"base64 -d /tmp/.lab.b64 > {remote} && md5sum {remote}", 20)
            if rc == 0 and md5 in out:
                return True
        raise IOError(f"{self.name}: file transfer to {remote} failed checksum 3 times")


# --------------------------------------------------------------------------
# Lab helpers
# --------------------------------------------------------------------------
def load_topo(labdir):
    p = os.path.join(labdir, "topology.json")
    if not os.path.isfile(p):
        raise SystemExit(f"{p} not found - pass a lab folder, e.g. labs/02-basic-bridging")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def console_endpoint(g, node):
    host = node.get("console_host") or ""
    if host in ("0.0.0.0", "::", "", "localhost"):
        host = re.sub(r"^https?://", "", g.server).split(":")[0]
        if host.startswith("["):
            host = host.strip("[]")
    return host, node["console"]


def get_project(g, topo, must=True):
    p = g.project_by_name(topo["project"])
    if not p and must:
        raise SystemExit(f"GNS3 project {topo['project']} does not exist - run 'build' first.")
    if p:
        g.open_project(p)
    return p


def cmd_templates(g, a):
    for t in g.templates():
        print(f"{t['name']:30s} {t.get('template_type', ''):12s} compute={t.get('compute_id')}")


def cmd_build(g, a):
    topo = load_topo(a.lab)
    p = g.project_by_name(topo["project"])
    if p:
        if not a.force:
            print(f"project {topo['project']} already exists (use --force to recreate)")
            return
        g.open_project(p)
        g.delete(f"/projects/{p['project_id']}")
    p = g.post("/projects", {"name": topo["project"]})
    pid = p["project_id"]
    rt = g.template_by_name(a.template)
    ht = g.template_by_name(a.host_template or a.template)
    print(f"project {topo['project']} ({pid}) - router template '{rt['name']}', host template '{ht['name']}'")
    ids = {}
    for n in topo["nodes"]:
        t = rt if n["kind"] == "router" else ht
        body = {"x": int(n["x"]), "y": int(n["y"])}
        comp = a.compute or t.get("compute_id")
        if comp:
            body["compute_id"] = comp
        node = g.post(f"/projects/{pid}/templates/{t['template_id']}", body)
        upd = {"name": n["name"], "port_name_format": "eth{0}",
               "properties": {"adapters": max(n["adapters"], 1)}}
        if not a.keep_ram:
            upd["properties"]["ram"] = n["ram"]
        node = g.put(f"/projects/{pid}/nodes/{node['node_id']}", upd)
        ids[n["name"]] = node["node_id"]
        print(f"  node {n['name']:10s} adapters={n['adapters']} ram={n['ram']}")
    for (a1, i1, b1, j1) in topo["links"]:
        body = {"nodes": [{"node_id": ids[a1], "adapter_number": int(i1[3:]), "port_number": 0},
                          {"node_id": ids[b1], "adapter_number": int(j1[3:]), "port_number": 0}]}
        g.post(f"/projects/{pid}/links", body)
        print(f"  link {a1}:{i1} <-> {b1}:{j1}")
    title = topo["title"]
    try:
        g.post(f"/projects/{pid}/drawings", {"x": -400, "y": -470, "svg":
               f'<svg height="30" width="900"><text font-family="Arial" font-size="18" font-weight="bold">'
               f'Lab {topo["lab"]} - {title.replace("&", "and").replace("<", "")}</text></svg>'})
    except SystemExit:
        pass
    print("built. Next: start (or 'up' to do everything).")


def cmd_start(g, a):
    topo = load_topo(a.lab)
    p = get_project(g, topo)
    g.post(f"/projects/{p['project_id']}/nodes/start")
    for _ in range(60):
        st = {n: x.get("status") for n, x in g.nodes(p["project_id"]).items()}
        if all(v == "started" for v in st.values()):
            break
        time.sleep(2)
    print("all nodes started" if all(v == "started" for v in st.values()) else f"node states: {st}")


def cmd_stop(g, a):
    topo = load_topo(a.lab)
    p = get_project(g, topo)
    g.post(f"/projects/{p['project_id']}/nodes/stop")
    print("all nodes stopped")


def cmd_delete(g, a):
    topo = load_topo(a.lab)
    p = get_project(g, topo, must=False)
    if not p:
        print("no such project")
        return
    g.delete(f"/projects/{p['project_id']}")
    print("deleted", topo["project"])


def selected_nodes(g, topo, a):
    p = get_project(g, topo)
    nodes = g.nodes(p["project_id"])
    want = [n["name"] for n in topo["nodes"]]
    if getattr(a, "nodes", None):
        want = [x.strip() for x in a.nodes.split(",") if x.strip()]
    missing = [w for w in want if w not in nodes]
    if missing:
        raise SystemExit(f"nodes not in the GNS3 project: {missing}")
    return p, {w: nodes[w] for w in want}


def push_one(g, node, script_text, name, password, verbose, results, boot_timeout):
    try:
        host, port = console_endpoint(g, node)
        c = Console(host, port, name, verbose)
        c.login(password, boot_timeout)
        c.put_file(script_text, "/tmp/lab-node.sh")
        rc, out = c.run("bash /tmp/lab-node.sh > /var/log/lab-apply.log 2>&1; r=$?; tail -n 5 /var/log/lab-apply.log; exit_code=$r; (exit $r)", 300)
        c.close()
        results[name] = (rc == 0, out if rc != 0 else "ok")
    except Exception as e:  # noqa
        results[name] = (False, str(e))


def cmd_push(g, a):
    topo = load_topo(a.lab)
    variant = a.variant or topo["default_variant"]
    if variant not in topo["variants"]:
        raise SystemExit(f"unknown variant {variant}; available: {', '.join(topo['variants'])}")
    p, nodes = selected_nodes(g, topo, a)
    print(f"pushing variant '{variant}' to {len(nodes)} nodes ...")
    results, threads = {}, []
    for name, node in nodes.items():
        if node.get("status") != "started":
            print(f"  {name}: not started - skipping (run 'start' first)")
            continue
        path = os.path.join(a.lab, "nodes", variant, name + ".sh")
        with open(path, encoding="utf-8") as f:
            txt = f.read().replace("\r\n", "\n")
        t = threading.Thread(target=push_one, args=(g, node, txt, name, a.password_root, a.verbose, results, a.boot_timeout))
        t.start()
        threads.append(t)
        while sum(th.is_alive() for th in threads) >= a.parallel:
            time.sleep(0.2)
    for t in threads:
        t.join()
    bad = 0
    for name in nodes:
        if name in results:
            ok, msg = results[name]
            print(f"  {'OK  ' if ok else 'FAIL'} {name}" + ("" if ok else f": {msg}"))
            bad += 0 if ok else 1
    if bad:
        print(f"{bad} node(s) failed. Look at /var/log/lab-apply.log and /var/log/lab-net.log on them.")
    else:
        print(f"variant '{variant}' applied. Give the protocols ~30 s to converge, then run 'check'.")


def cmd_exec(g, a):
    topo = load_topo(a.lab)
    p = get_project(g, topo)
    nodes = g.nodes(p["project_id"])
    if a.node not in nodes:
        raise SystemExit(f"no node {a.node}")
    host, port = console_endpoint(g, nodes[a.node])
    c = Console(host, port, a.node, a.verbose)
    c.login(a.password_root, a.boot_timeout)
    rc, out = c.run(a.command, a.timeout)
    c.close()
    print(out)
    if rc is None:
        print("(timed out)")
    sys.exit(0 if rc == 0 else 1)


def cmd_check(g, a):
    topo = load_topo(a.lab)
    variant = a.variant or topo["default_variant"]
    checks = topo["checks"].get(variant, [])
    if not checks:
        print("no automated checks for this variant")
        return
    p = get_project(g, topo)
    nodes = g.nodes(p["project_id"])
    cons = {}
    t0 = time.time()
    failed = 0
    for i, c in enumerate(checks):
        n = c["node"]
        if n not in cons:
            host, port = console_endpoint(g, nodes[n])
            try:
                cons[n] = Console(host, port, n, a.verbose)
                cons[n].login(a.password_root, a.boot_timeout)
            except (OSError, TimeoutError, ConnectionError) as e:
                print(f"FAIL        {n:10s} console problem: {e}")
                failed += 1
                continue
        budget = a.timeout if i == 0 else 60
        end = time.time() + budget
        out = ""
        while True:
            rc, out = cons[n].run(c["cmd"], 60)
            if out is not None and re.search(c["expect"], out or "", re.M):
                ok = True
                break
            if time.time() > end:
                ok = False
                break
            time.sleep(3)
        print(f"{'PASS' if ok else 'FAIL'} [{int(time.time() - t0):4d}s] {n:10s} {c['cmd']}" + (f"   ({c['desc']})" if c.get("desc") else ""))
        if not ok:
            failed += 1
            print("     expected /" + c["expect"] + "/, got:\n     " + (out or "").replace("\n", "\n     ")[-1500:])
    for c in cons.values():
        c.close()
    print(f"{len(checks) - failed}/{len(checks)} checks passed")
    sys.exit(1 if failed else 0)


def cmd_up(g, a):
    a.force = a.rebuild
    if not g.project_by_name(load_topo(a.lab)["project"]) or a.rebuild:
        cmd_build(g, a)
    cmd_start(g, a)
    print("waiting for the VMs to boot (consoles) ...")
    cmd_push(g, a)
    if not a.no_check:
        try:
            cmd_check(g, a)
        except SystemExit as e:
            if e.code:
                print("some checks failed - protocols may still be converging, re-run 'check' in a minute.")


def cmd_run_script(g, a):
    p = g.project_by_name(a.project)
    if not p:
        raise SystemExit(f"no project {a.project}")
    g.open_project(p)
    nodes = g.nodes(p["project_id"])
    if a.node not in nodes:
        raise SystemExit(f"no node {a.node} in {a.project}")
    with open(a.script, encoding="utf-8") as f:
        txt = f.read().replace("\r\n", "\n")
    host, port = console_endpoint(g, nodes[a.node])
    c = Console(host, port, a.node, True)
    c.login(a.password_root, a.boot_timeout)
    c.put_file(txt, "/tmp/run-script.sh")
    print(f"\n--- running {a.script} on {a.node} (output follows) ---")
    c.send("bash /tmp/run-script.sh; printf '__SCR''IPT_RC=%s\\n' \"$?\"\r")
    m, _ = c.expect(r"__SCRIPT_RC=(\d+)", a.timeout)
    c.close()
    if not m:
        raise SystemExit("\nscript did not finish within the timeout (it may still be running)")
    print(f"\n--- script finished, rc={m.group(1)} ---")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", default=os.environ.get("GNS3_SERVER"))
    ap.add_argument("--user", default=os.environ.get("GNS3_USER"))
    ap.add_argument("--password", default=os.environ.get("GNS3_PASSWORD"))
    ap.add_argument("--password-root", default=os.environ.get("LAB_ROOT_PASSWORD"),
                    help="root password of the VMs, if the console asks for one")
    ap.add_argument("-v", "--verbose", action="store_true", help="echo console traffic")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def lab_parser(name, **kw):
        sp = sub.add_parser(name, **kw)
        sp.add_argument("lab")
        return sp

    sub.add_parser("templates")
    for name in ("build", "up"):
        sp = lab_parser(name)
        sp.add_argument("--template", default=DEFAULT_TEMPLATE, help="router template (default debian-frr)")
        sp.add_argument("--host-template", default=None, help="host template (default = router template)")
        sp.add_argument("--compute", default=None, help="compute id (e.g. 'vm' for the GNS3 VM, 'local')")
        sp.add_argument("--keep-ram", action="store_true", help="don't override the template's RAM")
        if name == "build":
            sp.add_argument("--force", action="store_true", help="delete and recreate the project")
        else:
            sp.add_argument("--rebuild", action="store_true", help="delete and recreate the project")
            sp.add_argument("--variant")
            sp.add_argument("--no-check", action="store_true")
            sp.add_argument("--parallel", type=int, default=6)
            sp.add_argument("--boot-timeout", type=int, default=420)
            sp.add_argument("--timeout", type=int, default=180, help="first check's convergence budget")
            sp.add_argument("--nodes")
    for name in ("start", "stop", "delete"):
        lab_parser(name)
    sp = lab_parser("push")
    sp.add_argument("--variant")
    sp.add_argument("--nodes", help="comma separated subset")
    sp.add_argument("--parallel", type=int, default=6)
    sp.add_argument("--boot-timeout", type=int, default=420)
    sp = lab_parser("check")
    sp.add_argument("--variant")
    sp.add_argument("--timeout", type=int, default=120)
    sp.add_argument("--boot-timeout", type=int, default=60)
    sp = lab_parser("exec")
    sp.add_argument("node")
    sp.add_argument("command")
    sp.add_argument("--timeout", type=int, default=60)
    sp.add_argument("--boot-timeout", type=int, default=60)
    sp = sub.add_parser("run-script")
    sp.add_argument("--project", required=True)
    sp.add_argument("--node", required=True)
    sp.add_argument("--timeout", type=int, default=3600)
    sp.add_argument("--boot-timeout", type=int, default=420)
    sp.add_argument("script")
    a = ap.parse_args()

    if not a.server:
        cfg = find_local_server_config()
        if cfg:
            a.server = cfg["server"]
            if cfg["auth"] and not a.user:
                a.user, a.password = cfg["user"], cfg["password"]
        else:
            a.server = "http://127.0.0.1:3080"
    g = Gns3(a.server, a.user, a.password)
    {"templates": cmd_templates, "build": cmd_build, "up": cmd_up, "start": cmd_start, "stop": cmd_stop,
     "delete": cmd_delete, "push": cmd_push, "check": cmd_check, "exec": cmd_exec,
     "run-script": cmd_run_script}[a.cmd](g, a)


if __name__ == "__main__":
    main()
