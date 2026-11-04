"""Figures for the draft from raw rows; writes ../figures and appends hashes to ../trace_assets.csv. python analysis/build_figures.py"""
import csv, hashlib, os
import numpy as np
from nums import DRAFT
from lib import load, ci
from figstyle_saa import plt, sty

OUT = os.path.join(DRAFT, "figures")
MADE = []


def panel(size=(2.0, 1.7)):
    return plt.subplots(figsize=size)


def done(f, a, name, suite, ncol=2, legend=True):
    if legend:
        h, l = a.get_legend_handles_labels()
        a.legend(h, l, loc="upper center", bbox_to_anchor=(.46, -.27), ncol=ncol, fontsize=8.5, handlelength=1.8, columnspacing=.8, labelspacing=.3, handletextpad=.5)
    p = os.path.join(OUT, name + ".png"); f.savefig(p, bbox_inches="tight"); plt.close(f)
    MADE.append(dict(file=f"figures/{name}.png", source=suite, sha256_12=hashlib.sha256(open(p, "rb").read()).hexdigest()[:12],
                     script="TRACE_remediation/paper_draft/analysis/build_figures.py"))


def violation():
    d = load("viol").fillna(0.)
    f, a = panel()
    for n, k, lab, kw in (("RR", "rr", "Round-robin", {}), ("EPARA-style", "epara", "EPARA-style", {}),
                          ("JSQ oblivious", "rr", "JSQ (no trust)", dict(color="#76b7b2")), ("Oracle unconstrained", "oracle_u", "Central oracle (no trust)", {})):
        g = d[d.name == n].groupby("corr").viol
        a.errorbar(g.mean().index, 100 * g.mean(), yerr=100 * g.agg(ci), label=lab, **sty(k, **kw))
    a.set(xlabel="alignment λ", ylabel="violations, % of requests", ylim=(0, 24), xticks=[0, .5, 1]); done(f, a, "fig_violation_a", "viol")
    f, a = panel((2.3, 1.7)); pols = ["Oracle unconstrained", "EPARA-style", "JSQ oblivious", "RR"]
    x = [i * 5 + j for i in range(2) for j in range(4)]; base = np.zeros(8)
    parts = (("Ingress ineligible, kept local", "#4e79a7", ["dc_ii_local_v"]),
             ("Ingress ineligible, sent to ineligible", "#f28e2b", ["dc_ii_fwd_v_clear", "dc_ii_fwd_v_dom"]),
             ("Ingress eligible, sent to ineligible", "#e15759", ["dc_ie_fwd_v_clear", "dc_ie_fwd_v_dom"]))
    for l, c, cols in parts:
        h = np.array([100 * d[(d["corr"] == m) & (d.name == p)][[k for k in cols if k in d]].sum(axis=1).mean() for m in (0., 1.) for p in pols])
        a.bar(x, h, bottom=base, color=c, label=l, width=.8); base += h
    assert np.allclose(base, [100 * d[(d["corr"] == m) & (d.name == p)].viol.mean() for m in (0., 1.) for p in pols], atol=1e-6), "terms must add to the rate"
    a.set_xticks(x); a.set_xticklabels(["Oracle", "EPARA", "JSQ", "RR"] * 2, rotation=35, ha="right", fontsize=8); a.set(ylabel="violations, % of requests", ylim=(0, 24)); a.grid(axis="x", visible=False)
    a.text(1.5, 22, "λ = 0", ha="center", fontsize=7); a.text(6.5, 22, "λ = 1", ha="center", fontsize=7)
    h, l = a.get_legend_handles_labels(); a.legend(h, l, loc="upper center", bbox_to_anchor=(.46, -.32), ncol=1, fontsize=8); done(f, a, "fig_violation_b", "viol", legend=False)


def mix():
    d = load("mix"); assert len(d) == 1050
    for m, lab, name in (("cslo", "C-SLO", "fig_mix_a"), ("bcslo", "C-SLO$_\\mathrm{bal}$", "fig_mix_b")):
        f, a = panel()
        for n, k, l, kw in (("TRACE", "trace", "TRACE", {}), ("TF-JSQ", "tf_jsq", "TF-JSQ", {}), ("Oracle compliant", "oracle_c", "Central (compliant)", {}),
                            ("Static sized", "static", "Pools, exact mix", {}), ("Static sized40", "static", "Pools sized for 40%", dict(ls=":"))):
            g = d[d.name == n].groupby("sens_hi")[m]
            a.errorbar(100 * g.mean().index, g.mean(), yerr=g.agg(ci), label=l, **sty(k, **kw))
        a.set(xlabel="sensitive share, %", ylabel=lab, xticks=[0, 20, 40, 60, 80]); done(f, a, name, "mix")


def ring():
    d = load("stale"); d = d[d.N == 120]
    for rho, name in ((0.8, "fig_ring_a"), (1.0, "fig_ring_b")):
        f, a = panel()
        for n, k in (("TRACE", "trace"), ("TF-JSQ", "tf_jsq")):
            for ri, l, kw in ((False, "instant", {}), (True, "ring", dict(ls=":"))):
                g = d[(d.name == n) & (d.rho == rho) & (d.ring == ri)].groupby("hsync").cslo
                a.errorbar(g.mean().index, g.mean(), yerr=g.agg(ci), label=f"{n}, {l}", **sty(k, **kw))
        a.set(xlabel="sync interval H, s", ylabel="C-SLO", xscale="log", xticks=[.1, .5, 1, 2], xticklabels=["0.1", "0.5", "1", "2"]); done(f, a, name, "stale")


def scale():
    from lib import compare
    d = load("scale"); G = ((30, 1.0, "30"), (60, 1.0, "60"), (120, 1.0, "120"), (30, 2.0, "30 ×2"))
    for rho, name in ((0.8, "fig_scale_a"), (1.0, "fig_scale_b")):
        f, a = panel((2.3, 1.7))
        for j, (h, c) in enumerate(((1.0, "#1b9e77"), (0.1, "#999999"))):
            r = []
            for N, g, _ in G:
                s = lambda n: d[(d.name == n) & (d.rho == rho) & (d.N == N) & (d.gpu_scale == g) & (d.hsync == h)].sort_values("seed").bcslo.values
                r.append(compare(s("TRACE"), s("TF-JSQ")))
            a.bar(np.arange(4) + (j - .5) * .38, [x["diff"] for x in r], .38, yerr=[x["ci95"] for x in r], color=c, capsize=2, label=f"H = {h:g} s")
        a.axhline(0, color="k", lw=.8); a.set_xticks(range(4)); a.set_xticklabels([l for *_, l in G], fontsize=8)
        a.set(xlabel="N (×2: twice the slots)", ylabel="TRACE − TF-JSQ, points"); a.grid(axis="x", visible=False); done(f, a, name, "scale")


def sens():
    from lib import compare
    d = load("robust"); S = sorted(d.setting.unique())
    diff = lambda st, rho, m: compare(*(d[(d.setting == st) & (d.rho == rho) & (d.name == n)].sort_values("seed")[m].values for n in ("TRACE", "TF-JSQ")))
    order = sorted(S, key=lambda st: diff(st, 1.0, "bcslo")["diff"])
    for m, lab, name in (("cslo", "C-SLO", "fig_sens_a"), ("bcslo", "C-SLO$_\\mathrm{bal}$", "fig_sens_b")):
        f, a = plt.subplots(figsize=(3.45, 4.6)); y = np.arange(len(order))
        for rho, c, off in ((0.8, "#999999", -.18), (1.0, "#1b9e77", .18)):
            r = [diff(st, rho, m) for st in order]
            a.errorbar([x["diff"] for x in r], y + off, xerr=[x["ci95"] for x in r], fmt="o", ms=3, color=c, capsize=1.5, lw=1, label=f"ρ = {rho:g}")
        a.axvline(0, color="k", lw=.8); a.set_yticks(y); a.set_yticklabels(order, fontsize=7); a.set(xlabel=f"TRACE − TF-JSQ, {lab} points")
        a.grid(axis="y", visible=False); done(f, a, name, "robust")


def crypto():
    from lib import compare
    d = load("crypto")
    dif = lambda rho, n, cell: compare(d[cell & (d.rho == rho) & (d.name == n)].sort_values("seed").cslo.values,
                                       d[(d.design == "none") & (d.rho == rho) & (d.name == n)].sort_values("seed").cslo.values)
    for rho, name in ((0.8, "fig_crypto_a"), (1.0, "fig_crypto_b")):
        f, a = panel()
        for de, mo, l, c, ls in (("D2", "wait", "D2, outside slot", "#4e79a7", "-"), ("D2", "slot", "D2, inside slot", "#e15759", "-"), ("D3", "wait", "D3, per forward", "#f28e2b", "--")):
            xs = sorted(d[(d.design == de) & (d["mode"] == mo)].x.unique()); r = [dif(rho, "TRACE", (d.design == de) & (d.x == x) & (d["mode"] == mo)) for x in xs]
            a.errorbar(xs, [q["diff"] for q in r], yerr=[q["ci95"] for q in r], label=l, color=c, ls=ls, marker="o", ms=3, capsize=2)
        a.axhline(0, color="k", lw=.8); a.set(xlabel="added delay, ms", ylabel="TRACE C-SLO change, points"); done(f, a, name, "crypto", ncol=1)
    f, a = panel()
    for n, k in (("TRACE", "trace"), ("TF-JSQ", "tf_jsq")):
        for rho, ls in ((0.8, ":"), (1.0, "-")):
            xs = sorted(d[d.design == "D4"].x.unique()); r = [dif(rho, n, (d.design == "D4") & (d.x == x)) for x in xs]
            a.errorbar(xs, [q["diff"] for q in r], yerr=[q["ci95"] for q in r], label=f"{n}, ρ = {rho:g}", **sty(k, ls=ls))
    a.axhline(0, color="k", lw=.8); a.set(xlabel="TEE run-time multiplier", ylabel="C-SLO change, points"); done(f, a, "fig_crypto_c", "crypto")


def main():
    violation()
    mix()
    ring()
    scale()
    sens()
    crypto()
    p = os.path.join(DRAFT, "trace_assets.csv")
    rows = [r for r in csv.DictReader(open(p)) if r["file"] not in {m["file"] for m in MADE}] + MADE
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "source", "sha256_12", "script"]); w.writeheader(); w.writerows(rows)
    print(len(MADE), "figures")


if __name__ == "__main__":
    main()
