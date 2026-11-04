"""Apply the four acceptance rules of docs/acceptance_rules_v2.md: python analysis/accept.py <suite>. Writes processed/accept_<suite>.csv."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
from lib import load, compare, CATS, ROOT


def accept(d, base="TRACE"):
    """Rows of d averaged over load per seed, each router against base. Points."""
    s = d.groupby(["name", "seed"])[["cslo", "bcslo", "viol"]].mean().reset_index()
    b = s[s.name == base].set_index("seed")
    cat = [f"cslo_{c}" for c in CATS]
    bc = d[d.name == base].groupby("rho")[cat].mean()
    out = []
    for n in s.name.unique():
        if n == base:
            continue
        g = s[s.name == n].set_index("seed").loc[b.index]
        cb, cc = compare(g.bcslo, b.bcslo), compare(g.cslo, b.cslo)
        worst = (d[d.name == n].groupby("rho")[cat].mean() - bc).min().min() * 100
        r1 = cb["diff"] >= .5 and cb["diff"] - cb["ci95"] > 0
        r2 = cc["diff"] - cc["ci95"] >= -.5
        r3 = d[d.name == n].viol.max() == 0
        r4 = worst >= -2
        out.append(dict(name=n, d_bal=cb["diff"], ci_bal=cb["ci95"], d_cslo=cc["diff"], ci_cslo=cc["ci95"], worst_cat=worst, r1=r1, r2=r2, r3=r3, r4=r4, accepted=r1 and r2 and r3 and r4))
    return pd.DataFrame(out).sort_values("d_bal", ascending=False)


if __name__ == "__main__":
    t = accept(load(sys.argv[1])); t.to_csv(os.path.join(ROOT, "processed", f"accept_{sys.argv[1]}.csv"), index=False)
    print(t.round(2).to_string(index=False))
