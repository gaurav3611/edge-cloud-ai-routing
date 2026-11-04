"""D6 audit: the post-hoc viol and mix test families, recomputed from raw rows.

Reports, for each comparison: n, mean paired difference, 95% CI, raw Wilcoxon p, Holm p within the family used in the
draft, and Holm p under two stricter groupings (one pooled post-hoc family; Bonferroni over every test in both suites),
so the authors can see which conclusions depend on the grouping. Read-only on TRACE_revision/raw.
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "TRACE_revision"))
sys.path.insert(0, os.path.join(REV, "analysis"))
from lib import compare, holm, load  # noqa: E402


def rows():
    out = []
    v = load("viol"); assert len(v) == 750
    for lam in sorted(v["corr"].unique()):
        A = v[(v.name == "EPARA-style") & (v["corr"] == lam)].sort_values("seed")
        C = v[(v.name == "Oracle unconstrained") & (v["corr"] == lam)].sort_values("seed")
        assert (A.seed.values == C.seed.values).all() and len(A) == 30
        out.append(dict(suite="viol", family="viol", test=f"EPARA-style - central (no trust), alignment {lam}", metric="viol",
                        **compare(A.viol.values, C.viol.values)))
    m = load("mix"); assert len(m) == 1050
    for met in ("cslo", "bcslo"):
        for other in ("Static sized", "Static sized40"):
            for sh in (0.0, 0.2, 0.4, 0.6, 0.8):
                A = m[(m.name == "TRACE") & ((m.sens_hi - sh).abs() < 1e-9)].sort_values("seed")
                C = m[(m.name == other) & ((m.sens_hi - sh).abs() < 1e-9)].sort_values("seed")
                assert (A.seed.values == C.seed.values).all() and len(A) == 30
                out.append(dict(suite="mix", family=f"mix-{met}", test=f"TRACE - {other}, sensitive {sh:.0%}", metric=met,
                                **compare(A[met].values, C[met].values)))
    f = pd.DataFrame(out)
    f["p_h_draft"] = f.groupby("family")["p"].transform(lambda p: holm(p))
    f["p_h_pooled"] = holm(f["p"])                      # all 25 post-hoc tests as one family
    f["p_bonf_all"] = np.minimum(f["p"] * len(f), 1.0)  # Bonferroni over all 25
    f["holm_tost1_draft"] = f.groupby("family")["tost1.0"].transform(lambda p: holm(p))
    return f


def main():
    f = rows()
    cols = ["family", "test", "n", "diff", "ci95", "p", "p_h_draft", "p_h_pooled", "p_bonf_all", "holm_tost1_draft"]
    out = os.path.join(HERE, "d6_tests.csv")
    f[cols].to_csv(out, index=False, float_format="%.6g")
    sig = lambda c: int((f[c] < 0.05).sum())  # noqa: E731
    print(f"{len(f)} tests; significant at 0.05: draft families {sig('p_h_draft')}, pooled Holm {sig('p_h_pooled')}, "
          f"Bonferroni-all {sig('p_bonf_all')}")
    ch = f[(f.p_h_draft < 0.05) != (f.p_bonf_all < 0.05)]
    print("tests whose verdict changes under Bonferroni-all:", ch.test.tolist() or "none")
    print("CI excludes zero:", int(((f["diff"].abs() - f["ci95"]) > 0).sum()), "of", len(f))
    print(out)


if __name__ == "__main__":
    main()
