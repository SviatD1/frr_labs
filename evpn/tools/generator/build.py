"""Regenerate the labs:  python build.py [ROOT] [lab numbers...]   (ROOT defaults to the evpn folder)"""
import sys, os, importlib, shutil
sys.path.insert(0, os.path.dirname(__file__))
from gen import emit
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
MODS = ["labs_basics", "labs_external", "labs_mh", "labs_service", "labs_clos", "labs_underlay", "labs_overlay", "labs_multi"]
only = sys.argv[2:] 
labs = []
for m in MODS:
    try:
        mod = importlib.import_module(m)
    except ModuleNotFoundError as e:
        if e.name == m: continue
        raise
    for f in mod.LABS + getattr(mod, "LABS_LATE", []):
        lab = f()
        if only and str(lab.num) not in only: continue
        d = os.path.join(ROOT, "labs", lab.dirname)
        shutil.rmtree(d, ignore_errors=True)
        emit(lab, ROOT)
        labs.append(lab)
        print("built", lab.dirname, list(lab.variants))
