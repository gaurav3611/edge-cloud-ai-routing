"""render.py TEMPLATE OUT - fill {{...}} tokens from numbers_v3.json (all numbers come from the analysis)."""
import json, re, sys
N = json.load(open("../numbers_v3.json"))
def fam(f, l): return N[f"{f}|{l}"]
def pts(x, sign=True):
    s = f"{abs(x)*100:.1f}"
    return (("+" if x >= 0 else "−") + s) if sign else s
def pfmt(p):
    if p >= 0.995: return "1"
    if p >= 0.01: return f"{p:.2f}"
    e = int(f"{p:.0e}".split("e")[1]); m = p / 10**e
    return f"{m:.0f}×10^{e}^"
def val(key, metric):
    x = N[key][metric]
    if metric in ("throttled",): return f"{x*100:.1f}%"
    if metric == "drains": return f"{x:.1f}"
    if metric == "util_cv": return f"{x:.2f}"
    if metric == "hops": return f"{x:.2f}"
    return f"{x:.3f}"
def tok(m):
    kind, arg = m.group(1), m.group(2)
    if kind == "d": f, l = arg.split("|", 1); return pts(fam(f, l)["m"])
    if kind == "a": f, l = arg.split("|", 1); return pts(fam(f, l)["m"], False)
    if kind == "ph": f, l = arg.split("|", 1); return pfmt(fam(f, l)["p_holm"])
    if kind == "phmin":
        f, ls = arg.split("|", 1); return pfmt(min(fam(f, l)["p_holm"] for l in ls.split(";")))
    if kind == "v":
        parts = arg.split("|"); return val("|".join(parts[:-1]), parts[-1])
    if kind == "maxabs":
        fs, sub = arg.split("|", 1)
        xs = [abs(v["m"]) for k, v in N.items() if k.split("|")[0] in fs.split(",") and sub in k and isinstance(v, dict) and "m" in v]
        return pts(max(xs), False)
    if kind == "g":
        h, p = arg.split("|"); return pts(N[f"G|{float(h)}|{p}"][0])
    raise ValueError(kind)
s = open(sys.argv[1]).read()
s = re.sub(r"\{\{([a-z]+):([^}]*)\}\}", tok, s)
open(sys.argv[2], "w").write(s)
print("rendered", sys.argv[2])
