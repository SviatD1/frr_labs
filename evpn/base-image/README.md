# Base image: `debian-frr`

Every node in every lab - routers *and* hosts - is a linked clone of one QEMU image: **Debian 13 + FRR
(current stable) + lab tools**. You build it once (≈10 minutes), then create one GNS3 template from it.

## What ends up in the image

| | |
|---|---|
| OS | Debian 13 "trixie" (cloud *nocloud* image), classic interface names `eth0..ethN` (`net.ifnames=0`) |
| FRR | from `deb.frr.org` (frr-stable) - falls back to Debian's package if that repo is unavailable. IPv6-VTEP variants need FRR ≥ 10.6 |
| FRR daemons on | zebra, bgpd, ospfd, ospf6d, isisd, pimd, pim6d, bfdd, pbrd, vrrpd, staticd (`frr defaults datacenter`) |
| tools | iproute2, bridge, ethtool, tcpdump, iperf3, arping, traceroute, mtr, ndisc6, nftables, lldpd, scapy, socat, jq |
| lab helpers | `lab-reset`, `lab-apply`, `lab-info`, `mcast-send`, `mcast-recv`, systemd unit `lab-net.service` |
| console | serial console on `ttyS0` with **root autologin** (that's what `gns3_lab.py` talks to) |
| networking | no DHCP, no networkd/ifupdown management - each lab's `/etc/lab/net.sh` owns the interfaces |

How a lab node script uses it:

```text
labs/NN-xxx/nodes/<variant>/<node>.sh
   ├─ writes /etc/lab/net.sh        (Linux data plane; replayed at every boot by lab-net.service)
   ├─ writes /etc/frr/frr.conf      (FRR control plane)
   └─ runs   lab-apply <node>       (hostname, forwarding on/off, net.sh, restart or disable FRR)
net.sh always starts with lab-reset, so you can push another variant/lab onto the same VM at any time.
```

## Step 1 - get the cloud image

Download **`debian-13-nocloud-amd64.qcow2`** from
<https://cloud.debian.org/images/cloud/trixie/latest/> (the *nocloud* flavour allows root login without
password on the console and has no cloud-init).

## Step 2 - a throw-away "build" template

GNS3 → *Edit → Preferences → QEMU VMs → New*:

* Name `debian-frr-build`, run on the **GNS3 VM** (Windows/macOS) or locally (Linux)
* RAM 1024 MB, console type **telnet**
* Disk image: the downloaded qcow2 (let GNS3 copy/upload it)
* After creating, *Edit* the template:
  * *Network*: adapters **1**, type **virtio-net-pci**
  * *Advanced*: **untick "Use as a linked base VM"** - the build then writes into the image file itself.

## Step 3 - build

1. New project **`evpn-base`**. Drag in a **NAT** node and one `debian-frr-build` node. Link NAT ↔ the VM's
   first interface. Start the VM.
2. From the `evpn` folder on your PC:

   ```powershell
   python tools\gns3_lab.py run-script --project evpn-base --node debian-frr-build-1 base-image\build-base.sh
   ```

   (node name as shown in GNS3). The script's output streams to your terminal; the VM powers off at the end.

   *No Python / tool problems?* Open the VM console in GNS3, log in as `root`, and paste the content of
   `build-base.sh` (or `curl` it from somewhere you host it) - same result.
3. Delete the `evpn-base` project. Keep the qcow2.

## Step 4 - the real template `debian-frr`

*Preferences → QEMU VMs → New* (or *Copy* the build template and edit):

| setting | value |
|---|---|
| Name | **`debian-frr`** (the tool looks for this name; `--template X` to use another) |
| Server | GNS3 VM (Windows/macOS) |
| RAM | 512 MB (the tool sets 512 for routers / 256 for hosts per node anyway) |
| vCPUs | 1 |
| Console | telnet, *auto start console* off |
| Disk | the **same** (now built) qcow2 |
| Network | adapters 13, type **virtio-net-pci**, first port name `eth0`, name format `eth{0}` |
| Advanced | **"Use as a linked base VM" ticked** (default), *On close*: power off the VM |
| Category | Routers (cosmetic) |

Check it: `python tools\gns3_lab.py templates` lists `debian-frr`.

KVM matters: on Windows use the GNS3 VM (VMware Workstation/Player or VirtualBox with nested
virtualization) - QEMU without KVM is ~10x slower. Biggest labs have 14-18 VMs: give the GNS3 VM 8 GB RAM
and 4 vCPUs if you can.

## Updating later

Want a newer FRR? Make a temporary build node again (linked base VM unticked), boot it, attach NAT to eth0,
`dhclient eth0 && apt update && apt install --only-upgrade frr`, power off. Existing linked clones keep their
old overlay - delete and rebuild lab projects (`gns3_lab.py up ... --rebuild`) to pick up the change.
