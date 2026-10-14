#!/usr/bin/env python3
"""
Design -> config: edit DESIGN below, run `python design.py`, and a new lab folder
(labs/22-design-your-fabric-custom) is generated with GNS3 topology + node scripts.
Then:  python tools\gns3_lab.py up labs\22-design-your-fabric-custom
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "generator"))
from labs_clos import build_design
from gen import emit

DESIGN = {
    "name": "custom",
    "spines": 2,             # number of spines (= uplinks per leaf)
    "leaves": 4,             # number of leaves (<= 10 with the default 13 adapters on spines)
    "underlay": "isis",      # isis | ospf
    "asn": 65000,
    "vlans": {10: "10.10.10.1/24", 20: "10.20.20.1/24"},   # VLAN -> anycast gateway
    "vrf": "PROD",           # tenant VRF (symmetric IRB, L3VNI 1000)
    "hosts_per_leaf": 1,     # host i on leaf j gets VLAN (list order, round robin)
}

if __name__ == "__main__":
    lab = build_design(DESIGN)
    emit(lab, ROOT)
    print("generated", os.path.join(ROOT, "labs", lab.dirname))
