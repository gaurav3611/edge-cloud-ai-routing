"""Run one suite: python suites/run.py <suite> [--workers N]. Raw rows append to raw/<suite>.jsonl; finished runs are skipped by key."""
import argparse, json, os, sys, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RAW, job, key, commit
from defs import SUITES

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("suite"); ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    out = os.path.join(RAW, a.suite + ".jsonl"); c = commit()
    jobs = SUITES[a.suite]()
    assert len({key(d) for d in jobs}) == len(jobs), "duplicate jobs"
    done = {json.loads(l)["_k"] for l in open(out)} if os.path.exists(out) else set()
    todo = sorted([d for d in jobs if key(d) not in done], key=lambda d: -(d["N"] * d["T"]))
    print(a.suite, len(jobs), "runs;", len(todo), "to do; commit", c, time.ctime(), flush=True)
    with Pool(a.workers) as pool, open(out, "a") as f:
        for i, r in enumerate(pool.imap_unordered(job, todo, chunksize=1), 1):
            r["commit"] = c
            f.write(json.dumps(r, default=float) + "\n"); f.flush()
            if i % 200 == 0:
                print(i, "/", len(todo), time.ctime(), flush=True)
    print("done", a.suite, time.ctime(), flush=True)
