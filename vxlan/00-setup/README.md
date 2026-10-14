# 00 · Setup — GNS3, the Linux template, conventions

Do this once. Every lab afterwards is "drag VMs, cable them per `topology.txt`, run one script per node".

## 1. GNS3 on Windows

You are on Windows, so QEMU VMs must run inside the **GNS3 VM** (VMware Workstation Player or VirtualBox).

1. Install GNS3 (all-in-one) and import the matching **GNS3 VM** (same version number).
2. GNS3 → *Edit → Preferences → GNS3 VM*: enable it, give it **8–12 GB RAM** and 4+ vCPUs. The biggest labs (10, 13) run 10 VMs.
3. Turn on nested virtualization for the GNS3 VM (VMware: *Virtualize Intel VT-x/EPT*). Without KVM, Linux VMs boot very slowly.

## 2. Build one Linux template (used for routers AND hosts)

1. Download the Debian 12 **generic** cloud image (`debian-12-generic-amd64.qcow2`) from cloud.debian.org — "generic", not "genericcloud": the generic kernel has the vrf/vxlan/8021q modules. Alternatively use the GNS3 Marketplace "Debian" appliance.
2. GNS3 → *New template → Qemu VM*: name `debian-frr`, RAM **512 MB** (1024 for spines/leaves is comfortable), disk = the qcow2, **adapters = 5** (eth0…eth4), adapter type `virtio-net-pci`, console `telnet`. If the image needs cloud-init, attach the cloud-init ISO from the GNS3 appliance or use the marketplace appliance.
3. Drop one instance into a scratch project, connect `eth0` to a **NAT** node, boot, log in, become root.
4. Copy this whole `vxlan` folder to `/root/vxlan` (see §4), then run:

   ```bash
   bash /root/vxlan/00-setup/prep-node.sh
   reboot
   ip -br link        # must show eth0 eth1 eth2 eth3 eth4
   lsmod | grep -E 'vxlan|vrf'   # (modules load on first use; modprobe vrf must not fail)
   poweroff
   ```

5. In the template settings tick **"Use as a linked base VM"**, so every lab node is a thin clone that already contains FRR and the lab scripts.

> Hosts don't need FRR, but using one image for everything keeps life simple. If RAM is tight, set hosts to 256 MB.

## 3. Conventions used in every lab

| Item | Value |
|---|---|
| `eth0` | management, to the GNS3 NAT cloud (DHCP). Never part of a lab. |
| Leaf/VTEP `eth1`, `eth2` | uplinks to spine1 / spine2 (core = spine1 in labs 1-4) |
| Leaf/VTEP `eth3`, `eth4` | host-facing ports |
| Spine `ethN` | goes to leafN (`eth4` = spine-to-spine where present) |
| Host `eth1` | the only lab NIC |
| Loopbacks | spine1/core `10.0.0.1`, spine2 `10.0.0.2`, leafN/vtepN `10.0.0.1N` |
| Underlay links | spine*S* ↔ leaf*L* = `10.S.1L.0/31` (spine `.0`, leaf `.1`) |
| Spine ↔ spine | `10.12.0.0/31` |
| VXLAN UDP port | 4789 (IANA) everywhere |
| Host MTU | 1450 (underlay 1500 − 50 bytes VXLAN) — except lab 03, on purpose |
| BGP | iBGP AS 65000, spines are route reflectors; external router AS 65100 |
| FRR | Debian 12 package, 8.4.4 — the version the labs were tested against |

Every lab folder has:

```
labNN-name/
  README.md        theory recap, steps, verification, experiments, break/fix
  topology.txt     exact GNS3 cabling (nodeA:ifA nodeB:ifB)
  nodes/<node>.sh        kernel-side config (interfaces, bridges, VXLAN, VRFs)
  nodes/<node>.frr.conf  FRR config (first line lists the daemons it needs)
```

## 4. Getting the files into the VMs

Easiest: put them in the template once (step 2.4), then every linked clone has `/root/vxlan`. Ways to get them there:

- On Windows, in the folder that contains `vxlan`: `python -m http.server 8000` (allow it through the firewall). In the VM: `wget -r -np -nH -R "index.html*" http://<your-PC-LAN-IP>:8000/vxlan/` then `mv vxlan /root/`.
- Or zip it, serve the zip the same way, and `wget` + `unzip` (`apt install unzip`).

If you change the files later, refresh a running node with the same `wget`.

## 5. Running a lab

On each node, as root:

```bash
cd /root/vxlan/lab06-spine-leaf
./nodes/leaf1.sh          # on leaf1;  ./nodes/h1.sh on h1, etc.
```

Router scripts wipe the previous lab, configure the kernel, then call `00-setup/apply-frr.sh`, which writes `/etc/frr/frr.conf`, enables exactly the daemons that lab needs, and restarts FRR. Then use `vtysh`.

The kernel config is not persistent. After a reboot, re-run the node script, or make it automatic:

```bash
/root/vxlan/00-setup/persist.sh lab06-spine-leaf leaf1     # run at every boot
/root/vxlan/00-setup/persist.sh --off
```

Host scripts replace the host's default route with the lab gateway in the routed labs (11, 13–15), so `apt` stops working on hosts there — that's expected.

## 6. Tools you will use constantly

```bash
ip -d link show vxlan100          # VNI, local/remote/group, port, learning
bridge fdb show dev vxlan100      # MAC -> remote VTEP table (00:00:00:00:00:00 = flood list)
bridge link                       # bridge ports and their flags (learning, neigh_suppress)
ip neigh / ip route [vrf X]       # ARP and routing tables
tcpdump -ni eth1 udp port 4789    # VXLAN on the wire
vtysh -c 'show ...'               # FRR
```

GNS3 captures: right-click any link → *Start capture* → Wireshark decodes UDP/4789 as VXLAN automatically.
