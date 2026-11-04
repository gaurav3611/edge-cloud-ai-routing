"""Figure style of the original paper (SAA_Trace.pdf), values taken from ~/Desktop/sim/analyze_v3.py."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": .3, "figure.dpi": 300, "savefig.dpi": 300, "legend.fontsize": 8.5, "axes.titlesize": 10, "axes.linewidth": 1.0, "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.frameon": False})
COL = {"local": "#999999", "rr": "#b07aa1", "epara": "#e15759", "oracle_u": "#ff9d9a", "tf": "#4e79a7", "trace": "#1b9e77", "tf_rr": "#9c755f", "tf_p2c": "#f28e2b", "tf_jsq": "#edc948",
       "static": "#7f7f7f", "oracle_c": "#000000", "ew": "#e15759", "large": "#b07aa1", "fixed": "#9c755f"}   # large-JSQ and fixed pools are not in the original; they take unused palette colours
MK = {"oracle_c": "s", "oracle_u": "s", "trace": "o", "tf": "^"}
def sty(p, **k):
    return dict(color=COL[p], marker=MK.get(p, "."), ms=4, lw=2.8 if p == "trace" else 1.7, capsize=3, ls="--" if p.startswith("oracle") else "-") | k
def legend_below(f, ax, ncol, y=-.1):
    h, l = ax.get_legend_handles_labels()
    f.legend(h, l, loc="lower center", ncol=ncol, bbox_to_anchor=(.5, y))
def save(f, name, out):
    f.tight_layout(); f.savefig(os.path.join(out, name + ".png"), bbox_inches="tight"); plt.close(f)
import os
