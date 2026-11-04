"""Stage A: tuning-seed table per candidate, gamma and q* tests. Writes processed/stage_a_*.csv. Selection applies docs/acceptance_rules_v2.md."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from lib import load, compare, holm, MET, CATS, ROOT

MEMBERS = {"admission": ["adm_big.05", "adm_big.1", "adm_big.2", "adm_big.3", "adm_small.05", "adm_small.1", "adm_small.2", "large+adm_small.1", "large+adm_big.1"],
           "large": ["large_jsq", "large8", "large+frag", "frag"], "trunk": ["trunk.1", "trunk.25", "trunk.5", "trunk.25h"], "local_bf": ["local_bf"]}


def tune():
    d = load("tune")
    keys = ["cslo", "bcslo", "wcslo"]
    seed = d.groupby(["name", "seed"])[keys + ["viol"]].mean().reset_index()
    base = seed[seed.name == "TRACE"].set_index("seed")
    out = []
    for n, g in seed.groupby("name"):
        g = g.set_index("seed").loc[base.index]
        row = dict(name=n, viol=g.viol.max())
        for k in keys:
            c = compare(g[k], base[k]); row.update({k: g[k].mean() * 100, "d_" + k: c["diff"], "ci_" + k: c["ci95"]})
        worst = d[d.name == n].groupby("rho")[[f"cslo_{c}" for c in CATS]].mean() - d[d.name == "TRACE"].groupby("rho")[[f"cslo_{c}" for c in CATS]].mean()
        row["worst_cat"] = worst.min().min() * 100
        out.append(row)
    return pd.DataFrame(out).set_index("name")


def nondominated(t, names):
    x = t.loc[names, ["cslo", "bcslo", "wcslo"]]
    return [n for n in names if not any((x.loc[m] >= x.loc[n]).all() and (x.loc[m] > x.loc[n]).any() for m in names)]


def param(suite, base, grp):
    d = load(suite); rows = []
    for key, g in d.groupby(grp):
        p = g.pivot_table(index="seed", columns="name", values="cslo")
        for k in ("cslo", "bcslo"):
            p = g.pivot_table(index="seed", columns="name", values=k)
            for n in p.columns:
                if n != base:
                    rows.append(dict(group=key, name=n, metric=k, **compare(p[n], p[base])))
    r = pd.DataFrame(rows); r["p_h"] = holm(r.p.values)
    return r


if __name__ == "__main__":
    t = tune(); t.to_csv(os.path.join(ROOT, "processed", "stage_a_tune.csv"))
    pd.set_option("display.width", 200, "display.max_rows", 100, "display.max_columns", 20)
    print(t.round(2).sort_values("d_bcslo"))
    for f, m in MEMBERS.items():
        m = [x for x in m if x in t.index]; nd = nondominated(t, m)
        print(f, "nondominated", nd, "| best bal", t.loc[nd, "bcslo"].idxmax(), "| best cslo", t.loc[nd, "cslo"].idxmax())
    g = param("gamma", "g0.3", "rho"); g.to_csv(os.path.join(ROOT, "processed", "stage_a_gamma.csv"), index=False)
    print(g[["group", "name", "metric", "diff", "ci95", "p", "p_h"]].round(4))
    d = load("qstar"); print(d.groupby(["q_mode"] if "q_mode" in d else ["name"]).size().head())
    print(sorted(d.name.unique())[:30]); print(d.columns[:12].tolist()); print(d.groupby("exp").size())
    d = load("qstar", keep=("sens",)); d["hi"] = d.sens.map(lambda s: round(s[0], 2) if isinstance(s, (list, tuple)) else s)
    print(d.hi.value_counts().to_dict())
    rows = []
    for h, g in d.groupby("hi"):
        for k in ("cslo", "bcslo"):
            p = g.pivot_table(index="seed", columns="name", values=k)
            for n in p.columns:
                if n != "q0.3 count":
                    rows.append(dict(hi=h, name=n, metric=k, **compare(p[n], p["q0.3 count"])))
    q = pd.DataFrame(rows); q["p_h"] = holm(q.p.values); q.to_csv(os.path.join(ROOT, "processed", "stage_a_qstar.csv"), index=False)
    print("family", len(q), "better by >0.5 and Holm<.05:"); print(q[(q["diff"] > .5) & (q.p_h < .05)][["hi", "name", "metric", "diff", "ci95", "p_h"]].round(3).to_string())
    print(q[q.metric == "cslo"].pivot_table(index="name", columns="hi", values="diff").round(2).to_string())
    print(q[q.metric == "bcslo"].pivot_table(index="name", columns="hi", values="diff").round(2).to_string())
    print(d.groupby(["hi", "name"]).bf_switch.mean().unstack(0).round(1).filter(like="hyst", axis=0).to_string() if "bf_switch" in d else "")
