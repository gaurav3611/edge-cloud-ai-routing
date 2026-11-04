"""Prop 1 per topology on a seed range: which sensitivity-2 domains have no eligible server, for any router. Topology only, no outcome. python analysis/feasible_classes.py 8001 8030"""
import json, os, sys
import numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "sim"))
from ecsim_exact import build_topology


def main(a, b):
    empty, rows = 0, []
    for s in range(a, b + 1):
        t = build_topology(30, np.random.default_rng(s), clear_p=(0.30, 0.40, 0.30), n_dom=3)
        cap = [int(t["slots"][(t["clear"] >= 2) & (t["dom"] == d)].sum()) for d in range(3)]
        rows.append(dict(seed=s, c2_slots_by_domain=cap, c1_slots=int(t["slots"][t["clear"] >= 1].sum()), slots=int(t["slots"].sum())))
        empty += min(cap) == 0
    json.dump(rows, open(os.path.join(ROOT, "processed", f"feasible_{a}_{b}.json"), "w"))
    print(f"seeds {a}-{b}: {empty} of {b - a + 1} topologies have a domain with no clearance-2 slot; share of fleet at clearance>=1 {np.mean([r['c1_slots'] / r['slots'] for r in rows]):.3f}")


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
