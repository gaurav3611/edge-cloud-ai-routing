"""
analyze.py - statistics, figures and LaTeX tables from results_v2.csv.

Run:  .venv/bin/python analyze.py
Outputs: figures/*.pdf|png, tables/*.tex, STATS.md
"""
import os
import numpy as np, pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.makedirs("figures", exist_ok=True)
os.makedirs("tables", exist_ok=True)
df = pd.read_csv("results_v2.csv")

# fixed entity -> style mapping (same in every figure); local is a neutral baseline
STYLE = {
    "epara":      ("EPARA-style",        "#2a78d6", "o", "-"),
    "epara_priv": ("TF (trust filter)",  "#eb6834", "s", "-"),
    "tera":       ("TRACE (TF+best-fit)", "#1baf7a", "D", "-"),
    "ours":       ("TF+EW (energy wt.)", "#eda100", "^", "--"),
    "rr":         ("Round-robin",        "#e87ba4", "v", ":"),
    "energy":     ("EW only (no TF)",    "#4a3aa7", "P", "--"),
    "ours_b":     ("TF+EB (barrier)",    "#e34948", "X", "--"),
    "ours_c":     ("TF+EC (energy cap.)", "#008300", "*", "--"),
    "local":      ("Local only",         "#8a8984", "h", ":"),
    "rr_g":       ("RR, shared pointer (ref.)", "#8a8984", "<", "--"),
}
plt.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.labelsize": 8, "legend.fontsize": 6.5,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": "#e4e3df", "grid.linewidth": 0.5, "axes.edgecolor": "#52514e",
    "lines.linewidth": 1.5, "lines.markersize": 4.5, "savefig.bbox": "tight",
})
W1, W2 = 3.45, 7.0     # IEEE single / double column width (in)


def ci(x):
    x = np.asarray(x, float)
    if len(x) < 2:
        return np.mean(x), 0.0
    return x.mean(), stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))


def agg(d, by, col):
    g = d.groupby(by)[col].apply(list)
    return {k: ci(v) for k, v in g.items()}


def line_panel(ax, d, xcol, ycol, pols, xlabel, ylabel):
    for p in pols:
        sub = d[d.variant == p]
        if sub.empty:
            continue
        a = agg(sub, xcol, ycol)
        xs = sorted(a)
        m = np.array([a[x][0] for x in xs]); e = np.array([a[x][1] for x in xs])
        lab, c, mk, ls = STYLE[p]
        ax.plot(xs, m, ls, color=c, marker=mk, label=lab)
        ax.fill_between(xs, m - e, m + e, color=c, alpha=0.15, linewidth=0)
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)


def shared_legend(fig, ax, ncol=5):
    """One legend row above all panels, so no curve is covered."""
    h, l = ax.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=ncol, frameon=False,
               handlelength=2.6, columnspacing=1.2)


def save(fig, name):
    fig.savefig(f"figures/{name}.pdf"); fig.savefig(f"figures/{name}.png", dpi=200)
    plt.close(fig)


def paired(d, a, b, col, match):
    """Paired comparison of variant a vs b over identical (seed, settings)."""
    x = d[d.variant == a].set_index(match)[col]
    y = d[d.variant == b].set_index(match)[col]
    j = x.index.intersection(y.index)
    x, y = x[j], y[j]
    diff = (x - y).values
    p = stats.wilcoxon(diff).pvalue if np.any(diff != 0) and len(diff) >= 6 else float("nan")
    return diff.mean(), ci(diff)[1], p, len(diff), (diff > 0).mean()


out = ["# Statistics (mean +/- 95% CI over seeds; paired Wilcoxon signed-rank)\n"]

# ---------------- A: load sweep --------------------------------------------------
A = df[df.exp == "A_load"]
pA = ["local", "rr", "epara", "epara_priv", "tera"]
fig, ax = plt.subplots(1, 4, figsize=(W2, 2.0))
line_panel(ax[0], A, "rho", "cgoodput", pA, "Offered load $\\rho$", "Compliant goodput (req/s)")
line_panel(ax[1], A, "rho", "cslo", pA, "Offered load $\\rho$", "Compliant SLO (per request)")
line_panel(ax[2], A, "rho", "bcslo", pA, "Offered load $\\rho$", "Compliant SLO (cat.-balanced)")
line_panel(ax[3], A, "rho", "viol", pA, "Offered load $\\rho$", "Trust-violation rate")
for i in range(4):
    ax[i].set_title(f"({'abcd'[i]})", fontsize=8)
fig.tight_layout(); shared_legend(fig, ax[0], 5); save(fig, "fig_load")

# main table at rho = 0.8
A8 = A[A.rho == 0.8]
cols = [("slo", "SLO", 3), ("cslo", "C-SLO", 3), ("bcslo", "C-SLO$_{bal}$", 3), ("viol", "Viol.", 3),
        ("cgoodput", "C-goodput", 0), ("hops", "Fwd.", 2), ("dec_us", "$\\mu$s", 1)]
rows = []
for p in ["local", "rr", "rr_g", "epara", "epara_priv", "tera", "ours"]:
    s = A8[A8.variant == p]
    cells = []
    for c, _, nd in cols:
        m, e = ci(s[c])
        cells.append(f"{m:.{nd}f}$\\pm${e:.{nd}f}")
    rows.append(STYLE[p][0].replace("&", "\\&") + " & " + " & ".join(cells) + " \\\\")
with open("tables/tab_main.tex", "w") as f:
    f.write("\\begin{tabular}{l" + "c" * len(cols) + "}\n\\toprule\nPolicy & "
            + " & ".join(h for _, h, _ in cols) + " \\\\\n\\midrule\n" + "\n".join(rows)
            + "\n\\bottomrule\n\\end{tabular}\n")
out.append("## A. Load sweep (rho=0.8)\n")
for p in ["local", "rr", "rr_g", "epara", "epara_priv", "tera", "ours"]:
    s = A8[A8.variant == p]
    out.append(f"- {p}: slo {ci(s.slo)[0]:.3f}, cslo {ci(s.cslo)[0]:.3f}+/-{ci(s.cslo)[1]:.3f}, bcslo {ci(s.bcslo)[0]:.3f}+/-{ci(s.bcslo)[1]:.3f}, "
               f"viol {ci(s.viol)[0]:.3f}, cgoodput {ci(s.cgoodput)[0]:.0f}, dec_us {ci(s.dec_us)[0]:.1f}")
for metric in ["cslo", "bcslo", "slo"]:
    for a, b in [("epara_priv", "epara"), ("tera", "epara_priv"), ("tera", "epara"), ("tera", "rr"), ("epara", "rr"), ("rr_g", "rr")]:
        for rho in [0.4, 0.6, 0.8, 0.9, 1.0]:
            d = A[A.rho == rho]
            m, e, p, n, w = paired(d, a, b, metric, ["seed"])
            out.append(f"- {metric} {a} - {b} @rho={rho}: {m:+.3f} +/- {e:.3f} (p={p:.4f}, n={n}, wins {w:.0%})")
out.append("- rho sweep, per policy (cslo / bcslo / viol / cgoodput):")
for rho in sorted(A.rho.unique()):
    d = A[A.rho == rho]
    out.append(f"  rho={rho}: " + "; ".join(f"{p} {ci(d[d.variant == p].cslo)[0]:.3f}/{ci(d[d.variant == p].bcslo)[0]:.3f}/{ci(d[d.variant == p].viol)[0]:.3f}/{ci(d[d.variant == p].cgoodput)[0]:.0f}" for p in ["local", "rr", "rr_g", "epara", "epara_priv", "tera", "ours"]))

# ---------------- C: privacy strictness -------------------------------------------
C = df[df.exp == "C_privacy"]
fig, ax = plt.subplots(1, 2, figsize=(W1 * 1.4, 2.0))
line_panel(ax[0], C, "sens_hi", "slo", ["epara", "epara_priv", "tera"], "Share of sensitive requests", "Raw SLO attainment")
line_panel(ax[1], C, "sens_hi", "cslo", ["epara", "epara_priv", "tera"], "Share of sensitive requests", "Compliant SLO attainment")
ax[0].set_title("(a)", fontsize=8); ax[1].set_title("(b)", fontsize=8)
fig.tight_layout(); shared_legend(fig, ax[1], 3); save(fig, "fig_privacy")
out.append("\n## C. Privacy strictness (rho=0.8)\n")
for hi in sorted(C.sens_hi.unique()):
    d = C[np.isclose(C.sens_hi, hi)]
    line = f"- sens={hi:.1f}: " + ", ".join(f"{p} slo {ci(d[d.variant == p].slo)[0]:.3f} cslo {ci(d[d.variant == p].cslo)[0]:.3f} bcslo {ci(d[d.variant == p].bcslo)[0]:.3f} viol {ci(d[d.variant == p].viol)[0]:.3f}" for p in ["epara", "epara_priv", "tera"])
    m, e, pv, n, w = paired(d, "tera", "epara_priv", "cslo", ["seed"])
    m2, e2, pv2, _, _ = paired(d, "tera", "epara_priv", "bcslo", ["seed"])
    m3, e3, pv3, _, _ = paired(d, "epara_priv", "epara", "cslo", ["seed"])
    out.append(line + f" | TRACE-TF cslo {m:+.3f}+/-{e:.3f} p={pv:.3f}; bcslo {m2:+.3f}+/-{e2:.3f} p={pv2:.3f} | TF-EPARA cslo {m3:+.3f} p={pv3:.3f}")

# ---------------- B: energy ---------------------------------------------------------
B = df[df.exp == "B_energy"]
pB = ["epara_priv", "ours", "ours_b", "ours_c", "energy"]
fig, ax = plt.subplots(1, 3, figsize=(W2, 2.1))
line_panel(ax[0], B[~B.outage], "capscale", "cslo", pB, "Energy-cap scale", "Compl. SLO (soft throttling)")
line_panel(ax[1], B[B.outage], "capscale", "cslo", pB, "Energy-cap scale", "Compl. SLO (hard outage)")
line_panel(ax[2], B[B.outage], "capscale", "avail", pB, "Energy-cap scale", "Server availability (outage)")
for i, t in enumerate("abc"):
    ax[i].set_title(f"({t})", fontsize=8); ax[i].invert_xaxis()
fig.tight_layout(); shared_legend(fig, ax[0], 5); save(fig, "fig_energy")
out.append("\n## B. Energy (rho=0.8)\n")
for out_m in [False, True]:
    for cs in sorted(B.capscale.unique(), reverse=True):
        d = B[(B.outage == out_m) & np.isclose(B.capscale, cs)]
        s = ", ".join(f"{p} {ci(d[d.variant == p].cslo)[0]:.3f}" for p in pB)
        av = ", ".join(f"{p} {ci(d[d.variant == p].avail)[0]:.2f}" for p in pB) if out_m else ""
        th = ", ".join(f"{p} {ci(d[d.variant == p].throttled)[0]:.3f}" for p in pB)
        out.append(f"- {'outage' if out_m else 'soft'} cap x{cs}: cslo [{s}] thr [{th}] {('avail [' + av + ']') if av else ''}")
        for v in ["ours", "ours_b", "ours_c"]:
            m, e, pv, n, w = paired(d, v, "epara_priv", "cslo", ["seed"])
            out.append(f"    {v}-TF: {m:+.3f}+/-{e:.3f} p={pv:.3f}")

# ---------------- D: ablations -----------------------------------------------------
D = df[df.exp == "D_ablate"]
rows = []
out.append("\n## D. Energy ablation (cap x0.5, rho=0.8)\n")
for (b, th), d in D.groupby(["beta", "theta"]):
    cells = []
    for om in [False, True]:
        s = d[d.outage == om]
        for c, nd in [("cslo", 3), ("throttled", 3)] + ([("avail", 2)] if om else []):
            m, e = ci(s[c]); cells.append(f"{m:.{nd}f}$\\pm${e:.{nd}f}")
    rows.append(f"{b:g} & {th:g} & " + " & ".join(cells) + " \\\\")
    out.append(f"- beta={b}, theta={th}: soft cslo {ci(d[~d.outage].cslo)[0]:.3f}, outage cslo {ci(d[d.outage].cslo)[0]:.3f}, avail {ci(d[d.outage].avail)[0]:.2f}")
with open("tables/tab_ablation.tex", "w") as f:
    f.write("\\begin{tabular}{cc|cc|ccc}\n\\toprule\n & & \\multicolumn{2}{c|}{Soft throttling} & \\multicolumn{3}{c}{Hard outage}\\\\\n"
            "$\\beta$ & $\\theta$ & Compl. SLO & Throttled & Compl. SLO & Throttled & Avail. \\\\\n\\midrule\n"
            + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")

G = df[df.exp == "D_gamma"]
out.append("\n## D2. Best-fit clearance gamma (60% sensitive)\n")
rows = []
for g, d in sorted(G.groupby("gamma"), key=lambda x: -x[0]):
    if g != 1.0:
        mm, ee, pp, nn, ww = paired(G[G.gamma.isin([1.0, g])].assign(variant=lambda x: x.gamma.astype(str)), str(g), "1.0", "cslo", ["seed"])
        out.append(f"  gamma={g} vs 1.0 paired cslo diff {mm:+.3f}+/-{ee:.3f} p={pp:.3f}")
    m, e = ci(d.cslo)
    mb, eb = ci(d.bcslo)
    rows.append(f"{g:g} & {m:.3f}$\\pm${e:.3f} & {mb:.3f}$\\pm${eb:.3f} \\\\")
    out.append(f"- gamma={g}: cslo {m:.3f}+/-{e:.3f}, bcslo {mb:.3f}+/-{eb:.3f}")
with open("tables/tab_gamma.tex", "w") as f:
    f.write("\\begin{tabular}{ccc}\n\\toprule\n$\\gamma$ & C-SLO & C-SLO$_{bal}$\\\\\n\\midrule\n"
            + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")

# ---------------- E: staleness ------------------------------------------------------
E = df[df.exp == "E_stale"]
fig, ax = plt.subplots(1, 2, figsize=(W1 * 1.4, 2.0))
for i, rho in enumerate([0.8, 1.0]):
    line_panel(ax[i], E[E.rho == rho], "hsync", "slo", ["rr", "epara", "epara_priv"],
               "State-sync period $H$ (s)", f"Raw SLO ($\\rho$={rho})")
    ax[i].set_xscale("log"); ax[i].set_title(f"({'ab'[i]})", fontsize=8)
fig.tight_layout(); shared_legend(fig, ax[1], 3); save(fig, "fig_stale")
out.append("\n## E. Sync staleness\n")
for rho in [0.8, 1.0]:
    for h in sorted(E.hsync.unique()):
        d = E[(E.rho == rho) & np.isclose(E.hsync, h)]
        out.append(f"- rho={rho} H={h}: " + ", ".join(f"{p} slo {ci(d[d.variant == p].slo)[0]:.3f} hops {ci(d[d.variant == p].hops)[0]:.2f}" for p in ["rr", "epara", "epara_priv"]))

# ---------------- G: energy weighting vs. staleness (herding test) -----------------
Gs = df[df.exp == "G_estale"]
if not Gs.empty:
    fig, ax = plt.subplots(1, 2, figsize=(W1 * 1.4, 2.0))
    for i, om in enumerate([False, True]):
        line_panel(ax[i], Gs[Gs.outage == om], "hsync", "cslo", ["epara_priv", "ours", "ours_c"],
                   "State-sync period $H$ (s)", "Compl. SLO (" + ("hard outage" if om else "soft") + ")")
        ax[i].set_xscale("log"); ax[i].set_title(f"({'ab'[i]})", fontsize=8)
    fig.tight_layout(); shared_legend(fig, ax[0], 3); save(fig, "fig_estale")
    out.append("\n## G. Energy weighting vs sync period (cap x0.5)\n")
    for om in [False, True]:
        for h in sorted(Gs.hsync.unique()):
            d = Gs[(Gs.outage == om) & np.isclose(Gs.hsync, h)]
            m, e, pv, n, w = paired(d, "ours", "epara_priv", "cslo", ["seed"])
            m2, e2, pv2, _, _ = paired(d, "ours_c", "epara_priv", "cslo", ["seed"])
            out.append(f"- {'outage' if om else 'soft'} H={h}: TF {ci(d[d.variant == 'epara_priv'].cslo)[0]:.3f}, "
                       f"TF+EW-TF {m:+.3f}+/-{e:.3f} p={pv:.3f}; TF+EC-TF {m2:+.3f}+/-{e2:.3f} p={pv2:.3f}")

# ---------------- F: scale ---------------------------------------------------------
F = df[df.exp == "F_scale"]
fig, ax = plt.subplots(1, 2, figsize=(W1 * 1.4, 2.0))
line_panel(ax[0], F, "N", "cslo", ["rr", "epara_priv", "tera"], "Edge servers $N$", "Compliant SLO")
line_panel(ax[1], F, "N", "dec_us", ["rr", "epara_priv", "tera"], "Edge servers $N$", "Routing time / request ($\\mu$s)")
ax[0].set_title("(a)", fontsize=8); ax[1].set_title("(b)", fontsize=8)
fig.tight_layout(); shared_legend(fig, ax[0], 3); save(fig, "fig_scale")
out.append("\n## F. Scale\n")
for N in sorted(F.N.unique()):
    d = F[F.N == N]
    out.append(f"- N={N}: " + ", ".join(f"{p} cslo {ci(d[d.variant == p].cslo)[0]:.3f} dec {ci(d[d.variant == p].dec_us)[0]:.1f}us" for p in ["rr", "epara_priv", "tera"]))

open("STATS.md", "w").write("\n".join(out) + "\n")
print("\n".join(out))
