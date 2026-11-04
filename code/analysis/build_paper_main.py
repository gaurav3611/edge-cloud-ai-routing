"""Paper material from held-out main only: tab_held, tab_diff, load and category figures, facts.json. Writes to processed/paper, never to paper/."""
import json, os, sys
import numpy as np
from scipy import stats
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "analysis"), os.path.join(ROOT, "baseline", "paper_snapshot", "scripts")]
from lib import load, compare, family
from figstyle_saa import plt, COL, sty
OUT = os.path.join(ROOT, "processed", "paper")
LOADS = (.5, .8, 1., 1.2)
ROWS = [("Local only", "Local"), ("EPARA-style", "EPARA-style"), ("JSQ, no trust", "JSQ oblivious"), ("Central, no trust", "Oracle unconstrained"),
        ("TF-RR", "TF-RR"), ("TF-P2C", "TF-P2C"), ("TF-JSQ", "TF-JSQ"), ("Soft-JSQ", "soft-JSQ"), ("Static, equal clearance", "Static eq"),
        ("Static, sized", "Static sized"), ("TF", "TF"), ("TRACE", "TRACE"), ("TRACE, fit 0", "TRACE fit0"), ("large-JSQ", "large_jsq"),
        ("Central, compliant", "Oracle compliant")]
CMP = [("TRACE $-$ TF", "TRACE", "TF"), ("TRACE $-$ TF-JSQ", "TRACE", "TF-JSQ"), ("TRACE $-$ sized static", "TRACE", "Static sized"),
       ("large-JSQ $-$ TRACE", "large_jsq", "TRACE"), ("large-JSQ $-$ TF-JSQ", "large_jsq", "TF-JSQ"), ("TRACE fit 0 $-$ TRACE", "TRACE fit0", "TRACE"),
       ("Central $-$ TRACE", "Oracle compliant", "TRACE")]
METS = [("cslo", "C-SLO"), ("bcslo", "Balanced"), ("wcslo", "Work")]
CATS = ["cslo_LS<1", "cslo_LS>1", "cslo_FS<1", "cslo_FS>1"]
FIG = [("TRACE", "trace", "TRACE"), ("TF-JSQ", "tf_jsq", "TF-JSQ"), ("large_jsq", "large", "large-JSQ"), ("Static sized", "static", "Static, sized"), ("Oracle compliant", "oracle_c", "Central dispatcher")]


def ci(x):
    return stats.t.ppf(.975, len(x) - 1) * np.std(x, ddof=1) / np.sqrt(len(x))


def wrap(cap, lab, spec, head, body):
    return "\n".join([r"\begin{table*}[!t]", r"\centering", r"\caption{" + cap + "}", r"\label{" + lab + "}", r"\footnotesize", r"\begin{adjustbox}{max width=\textwidth}",
                      r"\begin{tabular}{" + spec + "}", r"\toprule", head + r" \\", r"\midrule"] + body + [r"\bottomrule", r"\end{tabular}", r"\end{adjustbox}", r"\end{table*}", ""])


def held(d):
    body = []
    g = d[d.rho == .8]
    for lab, n in ROWS:
        x = g[g.name == n]; assert len(x) == 30
        cell = lambda m: f"{x[m].mean():.3f}±{ci(x[m].values):.3f}"
        body.append(f"{lab} & {cell('slo')} & {cell('cslo')} & {cell('bcslo')} & {cell('wcslo')} & {x.viol.mean():.3f} & {x['drop'].mean():.3f} & {x.hops.mean():.2f}" + r" \\")
    cap = (r"Routers at \(\rho=0.8\) on held-out seeds 8001--8030, \(T=420\) s, 20 burst cycles, exact event order (mean ± 95\% CI over 30 seeds). Cell intervals include topology variance, "
           r"so compare routers with the paired tests of Table~\ref{tab:diff}, not by overlap. Attainment, Viol. and Shed are fractions of requests; Fwd.: forwards per request.")
    return wrap(cap, "tab:held", "llllllll", "Router & SLO & C-SLO & Balanced & Work-weighted & Viol. & Shed & Fwd.", body)


def diff(d):
    res = {}
    for m, _ in METS:
        rows = []
        for lab, a, b in CMP:
            for r in LOADS:
                A = d[(d.name == a) & (d.rho == r)].sort_values("seed"); B = d[(d.name == b) & (d.rho == r)].sort_values("seed")
                assert (A.seed.values == B.seed.values).all()
                rows.append(dict(cmp=lab, rho=r, metric=m, **compare(A[m].values, B[m].values)))
        res[m] = family(rows)
    body = []
    for lab, _, _ in CMP:
        for i, (m, name) in enumerate(METS):
            f = res[m]; cells = []
            for r in LOADS:
                x = f[(f.cmp == lab) & (f.rho == r)].iloc[0]
                mark = "" if x.p_h < .05 else (r"\textsuperscript{e}" if x["tost1.0_h"] < .05 else r"\textsuperscript{n}")
                cells.append(f"{x['diff']:+.2f}±{x.ci95:.2f}{mark}")
            body.append(f"{lab if i == 0 else ''} & {name} & " + " & ".join(cells) + r" \\")
    cap = (r"Paired differences on held-out seeds, in points, ± 95\% CI, \(n=30\). Holm over 28 comparisons per metric. Unmarked: significant at \(p_H<0.05\). "
           r"\textsuperscript{e}: equivalent within 1 point by TOST. \textsuperscript{n}: neither.")
    return wrap(cap, "tab:diff", "llllll", r"Comparison & Metric & \(\rho=0.5\) & \(\rho=0.8\) & \(\rho=1.0\) & \(\rho=1.2\)", body), res


def figures(d):
    for s, m, y in zip("abc", ("cslo", "bcslo", "wcslo"), ("C-SLO", "balanced C-SLO", "work-weighted C-SLO")):
        f, a = plt.subplots(figsize=(2.0, 1.7))
        for n, k, l in FIG:
            g = d[d.name == n].groupby("rho")[m]
            a.errorbar(list(LOADS), [g.get_group(r).mean() for r in LOADS], yerr=[ci(g.get_group(r).values) for r in LOADS], label=l, **sty(k))
        a.set(xlabel="offered load ρ", ylabel=y, xticks=[.5, .8, 1., 1.2], ylim=(.4, 1.03))
        h, lab = a.get_legend_handles_labels(); a.legend(h, lab, loc="upper center", bbox_to_anchor=(.46, -.27), ncol=2, fontsize=8.5, handlelength=1.8, columnspacing=.8, labelspacing=.3, handletextpad=.5)
        f.savefig(os.path.join(OUT, f"fig_load_{s}.png"), bbox_inches="tight"); plt.close(f)
    for s, rho in zip("ab", (.8, 1.)):
        f, a = plt.subplots(figsize=(2.0, 1.7))
        for i, (n, k, l) in enumerate(FIG):
            g = d[(d.name == n) & (d.rho == rho)]; a.bar(np.arange(4) + (i - 2) * .16, [g[c].mean() for c in CATS], .14, color=COL[k], label=l)
        a.set(ylabel="C-SLO", xticks=range(4), xticklabels=["LS<1", "LS>1", "FS<1", "FS>1"]); a.tick_params(axis="x", labelsize=7.5); a.grid(axis="x", visible=False)
        h, lab = a.get_legend_handles_labels(); a.legend(h, lab, loc="upper center", bbox_to_anchor=(.46, -.27), ncol=2, fontsize=8.5, handlelength=1.8, columnspacing=.8, labelspacing=.3, handletextpad=.5)
        f.savefig(os.path.join(OUT, f"fig_category_{s}.png"), bbox_inches="tight"); plt.close(f)


def facts(d, res):
    F = dict(means={}, shed_by_sens={}, cmp={})
    for n in d.name.unique():
        for r in LOADS:
            g = d[(d.name == n) & (d.rho == r)]
            F["means"][f"{n}|{r}"] = {m: round(float(g[m].mean()), 4) for m in ("slo", "cslo", "bcslo", "wcslo", "drop", "hops", "viol", *CATS)}
    for n in ("TRACE", "TF-JSQ", "large_jsq", "Static sized", "Oracle compliant"):
        g = d[(d.name == n) & (d.rho == .8)]
        F["shed_by_sens"][n] = {s: round(float((g[f"dcs{s}_shed"] / g[[c for c in g.columns if c.startswith(f"dcs{s}_")]].fillna(0).sum(axis=1)).mean()), 4) for s in range(3)}
    for m, f in res.items():
        F["cmp"][m] = f[["cmp", "rho", "diff", "ci95", "p", "p_h", "tost1.0_h", "label", "shapiro_p"]].to_dict("records")
    F["shapiro_rejected"] = int(sum((f.shapiro_p < .05).sum() for f in res.values())); F["shapiro_total"] = int(sum(len(f) for f in res.values()))
    json.dump(F, open(os.path.join(OUT, "facts_main.json"), "w"), indent=0)
    return F


def main():
    os.makedirs(OUT, exist_ok=True)
    d = load("main")
    assert len(d) == 3240 and d[d.name == "TRACE"].viol.sum() == 0
    open(os.path.join(OUT, "tab_held.tex"), "w").write(held(d))
    t, res = diff(d)
    open(os.path.join(OUT, "tab_diff.tex"), "w").write(t)
    figures(d)
    F = facts(d, res)
    print("TRACE .8", F["means"]["TRACE|0.8"]); print("shed by sensitivity", F["shed_by_sens"]); print("Shapiro", F["shapiro_rejected"], "of", F["shapiro_total"])


if __name__ == "__main__":
    main()
