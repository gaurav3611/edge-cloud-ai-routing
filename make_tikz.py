"""
make_tikz.py - turn results_v2.csv into self-contained pgfplots figures and appendix tables.

Every data point is written into the LaTeX source, so main.tex needs no image files.
Run:  .venv/bin/python make_tikz.py      -> paper/gen/*.tex (pasted inline into main.tex)
"""
import os
import numpy as np, pandas as pd
from scipy import stats

os.makedirs("paper/gen", exist_ok=True)
df = pd.read_csv("results_v2.csv")

# entity -> (label, colour name, mark, line style); same mapping as analyze.py
STYLE = {
    "epara":      ("EPARA-style",          "cEPARA", "*",         "solid"),
    "epara_priv": ("TF (trust filter)",    "cTF",    "square*",   "solid"),
    "tera":       ("\\textsc{Trace}",       "cTRACE", "diamond*",  "solid"),
    "ours":       ("TF+EW (energy wt.)",   "cEW",    "triangle*", "dashed"),
    "rr":         ("Round-robin",          "cRR",    "triangle*", "densely dotted"),
    "energy":     ("EW only (no TF)",      "cEWO",   "pentagon*", "dashed"),
    "ours_b":     ("TF+EB (barrier)",      "cEB",    "x",         "dashed"),
    "ours_c":     ("TF+EC (energy cap.)",  "cEC",    "star",      "dashed"),
    "local":      ("Local only",           "cLOC",   "o",         "densely dotted"),
}


def ci(x):
    x = np.asarray(x, float)
    if len(x) < 2:
        return float(np.mean(x)), 0.0
    return float(x.mean()), float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))


def series(d, xcol, ycol, p):
    sub = d[d.variant == p]
    pts = []
    for x, g in sorted(sub.groupby(xcol), key=lambda kv: kv[0]):
        m, e = ci(g[ycol])
        pts.append(f"({x:g},{m:.4g}) +- (0,{e:.3g})")
    lab, col, mk, ls = STYLE[p]
    opts = (f"color={col}, mark={mk}, {ls}, mark options={{solid, scale=0.9}}, line width=0.9pt, "
            "error bars/.cd, y dir=both, y explicit, error bar style={line width=0.4pt}")
    return f"\\addplot+[{opts}] coordinates {{{' '.join(pts)}}};\n\\addlegendentry{{{lab}}}\n"


def group(name, panels, cols, width, height="3.7cm", hsep="1.25cm", legend_cols=5):
    """panels: list of dicts(d, x, y, pols, xlabel, ylabel, extra)."""
    out = ["\\begin{tikzpicture}",
           f"\\begin{{groupplot}}[group style={{group size={cols} by 1, horizontal sep={hsep}}},",
           f"  width={width}, height={height}, grid=major, grid style={{gray!20}},",
           "  tick label style={font=\\scriptsize}, label style={font=\\scriptsize}, ylabel shift=-2pt,",
           "  title style={font=\\scriptsize, yshift=-1ex}, every axis plot/.append style={},",
           "  legend style={font=\\scriptsize, draw=none, column sep=6pt}, cycle list name=exotic]"]
    for i, P in enumerate(panels):
        opts = [f"title={{({'abcdefgh'[i]})}}", f"xlabel={{{P['xlabel']}}}", f"ylabel={{{P['ylabel']}}}"]
        opts += P.get("extra", [])
        if i == 0:
            opts.append(f"legend columns={legend_cols}, legend to name=leg:{name}")
        out.append(f"\\nextgroupplot[{', '.join(opts)}]")
        for p in P["pols"]:
            out.append(series(P["d"], P["x"], P["y"], p).rstrip())
        if i > 0:
            out.append("\\legend{}")
    out += ["\\end{groupplot}",
            f"\\node at ($(group c1r1.north west)!0.5!(group c{cols}r1.north east)+(0,0.75cm)$) {{\\pgfplotslegendfromname{{leg:{name}}}}};",
            "\\end{tikzpicture}"]
    with open(f"paper/gen/fig_{name}.tex", "w") as f:
        f.write("\n".join(out) + "\n")


A = df[df.exp == "A_load"]
pA = ["local", "rr", "epara", "epara_priv", "tera"]
xl = "Offered load $\\rho$"
group("load", [
    dict(d=A, x="rho", y="cgoodput", pols=pA, xlabel=xl, ylabel="C-goodput (req/s)"),
    dict(d=A, x="rho", y="cslo", pols=pA, xlabel=xl, ylabel="C-SLO (per request)"),
    dict(d=A, x="rho", y="bcslo", pols=pA, xlabel=xl, ylabel="C-SLO (balanced)"),
    dict(d=A, x="rho", y="viol", pols=pA, xlabel=xl, ylabel="Violation rate"),
], 4, "4.6cm")

C = df[df.exp == "C_privacy"]
pC = ["epara", "epara_priv", "tera"]
group("privacy", [
    dict(d=C, x="sens_hi", y="slo", pols=pC, xlabel="Share of sensitive requests", ylabel="Raw SLO"),
    dict(d=C, x="sens_hi", y="cslo", pols=pC, xlabel="Share of sensitive requests", ylabel="Compliant SLO"),
], 2, "4.6cm", legend_cols=3)

B = df[df.exp == "B_energy"]
pB = ["epara_priv", "ours", "ours_b", "ours_c", "energy"]
xr = ["x dir=reverse"]
group("energy", [
    dict(d=B[~B.outage], x="capscale", y="cslo", pols=pB, xlabel="Energy-cap scale", ylabel="C-SLO, soft", extra=xr),
    dict(d=B[B.outage], x="capscale", y="cslo", pols=pB, xlabel="Energy-cap scale", ylabel="C-SLO, outage", extra=xr),
    dict(d=B[B.outage], x="capscale", y="avail", pols=pB, xlabel="Energy-cap scale", ylabel="Availability", extra=xr),
], 3, "5.6cm", hsep="1.4cm")

G = df[df.exp == "G_estale"]
lg = ["xmode=log", "log basis x=10"]
group("estale", [
    dict(d=G[~G.outage], x="hsync", y="cslo", pols=["epara_priv", "ours", "ours_c"], xlabel="Sync period $H$ (s)", ylabel="C-SLO, soft", extra=lg),
    dict(d=G[G.outage], x="hsync", y="cslo", pols=["epara_priv", "ours", "ours_c"], xlabel="Sync period $H$ (s)", ylabel="C-SLO, outage", extra=lg),
], 2, "4.6cm", legend_cols=2)

E = df[df.exp == "E_stale"]
pE = ["rr", "epara", "epara_priv"]
group("stale", [
    dict(d=E[E.rho == 0.8], x="hsync", y="slo", pols=pE, xlabel="Sync period $H$ (s)", ylabel="Raw SLO ($\\rho{=}0.8$)", extra=lg),
    dict(d=E[E.rho == 1.0], x="hsync", y="slo", pols=pE, xlabel="Sync period $H$ (s)", ylabel="Raw SLO ($\\rho{=}1.0$)", extra=lg),
], 2, "4.6cm", legend_cols=3)

F = df[df.exp == "F_scale"]
pF = ["rr", "epara_priv", "tera"]
group("scale", [
    dict(d=F, x="N", y="cslo", pols=pF, xlabel="Edge servers $N$", ylabel="Compliant SLO"),
    dict(d=F, x="N", y="dec_us", pols=pF, xlabel="Edge servers $N$", ylabel="Time ($\\mu$s/request)"),
], 2, "4.6cm", legend_cols=3)

# ---------------- appendix tables ----------------------------------------------------
def pm(x, nd=3):
    m, e = ci(x)
    return f"{m:.{nd}f}$\\pm${e:.{nd}f}"


# per-category compliant SLO at rho = 0.8
cats = [("cslo_LS<1", "LS$<$1"), ("cslo_LS>1", "LS$>$1"), ("cslo_FS<1", "FS$<$1"), ("cslo_FS>1", "FS$>$1")]
A8 = A[A.rho == 0.8]
rows = []
for p in ["local", "rr", "epara", "epara_priv", "tera", "ours"]:
    s = A8[A8.variant == p]
    rows.append(STYLE[p][0] + " & " + " & ".join(pm(s[c]) for c, _ in cats) + " \\\\")
with open("paper/gen/tab_category.tex", "w") as f:
    f.write("\\begin{tabular}{lcccc}\n\\toprule\nPolicy & " + " & ".join(h for _, h in cats)
            + " \\\\\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")

# full energy table
rows = []
for om in [False, True]:
    for cs in [1.0, 0.7, 0.5, 0.35]:
        d = B[(B.outage == om) & np.isclose(B.capscale, cs)]
        cells = [pm(d[d.variant == p].cslo, 2) for p in pB]
        lab = ("Outage" if om else "Soft") if cs == 1.0 else ""
        rows.append(f"{lab} & {cs:g} & " + " & ".join(cells) + " \\\\")
    if not om:
        rows.append("\\midrule")
with open("paper/gen/tab_energy.tex", "w") as f:
    f.write("\\begin{tabular}{llccccc}\n\\toprule\nModel & Cap & TF & TF+EW & TF+EB & TF+EC & EW only \\\\\n\\midrule\n"
            + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")

# staleness table (raw SLO and forwards)
rows = []
for rho in [0.8, 1.0]:
    for h in sorted(E.hsync.unique()):
        d = E[(E.rho == rho) & np.isclose(E.hsync, h)]
        cells = []
        for p in pE:
            s = d[d.variant == p]
            cells += [f"{ci(s.slo)[0]:.3f}", f"{ci(s.hops)[0]:.2f}"]
        rows.append(f"{rho:g} & {h:g} & " + " & ".join(cells) + " \\\\")
    if rho == 0.8:
        rows.append("\\midrule")
with open("paper/gen/tab_stale.tex", "w") as f:
    f.write("\\begin{tabular}{cc|cc|cc|cc}\n\\toprule\n & & \\multicolumn{2}{c|}{Round-robin} & \\multicolumn{2}{c|}{EPARA-style} & \\multicolumn{2}{c}{TF}\\\\\n"
            "$\\rho$ & $H$ (s) & SLO & Fwd. & SLO & Fwd. & SLO & Fwd.\\\\\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")
print("written:", sorted(os.listdir("paper/gen")))
