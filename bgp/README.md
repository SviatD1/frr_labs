# BGP with FRR on Linux: 30 GNS3 labs

Hands-on labs for the **telecomTech** playlist
[Border Gateway Protocol (BGP)](https://www.youtube.com/playlist?list=PLmVr8r1kmMm0ncoc9L6bFICpuNbo7Tumu),
one lab per video. Every router is a Debian 13 VM running **FRRouting**, every host is a plain Debian VM, so
along the way you also practise everyday Linux networking (`ip`, `ss`, `tcpdump`, `traceroute`, `sysctl`).

## Start here

1. **[SETUP.md](SETUP.md)**: one-time setup: GNS3 VM, the FRR base image, two templates (about 20 minutes, mostly waiting).
2. Watch a video, then open its lab and run:
   ```powershell
   cd labs\01-what-is-bgp
   python ..\..\tools\lab.py build .
   ```
3. Work through the README's steps. Each step says what to do, has the solution folded away, and a
   **Verify** block with the commands to run and the output you should expect.
4. Keep **[CHEATSHEET.md](CHEATSHEET.md)** open: Linux and FRR commands on one page.

## The labs

| # | Video | Lab | Nodes | RAM |
|---|---|---|---|---|
| 01 | [What is BGP?](https://www.youtube.com/watch?v=fo9YxxKNO_g) | [labs/01-what-is-bgp](labs/01-what-is-bgp/README.md) | 2R + 2H | 1.4 GB |
| 02 | [eBGP vs iBGP - What's the difference?](https://www.youtube.com/watch?v=3x7yztGSY-g) | [labs/02-ebgp-vs-ibgp](labs/02-ebgp-vs-ibgp/README.md) | 3R + 2H | 1.8 GB |
| 03 | [BGP Attributes and Determining the Best Path](https://www.youtube.com/watch?v=ZZRsPcNllbU) | [labs/03-attributes-and-best-path](labs/03-attributes-and-best-path/README.md) | 4R + 2H | 2.1 GB |
| 04 | [Why does BGP require an IGP to function?](https://www.youtube.com/watch?v=SN_TDZ2eDAA) | [labs/04-why-bgp-needs-an-igp](labs/04-why-bgp-needs-an-igp/README.md) | 4R + 2H | 2.1 GB |
| 05 | [BGP - The BGP Weight Attribute](https://www.youtube.com/watch?v=akYzsBrrQ70) | [labs/05-weight](labs/05-weight/README.md) | 4R + 2H | 2.1 GB |
| 06 | [BGP Attribute Categories - well-known/optional, mandatory/discretionary, transitive/non-transitive](https://www.youtube.com/watch?v=9sHoHr82odQ) | [labs/06-attribute-categories](labs/06-attribute-categories/README.md) | 4R + 2H | 2.1 GB |
| 07 | [BGP - Why is the BGP Best Path Algorithm so complex?](https://www.youtube.com/watch?v=KGHk_y-nstM) | [labs/07-best-path-complexity](labs/07-best-path-complexity/README.md) | 4R + 1H | 1.8 GB |
| 08 | [BGP - What is the Local Preference BGP Attribute?](https://www.youtube.com/watch?v=n-CYvVm8aUI) | [labs/08-local-preference](labs/08-local-preference/README.md) | 5R + 2H | 2.5 GB |
| 09 | [BGP - What is the Originate Attribute?](https://www.youtube.com/watch?v=xa9OfO6i1_M) | [labs/09-locally-originated](labs/09-locally-originated/README.md) | 2R + 2H | 1.4 GB |
| 10 | [BGP - What is the AS_Path Attribute?](https://www.youtube.com/watch?v=Rw1Ps2JTtPc) | [labs/10-as-path](labs/10-as-path/README.md) | 4R + 2H | 2.1 GB |
| 11 | [BGP - What is the Origin Code BGP Attribute?](https://www.youtube.com/watch?v=qiqENy217nE) | [labs/11-origin](labs/11-origin/README.md) | 4R + 2H | 2.1 GB |
| 12 | [BGP - What is the MED BGP Attribute?](https://www.youtube.com/watch?v=k04h52XZFTc) | [labs/12-med](labs/12-med/README.md) | 3R + 2H | 1.8 GB |
| 13 | [BGP - Why does the BGP Algorithm Prefer eBGP routes over iBGP routes?](https://www.youtube.com/watch?v=0ffgcK70MxU) | [labs/13-ebgp-over-ibgp](labs/13-ebgp-over-ibgp/README.md) | 3R + 3H | 2.1 GB |
| 14 | [BGP - Route with the Lowest IGP Metric to the Next Hop is Preferred](https://www.youtube.com/watch?v=2B0gshKX9Us) | [labs/14-igp-metric-to-next-hop](labs/14-igp-metric-to-next-hop/README.md) | 4R + 2H | 2.1 GB |
| 15 | [BGP - Algorithm Prefers the Oldest External Path](https://www.youtube.com/watch?v=O0wC43lwxSs) | [labs/15-oldest-external-path](labs/15-oldest-external-path/README.md) | 4R + 2H | 2.1 GB |
| 16 | [BGP - BGP Algorithm Prefers the Lowest Router ID](https://www.youtube.com/watch?v=ZHlISG4l6TI) | [labs/16-lowest-router-id](labs/16-lowest-router-id/README.md) | 4R + 2H | 2.1 GB |
| 17 | [BGP - BGP Prefers the Lowest Neighbor IP Address](https://www.youtube.com/watch?v=VHe_w-zsNNY) | [labs/17-lowest-neighbor-ip](labs/17-lowest-neighbor-ip/README.md) | 2R + 2H | 1.4 GB |
| 18 | [BGP - Determining the next hop IP (next-hop-self)](https://www.youtube.com/watch?v=KTrGzMcanZg) | [labs/18-next-hop-self](labs/18-next-hop-self/README.md) | 3R + 2H | 1.8 GB |
| 19 | [BGP - Why does iBGP require full mesh peering?](https://www.youtube.com/watch?v=03Gl1YGeZYc) | [labs/19-ibgp-full-mesh](labs/19-ibgp-full-mesh/README.md) | 4R + 2H | 2.1 GB |
| 20 | [BGP - Understanding the iBGP Split-Horizon Rule](https://www.youtube.com/watch?v=lBWXBvyr6_Y) | [labs/20-ibgp-split-horizon](labs/20-ibgp-split-horizon/README.md) | 5R + 2H | 2.5 GB |
| 21 | [BGP - What are iBGP Route Reflectors?](https://www.youtube.com/watch?v=9-9Tw8yIqPM) | [labs/21-route-reflectors](labs/21-route-reflectors/README.md) | 5R + 3H | 2.8 GB |
| 22 | [BGP - Route Reflectors Basic Configuration (FRR version of the Cisco IOS video)](https://www.youtube.com/watch?v=ZwQ-lhRr7TU) | [labs/22-route-reflector-config](labs/22-route-reflector-config/README.md) | 4R + 2H | 2.1 GB |
| 23 | [BGP - Understanding BGP Confederations](https://www.youtube.com/watch?v=__ZlyKm4du0) | [labs/23-confederations](labs/23-confederations/README.md) | 5R + 2H | 2.5 GB |
| 24 | [BGP - Confederations Basic Config (FRR version of the Cisco IOS video)](https://www.youtube.com/watch?v=vf7CzMjdaUI) | [labs/24-confederation-config](labs/24-confederation-config/README.md) | 5R + 2H | 2.5 GB |
| 25 | [BGP - What is the BGP Originator ID?](https://www.youtube.com/watch?v=c8dJPJLlU08) | [labs/25-originator-id](labs/25-originator-id/README.md) | 5R + 2H | 2.5 GB |
| 26 | [BGP - What is the BGP Cluster List Attribute?](https://www.youtube.com/watch?v=tMizyaaOJeQ) | [labs/26-cluster-list](labs/26-cluster-list/README.md) | 5R + 2H | 2.5 GB |
| 27 | [BGP - What are BGP Communities?](https://www.youtube.com/watch?v=4nfOTEJUW80) | [labs/27-communities](labs/27-communities/README.md) | 4R + 2H | 2.1 GB |
| 28 | [BGP Answers (troubleshooting lab)](https://www.youtube.com/watch?v=NMTtn5a6ZXU) | [labs/28-troubleshooting](labs/28-troubleshooting/README.md) | 4R + 2H | 2.1 GB |
| 29 | [BGP in one minute!](https://www.youtube.com/watch?v=FJSor7jPptI) | [labs/29-bgp-in-one-minute](labs/29-bgp-in-one-minute/README.md) | 3R + 2H | 1.8 GB |
| 30 | [Understanding and Mastering BGP - Complete BGP Course (capstone)](https://www.youtube.com/watch?v=DIDex6WrX2E) | [labs/30-capstone-multihomed-enterprise](labs/30-capstone-multihomed-enterprise/README.md) | 6R + 2H | 2.9 GB |

R = FRR router VM (384 MB), H = Linux host VM (320 MB). RAM is the total for the lab inside the GNS3 VM.

## How a lab folder looks

```
labs/05-weight/
  README.md          explanation, topology, addressing, steps, expected output, challenges
  topology.json      nodes, interfaces, links (used by tools/lab.py)
  nodes/R1.sh ...    per-node setup: hostname + /etc/lab/net.sh (ip commands) + start frr.conf
  configs/R1.frr.conf  start FRR config
  solution/R1.frr.conf FRR running config after all steps
```

## Conventions used in every lab

| Thing | Convention |
|---|---|
| Router names / numbers | `Rn`, loopback and router ID `n.n.n.n/32` |
| Link between Rx and Ry (x<y) | `10.0.xy.0/24`, Rx = `.x`, Ry = `.y` |
| Host LAN behind Rn | `192.168.n.0/24`, router `.1`, host `Hn` = `.10` |
| Interfaces | `eth0, eth1, …` = GNS3 adapter 0, 1, … (core links first, host LAN last) |
| AS numbers | 100, 200, 300, … (private 65001/65002 for confederation sub-ASes) |
| eBGP policy | FRR rejects all eBGP routes without a policy (RFC 8212). Lab 1 shows this; the other labs use `no bgp ebgp-requires-policy` to keep configs short |
| Login | root / `lab` (auto-login on the console) |

## How the labs were checked

Every lab was run end to end before delivery: each topology was built with Linux network namespaces and
real FRR daemons (FRR 8.4), the start configs were loaded, every step's solution was applied, and every
claim the README makes (session states, best path and its reason, AS_PATH, communities, pings, traceroutes)
was asserted automatically. The "expected output" blocks are the real output of those runs.

What could not be tested from here: booting the Debian VMs in GNS3 (the base image needs a download that
was not available in the build environment). Your VMs run Debian 13's FRR (10.x), which can word some output
slightly differently. If a node does not come up with its config, paste its `nodes/<NODE>.sh` into the console
and see the troubleshooting table in [SETUP.md](SETUP.md).

The labs follow the topic in each video's title (the videos themselves were not transcribed). Where a video
demonstrates Cisco IOS configuration (labs 22 and 24), the lab does the same in FRR and includes a Cisco→FRR
command table.
