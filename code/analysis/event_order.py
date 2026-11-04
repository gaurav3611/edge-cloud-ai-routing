"""Event order, tracker A6 and R12: exact minus batch per router, load and metric, and what that does to router gaps.
Two sources only: `eventcmp` rows (seeds 5001-5020, both modes from one simulator) and seeds 4001-4030 (stored batch
`held.jsonl` against exact `bridge` rows). Never opens main. Differences are in points, paired by seed.
Run from anywhere: python analysis/event_order.py   Writes audit/followup/event_order_*.csv."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import load, compare, family, ROOT, CATS, MET

METRICS = ["cslo", "bcslo", "wcslo", "slo"] + ["cslo_" + c for c in CATS]
OUT = os.path.join(ROOT, "audit", "followup")
SEEDS = dict(held=range(4001, 4031), bridge=range(4001, 4031), eventcmp=range(5001, 5021))
HELD = os.path.join("..", "research_audit_20261031_142228", "12_variant_implementations", "raw", "held")   # relative to raw/


def guarded(df, source):
    """Refuse any row outside the seeds this analysis may read, so held-out 8001-8030 can never enter."""
    if not df.seed.isin(SEEDS[source]).all():
        raise ValueError(f"{source}: seeds outside {SEEDS[source]}")
    return df


def sources():
    """(label, batch rows, exact rows) for each comparison."""
    e = guarded(load("eventcmp"), "eventcmp")
    yield "eventcmp", e[e.event_mode == "batch"], e[e.event_mode == "exact"]
    yield "held_vs_bridge", guarded(load(HELD), "held"), guarded(load("bridge"), "bridge")


def wide(df, metric):
    return df.pivot_table(index=["rho", "seed"], columns="name", values=metric)


def shifts(batch, exact, metrics=METRICS):
    """Exact minus batch for every router, load and metric. Holm within each metric."""
    out = []
    for m in metrics:
        b, e = wide(batch, m), wide(exact, m); fam = []
        for rho in sorted(b.index.get_level_values("rho").unique()):
            for name in b.columns:
                x, y = e.loc[rho][name], b.loc[rho][name].reindex(e.loc[rho].index)
                fam.append(dict(metric=m, rho=rho, name=name, **compare(x, y)))
        out.append(family(fam))
    return pd.concat(out, ignore_index=True)


def gaps(batch, exact, ref="TRACE", metrics=tuple(MET)):
    """`ref` minus each router in both modes; `change` is the exact gap minus the batch gap, paired by seed."""
    out = []
    for m in metrics:
        b, e = wide(batch, m), wide(exact, m); fam = []
        for rho in sorted(b.index.get_level_values("rho").unique()):
            eb, bb = e.loc[rho], b.loc[rho].reindex(e.loc[rho].index)
            for name in b.columns.drop(ref):
                gb, ge = bb[ref] - bb[name], eb[ref] - eb[name]
                c = compare(ge, gb)
                fam.append(dict(metric=m, rho=rho, name=name, gap_batch=gb.mean() * 100, gap_exact=ge.mean() * 100,
                                change=c["diff"], ci95=c["ci95"], p=c["p"], **{k: c[k] for k in ("n", "tost0.5", "tost1.0")}))
        out.append(family(fam))
    g = pd.concat(out, ignore_index=True)
    g["sign_flip"] = np.sign(g.gap_batch) != np.sign(g.gap_exact)
    return g


if __name__ == "__main__":
    for label_, batch, exact in sources():
        s = shifts(batch, exact); g = gaps(batch, exact)
        s.to_csv(os.path.join(OUT, f"event_order_shift_{label_}.csv"), index=False, float_format="%.6g")
        g.to_csv(os.path.join(OUT, f"event_order_gaps_{label_}.csv"), index=False, float_format="%.6g")
        c = s[s.metric == "cslo"]; print(label_, "seeds", batch.seed.nunique(), "routers", batch.name.nunique())
        print(c.pivot_table(index="name", columns="rho", values="diff").round(2).to_string())
        print(s[s.metric.isin(MET)].groupby("metric")["diff"].agg(["min", "max"]).round(2).to_string())
        print(g[g.sign_flip][["metric", "rho", "name", "gap_batch", "gap_exact", "change", "label"]].round(2).to_string(index=False))
