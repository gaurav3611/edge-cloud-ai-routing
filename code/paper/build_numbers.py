"""Build numbers.tex and trace.csv from raw rows. One function per paper section; each reads only finished, validated suites.

python analysis/build_numbers.py
"""
import json, os, sys
import numpy as np
import pandas as pd
from nums import Book, REV, DRAFT
from lib import load, compare
import build_paper_main as BPM

S = os.path.abspath(__file__)
RHO = {0.5: "05", 0.8: "08", 1.0: "10", 1.2: "12"}
CMPKEY = {"TRACE $-$ TF": "trace-tf", "TRACE $-$ TF-JSQ": "trace-tfjsq", "TRACE $-$ sized static": "trace-sized",
          "large-JSQ $-$ TRACE": "large-trace", "large-JSQ $-$ TF-JSQ": "large-tfjsq", "TRACE fit 0 $-$ TRACE": "fit0-trace",
          "Central $-$ TRACE": "central-trace"}
NAMEKEY = {"TRACE": "trace", "TF-JSQ": "tfjsq", "large_jsq": "large", "Static sized": "sized", "Oracle compliant": "central",
           "Oracle unconstrained": "central-u", "EPARA-style": "epara", "TF": "tf", "TF-P2C": "tfp2c", "TF-RR": "tfrr", "TRACE fit0": "fit0"}
CATK = {"cslo_LS<1": "ls1", "cslo_LS>1": "lsg1", "cslo_FS<1": "fs1", "cslo_FS>1": "fsg1"}


def paired(d, a, b, m, rho):
    A = d[(d.name == a) & (d.rho == rho)].sort_values("seed"); B = d[(d.name == b) & (d.rho == rho)].sort_values("seed")
    assert len(A) == 30 and (A.seed.values == B.seed.values).all()
    return compare(A[m].values, B[m].values)


def main_sweep(B):
    """Held-out main, seeds 8001-8030. Significance only from the Table tab:diff family (7 comparisons x 4 loads per metric)."""
    d = load("main")
    assert len(d) == 3240 and d[d.name == "TRACE"].viol.sum() == 0
    _, res = BPM.diff(d)
    os.makedirs(os.path.join(DRAFT, "supplementary"), exist_ok=True)   # every statistic of every comparison in the held-out family
    pd.concat([f.assign(metric=m) for m, f in res.items()]).to_csv(os.path.join(DRAFT, "supplementary", "main_family_tests.csv"), index=False, float_format="%.6g")
    for m, f in res.items():
        for r in f.to_dict("records"):
            k = f"main.{CMPKEY[r['cmp']]}.{m}.{RHO[r['rho']]}"
            B.add(k, r["diff"], "pt", "main", f"paired mean, {r['cmp']}, {m}, rho {r['rho']}", S)
            B.add(k + ".ci", r["ci95"], "pt0", "main", "Student-t 95% CI half-width, n=30", S)
            B.add(k + ".lab", r["label"], "raw", "main", "labels: S significant (Holm), E0.5/E1 equivalent by TOST (Holm)", S)
            B.add(k + ".ph", f"{r['p_h']:.3f}" if r["p_h"] >= .001 else "<0.001", "raw", "main", "Holm p, family of 28 per metric", S)
    for n, nk in NAMEKEY.items():
        for rho, rk in RHO.items():
            g = d[(d.name == n) & (d.rho == rho)]
            assert len(g) == 30, (n, rho)
            for m in ("slo", "cslo", "bcslo", "wcslo", *CATK):
                B.add(f"main.{nk}.{CATK.get(m, m)}.{rk}", g[m].mean(), "fr", "main", f"mean over 30 seeds, {n}, {m}, rho {rho}", S)
    # descriptive paired CIs outside the Holm family (no significance claimed)
    for k, a, b, m in (("cu-c.slo", "Oracle unconstrained", "Oracle compliant", "slo"), ("epara-trace.slo", "EPARA-style", "TRACE", "slo"),
                       ("trace-tfp2c.cslo", "TRACE", "TF-P2C", "cslo"), ("trace-tfp2c.bcslo", "TRACE", "TF-P2C", "bcslo"),
                       ("trace-tfrr.cslo", "TRACE", "TF-RR", "cslo"), ("trace-tfrr.bcslo", "TRACE", "TF-RR", "bcslo")):
        for rho, rk in RHO.items():
            c = paired(d, a, b, m, rho)
            B.add(f"main.{k}.{rk}", c["diff"], "pt", "main", f"descriptive paired mean {a} - {b}, {m}", S)
            B.add(f"main.{k}.{rk}.ci", c["ci95"], "pt0", "main", "Student-t 95% CI half-width, n=30, no Holm", S)
    for k, a, b in (("trace-tfp2c", "TRACE", "TF-P2C"), ("trace-tfrr", "TRACE", "TF-RR")):
        lo = min(paired(d, a, b, m, r)["diff"] - paired(d, a, b, m, r)["ci95"] for m in ("cslo", "bcslo") for r in RHO)
        B.add(f"main.{k}.lowerci", lo, "pt", "main", f"smallest lower 95% CI bound of {a} - {b}, C-SLO and balanced, 4 loads", S)
    # TRACE vs TF: range over loads and metrics
    v = [r["diff"] for f in res.values() for r in f.to_dict("records") if r["cmp"] == "TRACE $-$ TF"]
    B.add("main.trace-tf.min", min(v), "pt0", "main", "smallest TRACE - TF over 3 metrics x 4 loads", S)
    B.add("main.trace-tf.max", max(v), "pt0", "main", "largest TRACE - TF over 3 metrics x 4 loads", S)
    B.add("main.trace-tf.allpos", str(all(x > 0 for x in v)), "raw", "main", "TRACE - TF positive in all 12 cells", S)


def category(B):
    """Shed by sensitivity at rho 0.8 and domains without clearance-2 capacity, held-out topologies."""
    F = json.load(open(os.path.join(REV, "processed", "paper", "facts_main.json")))
    for n, v in F["shed_by_sens"].items():
        for s, x in v.items():
            B.add(f"main.shed.{NAMEKEY[n]}.s{s}", x, "pc", "main", f"share of sensitivity-{s} requests shed at rho 0.8, {n} (build_paper_main.facts)", S)
    T = json.load(open(os.path.join(REV, "processed", "feasible_8001_8030.json")))
    B.add("main.nodomain2", sum(min(t["c2_slots_by_domain"]) == 0 for t in T), "int", "main",
          "held-out topologies with a domain lacking clearance-2 slots (analysis/feasible_classes.py, topology only)", S)
    import csv
    C = [r for r in csv.DictReader(open(os.path.join(DRAFT, "..", "checks", "category_counts.csv"))) if r["router"] == "TRACE"]
    for rho in ("0.8", "1.0"):
        off = {r["category"]: int(r["offered"]) for r in C if r["rho"] == rho}
        B.add(f"main.ls1share.{RHO[float(rho)]}", off["LS<1"] / sum(off.values()), "pc", "main",
              f"LS<1 share of offered requests, rho {rho} (TRACE_remediation/checks/category_counts.py)", S)
    d = load("main")
    for m in ("cslo", "bcslo", "wcslo"):
        v = [paired(d, "TRACE fit0", "TRACE", m, r)["diff"] for r in RHO]
        B.add(f"main.fit0-trace.{m}.lo", min(v, key=abs), "pt0", "main", f"fit0 - TRACE {m}, smallest magnitude over 4 loads", S)
        B.add(f"main.fit0-trace.{m}.hi", max(v, key=abs), "pt0", "main", f"fit0 - TRACE {m}, largest magnitude over 4 loads", S)
        B.add(f"main.fit0-trace.{m}.sign", "+" if all(x > 0 for x in v) else ("-" if all(x < 0 for x in v) else "mixed"), "raw", "main", "sign over 4 loads", S)


def violations(B):
    """viol: oblivious routers, seeds 8001-8030, rho 0.8, 200 s measured. Family: EPARA-style - central (no trust) at the 5 alignments, Holm."""
    from lib import family
    d = load("viol"); assert len(d) == 750
    LAM = {0.0: "0", 0.25: "025", 0.5: "05", 0.75: "075", 1.0: "1"}
    assert d[d.name == "TRACE"].viol.sum() == 0
    B.add("viol.runs", len(d), "int", "viol", "rows in suite", S)
    for n, k in (("EPARA-style", "epara"), ("Oracle unconstrained", "central-u"), ("RR", "rr"), ("JSQ oblivious", "jsq")):
        for lam, lk in LAM.items():
            B.add(f"viol.{k}.{lk}", d[(d.name == n) & (d["corr"] == lam)].viol.mean(), "pc", "viol", f"mean violation rate, {n}, alignment {lam}", S)
    rows = []
    for lam in LAM:
        A = d[(d.name == "EPARA-style") & (d["corr"] == lam)].sort_values("seed"); C = d[(d.name == "Oracle unconstrained") & (d["corr"] == lam)].sort_values("seed")
        assert (A.seed.values == C.seed.values).all() and len(A) == 30
        rows.append(dict(lam=lam, **compare(A.viol.values, C.viol.values)))
    f = family(rows)
    for r in f.to_dict("records"):
        k = f"viol.epara-central.{LAM[r['lam']]}"
        B.add(k, r["diff"], "pt", "viol", "paired EPARA-style - central (no trust), violation rate, points", S)
        B.add(k + ".ci", r["ci95"], "pt0", "viol", "Student-t 95% CI, n=30", S)
        B.add(k + ".ph", f"{r['p_h']:.3f}" if r["p_h"] >= .001 else "<0.001", "raw", "viol", "Holm p over 5 alignments", S)
        B.add(k + ".lab", r["label"], "raw", "viol", "S / E0.5 / E1 labels", S)
    g = d[d["corr"] == 1.0]
    B.add("viol.E.1", g[[c for c in g.columns if c.startswith("dc_ii_")]].fillna(0).sum(axis=1).max(), "fr", "viol",
          "largest share of requests with an ineligible ingress at alignment 1, over all rows (should be 0)", S)


def mixes(B):
    """mix: sensitive share 0-80%, rho 0.8, seeds 8001-8030, 200 s measured. Family per metric: TRACE vs exact-sized and vs 40%-sized pools at 5 shares (10 tests), Holm."""
    from lib import family
    d = load("mix"); assert len(d) == 1050
    assert d.viol.sum() == 0 and set(d.seed) == set(range(8001, 8031)) and set(d["T"] - d.warm) == {200}
    B.add("mix.runs", len(d), "int", "mix", "rows in suite", S)
    SH ={0.0: "0", 0.2: "20", 0.4: "40", 0.6: "60", 0.8: "80"}
    for n, k in (("TRACE", "trace"), ("Oracle compliant", "central"), ("TF-JSQ", "tfjsq"), ("Static sized", "sized"), ("Static sized40", "sized40"),
                 ("large_jsq", "large"), ("TRACE no best-fit", "nobf")):
        for sh, sk in SH.items():
            g = d[(d.name == n) & ((d.sens_hi - sh).abs() < 1e-9)]; assert len(g) == 30, (n, sh)
            for m in ("cslo", "bcslo"):
                B.add(f"mix.{k}.{m}.{sk}", g[m].mean(), "fr", "mix", f"mean, {n}, sensitive share {sh}", S)
    for m in ("cslo", "bcslo"):
        rows = []
        for other, ok in (("Static sized", "sized"), ("Static sized40", "sized40")):
            for sh in SH:
                A = d[(d.name == "TRACE") & ((d.sens_hi - sh).abs() < 1e-9)].sort_values("seed"); C = d[(d.name == other) & ((d.sens_hi - sh).abs() < 1e-9)].sort_values("seed")
                assert (A.seed.values == C.seed.values).all()
                rows.append(dict(ok=ok, sh=sh, **compare(A[m].values, C[m].values)))
        for r in family(rows).to_dict("records"):
            k = f"mix.trace-{r['ok']}.{m}.{SH[r['sh']]}"
            B.add(k, r["diff"], "pt", "mix", f"paired TRACE - {r['ok']}, {m}", S)
            B.add(k + ".ci", r["ci95"], "pt0", "mix", "95% CI, n=30", S)
            B.add(k + ".ph", f"{r['p_h']:.3f}" if r["p_h"] >= .001 else "<0.001", "raw", "mix", "Holm p, 10 tests per metric", S)
            B.add(k + ".lab", r["label"], "raw", "mix", "labels", S)
    for sh in SH:   # adaptive best-fit: descriptive only
        A = d[(d.name == "TRACE") & ((d.sens_hi - sh).abs() < 1e-9)].sort_values("seed"); C = d[(d.name == "TRACE no best-fit") & ((d.sens_hi - sh).abs() < 1e-9)].sort_values("seed")
        c = compare(A.cslo.values, C.cslo.values)
        B.add(f"mix.trace-nobf.cslo.{SH[sh]}", c["diff"], "pt", "mix", "descriptive paired TRACE - TRACE without best-fit, C-SLO", S)
        B.add(f"mix.trace-nobf.cslo.{SH[sh]}.ci", c["ci95"], "pt0", "mix", "95% CI, no Holm", S)


def owner(B):
    """owner: share of requests whose data-owner domain differs from the ingress domain, 0/25/50/100%; TRACE and TF-JSQ,
    rho 0.8 and 1.0, robustness seeds 5001-5020, 100 s measured. No test family was declared: descriptive paired CIs only."""
    d = load("owner"); assert len(d) == 320
    assert d[d.name.isin(["TRACE", "TF-JSQ"])].viol.sum() == 0
    B.add("owner.runs", len(d), "int", "owner", "rows in suite", S)
    B.add("owner.viol", d.viol.sum(), "int", "owner", "total violations over all rows", S)
    X = {0.0: "0", 0.25: "25", 0.5: "50", 1.0: "100"}
    s2 = lambda g: (g.dcs2_shed / g[[k for k in g.columns if k.startswith("dcs2_")]].fillna(0).sum(axis=1)).mean()
    for rho in (0.8, 1.0):
        for x, xk in X.items():
            T = d[(d.name == "TRACE") & (d.rho == rho) & (d.owner_cross == x)].sort_values("seed")
            J_ = d[(d.name == "TF-JSQ") & (d.rho == rho) & (d.owner_cross == x)].sort_values("seed")
            assert len(T) == 20 and (T.seed.values == J_.seed.values).all()
            k = f"owner.{RHO[rho]}.{xk}"
            for m in ("cslo", "bcslo"):
                B.add(f"{k}.trace.{m}", T[m].mean(), "fr", "owner", f"TRACE mean {m}, rho {rho}, foreign-owner share {x}", S)
                c = compare(T[m].values, J_[m].values)
                B.add(f"{k}.trace-tfjsq.{m}", c["diff"], "pt", "owner", f"paired TRACE - TF-JSQ {m}, descriptive", S)
                B.add(f"{k}.trace-tfjsq.{m}.ci", c["ci95"], "pt0", "owner", "95% CI, n=20, no Holm", S)
            B.add(f"{k}.trace.s2shed", s2(T), "pc", "owner", "TRACE share of sensitivity-2 requests shed", S)
            B.add(f"{k}.tfjsq.s2shed", s2(J_), "pc", "owner", "TF-JSQ share of sensitivity-2 requests shed", S)


def pdiff(B, d, sel_a, sel_b, key, suite, how, n):
    """Descriptive paired difference a - b (points) on C-SLO and C-SLObal; selections are boolean masks over d."""
    A, C = d[sel_a].sort_values("seed"), d[sel_b].sort_values("seed")
    assert len(A) == n and (A.seed.values == C.seed.values).all(), key
    for m in ("cslo", "bcslo"):
        c = compare(A[m].values, C[m].values)
        B.add(f"{key}.{m}", c["diff"], "pt", suite, f"descriptive paired {how}, {m}", S)
        B.add(f"{key}.{m}.ci", c["ci95"], "pt0", suite, f"95% CI, n={n}, no Holm", S)


def stale(B):
    """stale: sync interval H x ring delay x fleet size, five routers, rho 0.8 and 1.0, robustness seeds 5001-5020, 100 s measured.
    No test family was declared: means and descriptive paired CIs."""
    d = load("stale"); assert len(d) == 3200 and d.viol.sum() == 0 and set(d["T"] - d.warm) == {100} and set(d.seed) == set(range(5001, 5021))
    B.add("stale.runs", len(d), "int", "stale", "rows in suite", S)
    H = {0.1: "01", 0.5: "05", 1.0: "1", 2.0: "2"}; R = {False: "i", True: "r"}
    NM = {"TRACE": "trace", "TF-JSQ": "tfjsq", "TF-P3C": "tfp3c", "rand-JSQ": "rjsq", "large_jsq": "large"}
    at = lambda rho, N, ri, h: (d.rho == rho) & (d.N == N) & (d.ring == ri) & (d.hsync == h)
    for rho in (0.8, 1.0):
        for N in (30, 120):
            for ri in R:
                for h in H:
                    k = f"stale.{RHO[rho]}.{N}.{R[ri]}.{H[h]}"
                    for n, nk in NM.items():
                        g = d[at(rho, N, ri, h) & (d.name == n)]; assert len(g) == 20
                        for m in ("cslo", "bcslo"):
                            B.add(f"{k}.{nk}.{m}", g[m].mean(), "fr", "stale", f"mean {m}, {n}", S)
                    if rho == 0.8:
                        B.add(f"stale.age.{N}.{R[ri]}.{H[h]}", f"{d[at(rho, N, ri, h)].view_age_eff_s.mean():.2f}", "raw", "stale",
                              "mean effective view age at decisions, s, rho 0.8, all routers", S)
                    pdiff(B, d, at(rho, N, ri, h) & (d.name == "TRACE"), at(rho, N, ri, h) & (d.name == "TF-JSQ"), f"{k}.trace-tfjsq", "stale", "TRACE - TF-JSQ", 20)
                for n, nk in (("TRACE", "trace"), ("TF-JSQ", "tfjsq")):
                    pdiff(B, d, at(rho, N, ri, 0.1) & (d.name == n), at(rho, N, ri, 1.0) & (d.name == n),
                           f"stale.{RHO[rho]}.{N}.{R[ri]}.{nk}.h01-h1", "stale", f"{n} H 0.1 s - H 1 s", 20)
            for n, nk in (("TRACE", "trace"), ("TF-JSQ", "tfjsq")):
                pdiff(B, d, at(rho, N, True, 1.0) & (d.name == n), at(rho, N, False, 1.0) & (d.name == n),
                       f"stale.{RHO[rho]}.{N}.{nk}.ring-inst", "stale", f"{n} ring - instantaneous, H 1 s", 20)


def place(B):
    """place: full or half placement x no cloud / 40 ms / 80 ms cloud, four routers, rho 0.8 and 1.0, robustness seeds, 100 s measured.
    No test family was declared: means and descriptive paired CIs."""
    from lib import ci
    d = load("place"); assert len(d) == 960 and d.viol.sum() == 0 and set(d["T"] - d.warm) == {100}
    d = d.fillna({c: 0. for c in d.columns if c.endswith("cloud_ok")})
    B.add("place.runs", len(d), "int", "place", "rows in suite", S)
    P = {1.0: "100", 0.5: "50"}; NM = {"TRACE": "trace", "TF-JSQ": "tfjsq", "TF": "tf", "large_jsq": "large"}
    at = lambda rho, pl, cl: (d.rho == rho) & (d.place == pl) & (d.cl == cl)
    for rho in (0.8, 1.0):
        for pl in P:
            for cl in ("none", "40", "80"):
                k = f"place.{RHO[rho]}.{P[pl]}.{cl}"
                for n, nk in NM.items():
                    g = d[at(rho, pl, cl) & (d.name == n)]; assert len(g) == 20
                    for m in ("cslo", "bcslo", "cslo_FS>1"):
                        mk = m.replace("cslo_FS>1", "fsl")
                        B.add(f"{k}.{nk}.{mk}", g[m].mean(), "fr", "place", f"mean {m}, {n}", S)
                        B.add(f"{k}.{nk}.{mk}.ci", g[m].agg(ci), "fr", "place", f"Student-t 95% CI half-width of the mean, n=20", S)
                    B.add(f"{k}.{nk}.cloud", f"{100 * (g.dc_ie_cloud_ok + g.dc_ii_cloud_ok).mean():.2f}", "raw", "place", f"share of requests served in the cloud, %, 2 dp, {n}", S)
                pdiff(B, d, at(rho, pl, cl) & (d.name == "TRACE"), at(rho, pl, cl) & (d.name == "TF-JSQ"), f"{k}.trace-tfjsq", "place", "TRACE - TF-JSQ", 20)
                pdiff(B, d, at(rho, pl, cl) & (d.name == "large_jsq"), at(rho, pl, cl) & (d.name == "TRACE"), f"{k}.large-trace", "place", "large_jsq - TRACE", 20)


def scale(B):
    """scale: (N, slot factor) in (30,1), (60,1), (120,1), (30,2) x H 1 and 0.1 s, five routers, rho 0.8 and 1.0, scale seeds
    6001-6020 (used in the earlier study), 100 s measured. No test family under protocol v2: descriptive paired CIs."""
    d = load("scale"); assert len(d) == 1600 and d.viol.sum() == 0 and set(d["T"] - d.warm) == {100} and set(d.seed) == set(range(6001, 6021))
    B.add("scale.runs", len(d), "int", "scale", "rows in suite", S)
    G = {(30, 1.0): "30", (60, 1.0): "60", (120, 1.0): "120", (30, 2.0): "30x2"}; H = {1.0: "1", 0.1: "01"}
    at = lambda rho, N, g, h: (d.rho == rho) & (d.N == N) & (d.gpu_scale == g) & (d.hsync == h)
    for rho in (0.8, 1.0):
        for (N, g), gk in G.items():
            for h, hk in H.items():
                k = f"scale.{RHO[rho]}.{gk}.{hk}"
                pdiff(B, d, at(rho, N, g, h) & (d.name == "TRACE"), at(rho, N, g, h) & (d.name == "TF-JSQ"), f"{k}.trace-tfjsq", "scale", "TRACE - TF-JSQ", 20)
                pdiff(B, d, at(rho, N, g, h) & (d.name == "large_jsq"), at(rho, N, g, h) & (d.name == "TRACE"), f"{k}.large-trace", "scale", "large_jsq - TRACE", 20)
    for n, nk in (("TRACE", "trace"), ("TF-JSQ", "tfjsq")):   # wall-clock decision time: machine-dependent, indicative only
        for N in (30, 120):
            for rho in (0.8, 1.0):
                g = d[at(rho, N, 1.0, 1.0) & (d.name == n)]
                B.add(f"scale.us.{nk}.{N}.{RHO[rho]}", f"{g.dec_per_req_us.median():.1f}", "raw", "scale",
                      f"median over seeds of mean wall-clock decision time per request, us, H 1 s, {n} (Apple M3, Python)", S)


def ablation(B):
    """abl: one component removed (tracex flags) against the full router in `main` (same seeds 8001-8030, loads, window and arrivals;
    tracex without flags equals trace, tests/test_sim.py). Per seed, mean over the four loads, then paired full - ablated. Descriptive."""
    a, m = load("abl"), load("main"); assert len(a) == 1560 and a.viol.sum() == 0 and set(a["T"]) == set(m["T"]) == {420}
    B.add("abl.runs", len(a), "int", "abl", "rows in suite", S)
    per_seed = lambda d, n: d[d.name == n].groupby("seed")[["cslo", "bcslo"]].mean().sort_index()
    C = {"serve late": "shed", "no load": "load", "no best-fit": "bf", "no net": "net"}
    rows = [(b, bk, f"{b} | {c}", ck) for b, bk in (("TRACE", "trace"), ("large_jsq", "large")) for c, ck in C.items()]
    rows += [(b, bk, f"{b} | serve late", "shed") for b, bk in (("TF-JSQ", "tfjsq"), ("TF-RR", "tfrr"), ("soft-JSQ", "sjsq"),
                                                                 ("Static sized", "sized"), ("Oracle compliant", "central"))]
    for b, bk, n, ck in rows:
        F, X = per_seed(m, b), per_seed(a, n); assert len(F) == len(X) == 30 and (F.index == X.index).all(), n
        assert (a[a.name == n].groupby("seed").size() == 4).all()
        for met in ("cslo", "bcslo"):
            c = compare(F[met].values, X[met].values)
            B.add(f"abl.{bk}.{ck}.{met}", c["diff"], "pt", "abl", f"descriptive paired {b} full - without {ck}, mean over 4 loads, {met}", S)
            B.add(f"abl.{bk}.{ck}.{met}.ci", c["ci95"], "pt0", "abl", "95% CI, n=30, no Holm", S)


def slug(s):
    return "".join(c if c.isalnum() else "_" for c in s.lower())


def robust(B):
    """robust: 34 one-at-a-time settings, TRACE, TF-JSQ and large_jsq, rho 0.8 and 1.0, robustness seeds 5001-5020.
    No test family was declared under protocol v2: means and descriptive paired CIs."""
    d = load("robust"); assert len(d) == 4080 and d.viol.sum() == 0 and d.setting.nunique() == 34
    B.add("robust.runs", len(d), "int", "robust", "rows in suite", S)
    B.add("robust.settings", d.setting.nunique() - 1, "int", "robust", "settings other than default", S)
    for st in sorted(d.setting.unique()):
        for rho in (0.8, 1.0):
            at = (d.setting == st) & (d.rho == rho); k = f"robust.{slug(st)}.{RHO[rho]}"
            for n, nk in (("TRACE", "trace"), ("TF-JSQ", "tfjsq"), ("large_jsq", "large")):
                for m in ("cslo", "bcslo"):
                    B.add(f"{k}.{nk}.{m}", d[at & (d.name == n)][m].mean(), "fr", "robust", f"mean {m}, {n}, setting {st}", S)
            pdiff(B, d, at & (d.name == "TRACE"), at & (d.name == "TF-JSQ"), f"{k}.trace-tfjsq", "robust", f"TRACE - TF-JSQ, setting {st}", 20)
            pdiff(B, d, at & (d.name == "large_jsq"), at & (d.name == "TRACE"), f"{k}.large-trace", "robust", f"large_jsq - TRACE, setting {st}", 20)
    for rho in (0.8, 1.0):              # how many of the 34 settings have a paired 95% CI wholly above or below zero
        for m in ("cslo", "bcslo"):
            cs = [compare(*(d[(d.setting == st) & (d.rho == rho) & (d.name == n)].sort_values("seed")[m].values for n in ("TRACE", "TF-JSQ")))
                  for st in d.setting.unique()]
            B.add(f"robust.{RHO[rho]}.{m}.above", sum(c["diff"] - c["ci95"] > 0 for c in cs), "int", "robust", f"settings with TRACE - TF-JSQ {m} CI above 0, of 34", S)
            B.add(f"robust.{RHO[rho]}.{m}.below", sum(c["diff"] + c["ci95"] < 0 for c in cs), "int", "robust", f"settings with TRACE - TF-JSQ {m} CI below 0, of 34", S)


def crypto(B):
    """crypto: assumed delays D1 (0.05 ms), D2 key service (2-40 ms, outside or inside the GPU slot), D3 device round trip per forward
    (5-60 ms), D4 TEE multiplier (1.05-1.5), each against no crypto. TRACE, TF-JSQ, large_jsq; rho 0.8, 1.0; seeds 5001-5020. Descriptive."""
    d = load("crypto"); assert len(d) == 2520 and d.viol.sum() == 0 and set(d["T"] - d.warm) == {100}
    B.add("crypto.runs", len(d), "int", "crypto", "rows in suite", S)
    NM = {"TRACE": "trace", "TF-JSQ": "tfjsq", "large_jsq": "large"}
    for rho in (0.8, 1.0):
        for n, nk in NM.items():
            base = (d.rho == rho) & (d.name == n) & (d.design == "none")
            for (de, x, mo), _ in d[(d.design != "none")].groupby(["design", "x", "mode"]):
                cell = (d.rho == rho) & (d.name == n) & (d.design == de) & (d.x == x) & (d["mode"] == mo)
                xk = f"{x:g}".replace(".", "p")
                pdiff(B, d, cell, base, f"crypto.{RHO[rho]}.{nk}.{de}.{xk}.{mo}", "crypto", f"{n} {de} x={x} {mo} - no crypto", 20)


def statistics(B):
    """Test diagnostics of the held-out family, its detectable difference, and the topology share of variance (topovar)."""
    from scipy import stats as st
    d = load("main"); _, res = BPM.diff(d)
    f = pd.concat(res.values()); assert len(f) == 84
    B.add("stat.main.n", len(f), "int", "main", "comparisons in the held-out family, 28 per metric x 3 metrics", S)
    B.add("stat.main.shapiro", int((f.shapiro_p < .05).sum()), "int", "main", "differences where Shapiro-Wilk p < 0.05", S)
    B.add("stat.main.agree", int(((f.p < .05) == (f.p_t < .05)).sum()), "int", "main", "Wilcoxon and paired t agree on raw p < 0.05", S)
    t = st.t.ppf(1 - .05 / (2 * 28), 29) + st.t.ppf(.8, 29)   # first Holm step, 80% power, t approximation
    B.add("stat.main.mdd", float(np.median(t * f.sd / np.sqrt(30))), "pt0", "main", "median detectable paired difference, first Holm step, 80% power", S)
    v = load("topovar"); assert len(v) == 100
    for n, nk in (("EPARA-style", "epara"), ("TRACE", "trace")):
        g = v[v.name == n]; tot = g.cslo.var(ddof=0)
        B.add(f"stat.topo.{nk}", g.groupby("seed").cslo.mean().var(ddof=0) / tot, "pc", "topovar",
              f"share of {n} C-SLO variance between topologies (10 topologies x 5 arrival seeds)", S)


def fallback(B):
    """fallback: TF with an overload fallback (uniform or power-of-two over eligible peers when none fits in the view) against none;
    held-out seeds 8001-8030, four loads, 200 s measured. Descriptive."""
    d = load("fallback"); assert len(d) == 360 and d.viol.sum() == 0
    B.add("fallback.runs", len(d), "int", "fallback", "rows in suite", S)
    for rho in (0.5, 0.8, 1.0, 1.2):
        for f in ("uniform", "p2c"):
            pdiff(B, d, (d.rho == rho) & (d.name == f"TF {f}"), (d.rho == rho) & (d.name == "TF none"), f"fallback.{RHO[rho]}.{f}", "fallback", f"TF {f} fallback - TF no fallback", 30)


def eventorder(B):
    """eventcmp: the same runs in batch and exact event order (seeds 5001-5020, 200 s measured). All other results use exact order."""
    d = load("eventcmp"); assert len(d) == 480
    B.add("evo.runs", len(d), "int", "eventcmp", "rows in suite", S)
    NM = {"TRACE": "trace", "TF-JSQ": "tfjsq", "TF-RR": "tfrr", "TF": "tf", "large_jsq": "large", "EPARA-style": "epara", "rand-JSQ": "rjsq", "TF-P3C": "tfp3c"}
    shifts = []
    for rho in (0.8, 1.0):
        for n in d.name.unique():
            ex, ba = (d.rho == rho) & (d.name == n) & (d.event_mode == "exact"), (d.rho == rho) & (d.name == n) & (d.event_mode == "batch")
            pdiff(B, d, ex, ba, f"evo.{RHO[rho]}.{NM[n]}", "eventcmp", f"{n} exact - batch", 20)
            for m in ("cslo", "bcslo"):
                shifts.append((m, compare(d[ex].sort_values("seed")[m].values, d[ba].sort_values("seed")[m].values)["diff"]))
        for mode in ("batch", "exact"):
            at = (d.rho == rho) & (d.event_mode == mode)
            pdiff(B, d, at & (d.name == "TRACE"), at & (d.name == "TF-JSQ"), f"evo.{RHO[rho]}.{mode}.trace-tfjsq", "eventcmp", f"TRACE - TF-JSQ, {mode} order", 20)
    for m in ("cslo", "bcslo"):
        v = [x for k, x in shifts if k == m]
        B.add(f"evo.{m}.min", min(v), "pt", "eventcmp", f"most negative exact - batch shift over routers and loads, {m}", S)
        B.add(f"evo.{m}.max", max(v), "pt", "eventcmp", f"most positive exact - batch shift over routers and loads, {m}", S)


EVIDENCE = ["tune", "gamma", "qstar", "val2", "bridge", "estim", "eventcmp", "main", "abl", "viol", "mix", "fallback", "stale", "scale",
            "robust", "place", "topovar", "crypto", "owner", "eshort", "elong", "exlong"]


def evidence(B):
    """Row count of every suite for Table tab:evidence."""
    n = {s: len(load(s)) for s in EVIDENCE}
    for s in EVIDENCE:
        B.add(f"ev.{s}.runs", n[s], "int", s, "rows in raw suite file", S)
    B.add("ev.total.runs", sum(n.values()), "int", "all", "rows over every suite in Table tab:evidence", S)


ENR = {"TF+EW": "ew", "TF+EB": "eb", "TF+EC": "ec", "TF+EWD": "ewd", "TF+EF": "ef", "TRACE": "trace", "TF-JSQ": "tfjsq",
       "large_jsq": "large", "large+ewd": "largeewd", "TRACE+ewd": "traceewd"}
PHI = {0.6: "06", 0.9: "09", 1.2: "12"}; OUT = {False: "soft", True: "out"}


def energy(B):
    """Energy, bounded model. eshort: 40 seeds, 180 s, descriptive. elong: 12 seeds, 3,600 s, Holm family of 36 per metric
    (6 routers against TF in 6 cells, protocol amendment 1), and the protocol's stability and closure rules per router and cell."""
    from lib import stability, family
    closes = lambda d: (d.led_init + d.led_income - d.led_charged - d.led_spill - d.led_final).abs() <= 1e-6 * (d.led_init + d.led_income)
    e = load("eshort"); assert len(e) == 4400 and e.viol.sum() == 0 and set(e["T"] - e.warm) == {120}
    l = load("elong", keep=("bins", "series")); assert len(l) == 504 and l.viol.sum() == 0 and set(l["T"] - l.warm) == {2400}
    for s, d in (("eshort", e), ("elong", l)):
        assert closes(d).all() and (d.led_charged <= d.led_init + d.led_income).all(), s
        B.add(f"en.{s}.runs", len(d), "int", s, "rows in suite", S)
        B.add(f"en.{s}.chargemax", f"{(d.led_charged / (d.led_init + d.led_income)).max():.3f}", "raw", s, "max charged / (start charge + income) over runs", S)
    for (phi, o, sup), g in e.groupby(["phi", "outage", "supply"]):
        T = g[g.name == "TF"].sort_values("seed"); k = f"en.s.{PHI[phi]}.{OUT[o]}.{sup}"
        for m in ("cslo", "bcslo"):
            B.add(f"{k}.tf.{m}", T[m].mean(), "fr", "eshort", f"TF mean {m}", S)
        for n, nk in ENR.items():
            A = g[g.name == n].sort_values("seed"); assert len(A) == 40 and (A.seed.values == T.seed.values).all()
            for m in ("cslo", "bcslo"):
                c = compare(A[m].values, T[m].values)
                B.add(f"{k}.{nk}.{m}", c["diff"], "pt", "eshort", f"descriptive paired {n} - TF, {m}", S)
                B.add(f"{k}.{nk}.{m}.ci", c["ci95"], "pt0", "eshort", "95% CI, n=40, no Holm", S)
        B.add(f"{k}.ew.avail", g[g.name == "TF+EW"].avail.mean(), "fr", "eshort", "TF+EW mean server availability", S)
        B.add(f"{k}.tf.avail", T.avail.mean(), "fr", "eshort", "TF mean server availability", S)
    R = ["TF+EW", "TF+EWD", "TRACE", "TF-JSQ", "large_jsq", "large+ewd"]
    for m in ("cslo", "bcslo"):
        rows = []
        for (phi, o), g in l.groupby(["phi", "outage"]):
            T = g[g.name == "TF"].sort_values("seed")
            for n in R:
                A = g[g.name == n].sort_values("seed"); assert len(A) == 12 and (A.seed.values == T.seed.values).all()
                rows.append(dict(phi=phi, o=o, rt=n, **compare(A[m].values, T[m].values)))
        for r in family(rows).to_dict("records"):
            k = f"en.l.{PHI[r['phi']]}.{OUT[r['o']]}.{ENR[r['rt']]}.{m}"
            B.add(k, r["diff"], "pt", "elong", f"paired {r['rt']} - TF, {m}", S)
            B.add(k + ".ci", r["ci95"], "pt0", "elong", "95% CI, n=12", S)
            B.add(k + ".lab", r["label"], "raw", "elong", "labels, Holm family of 36 per metric", S)
            B.add(k + ".ph", f"{r['p_h']:.3f}" if r["p_h"] >= .001 else "<0.001", "raw", "elong", "Holm p, 36 per metric", S)
    assert all(min(map(int, bn)) == w // s for bn, w, s in zip(l.bins, l.warm, l.bin_s))   # stability(…, 0) needs bins to start at warm-up
    nst = 0
    for (phi, o, n), g in l.groupby(["phi", "outage", "name"]):
        st = stability(g.to_dict("records"), 0); nst += st["steady"]   # stored bins already start after warm-up
        k = f"en.l.{PHI[phi]}.{OUT[o]}.{'tf' if n == 'TF' else ENR[n]}"
        B.add(k + ".steady", "yes" if st["steady"] else "no", "raw", "elong", "passes drift, half, buffer and closure rules", S)
        for m in ("cslo", "bcslo"):
            B.add(f"{k}.mean.{m}", g[m].mean(), "fr", "elong", f"mean {m}", S)
    B.add("en.l.steady", nst, "int", "elong", "router-cell pairs passing all four rules, of 42", S)
    for (phi, o), g in l.groupby(["phi", "outage"]):   # TRACE against TF-JSQ, outside the family
        at = (l.phi == phi) & (l.outage == o)
        pdiff(B, l, at & (l.name == "TRACE"), at & (l.name == "TF-JSQ"), f"en.l.{PHI[phi]}.{OUT[o]}.trace-tfjsq", "elong", "TRACE - TF-JSQ", 12)
    m = load("main")
    for n, nk in (("TRACE", "trace"), ("TF-JSQ", "tfjsq"), ("large_jsq", "large"), ("Static sized", "sized")):
        B.add(f"en.jpg.{nk}", f"{m[(m.name == n) & (m.rho == 0.8)].energy_per_good.mean():.2f}", "raw", "main",
              f"estimated joules per good request, {n}, rho 0.8, held-out seeds", S)


def compliance(B):
    """Cost of compliance on held-out seeds at rho 0.8: plain SLO attainment of the unconstrained dispatcher minus the compliant
    dispatcher and minus TRACE, paired. Descriptive (outside the declared family)."""
    d = load("main"); at = d.rho == 0.8
    for n, nk in (("Oracle compliant", "central"), ("TRACE", "trace")):
        A, C = d[at & (d.name == "Oracle unconstrained")].sort_values("seed"), d[at & (d.name == n)].sort_values("seed")
        assert len(A) == len(C) == 30 and (A.seed.values == C.seed.values).all()
        c = compare(A.slo.values, C.slo.values)
        B.add(f"disc.cost.{nk}", c["diff"], "pt", "main", f"paired SLO attainment, unconstrained dispatcher - {n}, rho 0.8", S)
        B.add(f"disc.cost.{nk}.ci", c["ci95"], "pt0", "main", "95% CI, n=30, no Holm", S)


def exlong(B):
    """exlong: 14,400 s runs, seeds 7001-7008, 600 s buffer, 5 routers x Phi 0.6/0.9 x soft/outage. Descriptive by user decision
    (protocol amendment); stability rules per router and cell. Skipped until all 160 rows exist."""
    from lib import stability
    d = load("exlong", keep=("bins", "series"))
    if len(d) < 160:
        print(f"exlong: {len(d)} of 160 rows, skipped"); return
    assert len(d) == 160 and d.viol.sum() == 0 and set(d["T"] - d.warm) == {7200}
    assert ((d.led_init + d.led_income - d.led_charged - d.led_spill - d.led_final).abs() <= 1e-6 * (d.led_init + d.led_income)).all()
    B.add("en.x.runs", len(d), "int", "exlong", "rows in suite", S)
    assert all(min(map(int, bn)) == w // s for bn, w, s in zip(d.bins, d.warm, d.bin_s))   # stability(…, 0) needs bins to start at warm-up
    nst = 0
    for (phi, o, n), g in d.groupby(["phi", "outage", "name"]):
        st = stability(g.to_dict("records"), 0); nst += st["steady"]   # stored bins already start after warm-up
        B.add(f"en.x.{PHI[phi]}.{OUT[o]}.{'tf' if n == 'TF' else ENR[n]}.steady", "yes" if st["steady"] else "no", "raw", "exlong", "passes all four rules", S)
    B.add("en.x.steady", nst, "int", "exlong", "router-cell pairs passing all four rules, of 20", S)
    for (phi, o), g in d.groupby(["phi", "outage"]):
        at = (d.phi == phi) & (d.outage == o)
        for n in ("TF+EW", "TF+EWD", "TRACE", "TF-JSQ"):
            pdiff(B, d, at & (d.name == n), at & (d.name == "TF"), f"en.x.{PHI[phi]}.{OUT[o]}.{ENR[n]}", "exlong", f"{n} - TF", 8)
        pdiff(B, d, at & (d.name == "TRACE"), at & (d.name == "TF-JSQ"), f"en.x.{PHI[phi]}.{OUT[o]}.trace-tfjsq", "exlong", "TRACE - TF-JSQ", 8)


VARIANTS = ["large8", "large+adm_big.1", "adm_big.3", "frag", "trunk.1", "trunk.25h", "local_bf", "rand-JSQ e0.05"]


def variants(B):
    """Validation v2 (seeds 3101-3130, rho 0.5-1.2): frozen acceptance table from TRACE_revision/analysis/accept.py, with
    one row recomputed here from raw rows as a cross-check."""
    a = pd.read_csv(os.path.join(REV, "processed", "accept_val2.csv")).set_index("name")
    assert set(VARIANTS) <= set(a.index) and not a.accepted.any()
    d = load("val2"); assert len(d) == 1200 and d.viol.sum() == 0
    t = d[d.name == "TRACE"].groupby("seed").cslo.mean(); x = d[d.name == "large8"].groupby("seed").cslo.mean()
    assert abs((x - t).mean() * 100 - a.loc["large8", "d_cslo"]) < 1e-9, "accept_val2.csv disagrees with raw val2"
    B.add("val.runs", len(d), "int", "val2", "rows in suite", S)
    for n in VARIANTS + ["TF-JSQ"]:
        k = "val." + n.replace("+", "-").replace(" ", "-").replace("_", "")
        r = a.loc[n]
        B.add(k + ".bcslo", r.d_bal, "pt", "val2", f"{n} - TRACE, C-SLO_bal, mean of 4 loads (accept_val2.csv)", S)
        B.add(k + ".bcslo.ci", r.ci_bal, "pt0", "val2", "95% CI", S)
        B.add(k + ".cslo", r.d_cslo, "pt", "val2", f"{n} - TRACE, C-SLO, mean of 4 loads", S)
        B.add(k + ".cslo.ci", r.ci_cslo, "pt0", "val2", "95% CI", S)
        B.add(k + ".worst", r.worst_cat, "pt", "val2", "worst category change at any load", S)
        B.add(k + ".rules", "".join(str(i) for i in range(1, 5) if r[f"r{i}"]) or "none", "raw", "val2", "acceptance rules passed", S)


ALLROUTERS = ["Local", "EPARA-style", "JSQ oblivious", "Oracle unconstrained", "TF", "TF-RR", "TF-P2C", "TF-P3C", "TF-JSQ", "soft-JSQ",
              "rand-JSQ", "rand-JSQ e0.05", "Static eq", "Static sized", "PASHE-a", "Singh-a", "TRACE", "TRACE fit0", "large_jsq", "large8",
              "large+adm_big.1", "adm_big.3", "frag", "trunk.1", "trunk.25h", "local_bf", "Oracle compliant"]


SHOWN = {"Local": "Local only", "JSQ oblivious": "JSQ, no trust", "Oracle unconstrained": "Central, no trust",
         "Static eq": "Static, equal clearance", "Static sized": "Static, sized", "TRACE fit0": "TRACE, fit 0",
         "large_jsq": "large-JSQ", "Oracle compliant": "Central, compliant"}   # names as in Table tab:held


def allrouters(B):
    """Every router of the held-out sweep: means over 30 seeds, three metrics, four loads (Table tab:allheld)."""
    d = load("main"); assert len(d) == 3240 and set(d.name) == set(ALLROUTERS)
    rows = []
    for n in ALLROUTERS:
        k = "all." + "".join(c if c.isalnum() else "-" for c in n)
        cells = []
        for r, rk in ((0.5, "05"), (0.8, "08"), (1.0, "10"), (1.2, "12")):
            g = d[(d.name == n) & (d.rho == r)]; assert len(g) == 30
            for m in ("cslo", "bcslo", "wcslo"):
                B.add(f"{k}.{m}.{rk}", g[m].mean(), "fr", "main", f"mean {m}, {n}, rho {r}, 30 held-out seeds", S)
                cells.append(rf"\V{{{k}.{m}.{rk}}}")
        rows.append(SHOWN.get(n, n).replace("_", r"\_") + " & " + " & ".join(cells) + r" \\")
    open(os.path.join(DRAFT, "tables", "tab_allheld.tex"), "w").write(ALLHEAD + "\n".join(rows) + ALLTAIL)


ALLHEAD = r"""\begin{table*}[!t]
\centering
\caption{Every router of the held-out sweep (seeds 8001--8030, \(N=30\), 40\% sensitive, 420 s with 20 s warm-up): mean attainment over 30 seeds. C: C-SLO; B: C-SLO\(_\mathrm{bal}\); W: work-weighted C-SLO. Rows large8 to local\_bf are the unaccepted candidates of Table~\ref{tab:variants}; PASHE-a, Singh-a, TF-P3C and rand-JSQ are described in Appendix~\ref{app:allheld}. Generated from the raw rows; paired comparisons for the main routers are in Table~\ref{tab:diff}.}
\label{tab:allheld}
\footnotesize
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{l*{12}{r}}
\toprule
 & \multicolumn{3}{c}{\(\rho=0.5\)} & \multicolumn{3}{c}{\(\rho=0.8\)} & \multicolumn{3}{c}{\(\rho=1.0\)} & \multicolumn{3}{c}{\(\rho=1.2\)} \\
Router & C & B & W & C & B & W & C & B & W & C & B & W \\
\midrule
"""
ALLTAIL = r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\end{table*}
"""


def estimator(B):
    """estim: backlog estimator check, tuning seeds 1001-1020, rho 0.5-1.2, 100 s measured. Exploratory, descriptive."""
    d = load("estim"); assert len(d) == 320
    B.add("estim.runs", len(d), "int", "estim", "rows in suite", S)
    for a, b, k in (("TF-JSQ aged", "TF-JSQ", "tfjsq"), ("large_jsq unaged", "large_jsq", "large")):
        for r, rk in ((0.5, "05"), (0.8, "08"), (1.0, "10"), (1.2, "12")):
            for m in ("cslo", "bcslo"):
                A = d[(d.name == a) & (d.rho == r)].sort_values("seed"); C = d[(d.name == b) & (d.rho == r)].sort_values("seed")
                assert (A.seed.values == C.seed.values).all() and len(A) == 20
                c = compare(A[m].values, C[m].values)
                B.add(f"estim.{k}.{m}.{rk}", c["diff"], "pt", "estim", f"{a} - {b}, {m}, paired", S)
                B.add(f"estim.{k}.{m}.{rk}.ci", c["ci95"], "pt0", "estim", "95% CI, n=20", S)


def ringtime(B):
    """Ring circulation time logged by the simulator in every stale ring run."""
    d = load("stale"); g = d[d.ring_time_s.notna()] if "ring_time_s" in d else d.iloc[:0]
    for n in (30, 120):
        x = g[g.N == n].ring_time_s; assert len(x) == 800
        B.add(f"ring.time.{n}", x.mean(), "fr", "stale", f"mean ring circulation time, N={n}, s", S)


def diagnostic(B):
    """Large-job diagnostic (doc 05): tuning seeds 1001-1010, rho 0.8/1.0/1.2, 210 runs, explanation only. Decision rules fixed
    before the runs; the gap is TF-JSQ minus TRACE LS>1 attainment."""
    sys.path.insert(0, os.path.join(os.path.dirname(S), "..", "..", "diag"))
    import analyse as A
    import hashlib
    d = A.load(); src = "diag"
    h = hashlib.sha256(open(os.path.join(A.RAW, "diag.jsonl"), "rb").read()).hexdigest()[:12]   # diag raw lives outside TRACE_revision/raw
    B.add("diag.sha", h, "raw", src, "sha256_12 of TRACE_remediation/diag/raw/diag.jsonl", S)
    assert d.viol.sum() == 0
    B.add("diag.runs", len(d), "int", src, "rows", S)
    R = {0.8: "08", 1.0: "10", 1.2: "12"}
    tr = lambda n, r, c: A.arm(d, n, r, c)  # noqa: E731
    for r, k in R.items():
        B.add(f"diag.gap.{k}", (tr("A2 TF-JSQ", r, "cslo_LS>1") - tr("A1 TRACE", r, "cslo_LS>1")).mean(), "pt", src, "mean TF-JSQ - TRACE LS>1 attainment, points", S)
        for p, pk in (("P2 TRACE no early stop", "p2"), ("P3 TRACE kmax4", "p3"), ("P1 TRACE hsync0.1", "p1")):
            B.add(f"diag.{pk}.cslo.{k}", (tr(p, r, "cslo") - tr("A1 TRACE", r, "cslo")).mean(), "pt", src, f"mean {p} - TRACE C-SLO, points", S)
    _, pool = A.closure(d, "LS>1")
    for pk, v in pool.items():
        B.add(f"diag.close.{pk.lower()}", round(v), "int", src, "share of pooled LS>1 gap closed by the probe, %", S)
    for name, nk in (("A1 TRACE", "trace"), ("A2 TF-JSQ", "tfjsq")):
        t = A.per_request(d, name, "LS>1")
        for col, ck in (("no eligible node with m free slots", "nofree"), ("recoverable (_shed_check)", "recov"), ("early stop", "early"),
                        ("hop limit", "hop"), ("view fits, truth does not", "viewover")):
            v = t[col].str.rstrip("%").astype(float)
            B.add(f"diag.{nk}.{ck}.min", round(v.min()), "int", src, f"{name} LS>1: {col}, lowest over loads, %", S)
            B.add(f"diag.{nk}.{ck}.max", round(v.max()), "int", src, f"{name} LS>1: {col}, highest over loads, %", S)
        B.add(f"diag.{nk}.shed.12", int(t.shed.iloc[-1]), "int", src, f"{name} LS>1 sheds at rho 1.2, all seeds", S)


def energyci(B):
    """Table tab:energyci: 95% CI half-widths for every cell of Table tab:energy (keys from energy())."""
    txt = {r["key"]: r["text"] for r in B.rows}
    cols = ["ew", "ewd", "trace", "tfjsq", "large", "largeewd"]
    body = []
    for m, mn in (("cslo", "C-SLO"), ("bcslo", r"C-SLO\(_\mathrm{bal}\)")):
        for phi, pk in (("0.6", "06"), ("0.9", "09"), ("1.2", "12")):
            for o in ("soft", "out"):
                cells = [rf"\V{{en.l.{pk}.{o}.{c}.{m}.ci}}" for c in cols]
                assert all(f"en.l.{pk}.{o}.{c}.{m}.ci" in txt for c in cols)
                body.append(f"{mn} & {phi} & {'soft' if o == 'soft' else 'outage'} & " + " & ".join(cells) + r" \\")
        if m == "cslo":
            body.append(r"\midrule")
    t = "\n".join([r"\begin{table}[!htb]", r"\centering",
                   r"\caption{95\% confidence half-widths (points, paired, \(n=12\)) for the differences of Table~\ref{tab:energy}.}",
                   r"\label{tab:energyci}", r"\footnotesize", r"\begin{adjustbox}{max width=\columnwidth}", r"\begin{tabular}{lll*{6}{r}}", r"\toprule",
                   r"Metric & \(\Phi\) & Failure & TF+EW & EWD & TRACE & TF-JSQ & large-JSQ & large+EWD \\", r"\midrule"]
                  + body + [r"\bottomrule", r"\end{tabular}", r"\end{adjustbox}", r"\end{table}", ""])
    open(os.path.join(DRAFT, "tables", "tab_energyci.tex"), "w").write(t)


def difftable(B):
    """Table tab:diff with independent labels: S (significant after Holm) and E (equivalent within 1 point, TOST, Holm) can both hold.
    Values and labels are the main-family keys; replaces the exclusive-label version of build_paper_main.py."""
    txt = {r["key"]: r["text"] for r in B.rows}
    mark = lambda lab: "S,E" if lab.startswith("S+") else "S" if lab == "S" else "E" if "E1" in lab else "n"  # noqa: E731
    body = []
    for cmp_, k in CMPKEY.items():
        for i, (m, name) in enumerate((("cslo", "C-SLO"), ("bcslo", "Balanced"), ("wcslo", "Work"))):
            cells = [rf"\V{{main.{k}.{m}.{rk}}}$\pm$\V{{main.{k}.{m}.{rk}.ci}}\textsuperscript{{{mark(txt[f'main.{k}.{m}.{rk}.lab'])}}}" for rk in RHO.values()]
            body.append(f"{cmp_ if i == 0 else ''} & {name} & " + " & ".join(cells) + r" \\")
    cap = (r"Paired differences on held-out seeds, in points, $\pm$ 95\% CI, \(n=30\). Holm over 28 comparisons per metric. "
           r"\textsuperscript{S}: significant at \(p_H<0.05\). \textsuperscript{E}: equivalent within \(\pm1\) point by TOST, Holm-adjusted. "
           r"A difference can be both; \textsuperscript{n}: neither (inconclusive).")
    t = "\n".join([r"\begin{table*}[!t]", r"\centering", r"\caption{" + cap + "}", r"\label{tab:diff}", r"\footnotesize",
                   r"\begin{adjustbox}{max width=\textwidth}", r"\begin{tabular}{llllll}", r"\toprule",
                   r"Comparison & Metric & \(\rho=0.5\) & \(\rho=0.8\) & \(\rho=1.0\) & \(\rho=1.2\) \\", r"\midrule"]
                  + body + [r"\bottomrule", r"\end{tabular}", r"\end{adjustbox}", r"\end{table*}", ""])
    open(os.path.join(DRAFT, "tables", "tab_diff.tex"), "w").write(t)


def main():
    B = Book()
    variants(B); allrouters(B); estimator(B); ringtime(B); diagnostic(B)
    statistics(B); fallback(B); eventorder(B); evidence(B); energy(B); compliance(B); exlong(B)
    main_sweep(B); category(B); violations(B); mixes(B); owner(B); stale(B); place(B); scale(B); ablation(B); robust(B); crypto(B)
    difftable(B); energyci(B)
    B.write()


if __name__ == "__main__":
    main()
