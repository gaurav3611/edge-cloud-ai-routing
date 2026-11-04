"""Integrity check of one raw suite: python analysis/validate_suite.py <suite>... Writes processed/validate_<suite>.json; exits 1 on any failure."""
import hashlib, json, math, os, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "suites"))
from defs import SUITES
CATS = ["LS<1", "LS>1", "FS<1", "FS>1"]


def replayed(suite):
    """Rows written before a simulator amendment stay valid only if a sample replays exactly on the current file (analysis/replay.py)."""
    p = os.path.join(ROOT, "processed", f"replay_{suite}.json")
    if not os.path.exists(p):
        return False
    r = json.load(open(p))
    return r["equal"] and r["sim_sha256"] == hashlib.sha256(open(os.path.join(ROOT, "sim", "ecsim_exact.py"), "rb").read()).hexdigest()


def check(suite):
    rows = [json.loads(l) for l in open(os.path.join(ROOT, "raw", suite + ".jsonl"))]
    plan = {__import__("common").key(d): d for d in SUITES[suite]()}
    keys = [r["_k"] for r in rows]
    bad = []
    if len(keys) != len(set(keys)): bad.append("duplicate rows")
    if set(keys) != set(plan): bad.append(f"planned {len(plan)}, stored {len(set(keys))}, missing {len(set(plan) - set(keys))}, extra {len(set(keys) - set(plan))}")
    nonfinite = range_bad = bal_bad = 0
    for r in rows:
        d = plan.get(r["_k"])
        if d and (r["seed"] if "seed" in r else d["seed"]) != d["seed"]: bad.append("seed mismatch")
        if any(isinstance(v, float) and not math.isfinite(v) for v in r.values()): nonfinite += 1
        if not all(0 <= r[k] <= 1 for k in ("cslo", "viol", "slo") if k in r): range_bad += 1
        c = [r[f"cslo_{x}"] for x in CATS if f"cslo_{x}" in r]
        if len(c) == 4 and abs(sum(c) / 4 - r["bcslo"]) > 1e-9: bal_bad += 1
    if nonfinite: bad.append(f"{nonfinite} rows with nan or inf")
    if range_bad: bad.append(f"{range_bad} rows out of range")
    if bal_bad: bad.append(f"{bal_bad} rows where bcslo is not the category mean")
    commits = sorted({r["commit"] for r in rows})
    for c in commits:
        if subprocess.run(["git", "-C", ROOT, "diff", "--quiet", c, "HEAD", "--", "sim"]).returncode and not replayed(suite): bad.append(f"sim differs at {c}, no passing replay")
    seeds = sorted({d["seed"] for d in plan.values()})
    return dict(suite=suite, rows=len(rows), planned=len(plan), seeds=[seeds[0], seeds[-1], len(seeds)], commits=commits, routers=len({d["name"] for d in plan.values()}), failures=bad)


if __name__ == "__main__":
    code = 0
    for s in sys.argv[1:]:
        r = check(s); print(r); code |= bool(r["failures"])
        json.dump(r, open(os.path.join(ROOT, "processed", f"validate_{s}.json"), "w"), indent=1)
    sys.exit(code)
