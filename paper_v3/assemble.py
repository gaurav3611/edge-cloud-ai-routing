"""assemble.py - build the full revised manuscript (markdown) from its parts and the generated tables."""
import re, json
T = lambda n: open(f"../tables_v3/{n}.md").read() if __import__("os").path.exists(f"../tables_v3/{n}.md") else "(table pending)\n"
cap = {
 "TABLE_MAIN_PLACEHOLDER": ("TABLE III. Routers at offered load $\\rho=0.8$ (mean ± 95% CI over 30 seeds). SLO: raw SLO attainment; C-SLO: compliant SLO attainment, per request and category-balanced; Viol.: violation rate; C-goodput: compliant goodput (req/s); Fwd.: forwards per request; Shed: share of requests shed; µs/dec.: routing time per decision in the Python prototype.", "tab_main"),
 "TABLE_TUNE_PLACEHOLDER": ("TABLE IV. Tuning of best-fit strength $\\gamma$ on the separate tuning seeds (1001–1010): mean paired gain in C-SLO over $\\gamma=1$ (plain TF) for each share of sensitive traffic ($\\rho=0.8$).", "tab_tune"),
 "TABLE_OVER_PLACEHOLDER": ("TABLE V. Compliant SLO attainment in overload with and without SLO-aware admission (30 seeds). \"Serve late\" executes requests that can no longer meet their SLO; \"shed\" rejects them.", "tab_over"),
 "TABLE_CLOUD_PLACEHOLDER": ("TABLE VI. Partial placement and a cloud fallback ($\\rho=0.8$, 20 seeds). Placement: share of servers hosting each service.", "tab_cloud"),
 "TABLE_B_PLACEHOLDER": ("TABLE VII. Compliant SLO attainment of energy-aware variants with constant supply (180 s runs, 10 seeds).", "tab_B"),
 "TABLE_S_PLACEHOLDER": ("TABLE VIII. Compliant SLO attainment with phase-shifted solar supply (three time zones; 10 seeds).", "tab_S"),
 "TABLE_PARAM_PLACEHOLDER": ("TABLE IX. One-at-a-time sensitivity of compliant SLO attainment ($\\rho=0.8$, 10 seeds).", "tab_param"),
}
def fill(s):
    for k, (c, n) in cap.items():
        s = s.replace(k, c + "\n\n" + T(n))
    return s
head = open("build/head.md").read().split("**DRAFT")[0]
parts = [open("abstract.md").read(), open("humanized_I-V.md").read(), open("results_VI.md").read(),
         open("energy_VII.md").read(), open("discussion.md").read()]
body = fill("\n\n".join(parts))
nruns = sum(1 for _ in open("../runs_v3.jsonl"))
body = body.replace("RUNCOUNT_PLACEHOLDER", f"{nruns:,}")
app = fill(open("appendix.md").read())
open("build/final.md", "w").write(head + body + "\n\n# References\n\n::: {#refs}\n:::\n\n" + app)
left = re.findall(r"[A-Z_]+_PLACEHOLDER", open("build/final.md").read())
print("runs", nruns, "| placeholders left:", left)
