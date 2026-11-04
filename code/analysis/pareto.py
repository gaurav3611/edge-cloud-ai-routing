"""Pareto frontiers per load: python analysis/pareto.py <suite> [outdir]. Three figures, one per metric pair, 95% CI whiskers. Frontier uses zero-violation routers only."""
import itertools, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, matplotlib
from scipy import stats
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from lib import load, MET, ROOT
plt.rcParams.update({"font.size": 8, "axes.grid": True, "grid.alpha": .3, "savefig.dpi": 300, "axes.linewidth": 1.0})
KEYS = list(MET)


def points(d):
    g = d.groupby(["rho", "name"])
    p = g[KEYS].mean() * 100
    ci = g[KEYS].agg(lambda x: stats.t.ppf(.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))) * 100
    p.columns = KEYS; ci.columns = ["ci_" + k for k in KEYS]
    out = pd.concat([p, ci], axis=1).reset_index()
    out["viol"] = g.viol.max().values
    return out


def front(t, x, y):
    """Names not dominated on (x, y), sorted by x."""
    ok = t[t.viol == 0]
    keep = [i for i, a in ok.iterrows() if not ((ok[x] >= a[x]) & (ok[y] >= a[y]) & ((ok[x] > a[x]) | (ok[y] > a[y]))).any()]
    return ok.loc[keep].sort_values(x)


def plot(p, x, y, out):
    rhos = sorted(p.rho.unique())
    f, ax = plt.subplots(2, 2, figsize=(7.2, 6.2))
    for a, r in zip(ax.flat, rhos):
        t = p[p.rho == r]; fr = front(t, x, y)
        o = t[~t.name.isin(fr.name) & (t.viol == 0)]
        a.errorbar(o[x], o[y], xerr=o["ci_" + x], yerr=o["ci_" + y], fmt="o", ms=3, color="#999999", lw=.6)
        v = t[t.viol > 0]
        a.scatter(v[x], v[y], facecolors="none", edgecolors="#e15759", s=14, lw=.7)
        a.errorbar(fr[x], fr[y], xerr=fr["ci_" + x], yerr=fr["ci_" + y], fmt="-o", ms=3.5, color="#4e79a7", lw=1)
        b = t[t.name == "TRACE"]
        a.scatter(b[x], b[y], color="#1b9e77", s=34, zorder=5)
        for _, q in pd.concat([fr, b]).drop_duplicates("name").iterrows():
            a.annotate(q["name"], (q[x], q[y]), xytext=(3, 3), textcoords="offset points", fontsize=6)
        a.set_title(f"$\\rho$ = {r}"); a.set_xlabel(MET[x] + " (%)"); a.set_ylabel(MET[y] + " (%)")
    f.tight_layout(); f.savefig(out, bbox_inches="tight"); plt.close(f)


if __name__ == "__main__":
    suite = sys.argv[1]; outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "figures")
    p = points(load(suite)); p.to_csv(os.path.join(ROOT, "processed", f"pareto_{suite}.csv"), index=False)
    rows = []
    for x, y in itertools.combinations(KEYS, 2):
        plot(p, x, y, os.path.join(outdir, f"fig_pareto_{x}_{y}.png"))
        for r, t in p.groupby("rho"):
            rows += [dict(rho=r, x=x, y=y, name=n) for n in front(t, x, y).name]
    pd.DataFrame(rows).to_csv(os.path.join(ROOT, "processed", f"pareto_front_{suite}.csv"), index=False)
    print(pd.DataFrame(rows).groupby(["x", "y", "rho"]).name.apply(", ".join).to_string())
