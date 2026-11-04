"""TRACE against each router by load on held-out main, per metric, Holm within load and metric. Writes processed/main_by_load.csv."""
import csv, json, math, os, sys
import numpy as np
from scipy import stats
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "analysis"))
from lib import holm
M = ("cslo", "bcslo", "cslo_LS<1", "cslo_LS>1", "cslo_FS<1", "cslo_FS>1")


def main():
    T = {}
    for l in open(os.path.join(ROOT, "raw", "main.jsonl")):
        r = json.loads(l); T.setdefault((r["name"], r["rho"]), {})[r["seed"]] = r
    assert all(len(v) == 30 for v in T.values())
    out = []
    for rho in sorted({k[1] for k in T}):
        t = T[("TRACE", rho)]; S = sorted(t)
        for m in M:
            names = [n for n, r in T if r == rho and n != "TRACE"]
            res = []
            for n in names:
                d = np.array([100 * (t[s][m] - T[(n, rho)][s][m]) for s in S])
                p = stats.wilcoxon(d).pvalue if np.any(d) else 1.0
                res.append((n, d.mean(), stats.t.ppf(.975, 29) * d.std(ddof=1) / math.sqrt(30), p))
            ph = holm(np.array([x[3] for x in res]))
            for (n, mean, ci, p), h in zip(res, ph):
                out.append(dict(rho=rho, metric=m, other=n, trace=round(100 * float(np.mean([t[s][m] for s in S])), 2), diff=round(mean, 2), ci=round(ci, 2), p=p, p_holm=float(h)))
    with open(os.path.join(ROOT, "processed", "main_by_load.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    print(len(out), "rows")


if __name__ == "__main__":
    main()
