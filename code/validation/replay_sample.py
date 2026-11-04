"""Replay 2 seeded rows per suite on the current simulator, one process at lowest priority; equality only. Writes replay_<suite>.json here."""
import hashlib, json, math, os, random, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "TRACE_revision"))
sys.path.insert(0, os.path.join(ROOT, "suites"))
from common import job
SKIP = {"dec_us", "dec_per_req_us", "_k", "wall_s", "commit"}
sha = hashlib.sha256(open(os.path.join(ROOT, "sim", "ecsim_exact.py"), "rb").read()).hexdigest()
for s in sys.argv[1:]:
    rows = open(os.path.join(ROOT, "raw", s + ".jsonl")).readlines()
    pick = [json.loads(l) for l in random.Random(s).sample(rows, 2)]
    pick = [o for o in pick if json.loads(o["_k"]).get("T", 0) <= 1200] or pick[:1]
    bad = []
    for o in pick:
        r = json.loads(json.dumps(job(json.loads(o["_k"]))))   # stored rows went through JSON: tuples become lists
        bad += [k for k, v in o.items() if k not in SKIP and r.get(k) != v and not (isinstance(v, float) and isinstance(r.get(k), float) and math.isclose(r[k], v, rel_tol=1e-12, abs_tol=1e-12))]
    out = dict(suite=s, rows=len(pick), equal=not bad, differing_fields=sorted(set(bad)), sim_sha256=sha)
    json.dump(out, open(f"replay_{s}.json", "w"), indent=1); print(out, flush=True)
