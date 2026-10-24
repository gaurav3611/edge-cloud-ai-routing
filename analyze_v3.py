"""
analyze_v3.py - statistics, figures and tables for the revised paper.
Reads runs_v3.jsonl; writes STATS_v3.md, figures_v3/*.png, tables_v3/*.md, numbers_v3.json.
Paired Wilcoxon signed-rank tests over seeds; Holm correction within each declared family.
"""
import json, os
import numpy as np, pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.makedirs("figures_v3", exist_ok=True)
os.makedirs("tables_v3", exist_ok=True)
d = pd.DataFrame([json.loads(l) for l in open("runs_v3.jsonl")])
OUT = []
NUM = {}

NAMES = {"local": "Local only", "rr": "Round-robin", "rr_g": "RR, shared pointer", "epara": "EPARA-style",
         "oracle_u": "Central oracle (no trust)", "tf": "TF", "trace": "TRACE", "tera": "TF+best-fit (always)",
         "tf_rr": "TF-RR", "tf_p2c": "TF-P2C", "tf_jsq": "TF-JSQ", "static": "Static pools",
         "oracle_c": "Central oracle (trust)", "ew": "TF+EW", "eb": "TF+EB", "ec": "TF+EC",
         "ewd": "TF+EW-bounded", "ef": "TF+EF (oracle feas.)"}


def ci(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return float(np.mean(x)) if len(x) else np.nan, 0.0
    return float(x.mean()), float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))


def fmt(m, h, k=3):
    return f"{m:.{k}f}±{h:.{k}f}"


class Family:
    """Collect paired comparisons, then apply Holm."""
    def __init__(self, name):
        self.name, self.rows = name, []

    def add(self, label, a, b):
        df = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
        diff = df["a"] - df["b"]
        m, h = ci(diff)
        if (diff != 0).sum() == 0:
            p = 1.0
        else:
            p = float(stats.wilcoxon(df["a"], df["b"]).pvalue)
        self.rows.append(dict(label=label, m=m, h=h, p=p, n=len(diff), wins=float((diff > 0).mean())))

    def done(self):
        k = len(self.rows)
        order = np.argsort([r["p"] for r in self.rows])
        adj, run = [0] * k, 0.0
        for rank, i in enumerate(order):
            run = max(run, min(1.0, (k - rank) * self.rows[i]["p"]))
            adj[i] = run
        OUT.append(f"\n### Family: {self.name} (Holm over {k} tests)\n")
        for r, a in zip(self.rows, adj):
            r["p_holm"] = a
            OUT.append(f"- {r['label']}: {r['m']:+.3f} ± {r['h']:.3f} (p={r['p']:.2g}, Holm p={a:.2g}, "
                       f"n={r['n']}, wins {r['wins']:.0%})")
            NUM[f"{self.name}|{r['label']}"] = r
        return self.rows


def piv(sub, metric, idx="seed", col="pol"):
    return sub.pivot_table(index=idx, columns=col, values=metric)


def table_md(name, header, rows):
    s = "| " + " | ".join(header) + " |\n|" + "---|" * len(header) + "\n"
    for r in rows:
        s += "| " + " | ".join(str(x) for x in r) + " |\n"
    open(f"tables_v3/{name}.md", "w").write(s)
    return s


plt.rcParams.update({"font.size": 8, "axes.grid": True, "grid.alpha": 0.3, "figure.dpi": 300,
                     "legend.fontsize": 7, "axes.titlesize": 8})
COL = {"local": "#999999", "rr": "#b07aa1", "rr_g": "#d4a6c8", "epara": "#e15759", "oracle_u": "#ff9d9a",
       "tf": "#4e79a7", "trace": "#1b9e77", "tera": "#76b7b2", "tf_rr": "#9c755f", "tf_p2c": "#f28e2b",
       "tf_jsq": "#edc948", "static": "#7f7f7f", "oracle_c": "#000000", "ew": "#e15759", "eb": "#f28e2b",
       "ec": "#b07aa1", "ewd": "#edc948", "ef": "#59a14f"}
MK = {"oracle_c": "s", "oracle_u": "s", "trace": "o", "tf": "^"}


def line(ax, sub, x, metric, pols, xlabel=None, ls=None):
    for p in pols:
        s = sub[sub.pol == p]
        if s.empty:
            continue
        g = s.groupby(x)[metric]
        xs = sorted(g.groups)
        mh = [ci(g.get_group(v)) for v in xs]
        ax.errorbar(xs, [a for a, _ in mh], yerr=[b for _, b in mh], label=NAMES.get(p, p),
                    color=COL.get(p), marker=MK.get(p, "."), ms=3, lw=1.2 if p != "trace" else 2,
                    capsize=2, ls=(ls or {}).get(p, "--" if p.startswith("oracle") else "-"))
    if xlabel:
        ax.set_xlabel(xlabel)


# ======================= A: load =======================
A = d[d.exp == "A_load"]
if len(A):
    pols = ["local", "rr", "epara", "oracle_u", "tf_rr", "tf_p2c", "tf_jsq", "static", "tf", "trace", "oracle_c"]
    rows = []
    a8 = A[A.rho == 0.8]
    for p in pols + ["rr_g"]:
        s = a8[a8.pol == p]
        if s.empty:
            continue
        rows.append([NAMES[p], fmt(*ci(s.slo)), fmt(*ci(s.cslo)), fmt(*ci(s.bcslo)), fmt(*ci(s.viol)),
                     f"{ci(s.cgoodput)[0]:.0f}±{ci(s.cgoodput)[1]:.0f}", f"{s.hops.mean():.2f}",
                     f"{s.drop.mean():.3f}", f"{s.dec_us.mean():.1f}"])
    table_md("tab_main", ["Policy", "SLO", "C-SLO", "C-SLO_bal", "Viol.", "C-goodput", "Fwd.", "Shed", "µs/dec."], rows)
    for rho in sorted(A.rho.unique()):
        s = A[A.rho == rho]
        for p in s.pol.unique():
            q = s[s.pol == p]
            NUM[f"A|{rho}|{p}"] = {k: ci(q[k])[0] for k in ["slo", "cslo", "bcslo", "viol", "cgoodput", "goodput", "hops", "drop", "dec_us"]}
            NUM[f"A|{rho}|{p}|ci"] = {k: ci(q[k])[1] for k in ["slo", "cslo", "bcslo", "viol", "cgoodput"]}
    # primary family: TRACE vs each compliant baseline at each load (C-SLO)
    fam = Family("A_primary_cslo")
    for rho in sorted(A.rho.unique()):
        P = piv(A[A.rho == rho], "cslo")
        for b in ["epara", "tf_rr", "tf_p2c", "tf_jsq", "static", "tf"]:
            if b in P and "trace" in P:
                fam.add(f"TRACE - {NAMES[b]} @rho={rho}", P["trace"], P[b])
    fam.done()
    fam = Family("A_balanced")
    for rho in sorted(A.rho.unique()):
        P = piv(A[A.rho == rho], "bcslo")
        for b in ["epara", "tf_rr", "tf_p2c", "tf_jsq", "static", "tf"]:
            if b in P and "trace" in P:
                fam.add(f"TRACE - {NAMES[b]} @rho={rho} (balanced)", P["trace"], P[b])
    fam.done()
    fam = Family("A_reference")
    for rho in sorted(A.rho.unique()):
        P = piv(A[A.rho == rho], "cslo")
        Pr = piv(A[A.rho == rho], "slo")
        if "oracle_c" in P:
            fam.add(f"oracle_c - TRACE C-SLO @rho={rho}", P["oracle_c"], P["trace"])
        if "oracle_u" in Pr and "oracle_c" in P:
            fam.add(f"cost of compliance (oracle_u raw - oracle_c) @rho={rho}", Pr["oracle_u"], P["oracle_c"])
        if "epara" in Pr:
            fam.add(f"EPARA raw - TRACE @rho={rho}", Pr["epara"], P["trace"])
        if "rr_g" in P:
            fam.add(f"rr_g - rr C-SLO @rho={rho}", P["rr_g"], P["rr"])
    fam.done()
    fig, ax = plt.subplots(1, 4, figsize=(7.2, 2.1))
    sel = ["epara", "oracle_u", "tf_rr", "tf_p2c", "tf_jsq", "static", "tf", "trace", "oracle_c"]
    line(ax[0], A, "rho", "cslo", sel, "offered load ρ"); ax[0].set_title("(a) compliant SLO attainment")
    line(ax[1], A, "rho", "bcslo", sel, "offered load ρ"); ax[1].set_title("(b) category-balanced")
    line(ax[2], A, "rho", "slo", ["epara", "oracle_u", "tf", "trace", "oracle_c"], "offered load ρ"); ax[2].set_title("(c) raw SLO attainment")
    line(ax[3], A, "rho", "viol", ["local", "rr", "epara", "oracle_u", "trace"], "offered load ρ"); ax[3].set_title("(d) trust-violation rate")
    h, l = ax[0].get_legend_handles_labels()
    h2, l2 = ax[3].get_legend_handles_labels()
    for hh, ll in zip(h2, l2):
        if ll not in l:
            h.append(hh); l.append(ll)
    fig.legend(h, l, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, -0.16))
    fig.tight_layout(); fig.savefig("figures_v3/fig_load.png", bbox_inches="tight"); plt.close(fig)

# ======================= Tuning =======================
T_ = d[d.exp == "T_tune"]
if len(T_):
    P = T_.pivot_table(index=["sens_hi", "seed"], columns="gamma", values="cslo")
    G = P.sub(P[1.0], axis=0).groupby("sens_hi").mean()
    rows = []
    for g in [0.5, 0.3, 0.1]:
        rows.append([f"{g}"] + [f"{G.loc[s, g]:+.3f}" for s in G.index] + [f"{G[g].mean():+.4f}"])
    table_md("tab_tune", ["γ"] + [f"{int(s*100)}%" for s in G.index] + ["mean"], rows)
    NUM["tune"] = {f"{g}|{s}": float(G.loc[s, g]) for g in [0.5, 0.3, 0.1] for s in G.index}

# ======================= C: sensitive share =======================
C = d[d.exp == "C_sens"]
if len(C):
    fam = Family("C_bestfit")
    for hi in sorted(C.sens_hi.unique()):
        P = piv(C[C.sens_hi == hi], "cslo")
        fam.add(f"TRACE - TF @share={hi}", P["trace"], P["tf"])
        fam.add(f"always-best-fit - TF @share={hi}", P["tera"], P["tf"])
    fam.done()
    fam = Family("C_bestfit_bal")
    for hi in sorted(C.sens_hi.unique()):
        P = piv(C[C.sens_hi == hi], "bcslo")
        fam.add(f"TRACE - TF balanced @share={hi}", P["trace"], P["tf"])
    fam.done()
    fam = Family("C_vs_baselines")
    for hi in sorted(C.sens_hi.unique()):
        P = piv(C[C.sens_hi == hi], "cslo"); Pr = piv(C[C.sens_hi == hi], "slo")
        fam.add(f"TRACE - EPARA (compliant) @share={hi}", P["trace"], P["epara"])
        fam.add(f"TRACE - Static @share={hi}", P["trace"], P["static"])
        fam.add(f"oracle_c - TRACE @share={hi}", P["oracle_c"], P["trace"])
        fam.add(f"cost of compliance oracle_u raw - oracle_c @share={hi}", Pr["oracle_u"], P["oracle_c"])
        fam.add(f"cost EPARA raw - TRACE @share={hi}", Pr["epara"], P["trace"])
    fam.done()
    for hi in sorted(C.sens_hi.unique()):
        for p in C.pol.unique():
            q = C[(C.sens_hi == hi) & (C.pol == p)]
            NUM[f"C|{hi}|{p}"] = {k: ci(q[k])[0] for k in ["slo", "cslo", "bcslo", "viol"]}
    fig, ax = plt.subplots(1, 3, figsize=(7.2, 2.2))
    line(ax[0], C, "sens_hi", "slo", ["epara", "oracle_u", "static", "tf", "trace", "oracle_c"], "share of sensitive requests")
    ax[0].set_title("(a) raw SLO attainment")
    line(ax[1], C, "sens_hi", "cslo", ["epara", "oracle_u", "static", "tf", "trace", "oracle_c"], "share of sensitive requests")
    ax[1].set_title("(b) compliant SLO attainment")
    P = C.pivot_table(index=["sens_hi", "seed"], columns="pol", values="cslo")
    for p, lab in [("trace", "TRACE (adaptive)"), ("tera", "best-fit always on")]:
        dd = (P[p] - P["tf"]).groupby(level=0)
        xs = sorted(dd.groups)
        mh = [ci(dd.get_group(v)) for v in xs]
        ax[2].errorbar(xs, [a for a, _ in mh], yerr=[b for _, b in mh], label=lab, marker="o", ms=3, capsize=2,
                       color=COL["trace"] if p == "trace" else COL["tera"])
    ax[2].axhline(0, color="k", lw=0.6); ax[2].set_xlabel("share of sensitive requests")
    ax[2].set_title("(c) gain over TF (paired)"); ax[2].legend()
    h, l = ax[1].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout(); fig.savefig("figures_v3/fig_sens.png", bbox_inches="tight"); plt.close(fig)

# ======================= K: correlation =======================
K = d[d.exp == "K_corr"]
if len(K):
    for lam in sorted(K.corr.unique()):
        for p in K.pol.unique():
            q = K[(K.corr == lam) & (K.pol == p)]
            NUM[f"K|{lam}|{p}"] = {k: ci(q[k])[0] for k in ["slo", "cslo", "viol"]}
            NUM[f"K|{lam}|{p}|ci"] = {k: ci(q[k])[1] for k in ["slo", "cslo", "viol"]}
    fam = Family("K_corr")
    for lam in sorted(K.corr.unique()):
        P = piv(K[K.corr == lam], "cslo"); Pr = piv(K[K.corr == lam], "slo")
        fam.add(f"TRACE - EPARA compliant @lambda={lam}", P["trace"], P["epara"])
        fam.add(f"EPARA raw - TRACE @lambda={lam}", Pr["epara"], P["trace"])
        fam.add(f"oracle_c - TRACE @lambda={lam}", P["oracle_c"], P["trace"])
        fam.add(f"cost of compliance oracle_u raw - oracle_c @lambda={lam}", Pr["oracle_u"], P["oracle_c"])
    fam.done()
    fig, ax = plt.subplots(1, 2, figsize=(4.6, 2.1))
    line(ax[0], K, "corr", "viol", ["local", "epara", "oracle_u"], "origin–sensitivity alignment λ")
    ax[0].set_title("(a) violation rate (trust-oblivious)"); ax[0].legend()
    line(ax[1], K, "corr", "cslo", ["epara", "oracle_u", "tf", "trace", "oracle_c"], "origin–sensitivity alignment λ")
    ax[1].set_title("(b) compliant SLO attainment"); ax[1].legend(fontsize=6)
    fig.tight_layout(); fig.savefig("figures_v3/fig_corr.png", bbox_inches="tight"); plt.close(fig)

# ======================= O: overload =======================
O = d[d.exp == "O_over"]
if len(O):
    O = O.copy()
    O["fb"] = O.get("fallback", pd.Series(index=O.index, dtype=object)).fillna("none")
    rows = []
    for p, fb, lab in [("epara", "none", "EPARA-style"), ("tf_rr", "none", "TF-RR"), ("tf_p2c", "none", "TF-P2C"),
                       ("tf", "none", "TF"), ("tf", "uniform", "TF + uniform probe"), ("tf", "p2c", "TF + P2C fallback"),
                       ("trace", "none", "TRACE"), ("oracle_c", "none", "Central oracle (trust)")]:
        r = [lab]
        for rho in [1.0, 1.2]:
            for late in ["serve", "drop"]:
                if late == "drop" and fb == "none":
                    q = A[(A.rho == rho) & (A.pol == p)]
                else:
                    q = O[(O.rho == rho) & (O.pol == p) & (O.fb == fb) & (O.late == late)]
                r.append(fmt(*ci(q.cslo)) if len(q) else "–")
                if len(q):
                    NUM[f"O|{rho}|{p}|{fb}|{late}"] = ci(q.cslo)
        rows.append(r)
    table_md("tab_over", ["Policy", "ρ=1.0 serve late", "ρ=1.0 shed", "ρ=1.2 serve late", "ρ=1.2 shed"], rows)
    fam = Family("O_shedding")
    for rho in [1.0, 1.2]:
        for p in ["epara", "tf_rr", "tf_p2c", "tf", "trace", "oracle_c"]:
            a = A[(A.rho == rho) & (A.pol == p)].set_index("seed").cslo
            b = O[(O.rho == rho) & (O.pol == p) & (O.fb == "none") & (O.late == "serve")].set_index("seed").cslo
            if len(a) and len(b):
                fam.add(f"shed - serve-late {NAMES[p]} @rho={rho}", a, b)
        for fb in ["uniform", "p2c"]:
            a = O[(O.rho == rho) & (O.pol == "tf") & (O.fb == fb) & (O.late == "serve")].set_index("seed").cslo
            b = O[(O.rho == rho) & (O.pol == "tf") & (O.fb == "none") & (O.late == "serve")].set_index("seed").cslo
            fam.add(f"TF {fb} fallback - TF (serve-late) @rho={rho}", a, b)
            a = O[(O.rho == rho) & (O.pol == "tf") & (O.fb == fb) & (O.late == "drop")].set_index("seed").cslo
            b = A[(A.rho == rho) & (A.pol == "tf")].set_index("seed").cslo
            fam.add(f"TF {fb} fallback - TF (shed) @rho={rho}", a, b)
    fam.done()

# ======================= E: staleness =======================
E = d[d.exp == "E_stale"]
if len(E):
    fig, ax = plt.subplots(1, 2, figsize=(4.6, 2.1))
    for i, rho in enumerate([0.8, 1.0]):
        line(ax[i], E[E.rho == rho], "hsync", "cslo", ["epara", "tf_jsq", "tf_p2c", "tf", "trace"], "sync period H (s)")
        ax[i].set_xscale("log"); ax[i].set_title(f"({'ab'[i]}) ρ={rho}")
    ax[1].legend(fontsize=6)
    fig.tight_layout(); fig.savefig("figures_v3/fig_stale.png", bbox_inches="tight"); plt.close(fig)
    fam = Family("E_stale")
    for rho in [0.8, 1.0]:
        for p in ["tf", "trace", "tf_jsq", "tf_p2c"]:
            P = piv(E[(E.rho == rho) & (E.pol == p)], "cslo", col="hsync")
            fam.add(f"{NAMES[p]} H=0.1 - H=2 @rho={rho}", P[0.1], P[2.0])
            fam.add(f"{NAMES[p]} H=1 - H=2 @rho={rho}", P[1.0], P[2.0])
        P = piv(E[(E.rho == rho) & (E.hsync == 0.1)], "cslo")
        fam.add(f"TRACE - TF-JSQ @H=0.1 rho={rho}", P["trace"], P["tf_jsq"])
        P = piv(E[(E.rho == rho) & (E.hsync == 2.0)], "cslo")
        fam.add(f"TRACE - TF-JSQ @H=2 rho={rho}", P["trace"], P["tf_jsq"])
    fam.done()
    for k, g in E.groupby(["rho", "hsync", "pol"]):
        NUM[f"E|{k[0]}|{k[1]}|{k[2]}"] = {m: ci(g[m])[0] for m in ["cslo", "hops"]}

# ======================= R: placement / cloud =======================
R = d[d.exp == "R_cloud"]
if len(R):
    rows = []
    for pl in [1.0, 0.5]:
        for cl in [False, True]:
            s = R[(R.place == pl) & (R.cloud_on == cl)]
            r = [f"{int(pl*100)}%", "yes" if cl else "no"]
            for p in ["epara", "tf", "trace"]:
                q = s[s.pol == p]
                r.append(fmt(*ci(q.cslo)))
                NUM[f"R|{pl}|{cl}|{p}"] = {m: ci(q[m])[0] for m in ["slo", "cslo", "viol", "cloud"]}
            r.append(f"{s[s.pol == 'trace'].cloud.mean():.3f}")
            r.append(f"{s[s.pol == 'epara'].viol.mean():.3f}")
            rows.append(r)
    table_md("tab_cloud", ["Placement", "Cloud", "EPARA-style C-SLO", "TF C-SLO", "TRACE C-SLO", "TRACE cloud share", "EPARA viol."], rows)
    fam = Family("R_cloud")
    for pl in [1.0, 0.5]:
        for cl in [False, True]:
            P = piv(R[(R.place == pl) & (R.cloud_on == cl)], "cslo")
            fam.add(f"TRACE - EPARA place={pl} cloud={cl}", P["trace"], P["epara"])
    fam.done()

# ======================= V: variance decomposition =======================
V = d[d.exp == "V_var"]
if len(V):
    OUT.append("\n### Variance decomposition (10 topologies x 5 workloads)\n")
    for p in ["epara", "tf", "trace"]:
        q = V[V.pol == p]
        g = q.groupby("seed").cslo
        within = g.var(ddof=1).mean()
        between = g.mean().var(ddof=1) - within / 5
        icc = max(between, 0) / (max(between, 0) + within)
        NUM[f"V|{p}"] = dict(icc=icc, sd_between=np.sqrt(max(between, 0)), sd_within=np.sqrt(within))
        OUT.append(f"- {p}: topology share of variance (ICC) {icc:.2f}; sd between topologies "
                   f"{np.sqrt(max(between,0)):.3f}, within {np.sqrt(within):.3f}")
    q = V.pivot_table(index=["seed", "wseed"], columns="pol", values="cslo")
    gain = (q["trace"] - q["epara"]).groupby(level=0).mean()
    gv = (q["trace"] - q["epara"]).groupby(level=0)
    within = gv.var(ddof=1).mean(); between = gain.var(ddof=1) - within / 5
    NUM["V|gain"] = dict(icc=max(between, 0) / (max(between, 0) + within), min=float(gain.min()), max=float(gain.max()))
    OUT.append(f"- TRACE-EPARA gain per topology: min {gain.min():+.3f}, max {gain.max():+.3f}; "
               f"topology ICC of gain {NUM['V|gain']['icc']:.2f}")
    # gain vs eligible-capacity share for s=2 requests
    from ecsim import build_topology
    xs, ys = [], []
    for t in range(1, 11):
        tp = build_topology(30, np.random.default_rng(t))
        S = tp["slots"]
        e2 = np.mean([(S * ((tp["clear"] >= 2) & (tp["dom"] == dd))).sum() / S.sum() for dd in range(3)])
        xs.append(e2); ys.append(gain.loc[t])
    rr_ = stats.spearmanr(xs, ys)
    NUM["V|corr_e2"] = dict(rho=float(rr_.statistic), p=float(rr_.pvalue))
    OUT.append(f"- Spearman(gain, eligible capacity share for s=2) = {rr_.statistic:+.2f} (p={rr_.pvalue:.2g})")

# ======================= P: parameter sensitivity =======================
Pp = d[d.exp == "P_param"]
if len(Pp):
    rows = []
    base = Pp[Pp.param == "default"]
    for p in ["tf", "trace"]:
        NUM[f"P|default|{p}"] = ci(base[base.pol == p].cslo)
    for name in ["kmax", "l0", "horizon", "fitfac", "n_dom", "clear_p"]:
        s = Pp[Pp.param == name]
        for v, g in s.groupby(s[name].astype(str)):
            r = [name, v.replace("[", "(").replace("]", ")")]
            for p in ["tf", "trace"]:
                q = g[g.pol == p]
                r.append(fmt(*ci(q.cslo)))
            rows.append(r)
            NUM[f"P|{name}|{v}"] = {p: ci(g[g.pol == p].cslo)[0] for p in ["tf", "trace"]}
    rows.insert(0, ["(default)", "Kmax=2, ℓ0=20 ms, Δ=0.5 s, 0.05, 3 dom., 0.3/0.4/0.3"] +
                [fmt(*ci(base[base.pol == p].cslo)) for p in ["tf", "trace"]])
    table_md("tab_param", ["Parameter", "Value", "TF C-SLO", "TRACE C-SLO"], rows)

# ======================= F: scale =======================
F = d[d.exp == "F_scale"]
if len(F):
    fig, ax = plt.subplots(1, 2, figsize=(4.6, 2.1))
    line(ax[0], F, "N", "cslo", ["tf_rr", "tf_p2c", "tf", "trace"], "number of servers N"); ax[0].set_title("(a) compliant SLO")
    line(ax[1], F, "N", "dec_us", ["tf_rr", "tf_p2c", "tf", "trace"], "number of servers N"); ax[1].set_title("(b) µs per routing decision")
    ax[1].legend(fontsize=6)
    fig.tight_layout(); fig.savefig("figures_v3/fig_scale.png", bbox_inches="tight"); plt.close(fig)
    for k, g in F.groupby(["N", "pol"]):
        NUM[f"F|{k[0]}|{k[1]}"] = {m: ci(g[m])[0] for m in ["cslo", "dec_us"]}

# ======================= Energy =======================
EN = ["tf", "ew", "eb", "ec", "ewd", "ef"]
for ex, key_ in [("B_energy", "B"), ("S_solar", "S")]:
    B = d[d.exp == ex]
    if not len(B):
        continue
    fam = Family(f"{key_}_energy")
    for (phi, out), g in B.groupby(["phi", "outage"]):
        P = piv(g, "cslo")
        for p in EN[1:]:
            if p in P:
                fam.add(f"{NAMES[p]} - TF phi={phi} outage={out}", P[p], P["tf"])
        for p in g.pol.unique():
            q = g[g.pol == p]
            NUM[f"{key_}|{phi}|{out}|{p}"] = {m: ci(q[m])[0] for m in
                                              ["cslo", "avail", "avail_cv", "util_cv", "util_max", "throttled",
                                               "drains", "hops", "energy_per_good", "spill", "energy_kw"]}
    fam.done()
    rows = []
    for (phi, out), g in B.groupby(["phi", "outage"]):
        r = [f"{phi}", "outage" if out else "soft"]
        for p in EN:
            r.append(fmt(*ci(g[g.pol == p].cslo), 2))
        rows.append(r)
    table_md(f"tab_{key_}", ["Φ", "Model"] + [NAMES[p] for p in EN], rows)
B = d[d.exp == "B_energy"]
S = d[d.exp == "S_solar"]
if len(B):
    fig, ax = plt.subplots(1, 4, figsize=(7.2, 2.1))
    for i, out in enumerate([False, True]):
        line(ax[i], B[B.outage == out], "phi", "cslo", EN, "energy supply ratio Φ")
        ax[i].set_title(f"({'ab'[i]}) C-SLO, {'hard outage' if out else 'soft throttling'}")
    line(ax[2], B[B.outage], "phi", "util_cv", EN, "energy supply ratio Φ"); ax[2].set_title("(c) load dispersion (CV), outage")
    line(ax[3], B[B.outage], "phi", "avail", EN, "energy supply ratio Φ"); ax[3].set_title("(d) availability, outage")
    h, l = ax[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, -0.14))
    fig.tight_layout(); fig.savefig("figures_v3/fig_energy.png", bbox_inches="tight"); plt.close(fig)
U = d[d.exp == "U_buf"]
if len(U):
    fam = Family("U_buffer")
    for (buf, out), g in U.groupby(["buf_s", "outage"]):
        P = piv(g, "cslo")
        for p in ["ew", "ec"]:
            fam.add(f"{NAMES[p]} - TF buffer={buf}s outage={out}", P[p], P["tf"])
        for p in g.pol.unique():
            NUM[f"U|{buf}|{out}|{p}"] = ci(g[g.pol == p].cslo)
    Bp = B[(B.phi == 0.9) & B.pol.isin(["tf", "ew", "ec"])]
    for (out), g in Bp.groupby("outage"):
        for p in g.pol.unique():
            NUM[f"U|120.0|{out}|{p}"] = ci(g[g.pol == p].cslo)
    fam.done()
G = d[d.exp == "G_estale"]
if len(G):
    fam = Family("G_estale")
    allg = pd.concat([G, S[(S.phi == 0.9) & S.outage & S.pol.isin(["tf", "ew", "ec"])]])
    for h, g in allg.groupby("hsync"):
        P = piv(g, "cslo")
        for p in ["ew", "ec"]:
            fam.add(f"{NAMES[p]} - TF H={h}", P[p], P["tf"])
            NUM[f"G|{h}|{p}"] = ci((P[p] - P["tf"]).dropna())
    fam.done()

json.dump(NUM, open("numbers_v3.json", "w"), indent=1, default=float)
open("STATS_v3.md", "w").write("# Statistics v3 (mean ± 95% CI; paired Wilcoxon; Holm within family)\n" + "\n".join(OUT))
print("\n".join(OUT)[:20000])
