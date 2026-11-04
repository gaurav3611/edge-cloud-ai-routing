"""Replay a seeded sample of stored rows on the current simulator: python analysis/replay.py <suite>... [--n 4]. Writes processed/replay_<suite>.json, equality only, no metric values."""
import argparse, hashlib, json, math, os, random, sys
from multiprocessing import Pool
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "suites"))
from common import job
SKIP = {"dec_us", "dec_per_req_us", "_k", "wall_s", "commit"}


def same(o):
    r = job(json.loads(o["_k"]))
    return [k for k, v in o.items() if k not in SKIP and r.get(k) != v and not (isinstance(v, float) and isinstance(r.get(k), float) and math.isclose(r[k], v, rel_tol=1e-12, abs_tol=1e-12))]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("suites", nargs="+"); ap.add_argument("--n", type=int, default=4)
    a = ap.parse_args()
    sha = hashlib.sha256(open(os.path.join(ROOT, "sim", "ecsim_exact.py"), "rb").read()).hexdigest()
    with Pool(8) as pool:
        for s in a.suites:
            rows = open(os.path.join(ROOT, "raw", s + ".jsonl")).readlines()
            pick = [json.loads(l) for l in random.Random(s).sample(rows, a.n)]
            bad = pool.map(same, pick)
            out = dict(suite=s, rows=len(pick), equal=not any(bad), differing_fields=sorted({k for b in bad for k in b}), sim_sha256=sha)
            json.dump(out, open(os.path.join(ROOT, "processed", f"replay_{s}.json"), "w"), indent=1); print(out, flush=True)
