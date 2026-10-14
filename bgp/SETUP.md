# Setup: GNS3 + Debian/FRR base image

You do this **once**. Afterwards every lab is a single command.

Everything (routers and hosts) runs from **one** Debian 13 cloud image with FRR installed:

* **frr-router**: the base image, 384 MB RAM, up to 8 NICs, FRR running
* **frr-host**: the same image, 320 MB RAM, FRR disabled (a plain Linux box with ping/traceroute/tcpdump/iperf3)

Both use *linked clones*, so 8 VMs cost about as much disk as one.

## 0. What you need

* GNS3 2.2.x GUI on Windows **with the GNS3 VM** running (QEMU nodes run inside the GNS3 VM).
  Give the GNS3 VM at least **4 GB RAM** (6 GB is comfortable). The biggest lab (30) runs 8 VMs ≈ 3 GB.
  Nested virtualisation (KVM inside the GNS3 VM) should be enabled, or the VMs will be very slow.
* Python 3.8+ on Windows, plus one package:
  ```powershell
  pip install pycdlib
  ```
* The Debian 13 "genericcloud" image (≈ 350 MB):
  <https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2>
* Internet access from the GNS3 VM (only during step 2, to install FRR).

Check that the script can reach GNS3 (the GUI must be open):

```powershell
cd C:\Users\super_svyat\my_vibe_coding\frr\bgp\tools
python lab.py check
```

You should see `compute vm ... connected=True`. If GNS3 listens on another port, add
`--server http://127.0.0.1:<port>` (Edit → Preferences → Server shows it).

## 1–3. Automatic way (recommended)

```powershell
# 1+2. upload the Debian image as frr-base.qcow2 and run the one-time preparation VM
python lab.py prep --image C:\Users\super_svyat\Downloads\debian-13-genericcloud-amd64.qcow2

# 3. create the two templates
python lab.py templates
```

`prep` creates a project **bgp-00-image-prep** with one VM attached to a NAT cloud and starts it.
Open the project in GNS3 and watch the VM's console: cloud-init installs FRR and tools, makes some lab
tweaks (listed below) and **powers the VM off by itself** (5–15 minutes). The script waits for that.
The VM writes directly into `frr-base.qcow2` (linked clone disabled on purpose), so after it stops,
the image *is* the finished base image.

When it is done you can delete the `bgp-00-image-prep` project in GNS3.

What the preparation does to the image:

| Change | Why |
|---|---|
| installs `frr frr-pythontools tcpdump traceroute mtr-tiny iperf3 netcat-openbsd …` | the routing suite and tools |
| enables `bgpd`, `ospfd`, `bfdd` in `/etc/frr/daemons` | zebra, staticd (and mgmtd in FRR 10) always run |
| kernel option `net.ifnames=0` | NICs are called `eth0, eth1, …` in GNS3 adapter order |
| disables cloud-init networking, removes default DHCP config | the labs configure interfaces themselves |
| installs `lab-net.service` | runs `/etc/lab/net.sh` at every boot, before FRR |
| auto-login as root on the serial console; root password `lab`; SSH root login allowed | convenience |
| aliases `v` = `vtysh`, `sbs` = `vtysh -c "show bgp summary"` | convenience |
| `cloud-init clean` | so every lab node runs its own cloud-init config on first boot |

## Building a lab

```powershell
cd C:\Users\super_svyat\my_vibe_coding\frr\bgp\labs\05-weight
python ..\..\tools\lab.py build .
```

The script:

1. creates a cloud-init ISO per node whose *user-data* is that node's `nodes/<NODE>.sh`, and uploads it
2. creates project `bgp-05-weight`, adds every node from the templates, sets its name and NIC count, attaches its ISO
3. cables everything exactly as in the lab's links table (`ethN` = GNS3 adapter N)
4. starts all nodes

After ~60–90 s each node has its hostname, IP addresses and start `frr.conf`. Open a console
(double-click) and you are root. Then follow the lab README.

Other useful commands:

| Command | What it does |
|---|---|
| `python lab.py build . --force` | delete and rebuild the lab project from scratch (resets everything) |
| `python lab.py build . --no-start` | build but don't start |
| `python lab.py delete .` | remove the lab's project |
| `python lab.py iso .` | only write the ISOs to `iso/` (for manual use) |

## Saving your work inside a lab

* FRR: `write memory` in vtysh (or `vtysh -w`) saves to `/etc/frr/frr.conf`, which survives a reboot.
* cloud-init runs **once** per node, so rebooting does not reset your changes.
* To reset one node to the lab's start config, paste its `nodes/<NODE>.sh` into its console.
* To reset the whole lab: `python lab.py build . --force`.

## Manual way (if the script does not work for you)

**Base image, by hand**

1. Copy `debian-13-genericcloud-amd64.qcow2` to `frr-base.qcow2`.
2. Run `python lab.py iso ..\labs\01-what-is-bgp` once just to make sure pycdlib works. To get the preparation ISO,
   run this in `tools`:
   ```powershell
   python -c "import lab,time; open('frr-prep-seed.iso','wb').write(lab.make_iso(lab.PREP_USER_DATA, lab.meta('prep-%d' % time.time(), 'frr-base')))"
   ```
3. In GNS3: Edit → Preferences → QEMU VMs → New → name `frr-prep`, server **GNS3 VM**, Linux, RAM 1024,
   console **telnet**, disk image `frr-base.qcow2`. Then Edit that template: **uncheck "Use as a linked base VM"**,
   HDD interface `virtio`, Network: 1 adapter, type `virtio-net-pci`, CD/DVD: `frr-prep-seed.iso`.
4. New project, drag in `frr-prep` and a **NAT** node, connect NAT ↔ frr-prep `eth0`, start, wait until it powers off.

**Templates, by hand**: QEMU VMs → New → `frr-router`, GNS3 VM, RAM 384, telnet console, disk `frr-base.qcow2`,
then Edit: linked base VM **checked**, HDD interface virtio, 8 adapters of type virtio-net-pci, symbol "router".
Same again for `frr-host` with RAM 320 and the "computer" symbol.

**A lab, by hand**: drag nodes in, name them as in the lab, set the adapter count, cable them by adapter
number (adapter 0 = `eth0`) as in the README's links table, start them, and paste each `nodes/<NODE>.sh` into
the matching console. (Or attach the ISOs from `python lab.py iso .` as each node's CD/DVD image.)

## Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot reach GNS3` | GNS3 GUI must be running; check host/port in Edit → Preferences → Server |
| `compute 'vm' not connected` | start the GNS3 VM (Preferences → GNS3 VM) |
| `template 'frr-router' not found` | run `python lab.py templates` |
| `already used by … linked base` (during prep --force) | another project uses frr-base.qcow2; delete those projects first |
| prep VM never powers off | open its console. No Internet? Check the NAT node and the GNS3 VM's own Internet access. Run `cloud-init status --long` |
| a node has no IP / wrong hostname | in its console: `cloud-init status --long`, `journalctl -u cloud-final`; or simply paste `nodes/<NODE>.sh` |
| interfaces are called `ens3` etc. | `net.ifnames=0` was not applied. `/etc/lab/net.sh` renames them anyway (eth0.. in PCI order) on every boot |
| VMs extremely slow | KVM not available in the GNS3 VM: enable nested virtualisation (VMware: *Virtualize Intel VT-x/EPT or AMD-V/RVI*; VirtualBox: *Enable Nested VT-x/AMD-V*) |
| out of memory | lower RAM per template (routers work with 320 MB, hosts with 256 MB) or give the GNS3 VM more |
