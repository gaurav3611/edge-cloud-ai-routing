"""Large-job diagnostic analysis (doc 05 decision rules, fixed 2026-11-03). Reads diag/raw only; prints markdown.

python analyse.py > ../05b_tables.md
"""
import gzip, json, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "TRACE_revision", "analysis"))
from lib import ci  # noqa: E402

RAW = os.path.join(HERE, "raw")
CATS = ("LS>1", "FS>1")
PROBES = ("P1 TRACE hsync0.1", "P2 TRACE no early stop", "P3 TRACE kmax4")


def load():
    d = pd.DataFrame([json.loads(x) for x in open(os.path.join(RAW, "diag.jsonl"))])
    assert len(d) == 210 and not d.duplicated("_k").any(), len(d)
    assert (d.groupby(["name", "rho"]).seed.nunique() == 10).all()
    return d.sort_values(["name", "rho", "seed"])


def arm(d, n, rho, col):
    return d[(d.name == n) & (d.rho == rho)].sort_values("seed")[col].to_numpy() * 100


def md(t):
    rows = [list(map(str, t.columns))] + [list(map(str, r)) for r in t.itertuples(index=False)]
    return "\n".join("| " + " | ".join(r) + " |" for r in rows[:1] + [["---"] * len(t.columns)] + rows[1:])


def fmt(x):
    return f"{x.mean():+.2f} ± {ci(x):.2f}"


def closure(d, cat):
    """Share of the TF-JSQ minus TRACE gap that each probe closes, per load and pooled over loads."""
    col = f"cslo_{cat}"
    rows = []
    for rho in sorted(d.rho.unique()):
        tr, tf = arm(d, "A1 TRACE", rho, col), arm(d, "A2 TF-JSQ", rho, col)
        gap = tf - tr
        row = {"rho": rho, "TRACE": f"{tr.mean():.2f}", "TF-JSQ": f"{tf.mean():.2f}", "gap": fmt(gap)}
        for p in PROBES:
            x = arm(d, p, rho, col) - tr
            row[p[:2]] = f"{fmt(x)} ({100 * x.mean() / gap.mean():.0f}%)" if gap.mean() > 0 else fmt(x)
        rows.append(row)
    pool = {}
    tr = np.concatenate([arm(d, "A1 TRACE", r, col) for r in sorted(d.rho.unique())])
    tf = np.concatenate([arm(d, "A2 TF-JSQ", r, col) for r in sorted(d.rho.unique())])
    for p in PROBES:
        x = np.concatenate([arm(d, p, r, col) for r in sorted(d.rho.unique())]) - tr
        pool[p[:2]] = 100 * x.mean() / (tf - tr).mean()
    return pd.DataFrame(rows), pool


def cost(d):
    """C-SLO and balanced change of each probe and comparison arm against TRACE, paired on seed."""
    rows = []
    for rho in sorted(d.rho.unique()):
        for n in ("A2 TF-JSQ", "A3 large_jsq", "A4 Oracle compliant") + PROBES:
            row = {"rho": rho, "arm": n}
            for m in ("cslo", "bcslo", "cslo_LS>1", "cslo_FS>1"):
                row[m] = fmt(arm(d, n, rho, m) - arm(d, "A1 TRACE", rho, m))
            rows.append(row)
    return pd.DataFrame(rows)


def requests(row):
    with gzip.open(os.path.join(RAW, "req", row.req_file + ".jsonl.gz"), "rt") as f:
        for x in f:
            yield json.loads(x)


def per_request(d, name, cat):
    """Capacity and estimation rules on one arm's logged requests of one category, per load."""
    out = []
    for rho in sorted(d.rho.unique()):
        shed = cap = recov = 0
        reason = {"hop limit": 0, "early stop": 0, "no eligible": 0}
        failed = over = 0
        for row in d[(d.name == name) & (d.rho == rho)].itertuples():
            for q in requests(row):
                if q["cat"] != cat:
                    continue
                h = q["hops"]
                for a, b in zip(h, h[1:]):   # a pick followed by the local try at the chosen peer
                    if "pick_at" in a and a["p"] is not None and "local_ok" in b and b["at"] == a["p"] and not b["local_ok"]:
                        failed += 1
                        over += int("view" in a and a["view"] >= q["m"] and a["true"] < q["m"])
                if q["dropped"]:
                    shed += 1; recov += q.get("recov", False); reason[q["reason"]] += 1
                    picks = [x for x in h if "pick_at" in x]
                    cap += int(all(x["max_true"] < q["m"] for x in picks))   # no eligible node had m free slots at any pick
        out.append({"rho": rho, "shed": shed,
                    "no eligible node with m free slots": f"{100 * cap / max(shed, 1):.1f}%",
                    "recoverable (_shed_check)": f"{100 * recov / max(shed, 1):.1f}%",
                    **{k: f"{100 * v / max(shed, 1):.1f}%" for k, v in reason.items()},
                    "failed hops": failed,
                    "view fits, truth does not": f"{100 * over / max(failed, 1):.1f}%"})
    return pd.DataFrame(out)


def main():
    d = load()
    print(f"Rows: {len(d)}; seeds {d.seed.min()}-{d.seed.max()}; loads {sorted(d.rho.unique())}; violations {d.viol.sum()}\n")
    for cat in CATS:
        t, pool = closure(d, cat)
        print(f"## Gap closure, {cat} attainment (points; probe minus TRACE, paired, 95% CI, n=10; % of mean gap)\n")
        print(md(t))
        print("\nPooled over loads, share of gap closed: " + ", ".join(f"{k} {v:.0f}%" for k, v in pool.items()) + "\n")
    print("## Change against TRACE (points, paired, 95% CI, n=10)\n")
    print(md(cost(d)) + "\n")
    for cat in CATS:
        for name in ("A1 TRACE", "A2 TF-JSQ"):
            print(f"## Sheds and hops, {name}, {cat}\n")
            print(md(per_request(d, name, cat)) + "\n")


if __name__ == "__main__":
    main()
